"""Engine tests: golden IR per fixture plus targeted structural checks."""

import json
from pathlib import Path

import pandas as pd
import pandas.testing as pdt
import pytest

from greater_tables import Fabricator, TableSpec, build, canonical_json

from registry import fixtures, golden_bytes

GOLDEN_IR = Path(__file__).parent / 'golden' / 'ir'
FIX = fixtures()


@pytest.mark.parametrize('name', sorted(FIX))
def test_ir_golden(name):
    data, spec = FIX[name]
    assert golden_bytes(build(data, spec)) == \
        (GOLDEN_IR / f'fx-{name}.json').read_bytes()


def test_never_mutates_input():
    df = Fabricator(seed=102).make(10, 'ff', index_levels=2)
    before = df.copy(deep=True)
    build(df, TableSpec(include_raw=True, row_flags={-1: ('total',)}))
    pdt.assert_frame_equal(df, before)


def test_structure_small():
    """Known 3-row MultiIndex: rowspans, sparsified cells, break depths."""
    df = pd.DataFrame(
        {'v': [1.0, 2.0, 3.0]},
        index=pd.MultiIndex.from_tuples(
            [('A', 'x'), ('A', 'y'), ('B', 'x')], names=['g', 's']))
    doc = build(df, TableSpec())
    assert doc.n_stub_levels == 2
    r0, r1, r2 = doc.body
    assert r0.cells[0].rowspan == 2          # 'A' spans rows 0-1
    assert len(r1.cells) == 2                # covered stub omitted
    assert r1.break_depth == 1
    assert r2.break_depth == 0
    assert len(r2.cells) == 3


def test_truncation_note():
    data, spec = FIX['truncated']
    doc = build(data, spec)
    assert len(doc.body) == 5
    assert any('first 5 of 12 rows' in n for n in doc.notes)


def test_raw_values():
    doc = build(*FIX['bigints'])
    id_col = doc.columns[doc.n_stub_levels]
    assert id_col.dtype == 'int' and id_col.raw
    first = doc.body[0].cells[0]
    assert first.raw == str(2 ** 53 + 1)      # big int rides as string
    assert doc.body[2].cells[1].raw == -3.25
    assert 'neg' in doc.body[2].cells[1].flags


def test_neg_flag_only_on_numeric_negatives():
    doc = build(*FIX['negatives'])
    for row in doc.body:
        for cell in row.cells[doc.n_stub_levels:]:
            assert ('neg' in cell.flags) == (cell.raw is not None and cell.raw < 0)


def test_math_and_html_cells():
    doc = build(*FIX['math-html'])
    expr0 = doc.body[0].cells[0]
    assert expr0.math and expr0.text == r'\alpha+\beta'
    assert not doc.body[1].cells[0].math
    link0 = doc.body[0].cells[1]
    assert link0.html and link0.text == '<a href="x">x</a>'


def test_headerless_and_empty():
    doc = build(*FIX['headerless'])
    assert doc.n_head_levels == 0 and doc.head == ()
    assert doc.body[0].cells[0].text == 'alpha'
    empty = build(*FIX['empty'])
    assert empty.columns == () and empty.body == ()


def test_markdown_ingest():
    doc = build(*FIX['markdown'])
    assert doc.caption == 'Simple table'
    assert doc.label == 'tbl-md'
    cols = doc.columns
    assert [c.align for c in cols] == ['l', 'r', 'l', 'r']   # from :--- / ---:
    assert doc.body[1].cells[1].text == '12'


def test_markdown_ingest_pipe_in_math():
    # a pipe inside math belongs to the cell; one between prices separates
    md = ('| $|x|$ | b |\n'
          '|---|---|\n'
          '| $\\|x\\|$ | 1 |\n'
          '| $1 | $2 |\n')
    doc = build(md)
    assert doc.columns[0].name == ('$|x|$',)
    assert [c.text for c in doc.body[0].cells] == ['\\|x\\|', '1']
    assert doc.body[0].cells[0].math
    assert [c.text for c in doc.body[1].cells] == ['$1', '$2']


def test_markdown_ingest_outer_whitespace():
    # a space after the closing pipe or an indent before the opening one
    # adds no empty cell, on any line
    md = ('| a | B | c | \n'
          '  |--|--|--|\n'
          '  | 1 | $\\|x\\|$ | works | \n'
          '| 2 | y | z |\n')
    doc = build(md)
    assert [c.name for c in doc.columns] == [('a',), ('B',), ('c',)]
    assert [c.text for c in doc.body[0].cells] == ['1', '\\|x\\|', 'works']
    assert [c.text for c in doc.body[1].cells] == ['2', 'y', 'z']


def test_totals_row_flag():
    doc = build(*FIX['totals'])
    assert doc.body[-1].flags == ('total',)
    assert all(r.flags == () for r in doc.body[:-1])


def test_year_tag():
    doc = build(*FIX['year'])
    year_col = next(c for c in doc.columns if 'year' in c.name)
    assert year_col.tag == 'year'
    assert year_col.align == 'c'
    assert year_col.format.kind == 'year'
    n_stub = doc.n_stub_levels
    dj = next(i for i, c in enumerate(doc.columns[n_stub:]) if 'year' in c.name)
    cell = doc.body[0].cells[n_stub + dj]          # row 0 emits all stub cells
    assert ',' not in cell.text                    # years never grouped


def test_include_raw_default_off():
    doc = build(*FIX['plain'])
    assert all(not c.raw for c in doc.columns)
    payload = json.loads(canonical_json(doc))
    for row in payload['body']:
        for cell in row['cells']:
            assert isinstance(cell, str) or 'raw' not in cell
