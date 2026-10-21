r"""One-node TikZ renderer: a real ``tabular`` inside a single node.

The ``matrix of nodes`` emitter in :mod:`.tikz` costs about 290 ms of TeX per
table, and the cost is materializing one pgf node per cell — not the matrix
library, not the table package. GT does not need per-cell nodes: they exist
only so rules can anchor to cell corners, and GT computes every column width
itself. One node with known geometry serves the same purpose about 30x faster.

The division of labor that makes it work:

- **x is ours, y is TeX's.** Column widths are known here, so every *vertical*
  rule is an ``xshift`` off the node's own corner — no measurement needed.
  Row heights are *not* known (cells wrap), so every *horizontal* rule is a
  booktabs rule inside the tabular, where TeX already knows where the rows are.
- **Bottom-aligned headers.** ``p{}`` is top aligned, so each header cell
  restates its column as ``b{}`` through ``\multicolumn{1}{...}``. Verbose in
  the source, free in TeX, and non-negotiable in the output.
- **Header alignment is centered** (stub columns flush left) regardless of the
  column's own alignment. That is not an oversight: in the matrix emitter the
  ``row N`` style beats the ``column N`` style, so headers have always
  rendered centered over right-aligned numbers, and this engine reproduces it.

The emitted body is a literal ``tabular``, which is also the point: the
``.tex`` goes to typesetters who do not use TikZ, and conversion is "delete
the wrapper" rather than five transformations of a ``\&`` matrix.
"""

from __future__ import annotations

import logging

from ..ir import Cell, TableDoc
from ..spec import HouseStyle
from .policy import rule_slot, vrule_slot
from .tikz_layout import (
    TABULAR_GEOMETRY, Layout, cell_tex, layout, placement, style_for,
    tex_escape,
)

__all__ = ['W2RULE', 'render_tikz_tabular']

logger = logging.getLogger(__name__)

# House float weight → booktabs rule width, matching pgf's line-width ladder
# exactly, so the two engines draw the same weight for the same house style.
# (pgf: ultra thin .1, very thin .2, thin .4, semithick .6, thick .8,
# very thick 1.2, ultra thick 1.6 — see W2TIKZ for the name mapping.)
W2RULE = {0: None, 0.25: '0.1pt', 0.5: '0.2pt', 0.75: '0.4pt', 1: '0.6pt',
          1.5: '0.8pt', 2: '1.2pt', 3: '1.6pt'}

_EM = 1000

_ALIGN = {'l': r'>{\raggedright\arraybackslash}',
          'r': r'>{\raggedleft\arraybackslash}',
          'c': r'>{\centering\arraybackslash}'}

# ---------------------------------------------------------- vertical metrics
#
# Four numbers reproduce the matrix's vertical rhythm, calibrated against
# compiled box heights across the fixture corpus (dev/tools/compare_engines.py
# reports the residual). They were found in this order, biggest effect first:
#
# 1. booktabs opens space around every rule where the matrix draws into the
#    row gap and adds none, so height tracked *rule count*: a deeply ruled
#    table ran 8% long. Zeroing \aboverulesep, \belowrulesep and \cmidrulesep
#    removes the dependence entirely — see the \setlength block in _emit.
# 2. header rows: the matrix gives them `minimum height=1.3em` plus inner
#    ysep, which no tabular strut reproduces, so header cells carry their own
#    (_HEAD_STRUT / _HEAD_DEPTH, the depth matching the matrix's inner ysep).
# 3. the frame: the matrix's bounding box runs out to rules half a row
#    separation beyond the cells (_FRAME_PAD).
# 4. the row floor: a tabular row is at least one array strut tall where a
#    matrix row is only as tall as its content, so _ARRAYSTRETCH trims the
#    strut. A floor, not a height — rows with taller content still grow.
#
# Result over 36 fixture and Fabricator tables: median +0.03%, p90 +1.35%.
# Six run over the 2% target and every one of them is a two- or three-row
# table where the absolute difference is under 5pt.

