"""Format layer: sugar parsing, float inference, value application.

This module had zero direct tests before 6.0.0a3 — everything rode on the
goldens, which only exercise the combinations the fixtures happen to use.
The house-default ladder is built on top of these three functions, so they
get pinned here.
"""

import math

import pandas as pd
import pytest
from pydantic import ValidationError

from greater_tables import FormatSpec
from greater_tables.engine.formats import (
    apply_format, infer_numeric_format, parse_sugar,
)


# ----------------------------------------------------------- parse_sugar

@pytest.mark.parametrize('sugar,kind,digits,group', [
    (',.1f', 'dec', 1, True),
    ('.2f', 'dec', 2, False),          # the comma IS the grouping flag
    ('f', 'dec', None, False),
    ('d', 'int', None, False),
    (',d', 'int', None, True),
    ('.3%', 'pct', 3, False),
    ('.2e', 'sci', 2, False),
    ('.3g', 'gen', 3, False),
    ('g', 'gen', None, False),
    (',.3g', 'gen', 3, True),
    ('{x:,.1f}', 'dec', 1, True),
    ('{x:.1%}', 'pct', 1, False),
    ('{x:.3g}', 'gen', 3, False),
    ('{x:,}', 'dec', None, True),
])
def test_sugar_strings(sugar, kind, digits, group):
    fs = parse_sugar(sugar)
    assert (fs.kind, fs.digits, fs.group) == (kind, digits, group)


def test_bare_int_groups():
    """GT2 groups whenever it picks the format; '.2f' opts out."""
    assert parse_sugar(2) == FormatSpec(kind='dec', digits=2, group=True)
    assert parse_sugar('.2f').group is False


@pytest.mark.parametrize('word', ['year', 'eng', 'si'])
def test_named_kinds(word):
    assert parse_sugar(word).kind == word


@pytest.mark.parametrize('pattern', ['%Y-%m-%d', '%d %b %Y', '%Y-%m-%d %H:%M'])
def test_strftime_patterns(pattern):
    fs = parse_sugar(pattern)
    assert fs.kind == 'date' and fs.pattern == pattern


def test_percent_and_percent_year_do_not_collide():
    """One regex ordering apart: '%' is a format, '%Y' is a date pattern."""
    assert parse_sugar('%').kind == 'pct'
    assert parse_sugar('%Y').kind == 'date'


def test_formatspec_passthrough_is_identity():
    fs = FormatSpec(kind='dec', digits=1, negative='paren')
    assert parse_sugar(fs) is fs


def test_mapping_branch_is_the_yaml_form():
    """The only way a config file reaches paren negatives, scale, suffix."""
    fs = parse_sugar({'kind': 'dec', 'digits': 1, 'negative': 'paren',
                      'scale': 0.001, 'suffix': 'k'})
    assert fs.negative == 'paren' and fs.scale == 0.001 and fs.suffix == 'k'


def test_mapping_with_a_bad_key_names_it():
    with pytest.raises(ValidationError, match='digitz'):
        parse_sugar({'kind': 'dec', 'digitz': 2})


def test_unrecognized_sugar_raises():
    with pytest.raises(ValueError, match='unrecognized format sugar'):
        parse_sugar('wat')


# --------------------------------------------------- infer_numeric_format

@pytest.mark.parametrize('mean,digits', [
    (0.5, 5), (5.0, 3), (500.0, 2), (50000.0, 0),
])
def test_decimal_buckets(mean, digits):
    fs = infer_numeric_format(pd.Series([mean, mean]))
    assert fs.kind == 'dec' and fs.digits == digits and fs.group


def test_empty_and_all_nan():
    for ser in (pd.Series([], dtype=float), pd.Series([float('nan')] * 3)):
        fs = infer_numeric_format(ser)
        assert fs == FormatSpec(kind='dec', digits=2, group=True)


