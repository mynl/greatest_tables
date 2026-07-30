"""greatest_tables: semantic table engine with a versioned table-document IR.

Python owns semantics (dtypes, format inference, hierarchy, spans); renderers
own geometry and style. No import side effects — importing this package does
not touch pandas options, warnings filters, or anything else global.
"""

from ._version import __version__
from .engine.build import build
from .engine.hashing import canonical_json, doc_hash, stamp
from .fabricator import Fabricator, quick_fab
from .ir import (
    IR_VERSION, Cell, Column, FormatSpec, HeadCell, Row, TableDoc,
    canonical_dict,
)
from .render.text import render_text
from .spec import HouseStyle, TableSpec

__all__ = [
    'IR_VERSION', '__version__', 'Cell', 'Column', 'Fabricator', 'FormatSpec',
    'HeadCell', 'HouseStyle', 'Row', 'TableDoc', 'TableSpec', 'build',
    'canonical_dict', 'canonical_json', 'doc_hash', 'quick_fab',
    'render_text', 'stamp',
]
