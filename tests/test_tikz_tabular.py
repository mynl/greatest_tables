"""One-node tabular TikZ engine: goldens, structural invariants, compile.

The invariant that earns its own tests is **bottom-aligned headers**. A
``p{}`` column is top aligned, so every header cell has to restate itself as
``b{}``; get it wrong and the table still compiles, still looks plausible in
isolation, and is wrong on every page. It is checked here mechanically rather
than by eye.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from greater_tables import (
    Etcher, HouseStyle, TableDoc, TableSpec, build, render_tikz,
)
from greater_tables.render.tikz import table_width
from greater_tables.render.tikz_tabular import W2RULE, render_tikz_tabular

from exemplars import EXEMPLARS

ROOT = Path(__file__).parent.parent
IR = ROOT / 'tests' / 'golden' / 'ir'
GOLDEN = ROOT / 'tests' / 'golden' / 'tikz-tabular'
NAMES = sorted(p.stem for p in IR.glob('*.json'))
TECTONIC = shutil.which('tectonic')

TABULAR = HouseStyle(tikz_engine='tabular')

_ROW_RE = re.compile(r'^(.*?)\s*\\\\$')
_MULTI_RE = re.compile(r'\\multicolumn\{(\d+)\}\{([^{]*(?:\{[^}]*\}[^{]*)*)\}')


def load(name: str) -> TableDoc:
    return TableDoc.read((IR / f'{name}.json').read_bytes())


def tabular(tex: str) -> str:
    """The tabular body: everything between \\begin{tabular} and \\end."""
    start = tex.index('\\begin{tabular}')
    return tex[tex.index('\n', start) + 1:tex.index('\\end{tabular}')]


def body_rows(tex: str) -> list[str]:
    """Every content row (rules and preamble excluded), \\\\ stripped."""
    return [m.group(1) for m in
            (_ROW_RE.match(line.strip()) for line in tabular(tex).split('\n'))
            if m]


def head_rows(doc: TableDoc, tex: str) -> list[str]:
    return body_rows(tex)[:len(doc.head)]


def cells(row: str) -> list[str]:
    """Split a row on its separators. A literal ampersand in cell text is
    escaped, so an unescaped & is always a separator."""
    return [c.strip() for c in re.split(r'(?<!\\)&', row)]


# ------------------------------------------------------------------ goldens

@pytest.mark.parametrize('name', NAMES)
def test_tabular_golden(name):
    assert render_tikz(load(name), TABULAR) == \
        (GOLDEN / f'{name}.tex').read_text(encoding='utf-8')


def test_render_tikz_is_the_tabular():
    """render_tikz is the tabular emitter, and tikz_engine='matrix', retired
    in 8.0.0, renders the same table."""
    doc = load('loss-dev')
    assert render_tikz(doc) == render_tikz(doc, HouseStyle())
    assert render_tikz(doc) == render_tikz(doc, TABULAR)
    assert render_tikz(doc, TABULAR) == render_tikz_tabular(doc, TABULAR)
    assert render_tikz(doc, HouseStyle(tikz_engine='matrix')) == \
        render_tikz(doc, TABULAR)


def test_empty_table_is_a_comment():
    assert render_tikz(load('fx-empty'), TABULAR).startswith('% greater_tables')


# ----------------------------------------------- the bottom-alignment rule

@pytest.mark.parametrize('name', NAMES)
def test_every_header_cell_is_bottom_aligned(name):
    """b{} in every header cell, and never p{} — p{} is top aligned, which is
    the one thing this renderer may not do."""
    doc = load(name)
    if not doc.columns or not doc.head:
        pytest.skip('no header')
    tex = render_tikz(doc, TABULAR)
    seen = 0
    for row in head_rows(doc, tex):
        for cell in cells(row):
            if not cell:
                continue                      # an empty cell aligns nothing
            assert '\\multicolumn' in cell, f'{name}: bare header cell {cell!r}'
            spec = _MULTI_RE.search(cell).group(2)
            assert 'b{' in spec, f'{name}: header cell is not b{{}}: {cell!r}'
            assert 'p{' not in spec, f'{name}: header cell is p{{}}: {cell!r}'
            seen += 1
    assert seen, f'{name}: no header cells checked'


@pytest.mark.parametrize('name', NAMES)
def test_header_alignment_is_centered_not_the_column(name):
    """Headers are centered (stubs flush left) whatever the column align is,
    as they always have been; this is a convention to hold, not a defect to
    'fix'."""
    doc = load(name)
    if not doc.columns or not doc.head:
        pytest.skip('no header')
    tex = render_tikz(doc, TABULAR)
    for row in head_rows(doc, tex):
        for cell in cells(row):
            if not cell:
                continue
            spec = _MULTI_RE.search(cell).group(2)
            # a stub header is the bold-italic one; everything else centers
            want = ('raggedright' if '\\itshape' in cell else 'centering')
            assert want in spec, f'{name}: header wants {want}: {cell!r}'
            assert 'raggedleft' not in spec, \
                f'{name}: header took the column align: {cell!r}'


def test_header_alignment_ignores_a_right_aligned_column():
    """The explicit case: a column of numbers still gets a centered heading."""
    doc = build(pd.DataFrame({'Amount': [1.5, 2.5]}), TableSpec(show_index=False))
    tex = render_tikz(doc, TABULAR)
    assert doc.columns[0].align == 'r'
    assert 'raggedleft\\arraybackslash}p{' in tex          # the body column
    assert 'centering\\arraybackslash}b{' in tabular(tex)  # the header cell


def test_header_rows_carry_the_strut():
    tex = render_tikz(load('loss-dev'), TABULAR)
    assert '\\providecommand{\\gtheadstrut}{\\rule[' in tex
    for row in head_rows(load('loss-dev'), tex):
        assert '\\gtheadstrut' in row


# ------------------------------------------------------------- structure

@pytest.mark.parametrize('name', NAMES)
def test_every_row_accounts_for_every_column(name):
    """Cells plus multicolumn spans must total ncols on every row, or the
    tabular silently shifts and the rules stop matching the columns."""
    doc = load(name)
    if not doc.columns:
        pytest.skip('empty')
    tex = render_tikz(doc, TABULAR)
    for row in body_rows(tex):
        total = sum(int(_MULTI_RE.search(c).group(1))
                    if '\\multicolumn' in c else 1
                    for c in cells(row))
        assert total == len(doc.columns), \
            f'{name}: row spans {total} of {len(doc.columns)} columns: {row!r}'


@pytest.mark.parametrize('name', NAMES)
def test_cmidrule_ranges_are_in_bounds(name):
    doc = load(name)
    if not doc.columns:
        pytest.skip('empty')
    tex = render_tikz(doc, TABULAR)
    for a, b in re.findall(r'\\cmidrule(?:\[[^]]*\])?(?:\([^)]*\))?'
                           r'\{(\d+)-(\d+)\}', tex):
        assert 1 <= int(a) <= int(b) <= len(doc.columns), \
            f'{name}: cmidrule {a}-{b} outside 1..{len(doc.columns)}'


def test_spanner_becomes_multicolumn_and_cmidrule():
    doc = EXEMPLARS['loss-dev']()
    tex = render_tikz(doc, TABULAR)
    assert '\\multicolumn{2}{' in tex and 'Group A' in tex
    assert re.search(r'\\cmidrule\[[\d.]+pt\]\{3-4\}', tex)   # over Group A
    assert '!0.5!' not in tex                  # no overlay nodes in this engine


def test_body_colspan_is_a_multicolumn():
    """A spanning body cell centers on its span."""
    tex = render_tikz(EXEMPLARS['loss-dev'](), TABULAR)
    span = next(c for c in cells(body_rows(tex)[-1]) if 'Total' in c)
    assert span.startswith('\\multicolumn{2}{')
    spec = _MULTI_RE.search(span).group(2)
    assert 'centering' in spec and 'p{' in spec and 'b{' not in spec


def test_numbers_sit_in_a_box_of_the_column_width():
    """A cell of a column that does not wrap is boxed at the column's width,
    so it cannot break; prose and headers are left to wrap."""
    df = pd.DataFrame({'note': ['a short note', 'another'], 'err': [-1.95e-05, 3.2e-06]})
    doc = build(df, TableSpec(show_index=False, formatters={'err': '.2e'}))
    tex = render_tikz(doc, TABULAR)
    note_w, err_w = re.findall(r'p\{([\d.]+)em\}', tex)[:2]
    head, *rows = body_rows(tex)
    assert 'makebox' not in head
    for row in rows:
        note, err = cells(row)
        assert 'makebox' not in note
        assert err.startswith(f'\\makebox[{err_w}em][r]{{')
    assert note_w != err_w


def test_macros_travel_with_the_picture():
    """Both macros sit inside the tikzpicture, so lifting the picture alone
    still carries them, and a host document need not define \\I."""
    tex = render_tikz(load('loss-dev'), TABULAR)
    picture = tex[tex.index('\\begin{tikzpicture}'):]
    assert '\\providecommand{\\I}{\\vphantom{lp}}' in picture
    assert '\\providecommand{\\gtheadstrut}' in picture


def test_rule_spacing_is_zeroed():
    """booktabs' rule spacing would make table height depend on rule count."""
    tex = render_tikz(load('fx-deep-stub'), TABULAR)
    for length in ('aboverulesep', 'belowrulesep', 'cmidrulesep'):
        assert f'\\setlength{{\\{length}}}{{0pt}}' in tex


