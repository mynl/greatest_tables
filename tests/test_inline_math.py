"""Inline math everywhere: the shared rule, the renderer matrix, the off-doc.

The 7.0.0 contract: ``$...$`` / ``$$...$$`` just work in body cells, stub
cells and column headers — whole-cell and mid-sentence — while currency
(``$10 to $20``) never becomes math. ``TableSpec`` has no math switch any
more; ``TableDoc.math='off'`` is the document-level escape hatch for
hand-authored IR. See ``src/greater_tables/mathspans.py`` for the rule.
"""

import pandas as pd
import pytest

from greater_tables import TableDoc, TableSpec, build
from greater_tables.ir import Cell, Column, HeadCell, Row
from greater_tables.mathspans import MATH_RE, segments, whole_cell
from greater_tables.render.html import render_html
from greater_tables.render.text import render_text
from greater_tables.render.textlength import display_milli, math_milli
from greater_tables.render.tikz import render_tikz
from greater_tables.render.tikz_layout import cell_tex, tex_escape
from greater_tables.spec import HouseStyle


# ---------------------------------------------------------------- [rule]

@pytest.mark.parametrize('text, spans', [
    ('this $x^2$ is a formula and $10 is an amount.', ['$x^2$']),
    ('$10 to $20', []),
    ('$5-$10', []),
    ('costs $5-$10 and $x^2$ too', ['$x^2$']),
    (r'a 50% cut with $\alpha$ inside', [r'$\alpha$']),
    (r'display $$\int_0^1 f$$ here', [r'$$\int_0^1 f$$']),
    (r'escaped \$100 and $y=1$', ['$y=1$']),
    ('$ loose $', []),
    (r'$\psi(u)$', [r'$\psi(u)$']),
    ('$x$2', []),                       # digit after close reads as currency
    ('$x$, $y$', ['$x$', '$y$']),
    ('$a+b$: total', ['$a+b$']),
    (r'rate ($\lambda$)', [r'$\lambda$']),
    ('$E[X]$ and $E[X^2]$', ['$E[X]$', '$E[X^2]$']),
    ('cost in $ (USD)', []),
    ('50% of $total', []),
    (r'$f(x)=\$3$', []),                # \$ inside math is unsupported
    ('$x\\$', []),                      # trailing backslash would break TeX
])
def test_rule_spans(text, spans):
    assert [m.group(0) for m in MATH_RE.finditer(text)] == spans


@pytest.mark.parametrize('text, inner', [
    (r'$\psi(u)$', r'\psi(u)'),
    ('$$x$$', 'x'),                     # display accepted, delimiters gone
    ('$ loose $', None),
    ('$x $', None),
    ('$x\\$', None),
    ('plain', None),
    ('$a$ $b$', None),                  # two spans are not one whole cell
])
def test_whole_cell(text, inner):
    assert whole_cell(text) == inner


def test_segments_unescape_dollar():
    assert list(segments(r'escaped \$100 and $y=1$')) == \
        [(False, 'escaped $100 and '), (True, 'y=1')]
    # no math: one prose run, still unescaped
    assert list(segments(r'flat \$5 fee')) == [(False, 'flat $5 fee')]
    assert list(segments('')) == [(False, '')]


# -------------------------------------------------- [matrix] location x form

@pytest.fixture(scope='module')
def matrix_doc():
    df = pd.DataFrame({
        r'formula $f(x)$': [r'$\psi(u)$', r'ruin $\psi(u)$ falls'],
        r'$\beta$': ['plain', 'x'],
    }, index=pd.Index([r'case $\alpha$', 'b'], name=r'label $\ell$'))
    return build(df, TableSpec(caption=r'cap $x^2$ end',
                               notes=[r'note $\sigma$ here']))


def test_matrix_build_flags(matrix_doc):
    head = matrix_doc.head[0]
    assert [hc.math for hc in head] == [False, False, True]
    assert head[2].text == r'\beta'             # whole-cell header stripped
    assert head[1].text == r'formula $f(x)$'    # inline header kept verbatim
    body0 = matrix_doc.body[0].cells
    assert body0[1].math and body0[1].text == r'\psi(u)'


def test_matrix_tikz(matrix_doc):
    tex = render_tikz(matrix_doc)
    assert r'$\beta$' in tex                    # header, whole-cell
    assert 'formula $f(x)$' in tex              # header, inline
    assert 'case $\\alpha$' in tex              # stub, inline
    assert 'ruin $\\psi(u)$ falls' in tex       # body, inline
    assert 'cap $x^2$ end' in tex               # caption
    assert 'note $\\sigma$ here' in tex         # notes


