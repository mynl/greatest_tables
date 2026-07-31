"""Notebook/Quarto integration helpers.

The mimebundle always carries ``text/html``. ``text/latex`` (the TikZ
rendering) joins only when explicitly requested or a Quarto render is
detected — which is what structurally fixes greater_tables 5.x's
compute-TikZ-then-discard-it-per-repr waste.
"""

from __future__ import annotations

import os

from ..ir import TableDoc
from ..spec import HouseStyle
from .html import render_html
from .tikz import render_tikz

__all__ = ['in_quarto', 'mimebundle']


def in_quarto() -> bool:
    """True inside a ``quarto render`` (any QUARTO_* env variable set)."""
    return any(k.startswith('QUARTO_') for k in os.environ)


def mimebundle(doc: TableDoc, *, css: str = 'embed',
               tikz: bool | None = None,
               style: HouseStyle | None = None) -> dict[str, str]:
    """MIME bundle for ``_repr_mimebundle_``.

    Parameters
    ----------
    doc
        The document.
    css
        Stylesheet policy for the HTML entry.
    tikz
        Include ``text/latex``: True/False forces; None (default) includes
        it only under Quarto.
    style
        HouseStyle, forwarded to both renderers (HTML reads only the rule
        depth caps; TikZ reads everything).
    """
    bundle = {'text/html': render_html(doc, css=css, style=style)}
    if tikz or (tikz is None and in_quarto()):
        bundle['text/latex'] = render_tikz(doc, style)
    return bundle
