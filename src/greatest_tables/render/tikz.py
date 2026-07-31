"""TikZ renderer: TableDoc → tikzpicture in a table environment.

The single implementation (greater_tables carried three, two dead), rebuilt
from the live ``make_tikz`` mechanics against the IR:

- a ``matrix of nodes`` with a zero-height spacer row that fixes column
  widths, header rows in bold (stub header cells bold-italic), and a
  trailing phantom column used as a stable anchor rail;
- rules drawn as ``\\path`` segments anchored on node corners, shifted by
  half the row/column separation into the inter-cell gap — row break rules
  start exactly at the changed stub column, mirroring the HTML renderer;
- **colspan support** (new vs. 5.x): spanning cells sit as empty matrix
  cells and their label is overlaid centered on the span via ``calc``
  midpoints — real spanners, not blanked repeats;
- character-based width estimation (the salvaged TextLength glyph table)
  lives here and only here — TeX genuinely needs geometry, HTML does not.

Cells flagged ``math`` re-wrap as ``$...$``; everything else is TeX-escaped.
The output expects the ``\\I`` strut macro (``TIKZ_PREAMBLE``) — Etcher's
standalone template defines it; Quarto documents include it once in the
preamble.
"""

from __future__ import annotations

import re

from ..ir import Cell, HeadCell, TableDoc
from ..spec import HouseStyle
from .textlength import text_display_len

__all__ = ['TIKZ_PREAMBLE', 'W2TIKZ', 'render_tikz']

# greater_tables' float-weight → TikZ line-style scale (0 = do not draw)
W2TIKZ = {0: None, 0.25: 'ultra thin', 0.5: 'very thin', 0.75: 'thin',
          1: 'semithick', 1.5: 'thick', 2: 'very thick', 3: 'ultra thick'}

TIKZ_PREAMBLE = r'\newcommand{\I}{\vphantom{lp}}'

_MAX_BREAK = 2
_MAX_VBREAK = 1
# header cells render bold (stubs bold-italic): widen their width estimate
# so long headers don't collide across the column gap (GT bold_adjustment)
_BOLD_ADJUSTMENT = 1.15

_TEX_SPECIALS = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%',
                 '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
                 '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
_TEX_RE = re.compile('|'.join(re.escape(k) for k in _TEX_SPECIALS))
_TAG_RE = re.compile(r'<[^>]*>')


def _style_for(weight: float) -> str | None:
    return W2TIKZ.get(weight, 'very thin')


def _escape(text: str) -> str:
    return _TEX_RE.sub(lambda m: _TEX_SPECIALS[m.group(0)], text)


def _cell_tex(cell: Cell | HeadCell, row_flags: tuple = ()) -> str:
    """TeX for one cell: math re-wrapped, html stripped, flags styled."""
    if cell.math:
        tex = f'${cell.text}$'
    else:
        text = _TAG_RE.sub('', cell.text) if cell.html else cell.text
        tex = _escape(text).replace(chr(0xa0), '~')
    flags = set(cell.flags) | set(row_flags)
    if flags & {'total', 'subtotal', 'emphasis'}:
        tex = f'\\bfseries {tex}'
    if 'muted' in flags:
        tex = f'\\textcolor{{gray}}{{{tex}}}'
    return tex


def _display_width(cell: Cell | HeadCell) -> float:
    """Em width estimate of a cell's displayed content."""
    text = f'${cell.text}$' if cell.math else _TAG_RE.sub('', cell.text) \
        if cell.html else cell.text
    return text_display_len(text)