_ARRAYSTRETCH = 0.92
_HEAD_STRUT = 1.58
_HEAD_DEPTH = 0.20
_FRAME_PAD = 0.28
# 5. (7.1.1) under a heading the matrix leaves about 3pt to the rule below
#    and the tabular left 1.6pt, which read as cramped side by side. The gap
#    is added after every header row rather than to the header strut, whose
#    depth a heading that wraps does not reach. It makes a table's head about
#    1.6pt a row taller than the calibration above.
_HEAD_GAP = 0.15


def _macros() -> str:
    r"""The two macros a table carries with it.

    ``\I`` is the header strut the layout appends to every header cell; the
    matrix emitter relies on the host document defining it, which is a
    standing trap in Quarto PDF builds — undefined, it takes the enclosing
    node down with it. ``\gtheadstrut`` sets the header row height the matrix
    gets from ``minimum height``. Both are ``\providecommand``, so a document
    that already defines them wins and nothing is clobbered.
    """
    return (r'\providecommand{\I}{\vphantom{lp}}%' '\n'
            r'\providecommand{\gtheadstrut}{\rule['
            f'-{_HEAD_DEPTH:.2f}em]{{0pt}}{{{_HEAD_STRUT:.2f}em}}}}%')



def _rule_width(weight: float) -> str | None:
    """booktabs rule width for a house-style weight, or None for 'do not draw'."""
    return W2RULE.get(weight, '0.2pt') if style_for(weight) else None


def render_tikz_tabular(doc: TableDoc, style: HouseStyle | None = None) -> str:
    """Render a table document as one ``tabular`` inside one TikZ node."""
    style = style or HouseStyle()
    if len(doc.columns) == 0:
        return '% greater_tables: empty table\n'
    lay = layout(doc, style, TABULAR_GEOMETRY)
    return _emit(doc, style, lay)


