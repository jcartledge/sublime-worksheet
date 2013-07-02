import sys

PY3K = sys.version_info >= (3, 0, 0)

if PY3K:
    from . import ftfy
    from .repl import get_repl
    from .repl import Repl
    from .repl import ReplResult
    from .repl import ReplStartError
    from .repl_thread import ReplThread
else:
    from repl import get_repl
    from repl import Repl
    from repl import ReplResult
    from repl import ReplStartError
    from repl_thread import ReplThread
    import ftfy
