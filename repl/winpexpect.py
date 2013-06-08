#
# This file is part of WinPexpect. WinPexpect is free software that is made
# available under the MIT license. Consult the file "LICENSE" that is
# distributed together with this file for the exact licensing terms.
#
# WinPexpect is copyright (c) 2008-2010 by the WinPexpect authors. See the
# file "AUTHORS" for a complete overview.

import os
import sys
import pywintypes
import itertools
import random

from Queue import Queue, Empty
from threading import Thread

from pexpect import spawn, ExceptionPexpect, EOF, TIMEOUT
from subprocess import list2cmdline

from msvcrt import open_osfhandle
from win32api import (SetHandleInformation, GetCurrentProcess, OpenProcess,
                      CloseHandle, GetCurrentThread)
from win32pipe import CreateNamedPipe, ConnectNamedPipe
from win32process import (STARTUPINFO, CreateProcess, CreateProcessAsUser,
			  GetExitCodeProcess, TerminateProcess, ExitProcess)
from win32event import WaitForSingleObject, INFINITE
from win32security import (LogonUser, OpenThreadToken, OpenProcessToken,
                           GetTokenInformation, TokenUser, ACL_REVISION_DS,
                           ConvertSidToStringSid, ConvertStringSidToSid,
                           SECURITY_ATTRIBUTES, SECURITY_DESCRIPTOR, ACL,
                           LookupAccountName)
from win32file import CreateFile, ReadFile, WriteFile

from win32con import (HANDLE_FLAG_INHERIT, STARTF_USESTDHANDLES,
                      STARTF_USESHOWWINDOW, CREATE_NEW_CONSOLE, SW_HIDE,
                      PIPE_ACCESS_DUPLEX, WAIT_OBJECT_0, WAIT_TIMEOUT,
                      LOGON32_PROVIDER_DEFAULT, LOGON32_LOGON_INTERACTIVE,
                      TOKEN_ALL_ACCESS, GENERIC_READ, GENERIC_WRITE,
                      OPEN_EXISTING, PROCESS_ALL_ACCESS, MAXIMUM_ALLOWED)
from winerror import (ERROR_PIPE_BUSY, ERROR_HANDLE_EOF, ERROR_BROKEN_PIPE,
                      ERROR_ACCESS_DENIED)
from pywintypes import error as WindowsError


# Compatibility with Python < 2.6
try:
    from collections import namedtuple
except ImportError:
    def namedtuple(name, fields):
        d = dict(zip(fields, [None]*len(fields)))
        return type(name, (object,), d)

# Compatbility wiht Python 3
if sys.version_info[0] == 3:

    _WriteFile = WriteFile
    def WriteFile(handle, s):
        return _WriteFile(handle, s.encode('ascii'))

    _ReadFile = ReadFile
    def ReadFile(handle, size):
        err, data = _ReadFile(handle, size)
        return err, data.decode('ascii')


def split_command_line(cmdline):
    """Split a command line into a command and its arguments according to
    the rules of the Microsoft C runtime."""
    # http://msdn.microsoft.com/en-us/library/ms880421
    s_free, s_in_quotes, s_in_escape = range(3)
    state = namedtuple('state',
                ('current', 'previous', 'escape_level', 'argument'))
    state.current = s_free
    state.previous = s_free
    state.argument = []
    result = []
    for c in itertools.chain(cmdline, ['EOI']):  # Mark End of Input
        if state.current == s_free:
            if c == '"':
                state.current = s_in_quotes
                state.previous = s_free
            elif c == '\\':
                state.current = s_in_escape
                state.previous = s_free
                state.escape_count = 1
            elif c in (' ', '\t', 'EOI'):
                if state.argument or state.previous != s_free:
                    result.append(''.join(state.argument))
                    del state.argument[:]
            else:
                state.argument.append(c)
        elif state.current == s_in_quotes:
            if c == '"':
                state.current = s_free
                state.previous = s_in_quotes
            elif c == '\\':
                state.current = s_in_escape
                state.previous = s_in_quotes
                state.escape_count = 1
            else:
                state.argument.append(c)
        elif state.current == s_in_escape:
            if c == '\\':
                state.escape_count += 1
            elif c == '"':
                nbs, escaped_delim = divmod(state.escape_count, 2)
                state.argument.append(nbs * '\\')
                if escaped_delim:
                    state.argument.append('"')
                    state.current = state.previous
                else:
                    if state.previous == s_in_quotes:
                        state.current = s_free
                    else:
                        state.current = s_in_quotes
                state.previous = s_in_escape
            else:
                state.argument.append(state.escape_count * '\\')
                state.argument.append(c)
                state.current = state.previous
                state.previous = s_in_escape
    if state.current != s_free:
        raise ValueError, 'Illegal command line.'
    return result


