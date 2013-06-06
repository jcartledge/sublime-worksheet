import pexpect
from ftfy import fix_text


class Repl():
    def __init__(self, cmd, prompt, prefix):
        self.prefix = prefix
        self.repl = pexpect.spawn(cmd)
        base_prompt = [pexpect.EOF, pexpect.TIMEOUT]
        self.prompt = base_prompt + self.repl.compile_pattern_list(prompt)
        self.repl.timeout = 10
        self.repl.expect_list(self.prompt)

    def correspond(self, input, is_last_line=False):
        prefix = self.prefix
        if is_last_line:
            prefix = "\n" + prefix
            input += "\n"
        self.repl.send(input)
        index = self.repl.expect_list(self.prompt)
        if index == 0:
            # EOF
            result = ''
        elif index == 1:
            # Timeout
            result = prefix + "Execution timed out."
        else:
            # Regular prompt
            result = '\n'.join([
                prefix + line
                for line in fix_text(unicode(self.repl.before)).split("\n")
                if len(line.strip())
            ][1:])
        if len(result.strip()) > 0 and not is_last_line:
            result += "\n"
        return result

    def close(self):
        self.repl.close()