def render_tikz(doc: TableDoc, style: HouseStyle | None = None) -> str:
    """Render a table document to a TikZ table (LaTeX source)."""
    style = style or HouseStyle()
    ncols = len(doc.columns)
    if ncols == 0:
        return '% greatest_tables: empty table\n'
    name = f'gt{doc.hash or "x"}'
    n_head = len(doc.head)
    n_stub = doc.n_stub_levels
    csep, rsep = style.tikz_column_sep, style.tikz_row_sep
    gap, ygap = csep / 2, rsep / 2

    # ---- lay out cells into an ncols-wide text matrix + overlay spans;
    # measure display widths at placement (true visual column known here)
    # matrix rows: 1 spacer + n_head + body(+foot); tikz indices are 1-based
    grid: list[list[str]] = [[''] * ncols]           # spacer row
    overlays: list[tuple[int, int, int, str]] = []   # (tikz row, c0, span, tex)
    wmax = [2.0] * ncols
    for level, hrow in enumerate(doc.head):
        cells = [''] * ncols
        col = 0
        for hc in hrow:
            tex = _cell_tex(hc)
            if hc.colspan == 1:
                cells[col] = tex + (r'\I' if hc.text else '')
                wmax[col] = max(wmax[col],
                                _display_width(hc) * _BOLD_ADJUSTMENT)
            elif hc.text:
                overlays.append((2 + level, col, hc.colspan, tex))
            col += hc.colspan
        grid.append(cells)

    body_start = 2 + n_head                          # tikz row of body row 0
    body_rows = list(doc.body) + list(doc.foot)
    pending = [0] * ncols
    for r, row in enumerate(body_rows):
        cells = [''] * ncols
        col = 0
        for entry in row.cells:
            cell = entry if isinstance(entry, Cell) else Cell(text=entry)
            while col < ncols and pending[col] > 0:
                col += 1
            if col >= ncols:
                break
            tex = _cell_tex(cell, row.flags)
            if cell.colspan == 1:
                cells[col] = tex
                wmax[col] = max(wmax[col], _display_width(cell))
            elif cell.text:
                overlays.append((body_start + r, col, cell.colspan, tex))
            for cc in range(col, min(ncols, col + cell.colspan)):
                if cell.rowspan > 1:
                    pending[cc] = cell.rowspan
            col += cell.colspan
        for cc in range(ncols):
            if pending[cc] > 0:
                pending[cc] -= 1
        grid.append(cells)
    n_rows = len(grid)

    # ---- column geometry: em text widths (TextLength) + source padding
    widths = [round(min(w, style.tikz_prose_max_em) if c.wrap else w, 2)
              for w, c in zip(wmax, doc.columns)]
    colw = [max((len(grid[r][j]) for r in range(n_rows)), default=1)
            for j in range(ncols)]
    pad = {'l': '<', 'r': '>', 'c': '^'}
    align_word = {'l': 'left', 'r': 'right', 'c': 'center'}
    aligns = [c.align for c in doc.columns]

    out: list[str] = []
    w = out.append

    # ---- container, caption, matrix styles
    latex = f'[{style.tikz_latex}]' if style.tikz_latex else ''
    w(f'\\begin{{{style.tikz_container_env}}}{latex}')
    w('\\centering')
    if doc.caption is not None:
        cap = doc.caption if isinstance(doc.caption, Cell) else Cell(text=doc.caption)
        label = f'\\label{{{doc.label}}}' if doc.label else ''
        w(f'\\caption{{{_cell_tex(cap)}}}{label}')
    w('\\begin{tikzpicture}[')
    w('    auto, transform shape,')
    w('    nosep/.style={inner sep=0},')
    w('    table/.style={')
    w('        matrix of nodes,')
    w(f'        row sep={rsep}em,')
    w(f'        column sep={csep}em,')
    w('        nodes in empty cells,')
    w(f'        nodes={{rectangle, scale={style.tikz_scale}, text badly ragged}},')
    w('\trow 1/.style={nodes={text=black, anchor=north, inner ysep=0, '
      'text height=0, text depth=0}},')
    for i in range(2, n_head + 2):
        w(f'\trow {i}/.style={{nodes={{text=black, anchor=south, '
          'inner ysep=.2em, minimum height=1.3em, font=\\bfseries, '
          'align=center}},')
        for j in range(1, 1 + n_stub):
            w(f'\trow {i} column {j}/.style='
              '{nodes={font=\\bfseries\\itshape, align=left}},')
    for j, (wd, al) in enumerate(zip(widths, aligns), start=1):
        extra = (f'inner xsep={csep}em, inner ysep=0, ' if j == 1 else 'nosep, ')
        w(f'\tcolumn {j:>2d}/.style={{nodes={{align={align_word[al]:<6s}}}, '
          f'{extra}text width={max(2.0, wd):.2f}em}},')
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
    for tikz_row, c0, span, tex in overlays:
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

    top = _style_for(style.frame_rule)
    if top:
        w(f'\\path[draw, {top}] ({name}-1-1.north west) -- '
          f'({name}-1-{ncols + 1}.north east);')
    base = _style_for(style.head_rule)
    if base and body_rows:
        hpath(base, body_start, 1, ygap)
    for r, row in enumerate(body_rows):
        if r == 0:
            continue
        rules = []
        d = row.break_depth
        if d is not None and d <= min(_MAX_BREAK, n_stub - 2):
            rules.append((_style_for(style.hrule_widths[d]), d + 1))
        if 'total' in row.flags or 'subtotal' in row.flags:
            rules.append((_style_for(style.total_rule), 1))
        for style_name, start_col in rules:
            if style_name:
                hpath(style_name, body_start + r, start_col, ygap)
    bottom = _style_for(style.frame_rule)
    if bottom:
        w(f'\\path[draw, {bottom}] '
          f'([yshift={-ygap}em]{name}-1-1.south west |- {name}.south) -- '
          f'([yshift={-ygap}em]{name}-1-{ncols + 1}.south east |- '
          f'{name}.south);')

    # ---- vertical rules
    stub = _style_for(style.stub_rule)
    if stub and n_stub > 0:
        w(f'\\path[draw, {stub}] '
          f'([xshift={gap}em]{name}-1-{n_stub}.south east) -- '
          f'([xshift={gap}em]{name}-1-{n_stub}.south east |- {name}.south);')
    for j, column in enumerate(doc.columns):
        d = column.break_depth
        if column.role != 'data' or d is None or d > _MAX_VBREAK:
            continue
        vstyle = _style_for(style.vrule_widths[d])
        if not vstyle:
            continue
        # start under the parent header level that changes at this boundary
        top_row = min(2 + d, 1 + n_head) if n_head else 1
        anchor = f'{name}-{top_row}-{j + 1}.south west'
        w(f'\\path[draw, {vstyle}] ([xshift={-gap}em, yshift={-ygap}em]'
          f'{anchor}) -- ([xshift={-gap}em]{anchor} |- {name}.south);')

    if style.tikz_post_process:
        w(style.tikz_post_process)
    w('\\end{tikzpicture}')
    for note in doc.notes:
        w(f'\\par{{\\footnotesize {_escape(note)}}}')
    w(f'\\end{{{style.tikz_container_env}}}')
    return '\n'.join(out) + '\n'