join_command_line = list2cmdline


def which(command):
    path = os.environ.get('Path', '')
    path = path.split(os.pathsep)
    pathext = os.environ.get('Pathext', '.exe;.com;.bat;.cmd')
    pathext = pathext.split(os.pathsep)
    for dir in itertools.chain([''], path):
        for ext in itertools.chain([''], pathext):
            fname = os.path.join(dir, command) + ext
            if os.access(fname, os.X_OK):
                return fname


def _read_header(handle, bufsize=4096):
    """INTERNAL: read a stub header from a handle."""
    header = ''
    while '\n\n' not in header:
        err, data = ReadFile(handle, bufsize)
        header += data
    return header


def _parse_header(header):
    """INTERNAL: pass the stub header format."""
    parsed = {}
    lines = header.split('\n')
    for line in lines:
        if not line:
            break
        p1 = line.find('=')
        if p1 == -1:
            if line.startswith(' '):  # Continuation
                if key is None:
                    raise ValueError, 'Continuation on first line.'
                input[key] += '\n' + line[1:]
            else:
                raise ValueError, 'Expecting key=value format'
        key = line[:p1]
        parsed[key] = line[p1+1:]
    return parsed


def _quote_header(s):
    """INTENAL: quote a string to be used in a stub header."""
    return s.replace('\n', '\n ')


def _get_current_sid():
    """INTERNAL: get current SID."""
    try:
        token = OpenThreadToken(GetCurrentThread(), MAXIMUM_ALLOWED, True)
    except WindowsError:
        token = OpenProcessToken(GetCurrentProcess(), MAXIMUM_ALLOWED)
    sid = GetTokenInformation(token, TokenUser)[0]
    return sid


def _lookup_sid(domain, username):
    """INTERNAL: lookup the SID for a user in a domain."""
    return LookupAccountName(domain, username)[0]


def _create_security_attributes(*sids, **kwargs):
    """INTERNAL: create a SECURITY_ATTRIBUTES structure."""
    inherit = kwargs.get('inherit', 0)
    access = kwargs.get('access', GENERIC_READ|GENERIC_WRITE)
    attr = SECURITY_ATTRIBUTES()
    attr.bInheritHandle = inherit
    desc = SECURITY_DESCRIPTOR()
    dacl = ACL()
    for sid in sids:
        dacl.AddAccessAllowedAce(ACL_REVISION_DS, access, sid)
    desc.SetSecurityDescriptorDacl(True, dacl, False)
    attr.SECURITY_DESCRIPTOR = desc
    return attr


def _create_named_pipe(template, sids=None):
    """INTERNAL: create a named pipe."""
    if sids is None:
        sattrs = None
    else:
        sattrs = _create_security_attributes(*sids)
    for i in range(100):
        name = template % random.randint(0, 999999)
        try:
            pipe = CreateNamedPipe(name, PIPE_ACCESS_DUPLEX,
                                   0, 1, 1, 1, 100000, sattrs)
            SetHandleInformation(pipe, HANDLE_FLAG_INHERIT, 0)
        except WindowsError, e:
            if e.winerror != ERROR_PIPE_BUSY:
                raise
        else:
            return pipe, name
    raise ExceptionPexpect, 'Could not create pipe after 100 attempts.'


