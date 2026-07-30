"""GT facade tests: constructor compatibility, laziness, formatter mapping."""

import warnings

import pandas as pd
import pytest

from greatest_tables import Fabricator, render_text
from greatest_tables.compat import GT


@pytest.fixture()
def df():
    return Fabricator(seed=201).make(6, 'sf', index_levels=1)


def test_basic_render(df):
    gt = GT(df, caption='Compat check')
    bundle = gt._repr_mimebundle_()
    assert 'text/html' in bundle and 'Compat check' in bundle['text/html']
    assert str(gt) == render_text(gt.doc)


def test_lazy_and_cached(df):
    gt = GT(df)
    assert 'doc' not in gt.__dict__          # nothing computed at construction
    doc = gt.doc
    assert gt.doc is doc                     # cached


def test_formatter_shapes():
    df = pd.DataFrame({'a': [1234.5678, 2.0], 'b': [0.1234, 0.5],
                       'c': [1.0, 2.0]})
    gt = GT(df, formatters={'a': 2, 'b': '{x:.1%}', 'c': lambda x: f'<{x}>'})
    texts = [c.text for c in gt.doc.body[0].cells]
    assert texts[0] == '1234.57'             # int ⇒ digits, no grouping (5.x)
    assert texts[1] == '12.3%'
    assert texts[2] == '<1.0>'
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


def test_tikz_renders(df):
    tikz = GT(df).tikz
    assert '\\begin{tikzpicture}' in tikz and '\\matrix' in tikz