def test_matrix_html(matrix_doc):
    html = render_html(matrix_doc, css='none')
    for tex in (r'\(f(x)\)', r'\(\beta\)', r'\(\alpha\)', r'\(\psi(u)\)',
                r'\(x^2\)', r'\(\sigma\)'):
        assert tex in html
    assert '<span class="gt-math">' in html


def test_matrix_text(matrix_doc):
    text = render_text(matrix_doc)
    assert r'$\beta$' in text                   # math header regains its $s
    assert r'ruin $\psi(u)$ falls' in text      # inline shown verbatim


# ------------------------------------------------------------- [currency]

def test_currency_never_math():
    df = pd.DataFrame({'price': ['$10 to $20', '$5-$10', '50% off_now']})
    doc = build(df)
    assert not any(c.math for row in doc.body
                   for c in row.cells if isinstance(c, Cell))
    tex = render_tikz(doc)
    assert r'\$10 to \$20' in tex
    assert r'\$5-\$10' in tex
    assert r'50\% off\_now' in tex
    html = render_html(doc, css='none')
    assert '$10 to $20' in html
    assert 'gt-math' not in html.split('<tbody>')[1]


# -------------------------------------------------------- [escaped-dollar]

def test_escaped_dollar_end_to_end():
    doc = build(pd.DataFrame({'c': [r'escaped \$100 and $y=1$']}))
    tex = render_tikz(doc)
    assert r'escaped \$100 and $y=1$' in tex    # \$ literal, $y=1$ math
    html = render_html(doc, css='none')
    assert 'escaped $100 and <span class="gt-math">' in html
    # the text oracle shows IR text verbatim, escape included
    assert r'escaped \$100 and $y=1$' in render_text(doc)


# --------------------------------------------------------------- [off-doc]

def _ticker_doc(math):
    col = Column(key='c0', name=('t',), dtype='string', align='l')
    return TableDoc(math=math, n_stub_levels=0, n_head_levels=1,
                    columns=(col,),
                    head=((HeadCell(text='$AB$ $CD$'),),),
                    body=(Row(cells=('$AB$ $CD$',)),),
                    caption='$AB$ $CD$', notes=('$AB$ $CD$',))


def test_off_doc_dollars_are_literal():
    doc = _ticker_doc('off')
    tex = render_tikz(doc)
    assert tex.count(r'\$AB\$ \$CD\$') >= 4     # head, body, caption, note
    html = render_html(doc, css='none')
    assert 'gt-math' not in html
    assert '$AB$ $CD$' in html
    assert '$AB$ $CD$' in render_text(doc)


def test_auto_doc_same_ir_is_math():
    tex = render_tikz(_ticker_doc('auto'))
    assert '$AB$ $CD$' in tex                   # re-emitted as math spans


def test_off_doc_explicit_flag_still_honored():
    # 'off' stops detection, not the explicit math flag
    col = Column(key='c0', name=('t',), dtype='string', align='l')
    doc = TableDoc(math='off', n_stub_levels=0, n_head_levels=0,
                   columns=(col,), head=(),
                   body=(Row(cells=(Cell(text=r'\psi(u)', math=True),)),))
    assert r'$\psi(u)$' in render_tikz(doc)


def test_spec_math_is_gone():
    with pytest.raises(TypeError):
        TableSpec(math='off')


# --------------------------------------------------------------- [measure]

def test_estimator_agrees_with_renderer():
    # the 6.x split brain: estimator saw '$10 to $20' as math, renderers
    # escaped it — same rule now, so a mixed cell measures as it renders
    literal = display_milli('$10 to $20', math=False)
    assert display_milli('$10 to $20') == literal
    mixed = display_milli(r'a $x$ b')
    prose = display_milli('a ') + display_milli(' b')
    assert mixed == prose + math_milli('x')


def test_tex_escape_segments():
    assert tex_escape(r'a $x_1$ b_2') == r'a $x_1$ b\_2'
    assert tex_escape('$10 to $20') == r'\$10 to \$20'
    assert tex_escape('$10 to $20', math=False) == r'\$10 to \$20'
    assert tex_escape(r'50% and $\alpha$') == r'50\% and $\alpha$'


def test_cell_tex_html_cells_never_segment():
    cell = Cell(text='<b>$5 and $9</b>', html=True)
    assert cell_tex(cell) == r'\$5 and \$9'