def _stub(cmd_name, stdin_name, stdout_name, stderr_name):
    """INTERNAL: Stub process that will start up the child process."""
    # Open the 4 pipes (command, stdin, stdout, stderr)
    cmd_pipe = CreateFile(cmd_name, GENERIC_READ|GENERIC_WRITE, 0, None,
                          OPEN_EXISTING, 0, None)
    SetHandleInformation(cmd_pipe, HANDLE_FLAG_INHERIT, 1)
    stdin_pipe = CreateFile(stdin_name, GENERIC_READ, 0, None,
                            OPEN_EXISTING, 0, None)
    SetHandleInformation(stdin_pipe, HANDLE_FLAG_INHERIT, 1)
    stdout_pipe = CreateFile(stdout_name, GENERIC_WRITE, 0, None,
                             OPEN_EXISTING, 0, None)
    SetHandleInformation(stdout_pipe, HANDLE_FLAG_INHERIT, 1)
    stderr_pipe = CreateFile(stderr_name, GENERIC_WRITE, 0, None,
                             OPEN_EXISTING, 0, None)
    SetHandleInformation(stderr_pipe, HANDLE_FLAG_INHERIT, 1)

    # Learn what we need to do..
    header = _read_header(cmd_pipe)
    input = _parse_header(header)
    if 'command' not in input or 'args' not in input:
        ExitProcess(2)

    # http://msdn.microsoft.com/en-us/library/ms682499(VS.85).aspx
    startupinfo = STARTUPINFO()
    startupinfo.dwFlags |= STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW
    startupinfo.hStdInput = stdin_pipe
    startupinfo.hStdOutput = stdout_pipe
    startupinfo.hStdError = stderr_pipe
    startupinfo.wShowWindow = SW_HIDE

    # Grant access so that our parent can open its grandchild.
    if 'parent_sid' in input:
        mysid = _get_current_sid()
        parent = ConvertStringSidToSid(input['parent_sid'])
        sattrs = _create_security_attributes(mysid, parent,
                                             access=PROCESS_ALL_ACCESS)
    else:
        sattrs = None

    try:
        res = CreateProcess(input['command'], input['args'], sattrs, None,
                            True, CREATE_NEW_CONSOLE, os.environ, os.getcwd(),
                            startupinfo)
    except WindowsError, e:
        message = _quote_header(str(e))
        WriteFile(cmd_pipe, 'status=error\nmessage=%s\n\n' % message)
        ExitProcess(3)
    else:
        pid = res[2]

    # Pass back results and exit
    err, nbytes = WriteFile(cmd_pipe, 'status=ok\npid=%s\n\n' % pid)
    ExitProcess(0)


class ChunkBuffer(object):
    """A buffer that allows a chunk of data to be read in smaller reads."""

    def __init__(self, chunk=''):
        self.add(chunk)

    def add(self, chunk):
        self.chunk = chunk
        self.offset = 0 

    def read(self, size):
        data = self.chunk[self.offset:self.offset+size]
        self.offset += size
        return data

    def __len__(self):
        return max(0, len(self.chunk)-self.offset)


