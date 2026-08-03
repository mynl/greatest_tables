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
from .policy import rule_slot, vrule_slot
from .textlength import display_milli, token_milli

__all__ = ['TIKZ_PREAMBLE', 'W2TIKZ', 'render_tikz']

# greater_tables' float-weight → TikZ line-style scale (0 = do not draw)
W2TIKZ = {0: None, 0.25: 'ultra thin', 0.5: 'very thin', 0.75: 'thin',
          1: 'semithick', 1.5: 'thick', 2: 'very thick', 3: 'ultra thick'}

TIKZ_PREAMBLE = r'\newcommand{\I}{\vphantom{lp}}'

# widths are milli-ems everywhere below and divided only at emit time, so the
# arithmetic is exact on every interpreter (see textlength's module docstring)
_EM = 1000
_MIN_COL = 2000                 # 2em floor on any column

# Slack added to every measured requirement. The estimate is exact against
# newtx, but *exact* is a knife edge: 'Sub 1' measures 2.306em, so a 2.31em
# column clears it by 0.17% — Etcher renders it on one line and the same table
# in a Quarto document, whose preamble brings microtype and friends, breaks it.
# Sizing to the estimate with no margin makes line breaking depend on the host
# document. 0.1em is invisible next to a column and costs under 1em across a
# typical table.
_WIDTH_PAD = 100

# header cells render bold (stubs bold-italic) and the glyph table is roman,
# so header estimates carry a widening factor (GT's bold_adjustment). Measured
# over the fixture corpus in newtx, bold/roman is 1.000 at the median and
# 1.130 at p99; 118 covers the tail of real words without visibly padding the
# common case, where bold and roman digits are the same width anyway.
_BOLD_PERCENT = 118

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


def _measured(cell: Cell | HeadCell) -> str:
    """The text whose width the renderer must reserve room for."""
    return f'${cell.text}$' if cell.math else _TAG_RE.sub('', cell.text) \
        if cell.html else cell.text


def _display_milli(cell: Cell | HeadCell) -> int:
    """Milli-em width of a cell's content set on one line."""
    return display_milli(_measured(cell))


def _token_milli(cell: Cell | HeadCell) -> int:
    """Milli-em width of a cell's widest unbreakable token."""
    return token_milli(_measured(cell))


def _bold(milli: int) -> int:
    """Bold text sets wider than the roman glyph table reports."""
    return milli * _BOLD_PERCENT // 100


def render_tikz(doc: TableDoc, style: HouseStyle | None = None) -> str:
    """Render a table document to a TikZ table (LaTeX source)."""
    style = style or HouseStyle()
    ncols = len(doc.columns)
    if ncols == 0:
        return '% greater_tables: empty table\n'
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
    spanners: list[tuple[int, int, int]] = []        # (level, c0, span)
    spans: list[tuple[int, int, int]] = []           # (c0, span, milli needed)
    wmax = [_MIN_COL] * ncols                        # body width, one line
    hmax = [0] * ncols                               # header floor
    for level, hrow in enumerate(doc.head):
        cells = [''] * ncols
        leaf = level == n_head - 1
        col = 0
        for hc in hrow:
            tex = _cell_tex(hc)
            if not leaf and hc.text:
                spanners.append((level, col, hc.colspan))
            if hc.colspan == 1:
                cells[col] = tex + (r'\I' if hc.text else '')
                # a header cell has a text width and wraps, so a long heading
                # only floors its column at its widest word — it does not drag
                # a column of six-em numbers out to the width of its title
                hmax[col] = max(hmax[col], _bold(_token_milli(hc)))
            elif hc.text:
                overlays.append((2 + level, col, hc.colspan, tex))
                # an overlaid label carries no text width: it cannot wrap, so
                # it constrains the whole group it spans
                spans.append((col, hc.colspan, _bold(_display_milli(hc))))
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
                wmax[col] = max(wmax[col], _display_milli(cell))
            elif cell.text:
                overlays.append((body_start + r, col, cell.colspan, tex))
                spans.append((col, cell.colspan, _display_milli(cell)))
            for cc in range(col, min(ncols, col + cell.colspan)):
                if cell.rowspan > 1:
                    pending[cc] = cell.rowspan
            col += cell.colspan
        for cc in range(ncols):
            if pending[cc] > 0:
                pending[cc] -= 1
        grid.append(cells)
    n_rows = len(grid)

    # ---- column geometry: milli-em text widths (TextLength) + source padding
    # the body sets the natural width (capped for prose columns); the header
    # only floors it, having been measured a word at a time above
    prose_cap = round(style.tikz_prose_max_em * _EM)
    widths = [max(min(w + _WIDTH_PAD, prose_cap) if c.wrap else w + _WIDTH_PAD,
                  h + _WIDTH_PAD, _MIN_COL)
              for w, h, c in zip(wmax, hmax, doc.columns)]
    # a spanning label cannot wrap: widen the last column it covers if the
    # span — including the column separations it crosses — cannot hold it
    csep_milli = round(csep * _EM)
    for c0, span, need in spans:
        have = sum(widths[c0:c0 + span]) + (span - 1) * csep_milli
        if need + _WIDTH_PAD > have:
            widths[c0 + span - 1] += need + _WIDTH_PAD - have
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
    n_body = len(doc.body)
    for r, row in enumerate(body_rows):
        if r == 0 or r == n_body:          # first row of body / of foot
            continue
        rules = []
        d = row.break_depth
        slot = rule_slot(d, n_stub, style.max_rule_depth)
        if slot is not None:
            # weight from the slot, start column from the raw depth
            rules.append((_style_for(style.hrule_widths[slot]), d + 1))
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

    # ---- spanner rules: full-width underline per group label, extended by
    # the half-gap each side so adjacent groups meet at the group vertical
    sp = _style_for(style.spanner_rule)
    if sp:
        for level, c0, span in spanners:
            row = 2 + level
            a = f'{name}-{row}-{c0 + 1}.south west'
            b = f'{name}-{row}-{c0 + span}.south east'
            w(f'\\path[draw, {sp}] ([xshift={-gap}em, yshift={-ygap}em]{a}) '
              f'-- ([xshift={gap}em, yshift={-ygap}em]{b});')

    # ---- vertical rules
    stub = _style_for(style.stub_rule)
    if stub and n_stub > 0:
        w(f'\\path[draw, {stub}] '
          f'([xshift={gap}em]{name}-1-{n_stub}.south east) -- '
          f'([xshift={gap}em]{name}-1-{n_stub}.south east |- {name}.south);')
    for j, column in enumerate(doc.columns):
        slot = (vrule_slot(column.break_depth, style.max_vrule_depth)
                if column.role == 'data' else None)
        if slot is None:
            continue
        vstyle = _style_for(style.vrule_widths[slot])
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
        w(f'\\par{{\\footnotesize {_escape(note)}}}')
    w(f'\\end{{{style.tikz_container_env}}}')
    return '\n'.join(out) + '\n'


