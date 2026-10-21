"""TikZ renderers: TableDoc → a tikzpicture in a table environment.

Two emitters share one layout pass (:mod:`.tikz_layout`) and are chosen by
``HouseStyle.tikz_engine``:

- ``'tabular'`` (default, :mod:`.tikz_tabular`) — one node holding one real
  ``tabular``, horizontal rules from booktabs and vertical rules drawn off the
  node's known geometry. Roughly 30x faster than the matrix, and the same
  table to the eye.
- ``'matrix'`` — a ``matrix of nodes`` with a zero-height spacer row that fixes
  column widths, header rows in bold (stub header cells bold-italic), and a
  trailing phantom column used as a stable anchor rail. Rules are ``\\path``
  segments anchored on node corners, shifted by half the row/column separation
  into the inter-cell gap; colspans sit as empty matrix cells whose label is
  overlaid centered on the span via ``calc`` midpoints. Roughly 290 ms of TeX
  per table — the cost is materializing one pgf node per cell and nothing
  else — but those nodes are addressable, which ``tikz_post_process`` TeX may
  rely on.

Cells flagged ``math`` re-wrap as ``$...$``; other text is TeX-escaped with
inline ``$...$`` spans passed through as math (``mathspans``, unless the
document says ``math='off'``).
The matrix emitter's output expects the ``\\I`` strut macro
(``TIKZ_PREAMBLE``) — Etcher's standalone template defines it, and a Quarto
document must include it once in the preamble. The tabular emitter carries its
own ``\\providecommand`` and needs nothing from the host document.
"""

from __future__ import annotations

import logging

from ..ir import Cell, TableDoc
from ..spec import HouseStyle
from .policy import rule_slot, vrule_slot
from .tikz_layout import (
    MATRIX_GEOMETRY, W2TIKZ, Layout, cell_tex, layout, placement, style_for,
    tex_escape,
)
from .tikz_tabular import render_tikz_tabular

__all__ = ['TIKZ_PREAMBLE', 'W2TIKZ', 'render_tikz', 'render_tikz_matrix',
           'render_tikz_tabular', 'table_width']

logger = logging.getLogger(__name__)

TIKZ_PREAMBLE = r'\newcommand{\I}{\vphantom{lp}}'

_EM = 1000


def table_width(widths, scale: float, ncols: int, csep_milli: int) -> int:
    """Emitted width of a *matrix* table, in milli-ems.

    Kept at module scope with its original signature; the general form lives
    on :class:`~.tikz_layout.Geometry`.
    """
    return MATRIX_GEOMETRY.table_width(widths, scale, ncols, csep_milli)


def render_tikz(doc: TableDoc, style: HouseStyle | None = None) -> str:
    """Render a table document to a TikZ table (LaTeX source).

    Dispatches on ``style.tikz_engine``; see the module docstring for what the
    two engines trade against each other.
    """
    style = style or HouseStyle()
    if style.tikz_engine == 'tabular':
        return render_tikz_tabular(doc, style)
    return render_tikz_matrix(doc, style)


def render_tikz_matrix(doc: TableDoc, style: HouseStyle | None = None) -> str:
    """Render a table document as a ``matrix of nodes`` tikzpicture."""
    style = style or HouseStyle()
    if len(doc.columns) == 0:
        return '% greater_tables: empty table\n'
    lay = layout(doc, style, MATRIX_GEOMETRY)
    return _emit(doc, style, lay)


