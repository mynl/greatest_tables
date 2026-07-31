"""Fabricator tests: determinism under seed, spec parsing, missing wiring."""

import pandas as pd
import pandas.testing as pdt
import pytest

from greater_tables import Fabricator, quick_fab


def test_seeded_runs_identical():
    """Two independently constructed seeded fabricators agree exactly."""
    make = lambda: Fabricator(seed=42).make(
        12, 's2fidry', index_levels=2, column_groups=2, column_levels=1)
    pdt.assert_frame_equal(make(), make())


def test_datetimes_deterministic():
    """Date/time columns derive from the fixed now, not the wall clock."""
    a = Fabricator(seed=7).make(8, 'dt')
    b = Fabricator(seed=7).make(8, 'dt')
    pdt.assert_frame_equal(a, b)
    assert (a.iloc[:, 0] <= pd.Timestamp('2026-01-01')).all()


def test_parse_colspec_forms():
    fab = Fabricator(seed=1)
    assert fab._parse_colspec('s3sfid') == ['s3', 's', 'f', 'i', 'd']
    assert fab._parse_colspec(3) == ['f', 'f', 'f']
    assert fab._parse_colspec(['f', 's2']) == ['f', 's2']


def test_missing_wired():
    df = Fabricator(seed=3).make(20, 'ff', missing=0.25)
    assert df.isna().sum().min() >= 5


def test_oversample_returns_requested_rows():
    df = Fabricator(seed=5).make(6, 'sf', oversample=3)
    assert df.shape[0] == 6


def test_every_dtype_code():
    fab = Fabricator(seed=11)
    df = fab.make(5, 'dfhilprs2tvwxy', simplify=False)
    assert df.shape == (5, 13)


def test_quick_fab():
    df = quick_fab(seed=9)
    assert df.shape[0] == 10


def test_unknown_dtype_raises():
    with pytest.raises(ValueError, match='Unknown dtype'):
        Fabricator(seed=1).make(3, 'q')
