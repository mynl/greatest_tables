"""Text-oracle tests: golden text per fixture plus semantic visibility spots."""

from pathlib import Path

import pytest

from greater_tables import build, render_text

from exemplars import EXEMPLARS
from registry import fixtures

GOLDEN_TEXT = Path(__file__).parent / 'golden' / 'text'
FIX = fixtures()


@pytest.mark.parametrize('name', sorted(FIX))
def test_text_golden(name):
    data, spec = FIX[name]
    assert render_text(build(data, spec)) == \
        (GOLDEN_TEXT / f'{name}.txt').read_text(encoding='utf-8')


def test_break_rules_visible():
    """A 2-level row MI draws partial rules at outer-level changes."""
    text = render_text(build(*FIX['row-mi-2']))
    assert '─' in text


def test_plain_has_no_internal_rules():
    text = render_text(build(*FIX['plain']))
    assert '─' not in text


def test_total_gutter():
    text = render_text(build(*FIX['totals']))
    assert '«total»' in text


def test_math_marked():
    text = render_text(build(*FIX['math-html']))
    assert r'$\alpha+\beta$' in text


def test_exemplar_renders():
    """The rich hand exemplar renders without error and shows its caption."""
    text = render_text(EXEMPLARS['loss-dev']())
    assert 'Loss development by year {#tbl-loss-dev}' in text
    assert '«total»' in text
