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
