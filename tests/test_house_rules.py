"""House defaults: the format ladder, and the YAML round trip.

The ladder is two steps — a column's *kind* is its semantic tag if it has
one, else its dtype; then that kind resolves formatters[col] >
shared_formatters[col] > house default > built-in. ``table_float_format`` is the exception that outranks an explicit
per-column entry, and only on the float line.
"""

import pandas as pd
import pytest

from greater_tables import FormatSpec, GT, HouseStyle, TableSpec, build
from greater_tables.config import (
    load_spec, load_style, spec_to_yaml, write_template,
)


@pytest.fixture
def df():
    return pd.DataFrame({
        'paid': [1234.5678, 2.5],
        'lr': [0.4576, 0.5121],
        'count': [1200, 34],
        'when': pd.to_datetime(['2026-01-15', '2026-07-31']),
        'name': ['alpha', 'beta'],
    })


def _fmt(doc, name):
    return next(c.format for c in doc.columns if c.name[-1] == name)


# ------------------------------------------------------------- the ladder

def test_ratio_tag_is_percent_at_one_decimal(df):
    """5.x's default_ratio_str was '{x:.1%}'; GT2 6.0 restores it."""
    doc = build(df, TableSpec(ratio_cols=['lr']))
    assert _fmt(doc, 'lr') == FormatSpec(kind='pct', digits=1)
    assert doc.body[0].cells[1].text == '45.8%'


def test_house_defaults_replace_the_built_ins(df):
    doc = build(df, TableSpec(ratio_cols=['lr'], float_format=',.2f',
                              int_format='d', ratio_format='.3%',
                              date_format='%d %b %Y'))
    assert _fmt(doc, 'paid') == FormatSpec(kind='dec', digits=2, group=True)
    assert _fmt(doc, 'count').group is False
    assert _fmt(doc, 'lr') == FormatSpec(kind='pct', digits=3)
    assert _fmt(doc, 'when').pattern == '%d %b %Y'


def test_per_column_beats_every_house_default(df):
    doc = build(df, TableSpec(ratio_cols=['lr'], float_format=',.2f',
                              ratio_format='.3%',
                              formatters={'paid': '.4f', 'lr': '.0%'}))
    assert _fmt(doc, 'paid') == FormatSpec(kind='dec', digits=4)
    assert _fmt(doc, 'lr') == FormatSpec(kind='pct', digits=0)


def test_leaf_name_matches_a_tuple_label():
    cols = pd.MultiIndex.from_tuples([('A', 'paid'), ('B', 'paid')])
    doc = build(pd.DataFrame([[1.0, 2.0]], columns=cols),
                TableSpec(formatters={'paid': '.3f'}))
    assert all(c.format.digits == 3 for c in doc.columns if c.role == 'data')


def test_float_format_suppresses_the_engineering_switch():
    """Stated house rule wins over the guess — that is the whole point."""
    wild = pd.DataFrame({'v': [1e-9, 1e9]})
    assert build(wild, TableSpec()).columns[0].format.kind == 'si'
    doc = build(wild, TableSpec(float_format=',.2f'))
    assert doc.columns[0].format == FormatSpec(kind='dec', digits=2, group=True)


def test_eng_knobs_apply_when_inference_runs():
    wild = pd.DataFrame({'v': [1e-9, 1e9]})
    doc = build(wild, TableSpec(eng_digits=2, eng_style='exp'))
    assert doc.columns[0].format == FormatSpec(kind='eng', digits=2)


def test_int_format_reaches_a_stub_level():
    df = pd.DataFrame({'v': [1.0, 2.0]},
                      index=pd.Index([1000, 2000], name='id'))
    doc = build(df, TableSpec(int_format='d'))
    assert doc.columns[0].role == 'stub' and doc.columns[0].format.group is False
    assert doc.body[0].cells[0].text == '1000'


def test_table_float_format_beats_even_a_per_column_entry(df):
    doc = build(df, TableSpec(formatters={'paid': '.4f'},
                              float_format=',.1f', table_float_format='.0f'))
    assert _fmt(doc, 'paid') == FormatSpec(kind='dec', digits=0)


