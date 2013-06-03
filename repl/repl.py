import pexpect
from ftfy import fix_text


class Repl():
    def __init__(self, cmd, prompt, prefix):
        self.prefix = prefix
        self.repl = pexpect.spawn(cmd)
        self.prompt = self.repl.compile_pattern_list(prompt)
        self.repl.timeout = 10
        self.repl.expect_list(self.prompt)

    def correspond(self, input):
        self.repl.send(input)
        self.repl.expect_list(self.prompt)
        return '\n'.join([
            self.prefix + line
            for line in fix_text(unicode(self.repl.before)).split("\n")
            if len(line.strip())
        ][1:]) + '\n'

    def close(self):
        self.repl.close()
