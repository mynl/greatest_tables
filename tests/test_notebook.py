"""Mimebundle rules: target detection, exact key sets, caller override.

Key sets are asserted **exactly** — the whole point of the design is which
types are absent, so ``in`` assertions would not test it.
"""

import os

import pytest

from greater_tables import Fabricator
from greater_tables.engine.build import build
from greater_tables.render.notebook import (
    in_quarto, mimebundle, quarto_target, validate_mimes)


@pytest.fixture()
def doc():
    return build(Fabricator(seed=42).make(5, 'sf', index_levels=1))


@pytest.fixture()
def no_quarto(monkeypatch):
    """A clean environment — the developer machine may itself be in Quarto."""
    for key in [k for k in os.environ if k.startswith('QUARTO_')]:
        monkeypatch.delenv(key, raising=False)


# ------------------------------------------------------------------ detection

def test_no_quarto(no_quarto):
    assert in_quarto() is False and quarto_target() is None


def test_target_pdf(no_quarto, monkeypatch):
    monkeypatch.setenv('QUARTO_FIG_FORMAT', 'pdf')
    assert quarto_target() == 'pdf'


def test_target_png_is_other(no_quarto, monkeypatch):
    # html and gfm both report png — indistinguishable, hence 'other'
    monkeypatch.setenv('QUARTO_FIG_FORMAT', 'png')
    assert quarto_target() == 'other'


def test_target_quarto_without_fig_format(no_quarto, monkeypatch):
    """A future Quarto could set QUARTO_* but drop QUARTO_FIG_FORMAT."""
    monkeypatch.setenv('QUARTO_PROJECT_ROOT', '/tmp/proj')
    assert in_quarto() is True and quarto_target() == 'other'


# --------------------------------------------------------------- auto-detect

def test_keys_outside_quarto(no_quarto, doc):
    assert set(mimebundle(doc)) == {'text/html', 'text/plain'}


def test_keys_quarto_non_pdf(no_quarto, monkeypatch, doc):
    monkeypatch.setenv('QUARTO_FIG_FORMAT', 'png')
    assert set(mimebundle(doc)) == {'text/html', 'text/plain'}


def test_keys_quarto_pdf(no_quarto, monkeypatch, doc):
    """html is omitted: pandoc would prefer it and its LaTeX writer drop it."""
    monkeypatch.setenv('QUARTO_FIG_FORMAT', 'pdf')
    bundle = mimebundle(doc)
    assert set(bundle) == {'text/latex', 'text/plain'}
    assert '\\begin{tikzpicture}' in bundle['text/latex']


def test_plain_is_the_text_rendering(no_quarto, doc):
    from greater_tables import render_text
    assert mimebundle(doc)['text/plain'] == render_text(doc)


# ------------------------------------------------------------------ overrides

def test_mimes_wins_over_pdf_detection(no_quarto, monkeypatch, doc):
    monkeypatch.setenv('QUARTO_FIG_FORMAT', 'pdf')
    assert set(mimebundle(doc, mimes=('text/plain',))) == {'text/plain'}


def test_mimes_wins_over_tikz_flag(no_quarto, doc):
    assert set(mimebundle(doc, tikz=True, mimes=('text/html',))) == {'text/html'}


def test_tikz_flag_still_forces(no_quarto, doc):
    assert set(mimebundle(doc, tikz=True)) == {'text/html', 'text/latex',
                                               'text/plain'}
    assert set(mimebundle(doc, tikz=False)) == {'text/html', 'text/plain'}


def test_unknown_mime_raises(doc):
    with pytest.raises(ValueError, match='unknown MIME type'):
        mimebundle(doc, mimes=('text/plian',))


def test_validate_mimes_returns_tuple():
    assert validate_mimes(['text/plain']) == ('text/plain',)
