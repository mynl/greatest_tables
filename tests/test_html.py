"""HTML renderer behaviors beyond conformance: escaping, css modes, inline."""

import pandas as pd
import pytest

from greater_tables import TableSpec, build
from greater_tables.render.html import render_html, reset_css_once

from registry import fixtures

FIX = fixtures()


@pytest.fixture()
def doc():
    return build(*FIX['plain'])


def test_injection_escaped_by_default():
    df = pd.DataFrame({'a': ['<script>alert(1)</script>', 'x < y & z']})
    html = render_html(build(df, TableSpec()), css='none')
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert 'x &lt; y &amp; z' in html


def test_html_cells_gated():
    doc = build(*FIX['math-html'])
    trusted = render_html(doc, css='none')                    # producer default
    assert '<a href="x">x</a>' in trusted
    safe = render_html(doc, css='none', allow_html=False)
    assert '<a href' not in safe and '&lt;a href' in safe


def test_css_modes(doc):
    reset_css_once()
    embedded = render_html(doc)
    assert embedded.count('<style>') == 1 and '.gt.gt' in embedded
    assert render_html(doc).count('<style>') == 1             # embed: always
    reset_css_once()
    first = render_html(doc, css='once')
    second = render_html(doc, css='once')
    assert '<style>' in first and '<style>' not in second
    assert '<style>' not in render_html(doc, css='none')
    reset_css_once()


def test_inline_css(doc):
    html = render_html(doc, inline_css=True)
    assert '<style>' not in html
    assert 'text-align: right;' in html                       # numeric cells
    assert 'var(' not in html                                 # vars resolved
    assert 'border-collapse: collapse;' in html


def test_wrapper_identity():
    doc = build(*FIX['plain'])
    html = render_html(doc, css='none')
    assert f'data-gt-hash="{doc.hash}"' in html
    assert 'id=' not in html.split('>')[1]                    # no label ⇒ no id
    labeled = build(FIX['plain'][0], TableSpec(label='tbl-x'))
    assert 'id="tbl-x"' in render_html(labeled, css='none')


def test_notes_rendered(doc_=None):
    doc = build(*FIX['truncated'])
    html = render_html(doc, css='none')
    assert 'gt-notes' in html and 'Showing first 5 of 12 rows.' in html
