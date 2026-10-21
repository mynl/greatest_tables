"""Matrix TikZ renderer: golden .tex files, structural checks, compile smoke
test. The default engine is ``'tabular'`` (6.2.0), so every render here asks
for ``MATRIX`` explicitly; ``test_tikz_tabular.py`` covers the default."""

import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from greater_tables import (
    Etcher, HouseStyle, TableDoc, TableSpec, build, render_tikz,
)
from greater_tables.render import tikz as _tikz
from greater_tables.render import tikz_layout
from greater_tables.render.fonts import FACES
from greater_tables.render.textlength import (
    text_display_len, token_display_len,
)

from exemplars import EXEMPLARS
from registry import fixtures

ROOT = Path(__file__).parent.parent
IR = ROOT / 'tests' / 'golden' / 'ir'
GOLDEN = ROOT / 'tests' / 'golden' / 'tikz'
NAMES = sorted(p.stem for p in IR.glob('*.json'))
TECTONIC = shutil.which('tectonic')

MATRIX = HouseStyle(tikz_engine='matrix')
FIXTURES = fixtures()


def widths(tikz: str) -> list[float]:
    """The emitted column text widths, in ems (the trailing rail excluded)."""
    return [float(w) for w in re.findall(r'text width=([\d.]+)em', tikz)][:-1]


@pytest.mark.parametrize('name', NAMES)
def test_tikz_golden(name):
    doc = TableDoc.read((IR / f'{name}.json').read_bytes())
    assert render_tikz(doc, MATRIX) == \
        (GOLDEN / f'{name}.tex').read_text(encoding='utf-8')


def test_structure_loss_dev():
    """Spanners, stub rule, math, and break rules all present."""
    tikz = render_tikz(EXEMPLARS['loss-dev'](), MATRIX)
    assert '\\matrix (gt' in tikz
    assert 'Group A' in tikz and '!0.5!' in tikz     # colspan overlay midpoint
    assert tikz.count('!0.5!') == 2                  # Group A + Total spanners
                                                     # (blank spans don't overlay)
    assert '\\caption{Loss development by year}\\label{tbl-loss-dev}' in tikz
    assert '\\path[draw, semithick]' in tikz         # frame/head/stub rules


def test_math_and_escaping():
    tikz = render_tikz(EXEMPLARS['minimal'](), MATRIX)
    assert '$\\psi(u) = \\Pr(U_t < 0)$' in tikz      # math re-wrapped
    assert '<a href' not in tikz                     # html stripped for TeX


def test_nbsp_becomes_tie():
    doc = TableDoc.read((IR / 'fx-wide-floats.json').read_bytes())
    tikz = render_tikz(doc, MATRIX)
    assert chr(0xa0) not in tikz                     # NBSP → ~ tie
    assert '~' in tikz


def test_header_measured_by_widest_word():
    """A long heading wraps; it must not stretch its column of numbers."""
    doc = build(pd.DataFrame({'Cumulative Incurred Loss': [1.5, 2.5]}),
                TableSpec(show_index=False))
    (width,) = widths(render_tikz(doc, MATRIX))
    assert text_display_len('Cumulative') <= width
    assert width < text_display_len('Cumulative Incurred Loss')


def test_spanner_label_widens_its_group():
    """An overlaid group label carries no text width, so it cannot wrap."""
    label = 'A Notably Long Group Label'
    doc = build(pd.DataFrame({(label, 'x'): [1.0], (label, 'y'): [2.0]}),
                TableSpec(show_index=False))
    tikz = render_tikz(doc, MATRIX)
    # the span covers both columns plus the separation between them
    assert sum(widths(tikz)) + MATRIX.tikz_column_sep \
        >= text_display_len(label)


def test_bold_rows_are_measured_bold():
    """A subtotal label sets bold, wider than its roman estimate; its column
    must hold the bold width, while bold digits keep their roman width."""
    df = pd.DataFrame({'line': ['Auto', 'Marine', 'Subtotal'],
                       'paid': [861054, 137763, 998817]})
    doc = build(df, TableSpec(show_index=False, row_flags={-1: ('subtotal',)}))
    line, paid = widths(render_tikz(doc, MATRIX))
    assert line >= text_display_len('Subtotal', bold=True) >         text_display_len('Subtotal')
    assert text_display_len('998,817', bold=True) == text_display_len('998,817')
    assert paid == pytest.approx(text_display_len('998,817') + 0.1, abs=0.01)


def test_alignment_is_flush():
    """Balanced ragged ('align=left') breaks lines that fit their column;
    only the flush variants honor the width estimates this renderer makes."""
    tikz = render_tikz(EXEMPLARS['loss-dev'](), MATRIX)
    assert 'align=flush' in tikz
    assert re.search(r'align=(?!flush)', tikz) is None


def test_token_width_is_the_widest_word():
    assert token_display_len('short longestword mid') == \
        text_display_len('longestword')


def test_token_width_treats_math_as_one_token():
    """Math sets as a box: it has no interword breakpoint to wrap at."""
    assert token_display_len(r'a $\alpha + \beta$ b') == \
        text_display_len(r'$\alpha + \beta$')