def test_non_finite_values_are_ignored():
    fs = infer_numeric_format(pd.Series([1.0, math.inf, math.nan, 3.0]))
    assert fs.kind == 'dec' and fs.digits == 3      # mean 2.0 → the <10 bucket


def test_eng_trigger_mean_outside_bounds():
    assert infer_numeric_format(pd.Series([1e-9, 2e-9])).kind == 'si'
    assert infer_numeric_format(pd.Series([1e9, 2e9])).kind == 'si'


def test_eng_trigger_wide_span_despite_a_normal_mean():
    """No single fixed precision serves 1e-4 and 1e4 in one column."""
    assert infer_numeric_format(pd.Series([1e-4, 1e4])).kind == 'si'


def test_pef_bounds_are_respected():
    ser = pd.Series([1e4, 2e4])
    assert infer_numeric_format(ser).kind == 'dec'
    assert infer_numeric_format(ser, pef_upper=3).kind == 'si'


def test_eng_style_and_digits():
    ser = pd.Series([1e9, 2e9])
    assert infer_numeric_format(ser, digits=2).digits == 2
    assert infer_numeric_format(ser, style='exp').kind == 'eng'


# ------------------------------------------------------------ apply_format

def test_kinds():
    assert apply_format(1234.5678, parse_sugar(',.2f')) == '1,234.57'
    assert apply_format(1234, parse_sugar(',d')) == '1,234'
    assert apply_format(0.4576, parse_sugar('.1%')) == '45.8%'
    assert apply_format(2023, parse_sugar('year')) == '2023'
    assert apply_format(pd.Timestamp('2026-08-01'),
                        FormatSpec(kind='date')) == '2026-08-01'
    assert apply_format('text', None) == 'text'


@pytest.mark.parametrize('value,sugar,want', [
    (1234.5678, '.3g', '1.23e+03'),      # g switches to scientific itself
    (0.0012345, '.3g', '0.00123'),       # ... and back to fixed
    (1234.5678, '.6g', '1234.57'),
    (1234.5678, 'g', '1234.57'),         # python's own default precision, 6
    (1234567.0, ',.9g', '1,234,567'),    # grouping still applies in fixed form
    (-0.000098765, '.2g', '-9.9e-05'),
])
def test_gen_kind_counts_significant_figures(value, sugar, want):
    """`.3g` is 3 *significant* figures, unlike `.3f`'s 3 decimal places."""
    assert apply_format(value, parse_sugar(sugar)) == want


def test_gen_composes_with_the_spec_fields():
    fs = FormatSpec(kind='gen', digits=3, negative='paren', prefix='$')
    assert apply_format(-1234.5678, fs) == '($1.23e+03)'


def test_null_zero_and_paren_negatives():
    fs = FormatSpec(kind='dec', digits=2, negative='paren', null='n/a',
                    zero='—')
    assert apply_format(float('nan'), fs) == 'n/a'
    assert apply_format(math.inf, fs) == 'n/a'
    assert apply_format(0.0, fs) == '—'
    assert apply_format(-5.0, fs) == '(5.00)'


def test_scale_prefix_suffix():
    fs = FormatSpec(kind='dec', digits=1, scale=0.001, prefix='$', suffix='k')
    assert apply_format(1500.0, fs) == '$1.5k'


def test_si_slot_is_a_no_break_space_so_decimals_align():
    """Same mantissa, suffix or not: the unsuffixed value still occupies the
    slot, so the decimal points line up down the column."""
    si = FormatSpec(kind='si', digits=3)
    plain, giga = apply_format(1.5, si), apply_format(1.5e9, si)
    assert plain == '1.500\xa0' and giga == '1.500G'
    assert len(plain) == len(giga)


def test_exponent_style_is_fixed_width():
    eng = FormatSpec(kind='eng', digits=2)
    assert len(apply_format(1.5e9, eng)) == len(apply_format(1.5e-9, eng))


def test_non_numeric_falls_back_to_str():
    assert apply_format('abc', parse_sugar(',.2f')) == 'abc'
