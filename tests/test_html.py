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


# ------------------------------------------------------------- rule weights

def _wrapper_style(style):
    doc = build(pd.DataFrame({'a': [1, 2]}), TableSpec())
    head = render_html(doc, style=style, css='none').split('\n', 1)[0]
    return head.partition('style="')[2].partition('"')[0]


def test_default_rule_weights_leave_the_sheet_alone():
    assert _wrapper_style(HouseStyle()) == ''


def test_rule_weights_scale_their_custom_property():
    """Twice the TikZ weight is twice the stylesheet width; 0 draws none."""
    got = _wrapper_style(HouseStyle(hrule_widths=(1.0, 0.25, 0.25), frame_rule=0,
                                    vrule_widths=(0.25, 0.25, 0.5)))
    assert '--gt-rule-0: 1pt solid;' in got        # 0.5 → 1.0, 0.5pt → 1pt
    assert '--gt-rule-frame: none;' in got
    assert '--gt-vrule-2: 0.4pt solid;' in got     # the third slot reaches HTML
    assert '--gt-rule-1' not in got


def test_rule_weights_reach_inline_css():
    doc = build(pd.DataFrame({'a': [1, 2]}), TableSpec())
    html = render_html(doc, style=HouseStyle(frame_rule=2), inline_css=True)
    assert 'border-top: 2.4pt solid' in html and '--gt-' not in html


def test_third_vertical_slot_is_stamped():
    # four levels: the leaf level is "next column" and carries no break
    cols = pd.MultiIndex.from_product([['A', 'B'], ['x', 'y'], ['p', 'q'], ['1', '2']])
    doc = build(pd.DataFrame([range(16)], columns=cols), TableSpec())
    html = render_html(doc, style=HouseStyle(max_vrule_depth=2), css='none')
    assert 'gt-vbreak-2' in html
