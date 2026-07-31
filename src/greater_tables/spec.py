"""User-facing table specification (semantics) and house style (opinions).

``TableSpec`` carries everything the *engine* needs to build a TableDoc —
semantic choices that ride with the table. ``HouseStyle`` carries renderer
opinions (rule weights, fonts, spacing) that must never enter the IR; it is
populated as renderers arrive.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Hashable, Literal

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
    formatters
        Per-column format override, keyed by column label (a tuple label also
        matches on its leaf name). Values: a FormatSpec, a mapping of
        FormatSpec fields (the YAML form), a sugar string (csv-grid
        ``',.1f'`` or GT ``'{x:.1%}'`` style), an int (decimal digits, with
        grouping), or a callable taking the value and returning a string.
        A callable owns its own NaN handling and does not reach the IR, so a
        client cannot re-render that column.
    float_format, int_format, ratio_format, date_format
        House defaults, one per kind — the 5.x ``default_*_str`` settings.
        Each overrides only its own kind's built-in default and loses to an
        explicit ``formatters`` entry. ``date_format`` covers the date tag
        and both date and datetime dtypes. Setting ``float_format`` turns the
        float *inference* off entirely, including the automatic
        engineering/SI switch, so ``pef_*`` and ``eng_*`` stop applying.
        Callables are rejected: these are house rules that must be
        YAML-expressible.
    table_float_format
        The sledgehammer: every **untagged float** column, overriding even an
        explicit ``formatters`` entry. Ratio, year and date columns have a
        kind, so it never reaches them. Default None, and deliberately absent
        from ``config.write_template`` — set it consciously at a call site,
        never in a config file where it would silently defeat per-column
        formats months later.
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
        **Data columns only** in every form — stub (index) columns never
        carry raw values, so a client that must sort on an index level
        wants ``df.reset_index()`` before ``build``.
    max_rows
        Truncate longer tables, appending a note. None = unlimited.
    sparsify, sparsify_columns
        Merge repeated stub values into rowspans / repeated header prefixes
        into colspans.
    pef_lower, pef_upper
        Engineering-format bounds: a float column whose mean magnitude falls
        outside ``[10**pef_lower, 10**pef_upper]`` renders in engineering
        notation, as does one whose nonzero values span more than
        ``10**pef_upper`` between largest and smallest (column-level
        decisions — 5.x switched per cell, mixing formats within a column).
    eng_digits, eng_style
        What engineering format looks like when it fires: decimals, and
        ``'si'`` suffixes (µ m k M G …) or ``'exp'`` aligned exponents.
        Both are dead if ``float_format`` is set — that turns inference off.
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
    formatters: Mapping[Hashable, FormatSpec | Mapping | str | int
                        | Callable[[Any], str]] = field(default_factory=dict)
    # --- house defaults, one per kind (5.x's default_*_str)
    float_format: FormatSpec | Mapping | str | int | None = None
    int_format: FormatSpec | Mapping | str | int | None = None
    ratio_format: FormatSpec | Mapping | str | int | None = None
    date_format: FormatSpec | Mapping | str | int | None = None
    table_float_format: FormatSpec | Mapping | str | int | None = None
    row_flags: Mapping[int, Sequence[str]] | Callable[[int, Any], Sequence[str]] | None = None
    cell_flags: Callable[[int, Hashable, Any], Sequence[str]] | None = None
    math: str = 'auto'
    include_raw: bool | str | Sequence[Hashable] = False
    max_rows: int | None = 200
    sparsify: bool = True
    sparsify_columns: bool = True
    pef_lower: int = -3
    pef_upper: int = 6
    eng_digits: int = 3
    eng_style: Literal['si', 'exp'] = 'si'


@dataclass
class HouseStyle:
    """Renderer opinions — never serialized into the IR.

    Rule weights are the greater_tables float scale, mapped to TikZ line
    styles via ``render.tikz.W2TIKZ`` (0 = don't draw, 0.25 = ultra thin …
    3 = ultra thick). HTML equivalents live as CSS custom properties in
    ``render.css.VARIABLES``.

    Parameters
    ----------
    max_rule_depth
        How deep the hierarchy is ruled. ``'auto'`` (default) rules every
        break except the innermost stub level — a change there is just "next
        row", so ruling it draws a line between every row; that gives no
        rules on a single-level index, depth 0 only on two levels, depths 0
        and 1 on three. An **int is literal**: ``0`` rules only outermost
        changes, and on a single-level index it rules every row whose stub
        changed. None draws no internal rules at all.
    max_vrule_depth
        The same for column-group verticals (None = none). Only
        ``render.policy.N_VRULE_SLOTS`` weights exist, so deeper breaks reuse
        the lightest.
    """

    max_rule_depth: int | Literal['auto'] | None = 'auto'
    max_vrule_depth: int | None = 1
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
    spanner_rule: float = 0.5           # cmidrule under column-group labels
    hrule_widths: tuple[float, float, float] = (0.5, 0.25, 0.25)
    vrule_widths: tuple[float, float, float] = (0.25, 0.25, 0.25)