def test_glyph_table_covers_table_furniture():
    """The characters a real table leans on must not take the 600 default."""
    for name, face in FACES.items():
        for ch in '—%µ−…':
            assert ch in face.roman and ch in face.bold,                 f'{name}: {ch!r} falls back to the default width'


def test_every_face_covers_the_same_glyphs():
    times = FACES['times'].roman.keys()
    for name, face in FACES.items():
        assert face.roman.keys() == times and face.bold.keys() == times, name


def test_unknown_face_fails_at_construction():
    with pytest.raises(ValueError, match='stix-two'):
        HouseStyle(tikz_font='stix two')


def test_face_sets_the_widths():
    """STIX Two sets lowercase wider than Times: its columns are wider, and
    the default face is Times, unchanged."""
    doc = load('fx-loss-lab')
    times = widths(render_tikz(doc, MATRIX))
    assert widths(render_tikz(doc, HouseStyle(tikz_engine='matrix',
                                              tikz_font='times'))) == times
    stix = widths(render_tikz(doc, HouseStyle(tikz_engine='matrix',
                                             tikz_font='stix-two')))
    assert stix[1] > times[1]           # the unit column: 'Unit 1'


# ------------------------------------------------------- max_table_width_em

def emitted(doc, budget, tikz_scale=1.0):
    """Render at a budget; return (predicted width em, scale, column widths)."""
    style = HouseStyle(tikz_engine='matrix', max_table_width_em=budget,
                       tikz_scale=tikz_scale)
    tikz = render_tikz(doc, style)
    cols = widths(tikz)
    scale = float(re.search(r'scale=([\d.]+),', tikz).group(1))
    milli = [round(w * 1000) for w in cols]
    total = _tikz.table_width(milli, scale, len(doc.columns),
                             round(style.tikz_column_sep * 1000))
    return total / 1000, scale, cols


def load(name):
    return TableDoc.read((IR / f'{name}.json').read_bytes())


@pytest.mark.parametrize('name', ['fx-wrap-low', 'fx-wrap-high', 'fx-tex',
                                  'fx-both-mi', 'loss-dev', 'fx-plain'])
@pytest.mark.parametrize('budget', [45, 38, 30, 24])
def test_budget_is_never_exceeded(name, budget, caplog):
    """The one hard promise: narrow, then scale, but do not overrun."""
    doc = load(name)
    total, _scale, _cols = emitted(doc, budget)
    if 'ladder stops' in caplog.text:
        return              # the documented dead end: reported, not silent
    assert total <= budget + 0.05, f'{name} at {budget}em came out {total}em'


@pytest.mark.parametrize('budget', [45, 41.4, 38, 30])
def test_budget_is_met_at_the_scale_ceiling(budget, caplog):
    """A 0.9 ceiling gives the columns the budget's room at 0.9, not at 1.0.

    Meeting the budget at full size and then setting the table at 0.9 used to
    narrow columns for width the table never took: the Loss Lab fixture's
    layer labels wrapped while a tenth of the line stood empty.
    """
    doc = load('fx-loss-lab')
    natural = widths(render_tikz(doc, MATRIX))
    total, scale, cols = emitted(doc, budget, tikz_scale=0.9)
    if 'ladder stops' in caplog.text:
        return              # the documented dead end: reported, not silent
    assert total <= budget + 0.05
    assert scale <= 0.9
    full = _tikz.table_width([round(w * 1000) for w in natural], 0.9,
                             len(doc.columns), 1000) / 1000
    if full <= budget:
        assert cols == natural          # fits at the ceiling: nothing narrows


def test_label_columns_hold_under_a_budget():
    """Short labels scale with the table rather than wrap to save an em.

    The Loss Lab fixture's stub labels are at most three words ("Portfolio
    A", "40M xs 10M"), so a budget that cannot be met at the ceiling scale
    steps the scale down and leaves those columns at their natural width.
    """
    doc = load('fx-loss-lab')
    natural = widths(render_tikz(doc, MATRIX))
    _total, scale, cols = emitted(doc, 34, tikz_scale=0.9)
    assert scale < 0.9
    assert cols[:3] == natural[:3]


def test_budget_narrows_prose_before_scaling():
    """Prose gives way first; the scale only moves once floors are reached."""
    doc = load('fx-wrap-low')
    wide, scale_wide, _ = emitted(doc, 45)
    assert scale_wide == 1.0            # narrowing alone was enough
    assert wide == pytest.approx(45, abs=0.1)   # and it used the budget


def test_budget_leaves_unbreakable_columns_alone():
    """An all-numeric table has nothing to narrow, so it scales instead."""
    doc = load('fx-both-mi')
    natural = widths(render_tikz(doc, MATRIX))
    _total, scale, cols = emitted(doc, 24)
    assert cols == natural              # every column untouched
    assert scale < 1.0                  # the table shrank as a whole