def _emit(doc: TableDoc, style: HouseStyle, lay: Layout) -> str:
    ncols, n_head, n_stub = lay.ncols, lay.n_head, lay.n_stub
    aligns = lay.aligns
    csep, rsep = style.tikz_column_sep, style.tikz_row_sep
    gap = csep / 2                              # == \tabcolsep
    gap_milli = round(gap * _EM)
    csep_milli = lay.csep_milli
    # TeX only ever sees the two-decimal widths in the colspec, so every rule
    # offset must be computed from *those*, not from the solver's milli-ems —
    # otherwise the rules drift from the columns by up to half a step each
    widths = [10 * round(w / 10) for w in lay.widths]

    # ---- geometry, all of it derivable because every width is known here.
    # Column 1 carried inner xsep=csep on *both* sides in the matrix, so the
    # gap it opens before column 2 is 2*csep where every other gap is csep.
    def gap_after(j: int) -> int:
        """Milli-em space following 0-based column ``j``."""
        return 2 * csep_milli if j == 0 else csep_milli

    def xleft(col: int) -> int:
        """Milli-em x of 1-based ``col``'s text box, from the node's west."""
        x = csep_milli
        for j in range(col - 1):
            x += widths[j] + gap_after(j)
        return x

    def span_milli(c0: int, span: int) -> int:
        """Width a \\multicolumn must declare to cover ``span`` columns from
        0-based ``c0`` — the columns plus the gaps it swallows."""
        return (sum(widths[c0:c0 + span])
                + sum(gap_after(j) for j in range(c0, c0 + span - 1)))

    def em(milli: int) -> str:
        return f'{milli / _EM:.2f}em'

    def mc_preamble(c0: int, c1: int, inner: str) -> str:
        """A \\multicolumn preamble over 0-based columns ``c0..c1`` whose
        entry is exactly as wide as the body entries it replaces.

        A \\multicolumn drops the inter-column material of the columns it
        covers and adds a \\tabcolsep on each side unless an @{} says
        otherwise. Left bare, a header over column 2, which follows column
        1's 2*csep gap and so has no \\tabcolsep of its own, comes out a
        \\tabcolsep wider than the body: TeX widens the column to fit, and
        every column to its right moves off the x its vertical rule is drawn
        at. A header over column 1 comes out narrower and sits a \\tabcolsep
        left of its body.
        """
        if c0 == 0:
            left = f'@{{\\hspace{{{em(csep_milli)}}}}}'
        elif gap_after(c0 - 1) != csep_milli:
            left = '@{}'
        else:
            left = ''
        if c1 == ncols - 1:
            right = f'@{{\\hspace{{{em(csep_milli)}}}}}'
        elif gap_after(c1) != csep_milli:
            right = f'@{{\\hspace{{{em(gap_after(c1))}}}}}'
        else:
            right = ''
        return left + inner + right

    # ---- cells: the layout's grid, with spans folded back in as \multicolumn
    rows = [list(r) for r in lay.grid[1:]]      # drop the matrix spacer row
    for tikz_row, c0, span, tex in lay.overlays:
        i = tikz_row - 2                        # grid index → tabular row
        head = i < n_head
        # a header spanner is bold and bottom aligned like every other header
        # cell; a body colspan is centered on its span, as the matrix overlay
        # placed it, and sits with the rest of the body
        kind = 'b' if head else 'p'
        body = f'\\gtheadstrut \\bfseries {tex}' if head else tex
        pre = mc_preamble(c0, c0 + span - 1,
                          f'{_ALIGN["c"]}{kind}{{{em(span_milli(c0, span))}}}')
        rows[i][c0] = f'\\multicolumn{{{span}}}{{{pre}}}{{{body}}}'
        for j in range(c0 + 1, c0 + span):
            rows[i][j] = None                   # swallowed by the multicolumn

    # ---- header cells: b{} so they sit on the row's baseline, centered
    # (stubs flush left) because that is what the matrix's row style does
    for i in range(n_head):
        for j, text in enumerate(rows[i]):
            if not text or text.startswith('\\multicolumn'):
                continue
            font = '\\bfseries\\itshape ' if j < n_stub else '\\bfseries '
            al = _ALIGN['l'] if j < n_stub else _ALIGN['c']
            pre = mc_preamble(j, j, f'{al}b{{{em(widths[j])}}}')
            rows[i][j] = (f'\\multicolumn{{1}}{{{pre}}}'
                          f'{{\\gtheadstrut {font}{text}}}')

    # body cells are plain, so pad them into columns — the source is meant to
    # be liftable into someone else's document, and a ragged grid is not
    colw = [max((len(rows[i][j]) for i in range(n_head, len(rows))
                 if rows[i][j] and not rows[i][j].startswith('\\multicolumn')),
                default=0) for j in range(ncols)]
    pad = {'l': '<', 'r': '>', 'c': '^'}

    def row_tex(i: int) -> str:
        cells = [c for c in rows[i] if c is not None]
        if i < n_head:
            return ' & '.join(cells) + r' \\'
        keep = [j for j in range(ncols) if rows[i][j] is not None]
        return ' & '.join(
            rows[i][j] if (rows[i][j] or '').startswith('\\multicolumn')
            else f'{rows[i][j] or "":{pad[aligns[j]]}{colw[j]}s}'
            for j in keep).rstrip() + r' \\'

    # ---- horizontal rules, from booktabs: TeX knows where the rows are
    def hrule(width: str, start_col: int) -> str:
        """A rule across the table from ``start_col`` (1-based) to the right
        edge. Extended past the last column so it reaches the frame, which
        sits csep out where booktabs would stop at \\tabcolsep."""
        if start_col <= 1:
            return f'\\midrule[{width}]'
        return (f'\\cmidrule[{width}](r{{-{gap:.2f}em}})'
                f'{{{start_col}-{ncols}}}')

    out: list[str] = []
    w = out.append

    latex = placement(style)
    w(f'\\begin{{{style.tikz_container_env}}}{latex}')
    w('\\centering')
    if doc.caption is not None:
        cap = doc.caption if isinstance(doc.caption, Cell) else Cell(text=doc.caption)
        label = f'\\label{{{doc.label}}}' if doc.label else ''
        w(f'\\caption{{{cell_tex(cap, math=doc.math != "off")}}}{label}')
    w('\\begin{tikzpicture}[transform shape]')
    w(f'\\node[inner sep=0pt, scale={lay.scale}] ({lay.name}) {{%')
    # inside the node, so the picture is self-contained: lift the
    # tikzpicture on its own and it still carries its macros
    w(_macros())
    # \arraystretch sets the row *floor* (the array strut) and \extrarowheight
    # adds the separation on top — between them they reproduce the matrix's
    # `row sep` over content-sized rows. Neither touches \baselineskip, so
    # line spacing inside a wrapped cell is unaffected by either.
    w(f'\\setlength{{\\tabcolsep}}{{{gap:.2f}em}}%')
    w(f'\\renewcommand{{\\arraystretch}}{{{_ARRAYSTRETCH}}}%')
    w(f'\\setlength{{\\extrarowheight}}{{{rsep:.2f}em}}%')
    # booktabs opens space around every rule; the matrix draws its rules into
    # the row gap and adds none. Left alone, a table's height would depend on
    # how many break rules it happens to carry — 8% on a deeply ruled table.
    w('\\setlength{\\aboverulesep}{0pt}\\setlength{\\belowrulesep}{0pt}%')
    w('\\setlength{\\cmidrulesep}{0pt}%')
    w(f'\\setlength{{\\abovetopsep}}{{{_FRAME_PAD:.2f}em}}'
      f'\\setlength{{\\belowbottomsep}}{{{_FRAME_PAD:.2f}em}}%')
    # 2*\tabcolsep already opens csep between adjacent columns, so an explicit
    # @{} is needed only where that is wrong — after column 1 — and at the
    # outer edges, which must match column 1's inner xsep for the frame rules
    # to span the same width the matrix does
    parts = [f'@{{\\hspace{{{em(csep_milli)}}}}}']
    for j in range(ncols):
        if j > 0 and gap_after(j - 1) != csep_milli:
            parts.append(f'@{{\\hspace{{{em(gap_after(j - 1))}}}}}')
        parts.append(_ALIGN[aligns[j]] + f'p{{{em(widths[j])}}}')
    parts.append(f'@{{\\hspace{{{em(csep_milli)}}}}}')
    w(f'\\begin{{tabular}}{{{"".join(parts)}}}')

    top = _rule_width(style.frame_rule)
    if top:
        w(f'\\toprule[{top}]')
    head = _rule_width(style.head_rule)
    n_body = lay.n_body
    for i in range(len(rows)):
        # no head, no rule under it: it would double the top frame
        if i == n_head and n_head and head and lay.body_rows:
            w(f'\\midrule[{head}]')
        elif i > n_head:
            r = i - n_head
            if r != n_body:                     # first foot row: matrix skips
                row = lay.body_rows[r]
                # The matrix draws a break rule and a total rule at the *same*
                # y, so they land on top of each other and read as one rule of
                # the heavier weight across the wider extent. Consecutive
                # booktabs rules stack instead of overlapping, so merge them.
                weight, start = 0.0, ncols + 1
                slot = rule_slot(row.break_depth, n_stub, style.max_rule_depth)
                if slot is not None:
                    weight = max(weight, style.hrule_widths[slot])
                    start = min(start, row.break_depth + 1)
                if 'total' in row.flags or 'subtotal' in row.flags:
                    weight, start = max(weight, style.total_rule), 1
                width = _rule_width(weight) if weight else None
                if width:
                    w(hrule(width, start))
        w(row_tex(i))
        if i < n_head:
            # the room the matrix leaves between a heading and the rule under
            # it, which no header strut gives a heading that wraps
            w(f'\\addlinespace[{_HEAD_GAP:.2f}em]')
            # a group label's underline: plain \cmidrule spans exactly one
            # \tabcolsep each side, which is the ±gap the matrix draws. A
            # column after column 1's 2*csep gap has no \tabcolsep of its
            # own, so there the underline is extended to the stub rule.
            sp = _rule_width(style.spanner_rule)
            if sp:
                for level, c0, span in lay.spanners:
                    if level == i:
                        trim = (f'(l{{-{gap:.2f}em}})'
                                if c0 > 0 and gap_after(c0 - 1) != csep_milli
                                else '')
                        w(f'\\cmidrule[{sp}]{trim}{{{c0 + 1}-{c0 + span}}}')
    bottom = _rule_width(style.frame_rule)
    if bottom:
        w(f'\\bottomrule[{bottom}]')
    w('\\end{tabular}};')

    # ---- vertical rules: full height, at an x we already know exactly.
    # xshift is in picture coordinates while the node carries the scale, so
    # the offsets scale with it.
    def rule_pt(width: str | None) -> float:
        return float(width[:-2]) if width else 0.0

    # Header row pitch: the header strut's height over the array strut's
    # depth, which is 0.3 \baselineskip (about 1.2em) times \arraystretch,
    # and the space added under every heading. Spanner labels never wrap (the
    # layout widens their columns to fit), so every row above the leaf
    # headers is exactly one of these.
    head_row = (_HEAD_STRUT - _HEAD_DEPTH
                + max(_HEAD_DEPTH, 0.36 * _ARRAYSTRETCH) + _HEAD_GAP)
    spanner_rows = {level for level, _c0, _span in lay.spanners}

    def vrule(x_milli: int, line: str, rows_down: int = 0) -> None:
        """A vertical at ``x_milli``, from below header row ``rows_down - 1``
        (or from the top frame) to the bottom frame."""
        x = f'{lay.scale * x_milli / _EM:.3f}em'
        # inset by the frame padding, which is inside the node's bounding box
        # but outside the frame rules — without it the verticals overhang
        y = f'{lay.scale * _FRAME_PAD:.3f}em'
        if rows_down:
            # a vertical between groups that share a label at a higher level
            # starts under that label's underline, not through the label
            ems = _FRAME_PAD + rows_down * head_row
            pts = rule_pt(_rule_width(style.frame_rule)) + rule_pt(
                _rule_width(style.spanner_rule)) * sum(
                    1 for k in range(rows_down) if k in spanner_rows)
            factor = '' if lay.scale == 1 else f'{lay.scale:g}*'
            top = f'{{{factor}({ems:.3f}em+{pts:.2f}pt)}}'
        else:
            top = y
        w(f'\\draw[{line}] ([xshift={x}, yshift=-{top}]{lay.name}.north west) -- '
          f'([xshift={x}, yshift={y}]{lay.name}.south west);')

    stub = style_for(style.stub_rule)
    if stub and n_stub > 0:
        # the matrix anchors on the stub node's east, which for column 1
        # includes its inner xsep
        x = xleft(n_stub) + widths[n_stub - 1] + gap_milli
        if n_stub == 1:
            x += csep_milli
        vrule(x, stub)
    for j, column in enumerate(doc.columns):
        slot = (vrule_slot(column.break_depth, style.max_vrule_depth)
                if column.role == 'data' else None)
        if slot is None:
            continue
        line = style_for(style.vrule_widths[slot])
        if not line:
            continue
        # matching the HTML gt-vbreak border: full height through the body,
        # but in the head only from the level where the groups divide
        anchor = 0 if j == 0 else xleft(j + 1)
        depth = column.break_depth or 0
        vrule(anchor - gap_milli, line, min(depth, max(n_head - 1, 0)))

    if style.tikz_post_process:
        w(style.tikz_post_process)
    w('\\end{tikzpicture}')
    for note in doc.notes:
        w(f'\\par{{\\footnotesize {tex_escape(note, math=doc.math != "off")}}}')
    w(f'\\end{{{style.tikz_container_env}}}')
    return '\n'.join(out) + '\n'
