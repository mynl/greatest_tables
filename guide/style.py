"""Style for the guide's Quarto notes: house style, with nothing local yet.

House style's ``house`` module ships inside the installed extension. This
module puts that directory on ``sys.path``, derived from its own location so
the notes build wherever the repo is cloned, and re-exports house style. A
real project's module adds here whatever is genuinely its own.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / '_extensions' / 'house'))

from house import *  # noqa: E402,F403
from house import __all__  # noqa: E402,F401
