"""Text-oracle tests: golden text per fixture plus semantic visibility spots."""

from pathlib import Path

import pytest

from greater_tables import HouseStyle, build, render_text

from exemplars import EXEMPLARS
from registry import fixtures

GOLDEN_TEXT = Path(__file__).parent / 'golden' / 'text'
GOLDEN_ASCII = Path(__file__).parent / 'golden' / 'text-ascii'
FIX = fixtures()
ASCII_STYLE = HouseStyle(text_ascii_rules=True)


@pytest.mark.parametrize('name', sorted(FIX))
def test_text_golden(name):
    data, spec = FIX[name]
    assert render_text(build(data, spec)) == \
        (GOLDEN_TEXT / f'{name}.txt').read_text(encoding='utf-8')


@pytest.mark.parametrize('name', sorted(FIX))
def test_ascii_golden(name):
    data, spec = FIX[name]
    assert render_text(build(data, spec), ASCII_STYLE) == \
        (GOLDEN_ASCII / f'{name}.txt').read_text(encoding='utf-8')


@pytest.mark.parametrize('name', sorted(FIX))
def test_ascii_mode_draws_no_unicode(name):
    """The flag's promise: no rule or marker the renderer draws is non-ASCII."""
    data, spec = FIX[name]
    text = render_text(build(data, spec), ASCII_STYLE)
    assert not (set(text) & set('━─│«»'))


@pytest.mark.parametrize('name,survivor', [('nulls', '—'), ('wide-floats', 'µ')])
def test_ascii_mode_does_not_launder_cell_text(name, survivor):
    """The limit, asserted so it stays deliberate rather than accidental.

    ``text_ascii_rules`` swaps what the *renderer* draws. Cell text arrives
    already formatted from the IR, and two engine choices are non-ASCII:
    ``FormatSpec.null`` (an em dash) and the SI suffix ladder (µ). Rewriting
    either here would make the oracle disagree with the document it checks —
    change ``FormatSpec`` if a build must be pure ASCII end to end.
    """
    text = render_text(build(*FIX[name]), ASCII_STYLE)
    assert survivor in text and not text.isascii()
    assert not (set(text) & set('━─│«»'))       # but no drawn character


@pytest.mark.parametrize('name', sorted(FIX))
def test_default_unchanged_by_the_new_field(name):
    """HouseStyle() and no style at all must still agree — a10 changed nothing."""
    data, spec = FIX[name]
    doc = build(data, spec)
    assert render_text(doc) == render_text(doc, HouseStyle())


def test_ascii_keeps_heavy_light_distinction():
    """`=` frame against `-` break: collapsing both would lose the semantics."""
    text = render_text(build(*FIX['row-mi-2']), ASCII_STYLE)
    assert '=' * 10 in text and '-' * 10 in text
    assert '|' in text


def test_ascii_total_gutter():
    assert '<<total>>' in render_text(build(*FIX['totals']), ASCII_STYLE)


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
