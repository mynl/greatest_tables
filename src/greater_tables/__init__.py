"""greater_tables: semantic table engine with a versioned table-document IR.

Python owns semantics (dtypes, format inference, hierarchy, spans); renderers
own geometry and style. No import side effects — importing this package does
not touch pandas options, warnings filters, or anything else global.
"""

from ._version import __version__
from .compat import GT
from .config import load_spec, load_style
from .engine.build import build
from .engine.hashing import canonical_json, doc_hash, stamp
from .fabricator import Fabricator, quick_fab
from .ir import (
    IR_VERSION, Cell, Column, FormatSpec, HeadCell, Row, TableDoc,
    canonical_dict,
)
from .render.etcher import Etcher
from .render.html import render_html
from .render.text import render_text
from .render.tikz import render_tikz
from .spec import HouseStyle, TableSpec

__all__ = [
    'Etcher', 'GT', 'IR_VERSION', '__version__', 'Cell', 'Column',
    'Fabricator', 'FormatSpec', 'HeadCell', 'HouseStyle', 'Row', 'TableDoc',
    'TableSpec', 'build', 'canonical_dict', 'canonical_json', 'doc_hash',
    'load_spec', 'load_style', 'quick_fab', 'render_html', 'render_text',
    'render_tikz', 'stamp',
]
