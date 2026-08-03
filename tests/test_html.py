"""HTML renderer behaviors beyond conformance: escaping, css modes, inline."""

import pandas as pd
import pytest

from greater_tables import HouseStyle, TableSpec, build
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


# ------------------------------------------------------------- width budget
# HTML runs no solver: gt-nowrap already pins the columns that must not be
# narrowed, so a table max-width leaves the browser to narrow exactly the
# prose ones — measuring the real font instead of estimating it.

def test_no_width_properties_by_default():
    """A table with nothing to say about width says nothing."""
    html = render_html(build(*FIX['wrap-low']), css='none')
    assert 'style=' not in html.split('>')[0]
    assert '--gt-max-width' not in html


def test_width_budget_rides_as_custom_properties():
    doc = build(*FIX['wrap-low'])
    html = render_html(doc, css='none',
                       style=HouseStyle(max_table_width_em=40,
                                        max_prose_width_em=12))
    wrapper = html.split('>')[0]
    assert '--gt-max-width: 40em;' in wrapper
    assert '--gt-prose-max: 12em;' in wrapper


def test_prose_default_is_not_restated():
    """Say only what the stylesheet does not already say."""
    html = render_html(build(*FIX['wrap-low']), css='none',
                       style=HouseStyle(max_table_width_em=40))
    assert '--gt-prose-max' not in html


def test_inline_css_resolves_widths_to_literals():
    """Email clients know no custom properties, so none may be relied on."""
    html = render_html(build(*FIX['wrap-low']), css='none', inline_css=True,
                       style=HouseStyle(max_table_width_em=40,
                                        max_prose_width_em=12))
    assert '--gt' not in html                     # no declarations survive
    assert 'max-width: 40em;' in html.split('>')[0]
    assert 'max-width: 12em;' in html             # this table's prose cap