def test_table_float_format_does_not_touch_tagged_columns(df):
    """A ratio is an honorary non-float: it has a kind, so the sledgehammer
    never reaches it. Same for year and date."""
    doc = build(df, TableSpec(ratio_cols=['lr'], year_cols=['count'],
                              table_float_format='.0f'))
    assert _fmt(doc, 'lr') == FormatSpec(kind='pct', digits=1)
    assert _fmt(doc, 'count').kind == 'year'
    assert _fmt(doc, 'when').kind == 'date'
    assert _fmt(doc, 'paid') == FormatSpec(kind='dec', digits=0)


def test_callable_in_a_house_default_raises(df):
    with pytest.raises(TypeError, match='not a callable'):
        build(df, TableSpec(float_format=lambda x: str(x)))


def test_bad_sugar_names_the_field(df):
    with pytest.raises(ValueError, match='TableSpec.float_format'):
        build(df, TableSpec(float_format='nonsense'))


def test_facade_passes_house_rules_through(df):
    gt = GT(df, ratio_cols=['lr'], float_format=',.2f')
    assert _fmt(gt.doc, 'paid').digits == 2
    assert _fmt(gt.doc, 'lr').kind == 'pct'


# --------------------------------------------------------------- the YAML

def test_house_yaml_round_trip(tmp_path, df):
    (tmp_path / 'house.yaml').write_text(
        "float_format: ',.2f'\n"
        "int_format: ',d'\n"
        "ratio_format: '.1%'\n"
        "date_format: '%d %b %Y'\n"
        "ratio_cols: 'lr|ratio$'\n"
        'shared_formatters: {paid: {kind: dec, digits: 1, negative: paren}}\n',
        encoding='utf-8')
    spec = load_spec(tmp_path / 'house.yaml')
    doc = build(df, spec)
    assert _fmt(doc, 'paid') == FormatSpec(kind='dec', digits=1,
                                           negative='paren')
    assert _fmt(doc, 'lr').kind == 'pct'
    assert doc.body[0].cells[3].text == '15 Jan 2026'


def test_template_covers_every_field(tmp_path):
    from dataclasses import fields
    text = write_template(tmp_path / 't.yaml').read_text(encoding='utf-8')
    missing = [f.name for f in fields(TableSpec) if f.name not in text]
    assert not missing


def test_template_omits_the_sledgehammer(tmp_path, df):
    """table_float_format must not rot inside a config file."""
    spec = TableSpec(table_float_format='.0f', float_format=',.2f')
    text = write_template(tmp_path / 'house.yaml', spec).read_text(encoding='utf-8')
    assert 'table_float_format' not in text
    assert "float_format: ',.2f'" in text


def test_effective_dump_reloads(tmp_path):
    spec = TableSpec(caption='Demo', ratio_cols='all', float_format=',.2f',
                     max_rows=50)
    path = write_template(tmp_path / 'house.yaml', spec)
    assert load_spec(path) == spec


def test_both_format_maps_round_trip(tmp_path):
    """A dump keeps each map in its own field, checked and unchecked."""
    spec = TableSpec(formatters={'paid': ',.1f'},
                     shared_formatters={'case': {'kind': 'dec', 'digits': 3}})
    path = write_template(tmp_path / 'house.yaml', spec)
    assert load_spec(path) == spec


def test_spec_to_yaml_refuses_code():
    spec = TableSpec(row_flags=lambda pos, row: ['total'])
    with pytest.raises(ValueError, match='no YAML form'):
        spec_to_yaml(spec)


def test_load_style(tmp_path):
    (tmp_path / 'style.yaml').write_text(
        'max_rule_depth: 0\nhrule_widths: [1, 0.5, 0]\n', encoding='utf-8')
    style = load_style(tmp_path / 'style.yaml')
    assert style == HouseStyle(max_rule_depth=0, hrule_widths=(1, 0.5, 0))
