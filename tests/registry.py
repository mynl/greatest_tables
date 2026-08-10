"""Fixture registry: named (data, TableSpec) pairs driving the goldens.

All frames are Fabricator-generated (fixed seeds — fully deterministic) or
tiny hand-built synthetics. Nothing real, per the data firewall.

Also home to :func:`golden_bytes`, the byte form the engine-built goldens are
written and compared in.
"""

import pandas as pd

from greater_tables import Fabricator, TableSpec, canonical_json
from greater_tables.ir import TableDoc


def golden_bytes(doc: TableDoc) -> bytes:
    """Canonical bytes for golden comparison, with ``generator`` stripped.

    ``generator`` carries the package version. It is informative, excluded
    from the content hash, and identical across every fixture — so leaving it
    in would rewrite all 20-odd engine goldens on each version bump and bury
    real IR changes in the churn. The hand-authored exemplars keep theirs
    (a fixed test string), so the field itself stays covered.
    """
    return canonical_json(doc.model_copy(update={'generator': None}))


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
    # the inline-math matrix: math in a column name (inline and whole-cell),
    # the stub name, stub values and body cells; currency that must never
    # become math; an escaped literal dollar beside a real span
    fx['inline-math'] = (
        pd.DataFrame({
            r'formula $f(x)$': [r'$\psi(u)$', r'ruin $\psi(u)$ falls',
                                'plain'],
            r'$\beta$': [r'escaped \$100 and $y=1$', '$10 to $20',
                         '$5-$10'],
        }, index=pd.Index([r'case $\alpha$', 'case b', 'case c'],
                          name=r'label $\ell$')),
        TableSpec(caption=r'Mixed $x^2$ caption',
                  notes=[r'A note with $\sigma$ inside.']))
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
    # 5 stub levels: the only depth where a fixed depth-2 cap and the
    # n_stub_levels-2 policy disagree — this is the fixture that exposes a
    # renderer drifting from render.policy. Hand-built because Fabricator's
    # simplify=True drops singleton outer levels at small row counts.
    fx['deep-stub'] = (
        pd.DataFrame(
            {'v': range(32)},
            index=pd.MultiIndex.from_product(
                [list('AB'), list('cd'), list('ef'), list('gh'), list('ij')],
                names=[f'L{k}' for k in range(5)])),
        TableSpec())
    fx['markdown'] = (
        ': Simple table {#tbl-md}\n\n'
        '| item | count |\n|:-----|------:|\n| apples | 3 |\n| pears | 12 |\n',
        TableSpec())
    return fx
