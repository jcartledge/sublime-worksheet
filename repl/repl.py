import re
import os
from functools import reduce

from . import PY3K, POSIX, PLATFORM


if POSIX:
    from . import pexpect
    spawn = pexpect.spawn
else:
    from . import winpexpect as pexpect
    spawn = pexpect.winspawn

from .ftfy import fix_text

repl_base = os.path.abspath(os.path.dirname(__file__))



def get_repl(language, repl_def):
    if repl_def.get("cmd") is not None:
        return Repl(
            repl_def.pop("cmd").format(repl_base=repl_base),
            **repl_def
        )
    raise ReplStartError("No worksheet REPL found for " + language)


class ReplResult():
    def __init__(self, text="",
                 is_timeout=False,
                 is_eof=False,
                 is_error=False):
        if len(text.strip()) > 0:
            text += "\n"
        self.text = text
        self.is_timeout = is_timeout
        self.is_eof = is_eof
        self.is_error = is_error

    def __str__(self):
        return self.text

    @property
    def terminates(self):
        return self.is_timeout or self.is_eof or self.is_error


class ReplStartError(Exception):
    pass


class ReplCloseError(Exception):
    pass


class Repl():
    def __init__(self, cmd, prompt, prefix, error=[], ignore=[], timeout=10, cwd=None):
        self.repl = spawn(cmd, timeout=timeout, cwd=cwd)
        base_prompt = [pexpect.EOF, pexpect.TIMEOUT]
        self.prompt = base_prompt + self.repl.compile_pattern_list(prompt)
        self.prefix = prefix
        self.error = [re.compile(prefix + x) for x in error]
        self.ignore = [re.compile(x) for x in ignore]
        self.repl.timeout = timeout
        index = self.repl.expect_list(self.prompt)
        if self.prompt[index] in [pexpect.EOF, pexpect.TIMEOUT]:
            raise ReplStartError("Could not start " + cmd)

    def correspond(self, input):
        if self.should_ignore(input):
            return ReplResult()
        prefix = self.prefix
        self.repl.send(re.sub("\t", " ", input))
        index = self.repl.expect_list(self.prompt)
        if self.prompt[index] == pexpect.TIMEOUT:
            # Timeout
            return ReplResult(prefix + "Execution timed out.", is_timeout=True)
        else:
            # For multiline statements additional newline is needed. See #26 issue
            start_index = 1 if len(input.strip()) else 0
            # Regular prompt - need to check for error
            result_list = [
                prefix + line
                for line in fix_text(self.repl.before).split("\n")
                if len(line.strip())
            ]
            if POSIX:
                # this is needed for POSIX only
                # on windows, there's no echo back for the input (defect: not for irb)
                result_list = result_list[start_index:]
            result_str = "\n".join(result_list)
            is_eof = self.prompt[index] == pexpect.EOF
            if is_eof:
                result_str = "\n".join([result_str, prefix + " [exit]"])
            return ReplResult(result_str,
                              is_error=self.is_error(result_str),
                              is_eof=is_eof)

    def should_ignore(self, str):
        return self._match_one(self.ignore, str)

    def is_error(self, str):
        return self._match_one(self.error, str)

    def _match_one(self, regexes, str):
        return reduce(
            lambda acc, pattern: acc or pattern.match(str) is not None,
            regexes, False)

    def close(self, tries=0, max_retries=3):
        try:
            # sometimes the process (*ahem* java) takes a little too long to
            # close, so take 3 tries.
            self.repl.close(force=True)
        except pexpect.ExceptionPexpect as e:
            # wasn't closed, try again
            tries += 1
            if tries >= max_retries:
                raise ReplCloseError(e.message)
            else:
                self.close(tries, max_retries)
        except OSError as e:
            # Already closed - we're done.
            pass
