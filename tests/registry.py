"""Fixture registry: named (data, TableSpec) pairs driving the goldens.

All frames are Fabricator-generated (fixed seeds — fully deterministic) or
tiny hand-built synthetics. Nothing real, per the data firewall.
"""

import pandas as pd

from greatest_tables import Fabricator, TableSpec


def fixtures() -> dict[str, tuple[object, TableSpec]]:
    """Return the named fixtures, freshly built (order is golden-file order)."""
    fx: dict[str, tuple[object, TableSpec]] = {}
    fx['plain'] = (Fabricator(seed=101).make(6, 's2fi'), TableSpec())
    fx['row-mi-2'] = (Fabricator(seed=102).make(10, 'ff', index_levels=2),
                      TableSpec())
    fx['row-mi-3'] = (Fabricator(seed=103).make(24, 'ff', index_levels=3),
                      TableSpec())
    fx['col-mi-2'] = (Fabricator(seed=104).make(8, 'fr', column_groups=2),
                      TableSpec())
    fx['both-mi'] = (Fabricator(seed=105).make(
        12, 'fi', index_levels=2, column_groups=2), TableSpec())
    fx['negatives'] = (Fabricator(seed=106).make(8, 'ff'),
                       TableSpec(include_raw=True))
    fx['dates'] = (Fabricator(seed=107).make(6, 'dt'), TableSpec())
    fx['ratios'] = (Fabricator(seed=108).make(6, 'rr'),
                    TableSpec(ratio_cols='all'))
    fx['nulls'] = (Fabricator(seed=109).make(10, 'ffs2', missing=0.2),
                   TableSpec())
    fx['eng'] = (Fabricator(seed=110).make(6, 'lv'), TableSpec())
    fx['bigints'] = (pd.DataFrame({'id': [2 ** 53 + 1, 2 ** 53 + 7, 12],
                                   'v': [1.5, 2.5, -3.25]}),
                     TableSpec(include_raw=True))
    fx['math-html'] = (pd.DataFrame({
        'expr': [r'$\alpha+\beta$', 'plain', r'$e^{i\pi}$'],
        'link': ['<a href="x">x</a>', '<b>b</b>', 'none']}),
        TableSpec(html_cols=['link']))
    base = Fabricator(seed=111).make(5, 'ff')
    totals = pd.concat([base, base.sum().to_frame('Total').T])
    fx['totals'] = (totals, TableSpec(row_flags={-1: ('total',)}))
    fx['year'] = (Fabricator(seed=112).make(
        6, 'yf', metric_name_spec=['year', 'amount']),
        TableSpec(year_cols=['year']))
    fx['truncated'] = (Fabricator(seed=113).make(12, 'sf'),
                       TableSpec(max_rows=5))
    fx['headerless'] = ([['alpha', 1], ['beta', 2]], TableSpec())
    fx['empty'] = (pd.DataFrame(), TableSpec())
    # demo2 showcase fixtures: TeX, wrapping (both text generators), wide floats
    fx['tex'] = (Fabricator(seed=116).make(
        8, 'xs3f', metric_name_spec=['formula', 'commentary', 'value']),
        TableSpec())
    fx['wrap-low'] = (Fabricator(seed=114).make(
        6, 's14s6f',
        metric_name_spec=['long description', 'shorter note', 'amount']),
        TableSpec())
    fx['wrap-high'] = (Fabricator(seed=115).make(
        6, 'w10w4f',
        metric_name_spec=['variable length text', 'short variable', 'amount']),
        TableSpec())
    fx['wide-floats'] = (Fabricator(seed=117).make(
        8, 'flv',
        metric_name_spec=['normal scale', 'log wide', 'extreme range']),
        TableSpec())
    fx['markdown'] = (
        ': Simple table {#tbl-md}\n\n'
        '| item | count |\n|:-----|------:|\n| apples | 3 |\n| pears | 12 |\n',
        TableSpec())
    return fx
