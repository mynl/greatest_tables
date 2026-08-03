"""Column-width allocation under a total-width budget.

A port of the csv-grid solver the JS walker also carries (``solveWidths`` in
``js/src/gt-render.js``, itself copied from csv-grid). The allocation math is
identical; what differs is entirely the caller's business:

- csv-grid narrows a column by **truncating** cells, so a column's floor is a
  minimum readable width and narrowing destroys content;
- a typeset table narrows a column by **wrapping** it, so the floor is the
  widest unbreakable token — TeX will not hyphenate inside a word — and
  narrowing costs height, not content.

Same solver, different floors. This module takes floors as given and never
asks which world it is in.

Units are plain integers and the module does not care what they mean:
milli-ems for TikZ, characters for a text renderer. Integers in, integers
out, so an allocation is identical on every interpreter — the same
discipline, and the same reason, as ``render/textlength.py``.

The budget is **text width only**. Column separations, padding and rules are
the caller's geometry: subtract them before calling, add them back after.

Two modes:

``equal-risk`` (default)
    Find the one quantile *q* that every column is measured at, so each takes
    the width its *q*-th percentile cell needs. Every column then carries the
    same probability of a cell overflowing its width — nothing is singled out
    and made to look mangled. Monotone in *q*, so a bisection finds it.

``coverage``
    Maximize the number of cells that fit outright, by spending the budget
    where it buys the most cells per unit width (a water-fill along each
    column's concave envelope). Equalizes marginal cost rather than
    probability: a column with a fat tail is left short so several tight
    columns can complete.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

__all__ = ['Allocation', 'Mode', 'solve_widths']

Mode = Literal['equal-risk', 'coverage']
Status = Literal['natural', 'solved', 'over']


@dataclass(frozen=True)
class Allocation:
    """Solved column widths and how the budget worked out.

    ``status`` is ``'natural'`` when nothing had to be narrowed,
    ``'solved'`` when narrowing brought the table inside the budget, and
    ``'over'`` when the floors alone exceed it — no allocation can help and
    the caller must scale, rotate, or accept the overflow.
    """

    widths: tuple[int, ...]
    status: Status

    @property
    def total(self) -> int:
        """Total text width; add the caller's separations for the real one."""
        return sum(self.widths)


def solve_widths(samples: Sequence[Sequence[int]], floors: Sequence[int],
                 budget: int, mode: Mode = 'equal-risk') -> Allocation:
    """Allocate ``budget`` across columns.

    Parameters
    ----------
    samples
        Per column, the width of every cell in it, in any order. A column
        with no samples is held at its floor.
    floors
        Per column, the width below which it must not be narrowed. A column
        that must not be narrowed *at all* passes its natural width here, and
        then simply rides through the allocation as a constant.
    budget
        Total text width available.
    mode
        ``'equal-risk'`` or ``'coverage'``; see the module docstring.

    Returns
    -------
    Allocation
        Widths in column order, and the status of the fit.
    """
    if len(samples) != len(floors):
        raise ValueError(f'{len(samples)} sample sets against '
                         f'{len(floors)} floors')
    if not floors:
        return Allocation((), 'natural')
    ordered = [sorted(s) for s in samples]
    natural = [max(f, s[-1] if s else 0) for s, f in zip(ordered, floors)]
    if sum(natural) <= budget:
        return Allocation(tuple(natural), 'natural')
    if sum(floors) >= budget:
        # nothing to negotiate: hand back the floors, which is the narrowest
        # honest answer and so the best base for a scale factor
        return Allocation(tuple(floors), 'over')
    solver = _coverage_widths if mode == 'coverage' else _equal_risk_widths
    widths = solver(ordered, list(floors), budget)
    return Allocation(tuple(widths),
                      'solved' if sum(widths) <= budget else 'over')


# --------------------------------------------------------------- equal risk
# The two solvers below are line-for-line ports of csv-grid's, including
# their own early returns, so they can be compared against the JS directly
# (tests/test_widths.py). They assume each sample list is already sorted.

def _equal_risk_widths(samples: list[list[int]], floors: list[int],
                       budget: int) -> list[int]:
    """Widths at the largest shared quantile whose total fits the budget."""
    def pct(s: list[int], q: float) -> int:
        return s[int(q * (len(s) - 1))] if s else 0

    def widths_at(q: float) -> list[int]:
        return [max(f, pct(s, q)) for s, f in zip(samples, floors)]

    if sum(widths_at(1)) <= budget:
        return widths_at(1)
    if sum(widths_at(0)) >= budget:
        return widths_at(0)
    # f(q) is monotone; bisect for the largest q that still fits. q walks
    # exact binary fractions, so the chosen sample index is reproducible.
    lo, hi = 0.0, 1.0
    for _ in range(32):
        mid = (lo + hi) / 2
        if sum(widths_at(mid)) <= budget:
            lo = mid
        else:
            hi = mid
    return widths_at(lo)


# ----------------------------------------------------------------- coverage

def _coverage_widths(samples: list[list[int]], floors: list[int],
                     budget: int) -> list[int]:
    """Widths that fit the most cells outright, buying cheapest cells first."""
    natural = [max(f, s[-1] if s else 0) for s, f in zip(samples, floors)]
    if sum(natural) <= budget:
        return natural
    if sum(floors) >= budget:
        return list(floors)

    widths = list(floors)
    remaining = budget - sum(floors)
    segments: list[tuple[float, int, int]] = []   # (slope, column, width step)
    for j, (s, floor) in enumerate(zip(samples, floors)):
        envelope = _concave_envelope(s, floor)
        for (w0, c0), (w1, c1) in zip(envelope, envelope[1:]):
            dw, dc = w1 - w0, c1 - c0
            if dw > 0 and dc > 0:
                segments.append((dc / dw, j, dw))
    # best cells-per-unit-width first; ties by column for a stable result
    segments.sort(key=lambda seg: (-seg[0], seg[1]))
    for _slope, j, step in segments:
        if remaining <= 0:
            break
        buy = min(step, remaining)      # a partial buy is fine, width is dense
        widths[j] += buy
        remaining -= buy
    return widths


def _concave_envelope(samples: list[int], floor: int) -> list[tuple[int, int]]:
    """Upper concave hull of (width, cells that fit at that width).

    Diminishing returns made explicit: each hull segment is a price per cell,
    and the prices decrease along it, which is what lets ``_coverage_widths``
    buy greedily and still land on the optimum.
    """
    n = len(samples)
    i = 0
    while i < n and samples[i] <= floor:     # cells the floor already covers
        i += 1
    points = [(floor, i)]
    while i < n:                             # one vertex per distinct width
        w = samples[i]
        while i < n and samples[i] == w:
            i += 1
        points.append((w, i))

    hull: list[tuple[int, int]] = []
    for point in points:
        while len(hull) >= 2:
            (aw, ac), (bw, bc) = hull[-2], hull[-1]
            pw, pc = point
            # drop b unless it is a strict concave vertex
            cross = (bw - aw) * (pc - ac) - (bc - ac) * (pw - aw)
            if cross >= 0:
                hull.pop()
            else:
                break
        hull.append(point)
    return hull
