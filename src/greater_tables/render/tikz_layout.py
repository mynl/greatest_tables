"""Shared TikZ layout: the grid, the column geometry, the width solve.

Both TikZ emitters — the ``matrix of nodes`` renderer in :mod:`.tikz` and the
one-node ``tabular`` renderer in :mod:`.tikz_tabular` — need the same answers
before they can emit anything: which cell text goes where, how wide each
column is, which cells are spanned, and what scale the table sets at. Only the
*emission* differs, so all of that lives here and neither emitter repeats it.

The one thing that genuinely differs is how a table's total width decomposes
into the part the width solver may spend and the part it cannot — a matrix
pays for its column separations outside the scaled node, a single node scales
everything inside it. :class:`Geometry` names that difference and the two
module constants supply it.

Widths are milli-ems everywhere below and divided only at emit time, so the
arithmetic is exact on every interpreter (see textlength's module docstring).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..ir import Cell, HeadCell, Row, TableDoc
from ..mathspans import segments
from ..spec import HouseStyle
from .textlength import display_milli, math_milli, token_milli
from .widths import solve_widths

__all__ = ['W2TIKZ', 'Geometry', 'Layout', 'MATRIX_GEOMETRY',
           'TABULAR_GEOMETRY', 'layout', 'style_for', 'tex_escape']

logger = logging.getLogger(__name__)

# greater_tables' float-weight → TikZ line-style scale (0 = do not draw)
W2TIKZ = {0: None, 0.25: 'ultra thin', 0.5: 'very thin', 0.75: 'thin',
          1: 'semithick', 1.5: 'thick', 2: 'very thick', 3: 'ultra thick'}

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

# What a *matrix* table measures beyond its columns and its scaled node:
#   width(scale) = scale * (sum(widths) + 2*csep) + ncols*csep + overhang
# The 2*csep is column 1's inner xsep — a node option, so it scales; the matrix
# column separations do not. Checked across every fixture against compiled page
# widths: the residual is +0.68em on average, spread 0.56 to 0.72, flat in both
# column count and table width, which is the rules overhanging the matrix
# bounding box. Taking the top of that range keeps the estimate conservative.
# The one-node emitter has no such residual — see TABULAR_GEOMETRY.
_RULE_OVERHANG = 700

# Coarse on purpose: two tables in one document landing on the same step look
# deliberate, where 0.87 and 0.91 look like a mistake.
_SCALE_STEPS = (1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6)

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


def style_for(weight: float) -> str | None:
    """TikZ line-style name for a house-style rule weight."""
    return W2TIKZ.get(weight, 'very thin')


def _escape_run(run: str) -> str:
    return _TEX_RE.sub(lambda m: _TEX_SPECIALS[m.group(0)], run)


def tex_escape(text: str, math: bool = True) -> str:
    """TeX-escape prose; with ``math`` on, ``$...$`` spans re-emit as math.

    ``math=False`` (a ``TableDoc.math='off'`` document, or html-flag text)
    escapes wholesale — every ``$`` becomes ``\\$``.
    """
    if not math or '$' not in text:
        return _escape_run(text)
    return ''.join(f'${run}$' if is_math else _escape_run(run)
                   for is_math, run in segments(text))


def cell_tex(cell: Cell | HeadCell, row_flags: tuple = (),
             math: bool = True) -> str:
    """TeX for one cell: math re-wrapped, html stripped, flags styled."""
    if cell.math:
        tex = f'${cell.text}$'
    else:
        if cell.html:
            # user markup: strip tags, never segment — its $s are literal
            text, math = _TAG_RE.sub('', cell.text), False
        else:
            text = cell.text
        tex = tex_escape(text, math).replace(chr(0xa0), '~')
    flags = set(cell.flags) | set(row_flags)
    if flags & {'total', 'subtotal', 'emphasis'}:
        tex = f'\\bfseries {tex}'
    if 'muted' in flags:
        tex = f'\\textcolor{{gray}}{{{tex}}}'
    return tex


def _measured(cell: Cell | HeadCell) -> str:
    """The text whose width the renderer must reserve room for."""
    return _TAG_RE.sub('', cell.text) if cell.html else cell.text


def _display_milli(cell: Cell | HeadCell, math: bool = True) -> int:
    """Milli-em width of a cell's content set on one line."""
    if cell.math:
        return math_milli(cell.text)
    return display_milli(_measured(cell), math=math and not cell.html)


