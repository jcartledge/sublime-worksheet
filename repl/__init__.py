import os
import sys

PY3K = sys.version_info >= (3, 0, 0)
POSIX = sys.platform != 'win32'
if sys.platform == 'win32':
    PLATFORM = 'windows'
elif sys.platform.startswith('darwin'):
    PLATFORM = 'osx'
elif sys.platform.startswith('linux'):
    PLATFORM = 'linux'

assert PLATFORM in ('windows', 'osx', 'linux')

if not POSIX:
    # (ST2) In order to get unicodedata work, add search path to where `sublime_text.exe` locates
    def _add_search_path(lib_path):
        def _try_get_short_path(p):
            # Python2.x cannot handle unicode path (contains any non-ascii characters) correctly
            p = os.path.normpath(p)
            if (not PY3K) and (not POSIX) and isinstance(p, unicode):
                try:
                    import locale
                    p = p.encode(locale.getpreferredencoding())
                except:
                    from ctypes import windll, create_unicode_buffer
                    buf = create_unicode_buffer(512)
                    if windll.kernel32.GetShortPathNameW(p, buf, len(buf)):
                        p = buf.value
            return p
        lib_path = _try_get_short_path(lib_path)
        if lib_path not in sys.path:
            sys.path.append(lib_path)
    _add_search_path(os.path.dirname(sys.executable))


from .repl import get_repl
from .repl import Repl
from .repl import ReplResult
from .repl import ReplStartError
from .repl_thread import ReplThread
from . import ftfy
