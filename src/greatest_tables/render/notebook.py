"""Notebook/Quarto integration helpers.

The mimebundle always carries ``text/html``. A ``text/latex`` entry joins it
once the TikZ renderer exists ([tikz-blog]) — and then only when explicitly
requested or a Quarto render is detected, which is what structurally fixes
greater_tables 5.x's compute-TikZ-then-discard-it-per-repr waste.
"""

from __future__ import annotations

import os

from ..ir import TableDoc
from .html import render_html

__all__ = ['in_quarto', 'mimebundle']


def in_quarto() -> bool:
    """True inside a ``quarto render`` (any QUARTO_* env variable set)."""
    return any(k.startswith('QUARTO_') for k in os.environ)


def mimebundle(doc: TableDoc, *, css: str = 'embed') -> dict[str, str]:
    """MIME bundle for ``_repr_mimebundle_``."""
    return {'text/html': render_html(doc, css=css)}
