"""Inline markdown in cells: the rule, each renderer's step, and the build.

The rule's cases are checked here in Python, and against the walker's port
through ``js/markdown-check.mjs``; the fixtures carry them through the
goldens of every renderer.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from greater_tables import (
    GT, HouseStyle, TableSpec, build, render_html, render_text, render_tikz,
)
from greater_tables.ir import Cell, HeadCell
from greater_tables.markdownspans import runs
from greater_tables.render import tikz_layout
from greater_tables.render.html import _markdown_html
from greater_tables.render.textlength import display_milli

ROOT = Path(__file__).parent.parent
NODE = shutil.which('node')

# input, runs as (kind, style, text), TeX, HTML
CASES = [
    ('*alpha*', [('text', 'em', 'alpha')], r'\emph{alpha}', '<em>alpha</em>'),
    ('**Total**', [('text', 'strong', 'Total')], r'\textbf{Total}',
     '<strong>Total</strong>'),
    ('uses `col_name`', [('text', None, 'uses '), ('code', None, 'col_name')],
     r'uses \texttt{col\_name}', 'uses <code>col_name</code>'),
    ('`$x$`', [('code', None, '$x$')], r'\texttt{\$x\$}', '<code>$x$</code>'),
    ('*see $x$*', [('text', 'em', 'see '), ('math', 'em', 'x')],
     r'\emph{see $x$}', '<em>see <span class="gt-math">\\(x\\)</span></em>'),
    ('$a*b*c$', [('math', None, 'a*b*c')], '$a*b*c$',
     '<span class="gt-math">\\(a*b*c\\)</span>'),
    ('a*b*c', [('text', None, 'a*b*c')], 'a*b*c', 'a*b*c'),
    ('0.23**', [('text', None, '0.23**')], '0.23**', '0.23**'),
    ('Revenue*', [('text', None, 'Revenue*')], 'Revenue*', 'Revenue*'),
    ('2 * 3 * 4', [('text', None, '2 * 3 * 4')], '2 * 3 * 4', '2 * 3 * 4'),
    ('*x', [('text', None, '*x')], '*x', '*x'),
    (r'\*x\*', [('text', None, '*x*')], '*x*', '*x*'),
    ('***x***', [('text', 'strong', '*x*')], r'\textbf{*x*}',
     '<strong>*x*</strong>'),
    ('*a<b* & c', [('text', 'em', 'a<b'), ('text', None, ' & c')],
     r'\emph{a<b} \& c', '<em>a&lt;b</em> &amp; c'),
    ('(*a*), **b**.', [('text', None, '('), ('text', 'em', 'a'),
                       ('text', None, '), '), ('text', 'strong', 'b'),
                       ('text', None, '.')],
     r'(\emph{a}), \textbf{b}.', '(<em>a</em>), <strong>b</strong>.'),
    ('*use `x`*', [('text', 'em', 'use '), ('code', 'em', 'x')],
     r'\emph{use \texttt{x}}', '<em>use <code>x</code></em>'),
    ('', [('text', None, '')], '', ''),
]

# more inputs the walker must split the same way: edge cases, not specs
MORE = ['``x``', '`a\\`b`', '** x**', '*x *', 'x**a**y', '**a***b*', '*a*b*',
        ' *a*', '*a\nb*', '$x$*y*', '"*q*"', '*a*\n', 'p\\$1 *q*']


@pytest.mark.parametrize('text, want, _tex, _html', CASES, ids=[c[0] for c in CASES])
def test_rule(text, want, _tex, _html):
    assert [tuple(r) for r in runs(text)] == want


@pytest.mark.parametrize('text, _runs, tex, _html', CASES, ids=[c[0] for c in CASES])
def test_tex(text, _runs, tex, _html):
    assert tikz_layout.markdown_tex(text) == tex


@pytest.mark.parametrize('text, _runs, _tex, html', CASES, ids=[c[0] for c in CASES])
def test_html(text, _runs, _tex, html):
    assert _markdown_html(text, math=True) == html


def test_math_off_leaves_dollars_alone():
    assert [tuple(r) for r in runs('*see $x$*', math=False)] == \
        [('text', 'em', 'see $x$')]
    assert tikz_layout.markdown_tex('*see $x$*', math=False) == r'\emph{see \$x\$}'


@pytest.mark.skipif(NODE is None, reason='node not available')
@pytest.mark.parametrize('math', [True, False])
def test_walker_splits_alike(math, tmp_path):
    texts = [c[0] for c in CASES] + MORE
    src = tmp_path / 'cases.json'
    src.write_text(json.dumps(texts), encoding='utf-8')
    args = [NODE, str(ROOT / 'js' / 'markdown-check.mjs'), str(src)]
    out = subprocess.run(args + ([] if math else ['--math-off']), check=True,
                         capture_output=True, cwd=ROOT, encoding='utf-8').stdout
    for text, theirs in zip(texts, json.loads(out)):
        assert [list(r) for r in runs(text, math)] == theirs, repr(text)


# ------------------------------------------------------------------ the build

GOAL = """
| Item     | Note              | Value |
|:---------|:------------------|------:|
| *alpha*  | uses `col_name`   |  1.25 |
| **beta** | the base case     |   2.5 |

