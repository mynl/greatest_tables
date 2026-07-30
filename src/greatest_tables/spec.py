"""User-facing table specification (semantics) and house style (opinions).

``TableSpec`` carries everything the *engine* needs to build a TableDoc —
semantic choices that ride with the table. ``HouseStyle`` carries renderer
opinions (rule weights, fonts, spacing) that must never enter the IR; it is
populated as renderers arrive.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Hashable

from .ir import FormatSpec

__all__ = ['ColSelector', 'HouseStyle', 'TableSpec']

# 'all' | regex string | explicit list of column labels | None
ColSelector = str | Sequence[Hashable] | None


@dataclass
class TableSpec:
    """Semantic specification for one table.

    Parameters
    ----------
    caption, label, notes
        Table metadata; ``label`` is the Quarto cross-reference id.
    show_index
        Show the row index as stub columns. None (default) auto-hides a
        trivial unnamed RangeIndex.
    header_row
        For list input: promote the first row to column headers.
    ratio_cols, year_cols, date_cols, raw_cols
        Semantic column tags: a list of labels, ``'all'``, or a regex
        matched against column names.
    html_cols
        String columns whose cells carry raw HTML (sets the cell
        ``html`` flag; renderers still gate on their own allow-html option).
    unbreakable
        Columns forced to ``wrap=False`` regardless of dtype.
    aligners
        ``'lrc'``-style string (positional) or mapping label → 'l'/'r'/'c'.
    formats
        Per-column format override: a FormatSpec, sugar string (csv-grid
        ``',.1f'`` or GT ``'{x:.1%}'`` style), or int (decimal digits).
    row_flags
        Mapping row position (negative allowed) → flags, or a callable
        ``(position, row_series) -> flags``. Vocabulary: total, subtotal,
        emphasis, muted.
    cell_flags
        Callable ``(position, column_label, value) -> flags`` for per-cell
        emphasis/muted. The ``neg`` flag is stamped automatically.
    math
        ``'auto'`` detects ``$...$``-wrapped string cells as math;
        ``'off'`` disables.
    include_raw
        Carry raw values in body cells: False (default), True/'data'
        (numeric/date/bool data columns), or an explicit column list.
    max_rows
        Truncate longer tables, appending a note. None = unlimited.
    sparsify, sparsify_columns
        Merge repeated stub values into rowspans / repeated header prefixes
        into colspans.
    pef_lower, pef_upper
        Engineering-format bounds: a float column whose mean magnitude falls
        outside ``[10**pef_lower, 10**pef_upper]`` renders in engineering
        notation (column-level decision).
    """

    caption: str | None = None
    label: str | None = None
    notes: Sequence[str] = ()
    show_index: bool | None = None
    header_row: bool = False
    ratio_cols: ColSelector = None
    year_cols: ColSelector = None
    date_cols: ColSelector = None
    raw_cols: ColSelector = None
    html_cols: ColSelector = None
    unbreakable: ColSelector = None
    aligners: str | Mapping[Hashable, str] | None = None
    formats: Mapping[Hashable, FormatSpec | str | int] = field(default_factory=dict)
    row_flags: Mapping[int, Sequence[str]] | Callable[[int, Any], Sequence[str]] | None = None
    cell_flags: Callable[[int, Hashable, Any], Sequence[str]] | None = None
    math: str = 'auto'
    include_raw: bool | str | Sequence[Hashable] = False
    max_rows: int | None = 200
    sparsify: bool = True
    sparsify_columns: bool = True
    pef_lower: int = -3
    pef_upper: int = 6


@dataclass
class HouseStyle:
    """Renderer opinions — never serialized into the IR.

    Rule weights are the greater_tables float scale, mapped to TikZ line
    styles via ``render.tikz.W2TIKZ`` (0 = don't draw, 0.25 = ultra thin …
    3 = ultra thick). HTML equivalents live as CSS custom properties in
    ``render.css.VARIABLES``.
    """

    max_rule_depth: int = 2
    # --- TikZ geometry (em) and container
    tikz_scale: float = 1.0
    tikz_column_sep: float = 1.0
    tikz_row_sep: float = 0.25
    tikz_container_env: str = 'table'   # 'table' | 'figure' | 'sidewaysfigure'
    tikz_latex: str | None = None       # placement, e.g. 'ht'
    tikz_post_process: str = ''
    tikz_prose_max_em: float = 18.0     # wrap columns cap (TikZ text width)
    # --- rule weights (w2tikz scale)
    frame_rule: float = 1.0             # top and bottom of table
    head_rule: float = 1.0              # under the header block
    stub_rule: float = 1.0              # stub/body vertical divider
    total_rule: float = 0.75            # above rows flagged total
    hrule_widths: tuple[float, float, float] = (0.5, 0.25, 0.25)
    vrule_widths: tuple[float, float, float] = (0.25, 0.25, 0.25)
