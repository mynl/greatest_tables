"""greatest_tables: semantic table engine with a versioned table-document IR.

Python owns semantics (dtypes, format inference, hierarchy, spans); renderers
own geometry and style. No import side effects — importing this package does
not touch pandas options, warnings filters, or anything else global.
"""

__version__ = '1.0.0'

from .engine.hashing import canonical_json, doc_hash, stamp
from .fabricator import Fabricator, quick_fab
from .ir import (
    IR_VERSION, Cell, Column, FormatSpec, HeadCell, Row, TableDoc,
    canonical_dict,
)

__all__ = [
    'IR_VERSION', '__version__', 'Cell', 'Column', 'Fabricator', 'FormatSpec',
    'HeadCell', 'Row', 'TableDoc', 'canonical_dict', 'canonical_json',
    'doc_hash', 'quick_fab', 'stamp',
]