def _token_milli(cell: Cell | HeadCell, math: bool = True) -> int:
    """Milli-em width of a cell's widest unbreakable token."""
    if cell.math:
        return math_milli(cell.text)
    return token_milli(_measured(cell), math=math and not cell.html)


def _bold(milli: int) -> int:
    """Bold text sets wider than the roman glyph table reports."""
    return milli * _BOLD_PERCENT // 100


# ------------------------------------------------------------------ geometry

@dataclass(frozen=True)
class Geometry:
    """How an emitter's table width splits into scaled and unscaled parts.

    ``inner`` is the furniture that lives *inside* whatever the scale applies
    to and so shrinks with it; ``unscaled`` is what sits outside and does not.
    Both take ``(ncols, csep_milli)`` and return milli-ems.
    """

    inner: Callable[[int, int], int]
    unscaled: Callable[[int, int], int]

    def table_width(self, widths: Sequence[int], scale: float, ncols: int,
                    csep_milli: int) -> int:
        """Emitted table width in milli-ems."""
        return (round(scale * (sum(widths) + self.inner(ncols, csep_milli)))
                + self.unscaled(ncols, csep_milli))


# A matrix scales its node contents and column 1's inner xsep; the matrix
# column separations and the rules' overhang sit outside the scale.
MATRIX_GEOMETRY = Geometry(
    inner=lambda ncols, csep: 2 * csep,
    unscaled=lambda ncols, csep: ncols * csep + _RULE_OVERHANG)

# One node holds the whole tabular, so every separation scales with it and
# nothing overhangs: the frame rules are the tabular's own booktabs rules and
# the vertical rules are interior. Padding is csep at each outer edge plus
# csep between adjacent columns — except column 1, which carries csep on both
# sides and so contributes 2*csep before column 2 (hence ncols + 2, not
# ncols + 1). A single column has both outer pads and no gap.
TABULAR_GEOMETRY = Geometry(
    inner=lambda ncols, csep: (ncols + 2) * csep if ncols >= 2 else 2 * csep,
    unscaled=lambda ncols, csep: 0)


# ------------------------------------------------------------- width solving

def _shrink(widths: list[int], floors: list[int], budget: int) -> list[int]:
    """Take ``sum(widths) - budget`` back, in proportion to each column's
    slack above its floor. Integer throughout; the rounding remainder goes to
    the roomiest columns, at most one unit each."""
    slack = [w - f for w, f in zip(widths, floors)]
    excess, total = sum(widths) - budget, sum(slack)
    if excess <= 0 or total <= 0:
        return list(widths)
    if excess >= total:
        return list(floors)
    out = list(widths)
    taken = 0
    for j, s in enumerate(slack):
        take = excess * s // total
        out[j] -= take
        taken += take
    for j in sorted(range(len(out)), key=lambda j: -slack[j]):
        if taken >= excess:
            break
        if out[j] > floors[j]:
            out[j] -= 1
            taken += 1
    return out


def _grow(widths: list[int], naturals: list[int], budget: int) -> list[int]:
    """Spend what the quantile pass left over, in proportion to how far each
    column still is from its natural width. Equal risk is discrete — it lands
    on whichever quantile happens to fit — so it routinely leaves room unused,
    and unused room is just extra wrapping."""
    room = [n - w for w, n in zip(widths, naturals)]
    spare, total = budget - sum(widths), sum(room)
    if spare <= 0 or total <= 0:
        return list(widths)
    if spare >= total:
        return list(naturals)
    out = list(widths)
    given = 0
    for j, r in enumerate(room):
        add = spare * r // total
        out[j] += add
        given += add
    for j in sorted(range(len(out)), key=lambda j: -room[j]):
        if given >= spare:
            break
        if out[j] < naturals[j]:
            out[j] += 1
            given += 1
    return out