Table: *x*
"""


def test_markdown_string_sets_markdown():
    """The plan's goal: italic, bold and code in HTML and TeX, as typed in
    text, and an italic caption."""
    gt = GT(GOAL)
    html, tex, text = gt.html, gt.tikz, gt.text
    assert '<em>alpha</em>' in html and '<strong>beta</strong>' in html
    assert '<code>col_name</code>' in html
    assert r'\emph{alpha}' in tex and r'\textbf{beta}' in tex
    assert r'\texttt{col\_name}' in tex
    assert '*alpha*' in text and '`col_name`' in text
    assert '<em>x</em></caption>' in html
    assert r'\caption{\emph{x}}' in tex


def test_header_stars():
    """A whole **...** header is stripped, *Note* sets bold italic, and a
    footnote star stays."""
    doc = build('| **Total** | *Note* | Revenue* |\n|---|---|---|\n| 1 | 2 | 3 |\n')
    total, note, revenue = doc.head[0]
    assert total.text == 'Total' and not total.markdown
    assert note.text == '*Note*' and note.markdown
    assert revenue.text == 'Revenue*'
    tex = render_tikz(doc)
    assert r'\bfseries \emph{Note}' in tex and r'\bfseries Revenue*' in tex


def test_dataframe_caption_is_literal_unless_asked():
    df = pd.DataFrame({'a': [1]})
    assert build(df, TableSpec(caption='*x*')).caption == '*x*'
    doc = build(df, TableSpec(caption='*x*', markdown_caption=True))
    assert doc.caption == Cell(text='*x*', markdown=True)
    assert build('| a |\n|---|\n| 1 |\n\nTable: *x*',
                 TableSpec(markdown_caption=False)).caption == '*x*'


def test_dataframe_cells_are_literal_unless_selected():
    df = pd.DataFrame({'note': ['*a*'], 'sig': ['0.23**']},
                      index=pd.Index(['*i*'], name='case'))
    doc = build(df)
    assert not any(c.markdown for c in doc.body[0].cells)
    doc = build(df, TableSpec(markdown_cols=['note', 'case']))
    stub, note, sig = doc.body[0].cells
    assert stub.markdown and note.markdown and not sig.markdown
    assert [h.markdown for h in doc.head[0]] == [False, False, False]  # no stars
    doc = build(df.rename(columns={'note': '*note*'}, index={'*i*': 'i'})
                .rename_axis('*case*'), TableSpec(markdown_cols=['*note*', '*case*']))
    assert [h.markdown for h in doc.head[0]] == [True, True, False]


def test_group_labels_are_never_markdown():
    df = pd.DataFrame([[1, 2]], columns=pd.MultiIndex.from_tuples(
        [('*g*', '*a*'), ('*g*', 'b')]))
    doc = build(df, TableSpec(markdown_cols='all'))
    assert not doc.head[0][0].markdown
    assert [h.markdown for h in doc.head[1]] == [True, False]


def test_html_cols_and_markdown_cols():
    """A markdown string's default leaves html_cols out; naming a column in
    both raises."""
    md = '| Item | Note |\n|---|---|\n| *a* | <b>x</b> *y* |\n'
    doc = build(md, TableSpec(html_cols=['Note']))
    item, note = doc.body[0].cells
    assert item.markdown and note.html and not note.markdown
    with pytest.raises(ValueError, match='Note'):
        build(md, TableSpec(html_cols=['Note'], markdown_cols=['Note']))
    with pytest.raises(ValueError, match='Note'):
        build(md, TableSpec(markdown_cols=['Note'], html_cols=['Note']))


def test_text_shows_markdown_as_typed():
    doc = build('| a |\n|---|\n| *x* `y` |\n')
    assert '*x* `y`' in render_text(doc)


def test_html_needs_no_allow_html_gate():
    """The tags come from the parse, so allow_html off still sets them and
    still escapes the text."""
    doc = build('| a |\n|---|\n| *<i>x</i>* |\n')
    html = render_html(doc, allow_html=False)
    assert '<em>&lt;i&gt;x&lt;/i&gt;</em>' in html


# ---------------------------------------------------------------- the widths

FONT = HouseStyle().tikz_font


def test_markers_are_not_measured():
    cell = Cell(text='*alpha* and `col_name`', markdown=True)
    roman = display_milli('alpha and ', font=FONT)
    assert tikz_layout._display_milli(cell, True, FONT) == \
        roman + tikz_layout._MONO_MILLI * len('col_name')


def test_strong_is_measured_bold():
    cell = Cell(text='**Subtotal**', markdown=True)
    assert tikz_layout._display_milli(cell, True, FONT) == \
        display_milli('Subtotal', font=FONT, bold=True) > display_milli('Subtotal', font=FONT)


def test_widest_word_runs_across_runs():
    """``*alpha*,`` is one word, an italic run and a comma."""
    cell = Cell(text='a *alpha*, b', markdown=True)
    assert tikz_layout._token_milli(cell, True, FONT) == \
        display_milli('alpha,', font=FONT)


def test_heading_words_drop_their_markers():
    doc = build(pd.DataFrame({'*Long* heading `x`': [1]}),
                TableSpec(show_index=False, markdown_cols='all'))
    head = doc.head[0][0]
    assert isinstance(head, HeadCell) and head.markdown
    words = tikz_layout._markdown_words(head.text, True, FONT, bold=True)
    assert words == [display_milli('Long', font=FONT, bold=True),
                     display_milli('heading', font=FONT, bold=True),
                     tikz_layout._MONO_MILLI]


def test_a_dataframe_without_markdown_cols_is_unchanged():
    """No flag is set, so no renderer takes the markdown path."""
    df = pd.DataFrame({'a': ['*x*', '`y`'], 'b': ['0.23**', 'p*q']})
    doc = build(df)
    assert not any(c.markdown for row in doc.body for c in row.cells)
    assert re.search(r'\*x\*', render_tikz(doc))