def test_rule_weights_match_the_pgf_ladder():
    """Same house weight, same drawn width in a booktabs rule and a TikZ
    vertical."""
    from greater_tables.render.tikz_layout import W2TIKZ
    assert set(W2RULE) == set(W2TIKZ)
    assert W2RULE[0] is None and W2TIKZ[0] is None
    widths = [float(W2RULE[k][:-2]) for k in sorted(W2RULE) if W2RULE[k]]
    assert widths == sorted(widths)            # heavier weight, wider rule


def test_coincident_break_and_total_rules_merge():
    """A break rule and a total rule on one row are one rule; consecutive
    booktabs rules would stack, so they merge to one heavier rule."""
    doc = load('fx-totals')
    tex = render_tikz(doc, TABULAR)
    lines = [ln.strip() for ln in tabular(tex).split('\n')]
    for a, b in zip(lines, lines[1:]):
        assert not (a.startswith(('\\midrule', '\\cmidrule'))
                    and b.startswith(('\\midrule', '\\cmidrule'))
                    and '{' in a and 'cmidrule' not in a), \
            f'stacked rules: {a!r} then {b!r}'


# ------------------------------------------------------------------ geometry

def widths_of(tex: str) -> list[float]:
    """Column widths from the tabular preamble (multicolumn specs excluded)."""
    start = tex.index('\\begin{tabular}{')
    spec = tex[start:tex.index('\n', start)]
    return [float(w) for w in re.findall(r'p\{([\d.]+)em\}', spec)]


