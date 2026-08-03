"""Width allocator: behavior, and parity with the JS copy of the same solver."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from greater_tables.render.widths import (
    _coverage_widths, _equal_risk_widths, solve_widths,
)

ROOT = Path(__file__).parent.parent
NODE = shutil.which('node')

# (samples per column, floors, budget) — the shapes that exercise the solver:
# room to spare, a genuine squeeze, floors that cannot fit, ragged tails,
# a column pinned at its natural width (floor == max sample) beside prose.
CASES = [
    ([[10, 20, 30], [5, 5, 5]], [10, 5], 100),          # fits naturally
    ([[10, 20, 30], [5, 5, 5]], [10, 5], 20),           # squeeze
    ([[10, 20, 30], [5, 5, 5]], [10, 5], 14),           # floors exactly fit
    ([[10, 20, 30], [5, 5, 5]], [10, 5], 5),            # floors too big
    ([[1, 1, 1, 1, 50], [8, 9, 10]], [1, 8], 30),       # one fat tail
    ([[30], [30], [30]], [30, 30, 30], 60),             # all unbreakable
    ([[5, 40], [5, 40], [5, 6]], [5, 5, 5], 40),        # two fat tails
    ([[], [7, 8, 9]], [3, 7], 12),                      # an empty column
    ([[100]], [4], 50),                                 # single column
    ([[2, 4, 6, 8, 10, 12, 14, 16]], [2], 9),           # long ramp
]


@pytest.mark.parametrize('samples, floors, budget', CASES)
def test_never_below_floor(samples, floors, budget):
    """A floor is the point below which the caller says do not go."""
    for mode in ('equal-risk', 'coverage'):
        got = solve_widths(samples, floors, budget, mode)
        assert all(w >= f for w, f in zip(got.widths, floors)), got


@pytest.mark.parametrize('samples, floors, budget', CASES)
def test_status_and_budget_agree(samples, floors, budget):
    """'over' means it did not fit; anything else means it did."""
    for mode in ('equal-risk', 'coverage'):
        got = solve_widths(samples, floors, budget, mode)
        assert (got.total > budget) == (got.status == 'over'), got
        assert len(got.widths) == len(floors)


def test_natural_when_there_is_room():
    got = solve_widths([[10, 20, 30], [5, 5, 5]], [10, 5], 100)
    assert got.status == 'natural'
    assert got.widths == (30, 5)          # each column's widest cell


def test_unbreakable_column_rides_through_untouched():
    """floor == natural is how a caller says 'never narrow this one'."""
    got = solve_widths([[9, 40], [30]], [9, 30], 45)
    assert got.widths[1] == 30            # held exactly, budget or not
    assert got.status == 'solved'


def test_floors_beyond_budget_report_over():
    got = solve_widths([[50], [50]], [50, 50], 60)
    assert got.status == 'over'
    assert got.widths == (50, 50)         # the narrowest honest answer


def test_equal_risk_shares_the_pain():
    """Two identically-shaped columns must be narrowed identically."""
    got = solve_widths([[1, 10], [1, 10]], [1, 1], 12)
    assert got.widths[0] == got.widths[1]


def test_coverage_completes_cheap_columns_first():
    """Given a fat tail and a tight column, coverage finishes the tight one."""
    samples = [[2, 2, 2, 60], [9, 9, 9, 10]]
    got = solve_widths(samples, [2, 9], 30, 'coverage')
    assert got.widths[1] == 10            # four cells bought for one unit
    assert got.widths[0] < 60             # the outlier goes unserved


def test_empty_input():
    assert solve_widths([], [], 100).widths == ()


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        solve_widths([[1]], [1, 2], 10)


@pytest.mark.skipif(NODE is None, reason='node not available')
def test_matches_the_js_solver():
    """The port and the walker's copy must allocate identically.

    Compared against the faithful inner functions, not ``solve_widths``:
    that one adds GT2 policy on top (it reports floors, not
    ``widths_at(0)``, when nothing can fit) and so is deliberately not a
    line-for-line match.
    """
    payload = [{'samples': s, 'floors': f, 'budget': b, 'mode': m}
               for s, f, b in CASES for m in ('equal-risk', 'coverage')]
    proc = subprocess.run(
        [NODE, str(ROOT / 'js' / 'solver-check.mjs')],
        input=json.dumps(payload), capture_output=True, text=True,
        check=True, cwd=ROOT)
    theirs = json.loads(proc.stdout)
    for case, want in zip(payload, theirs):
        ordered = [sorted(s) for s in case['samples']]
        solver = (_coverage_widths if case['mode'] == 'coverage'
                  else _equal_risk_widths)
        ours = solver(ordered, list(case['floors']), case['budget'])
        assert ours == want, f'{case["mode"]} on {case["samples"]}'