class winspawn(spawn):
    """A version of pexpect.spawn for the Windows platform. """

    # The Windows version of spawn is quite different when compared to the
    # Posix version.
    #
    # The first difference is that it's not possible on Windows to select()
    # on a file descriptor that corresponds to a file or a pipe. Therefore,
    # to do non-blocking I/O, we need to use threads.
    #
    # Secondly, there is no way to pass /only/ the file descriptors
    # corresponding to the redirected stdin/out/err to the child. Either all
    # inheritable file descriptors are passed, or none. We solve this by
    # indirectly executing our child via a stub for which we close all file
    # descriptors. The stub communicates back to us via a named pipe.
    # 
    # Finally, Windows does not have ptys. It does have the concept of a
    # "Console" though but it's much less sophisticated. This code runs the
    # child in a new console by passing the flag CREATE_NEW_CONSOLE to
    # CreateProcess(). We create a new console for our child because this
    # way it cannot interfere with the current console, and it is also
    # possible to run the main program without a console (e.g. a Windows
    # service).

    pipe_buffer = 4096
    pipe_template = r'\\.\pipe\winpexpect-%06d'

    def __init__(self, command, args=[], timeout=30, maxread=2000,
                 searchwindowsize=None, logfile=None, cwd=None, env=None,
                 username=None, domain=None, password=None):
        """Constructor."""
        self.username = username
        self.domain = domain
        self.password = password
        self.child_handle = None
        self.child_output = Queue()
        self.chunk_buffer = ChunkBuffer()
        self.stdout_handle = None
        self.stdout_eof = False
        self.stdout_reader = None
        self.stderr_handle = None
        self.stderr_eof = False
        self.stderr_reader = None
        super(winspawn, self).__init__(command, args, timeout=timeout,
                maxread=maxread, searchwindowsize=searchwindowsize,
                logfile=logfile, cwd=cwd, env=env)

    def __del__(self):
        try:
            self.terminate()
        except WindowsError:
            pass

    def _spawn(self, command, args=None):
        """Start the child process. If args is empty, command will be parsed
        according to the rules of the MS C runtime, and args will be set to
        the parsed args."""
        if args:
            args = args[:]  # copy
            args.insert(0, command)
        else:
            args = split_command_line(command)
            command = args[0]

        self.command = command
        self.args = args
        command = which(self.command)
        if command is None:
            raise ExceptionPexpect, 'Command not found: %s' % self.command
        args = join_command_line(self.args)

        # Create the pipes
        sids = [_get_current_sid()]
        if self.username and self.password:
            sids.append(_lookup_sid(self.domain, self.username))
        cmd_pipe, cmd_name = _create_named_pipe(self.pipe_template, sids)
        stdin_pipe, stdin_name = _create_named_pipe(self.pipe_template, sids)
        stdout_pipe, stdout_name = _create_named_pipe(self.pipe_template, sids)
        stderr_pipe, stderr_name = _create_named_pipe(self.pipe_template, sids)

        startupinfo = STARTUPINFO()
        startupinfo.dwFlags |= STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = SW_HIDE

        python = os.path.join(sys.exec_prefix, 'python.exe')
        pycmd = 'import winpexpect; winpexpect._stub(r"%s", r"%s", r"%s", r"%s")' \
                    % (cmd_name, stdin_name, stdout_name, stderr_name)
        pyargs = join_command_line([python, '-c', pycmd])

        # Create a new token or run as the current process.
        if self.username and self.password:
            token = LogonUser(self.username, self.domain, self.password,
                              LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT)
            res = CreateProcessAsUser(token, python, pyargs, None, None,
                                      False, CREATE_NEW_CONSOLE, self.env,
                                      self.cwd, startupinfo)
        else:
            token = None
            res = CreateProcess(python, pyargs, None, None, False,
                                CREATE_NEW_CONSOLE, self.env, self.cwd,
                                startupinfo)
        child_handle = res[0]
        res[1].Close()  # don't need thread handle

        ConnectNamedPipe(cmd_pipe)
        ConnectNamedPipe(stdin_pipe)
        ConnectNamedPipe(stdout_pipe)
        ConnectNamedPipe(stderr_pipe)

        # Tell the stub what to do and wait for it to exit
        WriteFile(cmd_pipe, 'command=%s\n' % command)
        WriteFile(cmd_pipe, 'args=%s\n' % args)
        if token:
            parent_sid = ConvertSidToStringSid(_get_current_sid())
            WriteFile(cmd_pipe, 'parent_sid=%s\n' % str(parent_sid))
        WriteFile(cmd_pipe, '\n')

        header = _read_header(cmd_pipe)
        output = _parse_header(header)
        if output['status'] != 'ok':
            m = 'Child did not start up correctly. '
            m += output.get('message', '')
            raise ExceptionPexpect, m
        self.pid = int(output['pid'])
        self.child_handle = OpenProcess(PROCESS_ALL_ACCESS, False, self.pid)
        WaitForSingleObject(child_handle, INFINITE)

        # Start up the I/O threads
        self.child_fd = open_osfhandle(stdin_pipe.Detach(), 0)  # for pexpect
        self.stdout_handle = stdout_pipe
        self.stdout_reader = Thread(target=self._child_reader,
                                    args=(self.stdout_handle,))
        self.stdout_reader.start()
        self.stderr_handle = stderr_pipe
        self.stderr_reader = Thread(target=self._child_reader,
                                    args=(self.stderr_handle,))
        self.stderr_reader.start()
        self.terminated = False
        self.closed = False

    def terminate(self):
        """Terminate the child process. This also closes all the file
        descriptors."""
        if self.child_handle is None or self.terminated:
            return
        try:
            TerminateProcess(self.child_handle, 1)
        except WindowsError, e:
            # ERROR_ACCESS_DENIED (also) happens when the child has already
            # exited.
            if e.winerror == ERROR_ACCESS_DENIED and not self.isalive():
                pass
            else:
                raise
        self.close()
        self.wait()
        self.terminated = True

    def close(self):
        """Close all communications channels with the child."""
        if self.closed:
            return
        os.close(self.child_fd)
        CloseHandle(self.stdout_handle)
        CloseHandle(self.stderr_handle)
        # File descriptors are closed, nothing can be added to the queue
        # anymore. Empty it in case a thread was blocked on put().
        while self.child_output.qsize():
            self.child_output.get()
        # Now the threads are ready to be joined.
        self.stdout_reader.join()
        self.stderr_reader.join()
        self.closed = True

    def wait(self, timeout=None):
        """Wait until the child exits. If timeout is not specified this
        blocks indefinately. Otherwise, timeout specifies the number of
        seconds to wait."""
        if self.exitstatus is not None:
            return
        if timeout is None:
            timeout = INFINITE
        else:
            timeout = 1000 * timeout
        ret = WaitForSingleObject(self.child_handle, timeout)
        if ret == WAIT_TIMEOUT:
            raise TIMEOUT, 'Timeout exceeded in wait().'
        self.exitstatus = GetExitCodeProcess(self.child_handle)
        return self.exitstatus

    def isalive(self):
        """Return True if the child is alive, False otherwise."""
        if self.exitstatus is not None:
            return False
        ret = WaitForSingleObject(self.child_handle, 0)
        if ret == WAIT_OBJECT_0:
            self.exitstatus = GetExitCodeProcess(self.child_handle)
            return False
        return True

    def kill(self, signo):
        """Send a signal to the child (not available on Windows)."""
        raise ExceptionPexpect, 'Signals are not availalbe on Windows'

    def _child_reader(self, handle):
        """INTERNAL: Reader thread that reads stdout/stderr of the child
        process."""
        status = 'data'
        while True:
            try:
                err, data = ReadFile(handle, self.maxread)
                assert err == 0  # not expecting error w/o overlapped io
            except WindowsError, e:
                if e.winerror == ERROR_BROKEN_PIPE:
                    status = 'eof'
                    data = ''
                else:
                    status = 'error'
                    data = e.winerror
            self.child_output.put((handle, status, data))
            if status != 'data':
                break

    def _set_eof(self, handle):
        """INTERNAL: mark a file handle as end-of-file."""
        if handle == self.stdout_handle:
            self.stdout_eof = True
        elif handle == self.stderr_handle:
            self.stderr_eof = True

    def read_nonblocking(self, size=1, timeout=-1):
        """INTERNAL: Non blocking read."""
        if len(self.chunk_buffer):
            return self.chunk_buffer.read(size)
        if self.stdout_eof and self.stderr_eof:
            assert self.child_output.qsize() == 0
            return ''
        if timeout == -1:
            timeout = self.timeout
        try:    
            handle, status, data = self.child_output.get(timeout=timeout)
        except Empty:
            raise TIMEOUT, 'Timeout exceeded in read_nonblocking().'
        if status == 'data':
            self.chunk_buffer.add(data)
        elif status == 'eof':
            self._set_eof(handle)
            raise EOF, 'End of file in read_nonblocking().'
        elif status == 'error':
            self._set_eof(handle)
            raise OSError, data
        buf = self.chunk_buffer.read(size)
        if self.logfile is not None:
            self.logfile.write(buf)
            self.logfile.flush()
        if self.logfile_read is not None:
            self.logfile_read.write(buf)
            self.logfile_read.flush()
        return buf