def _fit_budget(style: HouseStyle, naturals: list[int], floors: list[int],
                samples: list[list[int]], prose_cap: int, csep_milli: int,
                geom: Geometry) -> tuple[list[int], float]:
    """Narrow prose columns to meet ``max_table_width_em``; scale if it can't.

    Returns the column widths and the scale to emit. The budget splits into
    a part the solver can spend (column text plus the furniture that scales
    with it) and a part it cannot — see :class:`Geometry`.
    """
    ncols = len(naturals)
    budget = round(style.max_table_width_em * _EM)
    unscaled = geom.unscaled(ncols, csep_milli)
    inner = geom.inner(ncols, csep_milli)
    # samples carry the same cap and pad the naturals do, so the solver's
    # idea of a column's natural width matches the one computed above
    text_budget = budget - unscaled - inner
    capped = [[min(x + _WIDTH_PAD, prose_cap) for x in s] for s in samples]
    widths = list(solve_widths(capped, floors, text_budget).widths)
    if sum(widths) > text_budget:
        # Equal risk has nothing left to say about a column whose cells *all*
        # overrun the prose cap: every quantile lands on the cap, so the
        # bisection cannot move it. Such a column is wrapping whatever we do
        # and narrowing it only costs height, so take the remaining slack
        # proportionally — the widest prose gives up the most.
        widths = _shrink(widths, floors, text_budget)
    elif sum(widths) < text_budget:
        widths = _grow(widths, naturals, text_budget)
    if sum(widths) <= text_budget:
        return widths, style.tikz_scale

    # nothing left to narrow: shrink the scaled part until the whole fits
    scaled = sum(widths) + inner
    needed = (budget - unscaled) / scaled if scaled > 0 else 1.0
    step = next((s for s in _SCALE_STEPS if s <= needed), _SCALE_STEPS[-1])
    scale = min(style.tikz_scale, step)
    full = geom.table_width(widths, 1.0, ncols, csep_milli) / _EM
    total = geom.table_width(widths, scale, ncols, csep_milli) / _EM
    if needed < _SCALE_STEPS[-1]:
        logger.warning(
            'table wants %.1fem of columns that cannot be narrowed against a '
            'max_table_width_em of %.1f; that needs scale %.2f and the ladder '
            'stops at %.2f, so it overruns at %.1fem. Shorten the headings, '
            'drop a column, or set tikz_container_env="sidewaysfigure".',
            full, style.max_table_width_em, needed, _SCALE_STEPS[-1], total)
    else:
        logger.warning(
            'table does not fit max_table_width_em=%.1f at full size — its '
            'columns that cannot be narrowed want %.1fem — so tikz_scale '
            'drops to %.2f for a final %.1fem.',
            style.max_table_width_em, full, scale, total)
    return widths, scale


# ----------------------------------------------------------------- the layout

@dataclass(frozen=True)
class Layout:
    """Everything both emitters need, resolved once.

    ``grid`` carries the matrix's zero-height spacer row at index 0, so a grid
    index maps to a TikZ matrix row as ``index + 1`` and the ``overlays`` /
    ``body_start`` row numbers below are TikZ rows. A ``tabular`` emitter skips
    ``grid[0]`` and subtracts one to get back to its own row numbering.
    """

    name: str                                   # tikz node/matrix name
    ncols: int
    n_head: int                                 # header levels
    n_stub: int                                 # stub (index) columns
    grid: list[list[str]]                       # spacer row, head rows, body
    overlays: list[tuple[int, int, int, str]]   # (tikz row, c0, span, tex)
    spanners: list[tuple[int, int, int]]        # (level, c0, span)
    widths: list[int]                           # milli-em column text widths
    aligns: list[str]                           # 'l' | 'r' | 'c' per column
    scale: float
    body_start: int                             # tikz row of body row 0
    body_rows: list[Row]                        # body + foot, in order
    n_body: int                                 # where foot starts within them
    csep_milli: int


