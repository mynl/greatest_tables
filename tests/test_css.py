"""CSS contract guards: committed asset matches RULES; vocabulary complete."""

from pathlib import Path

from greatest_tables.render import css

ASSET = (Path(__file__).parent.parent / 'src' / 'greatest_tables' / 'assets'
         / 'gt.css')

# the class vocabulary both renderers stamp — every name must be styled
VOCAB = [
    'gt-l', 'gt-r', 'gt-c', 'gt-stub', 'gt-data', 'gt-stub-end',
    'gt-nowrap', 'gt-wrap', 'gt-break-0', 'gt-break-1', 'gt-break-2',
    'gt-vbreak-0', 'gt-vbreak-1', 'gt-total', 'gt-subtotal', 'gt-emph',
    'gt-muted', 'gt-neg', 'gt-math', 'gt-caption', 'gt-notes', 'gt-fit',
    'gt-spanner',
]


def test_asset_matches_rules():
    assert ASSET.read_text(encoding='utf-8') == css.css_text(), (
        'assets/gt.css drifted from RULES — run tests/make_goldens.py')


def test_vocabulary_styled():
    # gt-data is a deliberate style-less hook — themes and host selectors
    # target it; the default sheet has no opinion about it
    hooks = {'gt-data'}
    text = css.css_text()
    missing = [c for c in VOCAB if c not in text and c not in hooks]
    assert not missing, f'classes with no styling: {missing}'


def test_selector_doubling():
    """Every rule except the wrapper itself must use .gt.gt specificity."""
    for selector in css.RULES:
        if selector == '.gt':
            continue
        assert selector.startswith('.gt.gt'), selector


def test_no_widths_no_fonts_no_colors():
    """The sheet expresses intent, not geometry: no width/font-family/colors
    beyond currentColor-derived defaults."""
    for selector, props in css.RULES.items():
        assert 'width' not in props or props.get('width') == 'fit-content', selector
        assert 'font-family' not in props, selector
        for key, value in props.items():
            if key.startswith('--gt-') or key in ('color',):
                assert 'rgb' not in value and '#' not in value, (selector, key)
