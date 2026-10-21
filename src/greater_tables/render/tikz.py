"""TikZ renderer: TableDoc → a tikzpicture in a table environment.

The emitter is :mod:`.tikz_tabular`: one node holding one real ``tabular``,
horizontal rules from booktabs and vertical rules drawn off the node's known
geometry. The layout it sets, cell text, column widths and scale, comes from
:mod:`.tikz_layout`. This module keeps the public entry points.

Cells flagged ``math`` re-wrap as ``$...$``; other text is TeX-escaped with
inline ``$...$`` spans passed through as math (``mathspans``, unless the
document says ``math='off'``). The table carries its own ``\\I`` strut as a
``\\providecommand`` and needs nothing from the host document beyond
``tikz``, ``booktabs`` and ``array``. ``TIKZ_PREAMBLE`` defines the same
strut for a document that wants it in the preamble.
"""

from __future__ import annotations

from ..ir import TableDoc
from ..spec import HouseStyle
from .tikz_layout import W2TIKZ, table_width
from .tikz_tabular import render_tikz_tabular

__all__ = ['TIKZ_PREAMBLE', 'W2TIKZ', 'render_tikz', 'render_tikz_tabular',
           'table_width']

TIKZ_PREAMBLE = r'\newcommand{\I}{\vphantom{lp}}'


def render_tikz(doc: TableDoc, style: HouseStyle | None = None) -> str:
    """Render a table document to a TikZ table (LaTeX source).

    Parameters
    ----------
    doc
        The table document.
    style
        House style; defaults to ``HouseStyle()``.

    Returns
    -------
    str
        A table environment holding one ``tikzpicture``, or a TeX comment
        for a table with no columns.
    """
    return render_tikz_tabular(doc, style or HouseStyle())
