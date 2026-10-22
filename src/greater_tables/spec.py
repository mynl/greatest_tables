"""User-facing table specification (semantics) and house style (opinions).

``TableSpec`` carries everything the *engine* needs to build a TableDoc —
semantic choices that ride with the table. ``HouseStyle`` carries renderer
opinions (rule weights, fonts, spacing) that must never enter the IR; it is
populated as renderers arrive.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Hashable, Literal

from .ir import FormatSpec

__all__ = ['ColSelector', 'HouseStyle', 'TableSpec']

logger = logging.getLogger(__name__)

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
    markdown_cols
        Columns whose cells carry inline markdown, ``*em*``, ``**strong**``
        and ```code``` (the rule is :mod:`greater_tables.markdownspans`).
        A selected column's leaf header is markdown too, and an index level
        selected by its name marks its stub cells and stub header. A
        markdown string input defaults to every column outside
        ``html_cols``; anything else defaults to none, since a star in a
        DataFrame may be a significance star, a footnote marker or a
        product. Naming a column here and in ``html_cols`` raises.
    markdown_caption
        Whether the caption is inline markdown. None (default) means yes for
        a markdown string input, whose ``Table:`` line is markdown, and no
        otherwise.
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
        client cannot re-render that column. A key that matches no column
        warns.
    shared_formatters
        Per-column formats for every table that has the column, keyed and
        matched as ``formatters`` is. A key the table lacks is skipped
        without a warning, which makes this the place for formats shared by
        a document's tables: a config file, or a ``functools.partial`` of
        ``GT``. An entry in ``formatters`` wins over one here. Nothing checks
        the keys, so a misspelled one does nothing and raises nothing; a
        format written for one table goes in ``formatters``, which warns.
    float_format, int_format, ratio_format, date_format
        House defaults, one per kind — the 5.x ``default_*_str`` settings.
        Each overrides only its own kind's built-in default and loses to an
        explicit ``formatters`` or ``shared_formatters`` entry.
        ``date_format`` covers the date tag and both date and datetime
        dtypes. Setting ``float_format`` turns the float *inference* off
        entirely, including the automatic engineering/SI switch, so
        ``pef_*`` and ``eng_*`` stop applying.
        Callables are rejected: these are house rules that must be
        YAML-expressible.
    table_float_format
        The sledgehammer: every **untagged float** column, overriding even an
        explicit ``formatters`` or ``shared_formatters`` entry. Ratio, year
        and date columns have a kind, so it never reaches them. Default None,
        and deliberately absent from ``config.write_template`` — set it
        consciously at a call site, never in a config file where it would
        silently defeat per-column formats months later.
    row_flags
        Mapping row position (negative allowed) → flags, or a callable
        ``(position, row_series) -> flags``. Vocabulary: total, subtotal,
        emphasis, muted.
    cell_flags
        Callable ``(position, column_label, value) -> flags`` for per-cell
        emphasis/muted. The ``neg`` flag is stamped automatically.
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
    markdown_cols: ColSelector = None
    markdown_caption: bool | None = None
    unbreakable: ColSelector = None
    aligners: str | Mapping[Hashable, str] | None = None
    formatters: Mapping[Hashable, FormatSpec | Mapping | str | int
                        | Callable[[Any], str]] = field(default_factory=dict)
    shared_formatters: Mapping[Hashable, FormatSpec | Mapping | str | int
                               | Callable[[Any], str]] = field(default_factory=dict)
    # --- house defaults, one per kind (5.x's default_*_str)
    float_format: FormatSpec | Mapping | str | int | None = None
    int_format: FormatSpec | Mapping | str | int | None = None
    ratio_format: FormatSpec | Mapping | str | int | None = None
    date_format: FormatSpec | Mapping | str | int | None = None
    table_float_format: FormatSpec | Mapping | str | int | None = None
    row_flags: Mapping[int, Sequence[str]] | Callable[[int, Any], Sequence[str]] | None = None
    cell_flags: Callable[[int, Hashable, Any], Sequence[str]] | None = None
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
    ``render.css.VARIABLES``; a weight set away from its default scales its
    property on that table, so both renderers follow one ``HouseStyle``.

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
    max_prose_width_em
        How wide a single *wrapping* column may get. TikZ reads it directly;
        HTML emits it as ``--gt-prose-max``. One column, not the table — the
        table is ``max_table_width_em``.
    min_prose_width_em
        How narrow a width budget may squeeze a column of prose, in ems: below
        it, the TikZ table scales instead. Without it a budget narrowed prose
        to its longest word, setting a description a word or two a line
        before it scaled anything. A column naturally narrower keeps its
        natural width, and a longer word still widens it. TikZ only: HTML
        has no scale to fall back on, so a minimum there would only overflow.
    max_table_width_em
        Total table width to aim for, in ems, or None (default) for no
        target. **A target, not a guarantee**: columns that must not wrap —
        numbers, dates, anything tagged or listed in ``TableSpec.unbreakable``
        — hold their natural width whatever the budget says, so a table of
        nothing but numbers can exceed it. What the budget can do is narrow
        the prose columns, which it does with one shared quantile so every
        one of them carries the same chance of wrapping
        (``render.widths``). When even the floors do not fit, TikZ steps
        ``tikz_scale`` down a fixed ladder, logging each step at WARNING and
        a table still too wide at the ladder's foot at ERROR;
        HTML hands the number to the browser as a CSS ``max-width`` and lets
        it measure. Ems because every other geometry field here is ems: at
        11pt, 8 inches is about 52em.
    tikz_engine
        The TikZ emitter, and ``'tabular'`` is the only one: one real
        ``tabular`` inside a single node, taking horizontal rules from
        booktabs and drawing only the vertical rules in TikZ. Its body is a
        literal ``tabular``, so the ``.tex`` lifts straight into a document
        that does not use TikZ, and it needs ``booktabs`` and ``array`` in
        the preamble. It cannot break across pages: a node is one
        unbreakable box. ``'matrix'``, a pgf ``matrix of nodes`` with one node
        per cell, was removed in 8.0.0; naming it logs a warning and renders
        the tabular, which sets the same table. The field stays so that a
        config naming either value still loads.
    tikz_font
        The face the document sets its tables in, which TikZ column widths
        are estimated in: ``'times'`` (default), ``'stix-two'``,
        ``'latin-modern'`` (the LaTeX default, a plain Quarto PDF's face),
        ``'lato'`` or ``'fira-sans'``. TeX needs the widths before it sets the
        table, so a mismatch shows: STIX Two sets lowercase about 5% wider
        than Times, enough to wrap a label sized in Times. Each face's glyph
        widths, roman and bold, are measured in ``render/fonts.py``. HTML is
        unaffected, because the browser measures. An unknown name raises
        ``ValueError``.
    tikz_post_process
        TeX appended inside the ``tikzpicture``, after the table and its
        rules. The table is one node, named ``gt<hash>`` from the document
        hash, so post-processing can address its anchors (``gt<hash>.north
        west`` and the like).
    text_ascii_rules
        Draw the text rendering with ASCII only — ``=`` and ``-`` for heavy
        and light rules, ``|`` for the stub divider, ``<<flag>>`` for the row
        gutter. Default False (box-drawing characters). Worth setting for a
        LaTeX verbatim block, where Pygments lexes U+2501 as an error token
        and styles it red, and for a console whose encoding or mono font
        cannot carry box drawing. Covers what the *renderer* draws, not cell
        text: values arrive already formatted, so ``FormatSpec.null`` (an em
        dash) and the SI suffix ladder (µ) still come through. Change those
        on the spec side if a build must be pure ASCII end to end.
    """

    max_rule_depth: int | Literal['auto'] | None = 'auto'
    max_vrule_depth: int | None = 1
    # --- widths, shared by every renderer that has an opinion about them
    max_prose_width_em: float = 18.0
    min_prose_width_em: float = 8.0
    max_table_width_em: float | None = None
    # --- text renderer
    text_ascii_rules: bool = False
    # --- TikZ engine, geometry (em) and container
    tikz_engine: Literal['tabular', 'matrix'] = 'tabular'
    tikz_font: str = 'times'
    tikz_scale: float = 1.0
    tikz_column_sep: float = 1.0
    tikz_row_sep: float = 0.25
    tikz_container_env: str = 'table'   # 'table' | 'figure' | 'sidewaystable' | 'sidewaysfigure'
    tikz_latex: str | None = None       # placement, e.g. 'ht'; sideways defaults to 'p'
    tikz_post_process: str = ''
    # --- rule weights (w2tikz scale)
    frame_rule: float = 1.0             # top and bottom of table
    head_rule: float = 1.0              # under the header block
    stub_rule: float = 1.0              # stub/body vertical divider
    total_rule: float = 0.75            # above rows flagged total
    spanner_rule: float = 0.5           # cmidrule under column-group labels
    hrule_widths: tuple[float, float, float] = (0.5, 0.25, 0.25)
    vrule_widths: tuple[float, float, float] = (0.25, 0.25, 0.25)

    def __post_init__(self):
        from .render.fonts import face
        face(self.tikz_font)            # fail at construction, not at render
        if self.tikz_engine == 'matrix':
            # a warning, not an error: the two engines set the same table, so
            # a document that still names the matrix keeps building
            logger.warning(
                "tikz_engine='matrix' was removed in 8.0.0; the table renders "
                "with 'tabular', the only TikZ engine. Drop the setting, or pin "
                "greater-tables<8 to keep the matrix.")
            self.tikz_engine = 'tabular'
        elif self.tikz_engine != 'tabular':
            raise ValueError(f"tikz_engine must be 'tabular', not "
                             f"{self.tikz_engine!r}")
