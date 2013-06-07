import pexpect
from ftfy import fix_text


class ReplResult():
    def __init__(self, text="", is_timeout=False, is_eof=False, is_last_line=False):
        if len(text.strip()) > 0 and not is_last_line:
            text += "\n"
        self.text = text
        self.is_timeout = is_timeout
        self.is_eof = is_eof

    def __str__(self):
        return self.text


class ReplStartError(Exception):
    pass

class ReplCloseError(Exception):
    pass


class Repl():
    def __init__(self, cmd, prompt, prefix, timeout=10, cwd=None):
        self.prefix = prefix
        self.repl = pexpect.spawn(cmd, timeout=timeout, cwd=cwd)
        base_prompt = [pexpect.EOF, pexpect.TIMEOUT]
        self.prompt = base_prompt + self.repl.compile_pattern_list(prompt)
        self.repl.timeout = timeout
        index = self.repl.expect_list(self.prompt)
        if self.prompt[index] in [pexpect.EOF, pexpect.TIMEOUT]:
            raise ReplStartError(cmd)

    def correspond(self, input, is_last_line=False):
        prefix = self.prefix
        if is_last_line:
            prefix = "\n" + prefix
            input += "\n"
        self.repl.send(input)
        index = self.repl.expect_list(self.prompt)
        if self.prompt[index] == pexpect.EOF:
            # EOF
            return ReplResult(prefix + " EOF", is_eof=True)
        elif self.prompt[index] == pexpect.TIMEOUT:
            # Timeout
            return ReplResult(prefix + "Execution timed out.", is_timeout=True)
        else:
            # Regular prompt
            return ReplResult('\n'.join([
                prefix + line
                for line in fix_text(unicode(self.repl.before)).split("\n")
                if len(line.strip())
            ][1:]))

    def close(self, tries=0, max_retries=3):
        try:
            # sometimes the process (*ahem* java) takes a little too long to
            # close, so take 3 tries.
            self.repl.close(force=True)
        except pexpect.ExceptionPexpect, e:
            # wasn't closed, try again
            tries += 1
            if tries >= max_retries:
                raise ReplCloseError(e.message)
            else:
                self.close(tries, max_retries)
        except OSError, e:
            # Already closed - we're done.
            pass
