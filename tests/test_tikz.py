"""TikZ renderer: golden .tex files, structural checks, compile smoke test."""

import shutil
from pathlib import Path

import pytest

from greatest_tables import Etcher, TableDoc, render_tikz

from exemplars import EXEMPLARS

ROOT = Path(__file__).parent.parent
IR = ROOT / 'tests' / 'golden' / 'ir'
GOLDEN = ROOT / 'tests' / 'golden' / 'tikz'
NAMES = sorted(p.stem for p in IR.glob('*.json'))
TECTONIC = shutil.which('tectonic')


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
