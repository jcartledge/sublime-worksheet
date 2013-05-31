import sublime
import sublime_plugin
import threading


class WorksheetCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.removePreviousResults()
        self.repl = IPopen(['node', '-i'])
        self.repl.correspond('')
        self.processLine(0)

    def removePreviousResults(self):
        view = self.view
        edit = view.begin_edit('removePreviousResults')
        for region in reversed(view.find_all("^// > ")):
            view.erase(edit, view.full_line(region))
        self.view.end_edit(edit)

    def processLine(self, start):
        view = self.view
        line = view.full_line(start)
        next_start = line.end()
        line_text = view.substr(line)
        is_last_line = "\n" not in line_text
        if is_last_line:
            next_start += 1
            line_text += "\n"
        thread = ReplThread(self.repl, line_text)
        self.queue_thread(thread, next_start, is_last_line)
        thread.start()

    def queue_thread(self, thread, start, is_last_line):
        sublime.set_timeout(
            lambda: self.handle_result(thread, start, is_last_line),
            100
        )

    def handle_result(self, thread, next_start, is_last_line):
        if thread.is_alive():
            self.queue_thread(thread, next_start, is_last_line)
        else:
            edit = self.view.begin_edit('processLine')
            self.view.insert(edit, next_start, thread.result)
            self.view.end_edit(edit)
            next_start += len(thread.result)
            if not is_last_line:
                self.processLine(next_start)


class ReplThread(threading.Thread):
    def __init__(self, repl, str):
        self.repl = repl
        self.str = str
        self.result = None
        threading.Thread.__init__(self)

    def run(self):
        if not self.is_processable():
            self.result = ''
        else:
            result = self.repl.correspond(self.str)
            self.result = '\n'.join([
                "// > " + line for line in result.split("\n")[:-1]
            ]) + '\n'
            if len(self.result.strip()) is 0:
                self.result = ''

    def is_processable(self):
        return len(self.str.strip()) > 0

import os
import time
import fcntl
import subprocess


class IPopen(subprocess.Popen):

    POLL_INTERVAL = 0.01

    def __init__(self, *args, **kwargs):
        """Construct interactive Popen."""
        keyword_args = {
            'stdin': subprocess.PIPE,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'prompt': ('> ', '... ')
        }
        keyword_args.update(kwargs)
        self.prompt = keyword_args.get('prompt')
        del keyword_args['prompt']
        subprocess.Popen.__init__(self, *args, **keyword_args)
        # Make stderr and stdout non-blocking.
        for outfile in (self.stdout, self.stderr):
            if outfile is not None:
                fd = outfile.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    def correspond(self, text, sleep=0.01):
        """Communicate with the child process without closing stdin."""
        self.stdin.write(text)
        self.stdin.flush()
        str_buffer = ''
        while not str_buffer.endswith(self.prompt):
            try:
                str_buffer += self.stdout.read()
            except IOError:
                time.sleep(sleep)
        return str_buffer