def test_budget_respects_the_longest_word():
    """A prose column may not be narrowed past a word it cannot hyphenate."""
    doc = load('fx-wrap-low')
    _total, _scale, cols = emitted(doc, 24)
    for col, width in zip(doc.columns, cols):
        if col.wrap:
            assert width >= 2.0


def test_budget_stops_narrowing_prose_at_its_minimum():
    """Past min_prose_width_em the table scales: at 24em, prose narrowed to
    its longest word used to set a word or two a line at full scale."""
    doc = load('fx-wrap-low')
    _total, scale, cols = emitted(doc, 24)
    for col, width in zip(doc.columns, cols):
        if col.wrap and col.role == 'data':
            assert width >= HouseStyle().min_prose_width_em
    # a minimum of 0 narrows to the longest word again, and scales less
    style = HouseStyle(tikz_engine='matrix', max_table_width_em=24, min_prose_width_em=0)
    narrowest = float(re.search(r'scale=([\d.]+),', render_tikz(doc, style)).group(1))
    assert scale < narrowest


def test_heading_lines_fill_greedily():
    lines = tikz_layout._heading_lines
    assert lines([3000, 2000, 2000], 250, 5250) == 2      # 3 | 2 2
    assert lines([3000, 2000, 2000], 250, 7500) == 1
    assert lines([3000, 2000, 2000], 250, 3000) == 3


def test_tallest_heading_drops_to_the_next_tallest():
    """Out of spare room, the one tallest heading widens until it is no
    taller than the next; ties and a full line leave everything alone."""
    balance, lines = tikz_layout._balance_headings, tikz_layout._heading_lines
    pad = tikz_layout._WIDTH_PAD
    short = [2000] * 4                                   # four lines at 2.1em
    tall = [2000] * 7                                    # seven lines
    widths = [2100, 2100]
    out = balance(widths, [short, tall], 250, 50_000)
    assert out[0] == 2100
    assert lines(tall, 250, out[1] - pad) == 4
    assert lines(tall, 250, out[1] - 1 - pad) > 4        # the least width that does it
    assert balance(widths, [tall, tall], 250, 50_000) == widths
    assert balance(widths, [short, tall], 250, 0) == widths
    # seven 1em words beside a two-line heading: the room holds three words a
    # line, not the four that two lines need, so three lines it is
    seven = [1000] * 7
    out = balance(widths, [[2000] * 2, seven], 250, 1500)
    assert out[1] == 3600 and lines(seven, 250, out[1] - pad) == 3


def test_budget_balances_long_headings():
    """The long-head-ratios fixture: a seven-line heading beside five-line
    ones drops to five under a budget; with no budget nothing moves."""
    data, spec = FIXTURES['long-head-ratios']
    doc = build(data, spec)
    style = HouseStyle(max_table_width_em=41.4, tikz_scale=0.9)
    natural = tikz_layout.layout(doc, HouseStyle(tikz_scale=0.9), tikz_layout.TABULAR_GEOMETRY)
    budgeted = tikz_layout.layout(doc, style, tikz_layout.TABULAR_GEOMETRY)
    grown = [b - n for b, n in zip(budgeted.widths, natural.widths)]
    assert sum(1 for g in grown if g > 0) == 1          # one column widened
    assert sum(budgeted.widths) > sum(natural.widths)


def test_no_budget_is_unchanged():
    doc = load('fx-wrap-low')
    assert render_tikz(doc, MATRIX) == \
        render_tikz(doc, HouseStyle(tikz_engine='matrix'))


def test_impossible_budget_errors_and_says_why(caplog):
    doc = load('fx-both-mi')
    with caplog.at_level('WARNING'):
        render_tikz(doc, HouseStyle(tikz_engine='matrix',
                                    max_table_width_em=6))
    assert 'ladder stops' in caplog.text
    assert 'sidewaystable' in caplog.text       # tells the user the way out
    # ERROR, so a caller that silences the routine ladder steps still sees it
    assert [r.levelname for r in caplog.records] == ['ERROR']


def test_ladder_step_is_only_a_warning(caplog):
    """A table the ladder brings inside its budget is the design working."""
    doc = load('fx-both-mi')
    with caplog.at_level('WARNING'):
        _total, scale, _cols = emitted(doc, 24)
    assert scale < 1.0
    assert [r.levelname for r in caplog.records] == ['WARNING']


@pytest.fixture(scope='session')
def tex_dir(tmp_path_factory):
    """Shared compile dir so the TeX .fmt file builds once per session."""
    return tmp_path_factory.mktemp('tex')


@pytest.mark.skipif(TECTONIC is None, reason='tectonic not available')
@pytest.mark.parametrize('name', ['loss-dev', 'fx-both-mi', 'fx-wide-floats',
                                  'fx-tex', 'fx-inline-math'])
def test_compiles(name, tex_dir):
    doc = TableDoc.read((IR / f'{name}.json').read_bytes())
    pdf = Etcher(render_tikz(doc, MATRIX), base_path=tex_dir).compile()
    assert pdf.exists() and pdf.stat().st_size > 1000
