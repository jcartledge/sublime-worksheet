import threading


class ReplThread(threading.Thread):
    def __init__(self, repl, str):
        self.repl = repl
        self.str = str
        self.result = None
        threading.Thread.__init__(self)

    def run(self):
        self.result = self.repl.correspond(self.str)
