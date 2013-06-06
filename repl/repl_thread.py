import threading


class ReplThread(threading.Thread):
    def __init__(self, repl, str, is_last_line):
        self.repl = repl
        self.str = str
        self.is_last_line = is_last_line
        self.result = None
        threading.Thread.__init__(self)

    def run(self):
        self.result = self.repl.correspond(self.str, self.is_last_line)