@pytest.mark.parametrize('name', NAMES)
def test_vertical_rules_land_on_column_boundaries(name):
    """Every vertical rule sits half a column separation left of some column
    edge."""
    doc = load(name)
    if not doc.columns:
        pytest.skip('empty')
    style = TABULAR
    tex = render_tikz(doc, style)
    widths = widths_of(tex)
    csep, gap = style.tikz_column_sep, style.tikz_column_sep / 2
    edges = {0.0 - gap}
    x = csep
    for j, wd in enumerate(widths):
        edges.add(x - gap)                     # left edge of column j+1
        x += wd + (2 * csep if j == 0 else csep)
    edges.add(csep + widths[0] + csep + gap)   # the stub rule, past column 1
    if len(widths) > 1:
        x = csep + widths[0] + 2 * csep
        for j, wd in enumerate(widths[1:], start=1):
            edges.add(x + wd + gap)
            x += wd + csep
    for value in re.findall(r'xshift=(-?[\d.]+)em', tex):
        assert any(abs(float(value) - e) < 0.02 for e in edges), \
            f'{name}: rule at {value}em matches no column boundary'


@pytest.mark.parametrize('name', ['fx-wrap-low', 'fx-wrap-high', 'fx-tex',
                                  'fx-both-mi', 'loss-dev', 'fx-plain'])
@pytest.mark.parametrize('budget', [45, 38, 30, 24])
def test_budget_is_never_exceeded(name, budget, caplog):
    """The one hard promise: narrow, then scale, but do not overrun."""
    style = HouseStyle(max_table_width_em=budget)
    tex = render_tikz(load(name), style)
    if 'ladder stops' in caplog.text:
        return              # the documented dead end: reported, not silent
    scale = float(re.search(r'scale=([\d.]+)\]', tex).group(1))
    milli = [round(w * 1000) for w in widths_of(tex)]
    total = table_width(
        milli, scale, len(milli), round(style.tikz_column_sep * 1000)) / 1000
    assert total <= budget + 0.05, f'{name} at {budget}em came out {total}em'


# -------------------------------------------------------------------- compile

@pytest.fixture(scope='session')
def tex_dir(tmp_path_factory):
    return tmp_path_factory.mktemp('tex-tabular')


@pytest.mark.skipif(TECTONIC is None, reason='tectonic not available')
@pytest.mark.parametrize('name', ['loss-dev', 'fx-both-mi', 'fx-wide-floats',
                                  'fx-tex', 'fx-deep-stub', 'fx-inline-math'])
def test_compiles(name, tex_dir):
    pdf = Etcher(render_tikz(load(name), TABULAR), base_path=tex_dir).compile()
    assert pdf.exists() and pdf.stat().st_size > 1000


# the packages the quickstart names, and nothing else: no TikZ library, no
# \I in the preamble
BARE_DOC = r"""\documentclass{article}
\usepackage{booktabs}\usepackage{array}\usepackage{tikz}
\begin{document}
%s
\end{document}
"""


@pytest.mark.skipif(TECTONIC is None, reason='tectonic not available')
def test_compiles_with_only_tikz_booktabs_and_array(tmp_path):
    """Spanners, a stub rule, math and a total row, in the bare preamble."""
    src = tmp_path / 'bare.tex'
    src.write_text(BARE_DOC % render_tikz(load('loss-dev')), encoding='utf-8')
    run = subprocess.run([TECTONIC, '--outdir', str(tmp_path), str(src)],
                         capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr[-2000:]
    assert (tmp_path / 'bare.pdf').stat().st_size > 1000