def layout(doc: TableDoc, style: HouseStyle, geom: Geometry) -> Layout:
    """Resolve a document into cell text and column geometry.

    Parameters
    ----------
    doc
        The table document.
    style
        House style; supplies separations, the scale ladder and the budget.
    geom
        The emitter's width decomposition — see :class:`Geometry`.
    """
    ncols = len(doc.columns)
    name = f'gt{doc.hash or "x"}'
    n_head = len(doc.head)
    n_stub = doc.n_stub_levels
    csep = style.tikz_column_sep
    math_on = doc.math != 'off'

    # ---- lay out cells into an ncols-wide text matrix + overlay spans;
    # measure display widths at placement (true visual column known here)
    # matrix rows: 1 spacer + n_head + body(+foot); tikz indices are 1-based
    grid: list[list[str]] = [[''] * ncols]           # spacer row
    overlays: list[tuple[int, int, int, str]] = []   # (tikz row, c0, span, tex)
    spanners: list[tuple[int, int, int]] = []        # (level, c0, span)
    spans: list[tuple[int, int, int]] = []           # (c0, span, milli needed)
    wmax = [_MIN_COL] * ncols                        # body width, one line
    hmax = [0] * ncols                               # header floor
    tokmax = [0] * ncols                             # widest body word
    samples: list[list[int]] = [[] for _ in range(ncols)]   # every cell width
    for level, hrow in enumerate(doc.head):
        cells = [''] * ncols
        leaf = level == n_head - 1
        col = 0
        for hc in hrow:
            tex = cell_tex(hc, math=math_on)
            if not leaf and hc.text:
                spanners.append((level, col, hc.colspan))
            if hc.colspan == 1:
                cells[col] = tex + (r'\I' if hc.text else '')
                # a header cell has a text width and wraps, so a long heading
                # only floors its column at its widest word — it does not drag
                # a column of six-em numbers out to the width of its title
                hmax[col] = max(hmax[col], _bold(_token_milli(hc, math_on)))
            elif hc.text:
                overlays.append((2 + level, col, hc.colspan, tex))
                # an overlaid label carries no text width: it cannot wrap, so
                # it constrains the whole group it spans
                spans.append((col, hc.colspan,
                              _bold(_display_milli(hc, math_on))))
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
            tex = cell_tex(cell, row.flags, math=math_on)
            if cell.colspan == 1:
                cells[col] = tex
                width = _display_milli(cell, math_on)
                samples[col].append(width)
                wmax[col] = max(wmax[col], width)
                tokmax[col] = max(tokmax[col], _token_milli(cell, math_on))
            elif cell.text:
                overlays.append((body_start + r, col, cell.colspan, tex))
                spans.append((col, cell.colspan, _display_milli(cell, math_on)))
            for cc in range(col, min(ncols, col + cell.colspan)):
                if cell.rowspan > 1:
                    pending[cc] = cell.rowspan
            col += cell.colspan
        for cc in range(ncols):
            if pending[cc] > 0:
                pending[cc] -= 1
        grid.append(cells)

    # ---- column geometry: milli-em text widths (TextLength) + source padding
    # the body sets the natural width (capped for prose columns); the header
    # only floors it, having been measured a word at a time above
    prose_cap = round(style.max_prose_width_em * _EM)
    csep_milli = round(csep * _EM)

    def sized(measure: int, header: int) -> int:
        return max(measure + _WIDTH_PAD, header + _WIDTH_PAD, _MIN_COL)

    naturals = [sized(w, h) for w, h in zip(wmax, hmax)]
    # how narrow a column may go: prose down to its widest single word, since
    # TeX will not hyphenate inside one; anything unbreakable, not at all
    floors = [sized(t, h) if c.wrap else n
              for t, h, n, c in zip(tokmax, hmax, naturals, doc.columns)]
    # the prose cap is a ceiling, not a target — but a single word beats it,
    # because the alternative is an overfull box
    naturals = [max(min(n, prose_cap), f) if c.wrap else n
                for n, f, c in zip(naturals, floors, doc.columns)]

    def apply_spans(widths: list[int]) -> None:
        """A spanning label carries no text width and so cannot wrap: widen
        the last column it covers when the span — including the separations
        it crosses — cannot hold it."""
        for c0, span, need in spans:
            have = sum(widths[c0:c0 + span]) + (span - 1) * csep_milli
            if need + _WIDTH_PAD > have:
                widths[c0 + span - 1] += need + _WIDTH_PAD - have

    apply_spans(naturals)
    apply_spans(floors)
    if style.max_table_width_em is None:
        widths, scale = naturals, style.tikz_scale
    else:
        widths, scale = _fit_budget(style, naturals, floors, samples,
                                    prose_cap, csep_milli, geom)
        apply_spans(widths)

    return Layout(
        name=name, ncols=ncols, n_head=n_head, n_stub=n_stub, grid=grid,
        overlays=overlays, spanners=spanners, widths=widths,
        aligns=[c.align for c in doc.columns], scale=scale,
        body_start=body_start, body_rows=body_rows, n_body=len(doc.body),
        csep_milli=csep_milli)
