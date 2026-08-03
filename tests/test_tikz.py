"""TikZ renderer: golden .tex files, structural checks, compile smoke test."""

import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from greater_tables import (
    Etcher, HouseStyle, TableDoc, TableSpec, build, render_tikz,
)
from greater_tables.render.textlength import (
    _WIDTH_TABLE, text_display_len, token_display_len,
)

from exemplars import EXEMPLARS

ROOT = Path(__file__).parent.parent
IR = ROOT / 'tests' / 'golden' / 'ir'
GOLDEN = ROOT / 'tests' / 'golden' / 'tikz'
NAMES = sorted(p.stem for p in IR.glob('*.json'))
TECTONIC = shutil.which('tectonic')


def widths(tikz: str) -> list[float]:
    """The emitted column text widths, in ems (the trailing rail excluded)."""
    return [float(w) for w in re.findall(r'text width=([\d.]+)em', tikz)][:-1]


@pytest.mark.parametrize('name', NAMES)
def test_tikz_golden(name):
    doc = TableDoc.read((IR / f'{name}.json').read_bytes())
    assert render_tikz(doc) == \
        (GOLDEN / f'{name}.tex').read_text(encoding='utf-8')


def test_structure_loss_dev():
    """Spanners, stub rule, math, and break rules all present."""
    tikz = render_tikz(EXEMPLARS['loss-dev']())
    assert '\\matrix (gt' in tikz
    assert 'Group A' in tikz and '!0.5!' in tikz     # colspan overlay midpoint
    assert tikz.count('!0.5!') == 2                  # Group A + Total spanners
                                                     # (blank spans don't overlay)
    assert '\\caption{Loss development by year}\\label{tbl-loss-dev}' in tikz
    assert '\\path[draw, semithick]' in tikz         # frame/head/stub rules


def test_math_and_escaping():
    tikz = render_tikz(EXEMPLARS['minimal']())
    assert '$\\psi(u) = \\Pr(U_t < 0)$' in tikz      # math re-wrapped
    assert '<a href' not in tikz                     # html stripped for TeX


def test_nbsp_becomes_tie():
    doc = TableDoc.read((IR / 'fx-wide-floats.json').read_bytes())
    tikz = render_tikz(doc)
    assert chr(0xa0) not in tikz                     # NBSP → ~ tie
    assert '~' in tikz


def test_header_measured_by_widest_word():
    """A long heading wraps; it must not stretch its column of numbers."""
    doc = build(pd.DataFrame({'Cumulative Incurred Loss': [1.5, 2.5]}),
                TableSpec(show_index=False))
    (width,) = widths(render_tikz(doc))
    assert text_display_len('Cumulative') <= width
    assert width < text_display_len('Cumulative Incurred Loss')


def test_spanner_label_widens_its_group():
    """An overlaid group label carries no text width, so it cannot wrap."""
    label = 'A Notably Long Group Label'
    doc = build(pd.DataFrame({(label, 'x'): [1.0], (label, 'y'): [2.0]}),
                TableSpec(show_index=False))
    tikz = render_tikz(doc)
    style = HouseStyle()
    # the span covers both columns plus the separation between them
    assert sum(widths(tikz)) + style.tikz_column_sep \
        >= text_display_len(label)


def test_alignment_is_flush():
    """Balanced ragged ('align=left') breaks lines that fit their column;
    only the flush variants honor the width estimates this renderer makes."""
    tikz = render_tikz(EXEMPLARS['loss-dev']())
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
    for ch in '—%µ−…':
        assert ch in _WIDTH_TABLE, f'{ch!r} falls back to the default width'


@pytest.fixture(scope='session')
def tex_dir(tmp_path_factory):
    """Shared compile dir so the TeX .fmt file builds once per session."""
    return tmp_path_factory.mktemp('tex')


@pytest.mark.skipif(TECTONIC is None, reason='tectonic not available')
@pytest.mark.parametrize('name', ['loss-dev', 'fx-both-mi', 'fx-wide-floats',
                                  'fx-tex'])
def test_compiles(name, tex_dir):
    doc = TableDoc.read((IR / f'{name}.json').read_bytes())
    pdf = Etcher(render_tikz(doc), base_path=tex_dir).compile()
    assert pdf.exists() and pdf.stat().st_size > 1000