def _emit(doc: TableDoc, style: HouseStyle, lay: Layout) -> str:
    name, ncols = lay.name, lay.ncols
    n_head, n_stub = lay.n_head, lay.n_stub
    grid, widths, aligns = lay.grid, lay.widths, lay.aligns
    csep, rsep = style.tikz_column_sep, style.tikz_row_sep
    gap, ygap = csep / 2, rsep / 2
    n_rows = len(grid)
    body_start, body_rows = lay.body_start, lay.body_rows

    colw = [max((len(grid[r][j]) for r in range(n_rows)), default=1)
            for j in range(ncols)]
    pad = {'l': '<', 'r': '>', 'c': '^'}
    # the *flush* variants: TikZ's plain 'left'/'right'/'center' are balanced
    # ragged, whose limited \rightskip stretch makes TeX break a line that
    # fits its column exactly — measured, a cell then needs ~0.1em of slack
    # per interword space. Flush is unlimited raggedness, so natural width
    # means natural width, which is what every width estimate here assumes
    # (and what the table-level 'text badly ragged' already asks for).
    align_word = {'l': 'flush left', 'r': 'flush right', 'c': 'flush center'}

    out: list[str] = []
    w = out.append

    # ---- container, caption, matrix styles
    latex = placement(style)
    w(f'\\begin{{{style.tikz_container_env}}}{latex}')
    w('\\centering')
    if doc.caption is not None:
        cap = doc.caption if isinstance(doc.caption, Cell) else Cell(text=doc.caption)
        label = f'\\label{{{doc.label}}}' if doc.label else ''
        w(f'\\caption{{{cell_tex(cap, math=doc.math != "off")}}}{label}')
    w('\\begin{tikzpicture}[')
    w('    auto, transform shape,')
    w('    nosep/.style={inner sep=0},')
    w('    table/.style={')
    w('        matrix of nodes,')
    w(f'        row sep={rsep}em,')
    w(f'        column sep={csep}em,')
    w('        nodes in empty cells,')
    w(f'        nodes={{rectangle, scale={lay.scale}, text badly ragged}},')
    w('\trow 1/.style={nodes={text=black, anchor=north, inner ysep=0, '
      'text height=0, text depth=0}},')
    for i in range(2, n_head + 2):
        w(f'\trow {i}/.style={{nodes={{text=black, anchor=south, '
          'inner ysep=.2em, minimum height=1.3em, font=\\bfseries, '
          'align=flush center}},')
        for j in range(1, 1 + n_stub):
            w(f'\trow {i} column {j}/.style='
              '{nodes={font=\\bfseries\\itshape, align=flush left}},')
    for j, (wd, al) in enumerate(zip(widths, aligns), start=1):
        extra = (f'inner xsep={csep}em, inner ysep=0, ' if j == 1 else 'nosep, ')
        w(f'\tcolumn {j:>2d}/.style={{nodes={{align={align_word[al]:<12s}}}, '
          f'{extra}text width={wd / _EM:.2f}em}},')
    w(f'\tcolumn {ncols + 1:>2d}/.style={{text height=0.9em, '
      'text depth=0.2em, nosep, text width=0em}')
    w('\t}]')

    # ---- the matrix
    w(f'\\matrix ({name}) [table, ampersand replacement=\\&]{{')
    for row in grid:
        line = ' '.join(
            f'{"" if j == 0 else chr(92) + "&"} '
            f'{row[j]:{pad[aligns[j]]}{colw[j]}s}'
            for j in range(ncols))
        w(line + ' \\& \\\\')
    w('};')

    # ---- overlaid spanners (real colspans)
    for tikz_row, c0, span, tex in lay.overlays:
        a = f'{name}-{tikz_row}-{c0 + 1}.west'
        b = f'{name}-{tikz_row}-{c0 + span}.east'
        opts = 'anchor=center' + (', font=\\bfseries'
                                  if tikz_row <= 1 + n_head else '')
        w(f'\\node[{opts}] at ($({a})!0.5!({b})$) {{{tex}}};')

    # ---- horizontal rules
    def hpath(style_name: str, tikz_row: int, start_col: int, shift: float):
        ref = f'{name}-{tikz_row}-{ncols + 1}'
        start = f'{name}-{tikz_row}-{start_col}'
        w(f'\\path[draw, {style_name}] '
          f'([yshift={shift}em]{ref}.north -| {start}.west) -- '
          f'([yshift={shift}em]{ref}.north -| {ref}.east);')

    top = style_for(style.frame_rule)
    if top:
        w(f'\\path[draw, {top}] ({name}-1-1.north west) -- '
          f'({name}-1-{ncols + 1}.north east);')
    base = style_for(style.head_rule)
    if base and body_rows:
        hpath(base, body_start, 1, ygap)
    n_body = lay.n_body
    for r, row in enumerate(body_rows):
        if r == 0 or r == n_body:          # first row of body / of foot
            continue
        rules = []
        d = row.break_depth
        slot = rule_slot(d, n_stub, style.max_rule_depth)
        if slot is not None:
            # weight from the slot, start column from the raw depth
            rules.append((style_for(style.hrule_widths[slot]), d + 1))
        if 'total' in row.flags or 'subtotal' in row.flags:
            rules.append((style_for(style.total_rule), 1))
        for style_name, start_col in rules:
            if style_name:
                hpath(style_name, body_start + r, start_col, ygap)
    bottom = style_for(style.frame_rule)
    if bottom:
        w(f'\\path[draw, {bottom}] '
          f'([yshift={-ygap}em]{name}-1-1.south west |- {name}.south) -- '
          f'([yshift={-ygap}em]{name}-1-{ncols + 1}.south east |- '
          f'{name}.south);')

    # ---- spanner rules: full-width underline per group label, extended by
    # the half-gap each side so adjacent groups meet at the group vertical
    sp = style_for(style.spanner_rule)
    if sp:
        for level, c0, span in lay.spanners:
            row = 2 + level
            a = f'{name}-{row}-{c0 + 1}.south west'
            b = f'{name}-{row}-{c0 + span}.south east'
            w(f'\\path[draw, {sp}] ([xshift={-gap}em, yshift={-ygap}em]{a}) '
              f'-- ([xshift={gap}em, yshift={-ygap}em]{b});')

    # ---- vertical rules
    stub = style_for(style.stub_rule)
    if stub and n_stub > 0:
        w(f'\\path[draw, {stub}] '
          f'([xshift={gap}em]{name}-1-{n_stub}.south east) -- '
          f'([xshift={gap}em]{name}-1-{n_stub}.south east |- {name}.south);')
    for j, column in enumerate(doc.columns):
        slot = (vrule_slot(column.break_depth, style.max_vrule_depth)
                if column.role == 'data' else None)
        if slot is None:
            continue
        vstyle = style_for(style.vrule_widths[slot])
        if not vstyle:
            continue
        # full height, table top to bottom — matching the HTML gt-vbreak
        # border which runs through the header rows
        anchor = f'{name}-1-{j + 1}.north west'
        w(f'\\path[draw, {vstyle}] ([xshift={-gap}em]{anchor}) -- '
          f'([xshift={-gap}em]{anchor} |- {name}.south);')

    if style.tikz_post_process:
        w(style.tikz_post_process)
    w('\\end{tikzpicture}')
    for note in doc.notes:
        w(f'\\par{{\\footnotesize {tex_escape(note, math=doc.math != "off")}}}')
    w(f'\\end{{{style.tikz_container_env}}}')
    return '\n'.join(out) + '\n'
