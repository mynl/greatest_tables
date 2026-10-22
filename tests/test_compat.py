"""GT facade tests: constructor compatibility, laziness, formatter mapping."""

import warnings
from functools import partial

import pandas as pd
import pytest

from greater_tables import Fabricator, HouseStyle, render_text
from greater_tables.compat import GT


@pytest.fixture()
def df():
    return Fabricator(seed=201).make(6, 'sf', index_levels=1)


def test_basic_render(df):
    gt = GT(df, caption='Compat check')
    bundle = gt._repr_mimebundle_()
    assert 'text/html' in bundle and 'Compat check' in bundle['text/html']
    assert bundle['text/plain'] == render_text(gt.doc)
    assert str(gt) == render_text(gt.doc)


def test_repr_is_the_table(df):
    """Not <GT at 0x…> — scripts and REPLs fall back to repr()."""
    gt = GT(df)
    assert repr(gt) == gt.text


def test_mimes_pins_the_bundle(df):
    """The gfm case: the caller knows what GT cannot detect."""
    gt = GT(df, mimes=('text/plain',))
    assert set(gt._repr_mimebundle_()) == {'text/plain'}


def test_mimes_typo_raises_at_construction(df):
    with pytest.raises(ValueError, match='unknown MIME type'):
        GT(df, mimes=('text/plian',))


def test_lazy_and_cached(df):
    gt = GT(df)
    assert 'doc' not in gt.__dict__          # nothing computed at construction
    doc = gt.doc
    assert gt.doc is doc                     # cached


def test_formatter_shapes():
    df = pd.DataFrame({'a': [1234.5678, 2.0], 'b': [0.1234, 0.5],
                       'c': [1.0, 2.0], 'd': [9876.5, 1.0]})
    gt = GT(df, formatters={'a': 2, 'b': '{x:.1%}', 'c': lambda x: f'<{x}>',
                            'd': '.2f'})
    texts = [c.text for c in gt.doc.body[0].cells]
    # a bare int groups — GT2 groups whenever it picks the format for you.
    # 5.x meant "no grouping" here; write '.2f' for that, as column d does.
    assert texts[0] == '1,234.57'
    assert texts[1] == '12.3%'
    assert texts[2] == '<1.0>'
    assert texts[3] == '9876.50'             # explicit sugar means what it says
    assert gt.doc.columns[2].format is None  # callables never enter the IR


def test_unknown_option_warns(df):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        GT(df, tikz_scale=1.5)
    assert any('tikz_scale' in str(w.message) for w in caught)


def test_spec_field_override_passes_through(df):
    gt = GT(df, max_rows=3)
    assert len(gt.doc.body) == 3


def test_markdown_input():
    gt = GT('| a | b |\n|--:|:--|\n| 1 | x |\n')
    assert gt.doc.body[0].cells[0].text == '1'


def test_config_path(tmp_path, df):
    cfg = tmp_path / 'spec.yaml'
    cfg.write_text('caption: From YAML\nmax_rows: 2\n', encoding='utf-8')
    gt = GT(df, config_path=cfg)
    assert gt.doc.caption == 'From YAML' and len(gt.doc.body) == 2
    override = GT(df, caption='Explicit wins', config_path=cfg)
    assert override.doc.caption == 'Explicit wins'


# ------------------------------------------- one house file, many tables

@pytest.fixture()
def house(tmp_path):
    cfg = tmp_path / 'house.yaml'
    cfg.write_text("float_format: ',.2f'\n"
                   'shared_formatters: {paid: {kind: dec, digits: 1, '
                   'negative: paren}}\n', encoding='utf-8')
    return partial(GT, config_path=cfg)


def _texts(gt):
    return [[c.text for c in row.cells] for row in gt.doc.body]


def test_house_file_skips_a_table_without_the_column(house):
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        gt = house(pd.DataFrame({'case': [1.0, 2.0]}))
        assert _texts(gt) == [['1.00'], ['2.00']]


def test_house_file_survives_call_formatters(house):
    df = pd.DataFrame({'paid': [1234.56, -20.0], 'case': [1.0, 2.0]})
    gt = house(df, formatters={'case': '.3f'})
    assert _texts(gt) == [['1234.6', '1.000'], ['(20.0)', '2.000']]


def test_misspelled_call_key_still_warns_at_the_caller(house):
    """The warning points at this file, not inside functools' cached_property."""
    gt = house(pd.DataFrame({'paid': [1.0]}), formatters={'piad': 1})
    with pytest.warns(UserWarning, match="'piad'.*shared_formatters") as caught:
        _ = gt.doc
    assert caught[0].filename == __file__


def test_call_mappings_merge_with_the_file(tmp_path):
    cfg = tmp_path / 'spec.yaml'
    cfg.write_text("formatters: {a: '.1f', b: '.1f'}\n"
                   'aligners: {a: c, b: c}\n', encoding='utf-8')
    gt = GT(config_path=cfg, formatters={'b': '.3f', 'c': '.2f'},
            aligners={'b': 'l'})
    assert gt.spec.formatters == {'a': '.1f', 'b': '.3f', 'c': '.2f'}
    assert gt.spec.aligners == {'a': 'c', 'b': 'l'}
    assert GT(config_path=cfg, aligners='rrl').spec.aligners == 'rrl'


def test_tikz_renders(df):
    tikz = GT(df).tikz
    assert '\\begin{tikzpicture}' in tikz and '\\begin{tabular}' in tikz


def test_matrix_engine_warns_and_renders_tabular(df, caplog):
    """The matrix engine went in 8.0.0; naming it still builds, says so once,
    and sets the tabular."""
    with caplog.at_level('WARNING'):
        style = HouseStyle(tikz_engine='matrix')
    assert [r.levelname for r in caplog.records] == ['WARNING']
    assert '8.0.0' in caplog.text and 'greater-tables<8' in caplog.text
    assert style.tikz_engine == 'tabular'
    assert GT(df, style=style).tikz == GT(df).tikz


def test_unknown_engine_raises():
    with pytest.raises(ValueError, match='tabular'):
        HouseStyle(tikz_engine='tabularx')
