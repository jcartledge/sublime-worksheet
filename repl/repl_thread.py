import threading


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
                self.repl.prefix + line for line in result.split("\n")[:-1]
            ]) + '\n'
            if len(self.result.strip()) is 0:
                self.result = ''

    def is_processable(self):
        return len(self.str.strip()) > 0

