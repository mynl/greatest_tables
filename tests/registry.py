"""Fixture registry: named (data, TableSpec) pairs driving the goldens.

All frames are Fabricator-generated (fixed seeds — fully deterministic) or
tiny hand-built synthetics. Nothing real, per the data firewall.

Also home to :func:`golden_bytes`, the byte form the engine-built goldens are
written and compared in.
"""

from dataclasses import replace

import numpy as np
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
    # --- the gallery shapes (dev/done/plan-gt7-review.md [gallery]). Indexes
    # are hand-built because Fabricator's outer levels come out singleton at
    # these row counts with simplify=False, and dropped with simplify=True.
    rng = np.random.default_rng(118)
    idx4 = pd.MultiIndex.from_product(
        [['North', 'South'], ['Auto', 'Property'], ['Primary', 'Excess'],
         [2023, 2024, 2025]], names=['region', 'line', 'layer', 'year'])
    fx['row-mi-4'] = (
        pd.DataFrame({'premium': rng.integers(200_000, 4_000_000, 24),
                      'loss': rng.integers(100_000, 3_000_000, 24),
                      'loss ratio': rng.uniform(0.45, 0.95, 24)}, index=idx4),
        TableSpec(year_cols=['year'], ratio_cols=['loss ratio']))
    data, spec = fx['row-mi-3']
    fx['row-mi-3-dense'] = (data, replace(spec, sparsify=False))
    # subtotals inside the groups of a 2-level index, and a grand total
    rng = np.random.default_rng(119)
    parts = []
    for group in ('Casualty', 'Property'):
        g = pd.DataFrame(rng.uniform(1e4, 9e5, (3, 3)).round(0),
                         columns=['paid', 'case', 'IBNR'],
                         index=pd.MultiIndex.from_product(
                             [[group], ['Auto', 'Marine', 'Other']]))
        sub = g.sum().to_frame().T
        sub.index = pd.MultiIndex.from_tuples([(group, 'Subtotal')])
        parts += [g, sub]
    body = pd.concat(parts)
    total = body[body.index.get_level_values(1) != 'Subtotal'].sum()
    total = total.to_frame().T
    total.index = pd.MultiIndex.from_tuples([('Total', '')])
    subtotals = pd.concat([body, total])
    subtotals.index.names = ['segment', 'line']
    fx['subtotals'] = (subtotals, TableSpec(
        row_flags={3: ('subtotal',), 7: ('subtotal',), -1: ('total',)}))
    rng = np.random.default_rng(120)
    cols3 = pd.MultiIndex.from_product(
        [['Gross', 'Net'], ['Paid', 'Incurred'], ['Count', 'Amount']])
    col3 = pd.DataFrame(rng.uniform(1e3, 5e6, (6, 8)), columns=cols3,
                        index=pd.Index(range(2020, 2026), name='year'))
    for c in col3.columns:
        if c[2] == 'Count':
            col3[c] = rng.integers(100, 5000, 6)
    fx['col-mi-3'] = (col3, TableSpec(year_cols=['year']))
    # the aggregate Loss Lab shape: a 3-level row index under 2-level columns
    rng = np.random.default_rng(121)
    lab_cols = pd.MultiIndex.from_product(
        [['Gross', 'Net'], ['Mean', 'CV', 'VaR 99%']])
    lab_idx = pd.MultiIndex.from_product(
        [['Portfolio A', 'Portfolio B'], ['Unit 1', 'Unit 2'],
         ['0 xs 0', '5M xs 5M', '40M xs 10M']],
        names=['portfolio', 'unit', 'layer'])
    lab = pd.DataFrame(index=lab_idx, columns=lab_cols, dtype=float)
    for side in ('Gross', 'Net'):
        mean = rng.uniform(1e6, 3e7, 12)
        lab[(side, 'Mean')] = mean
        lab[(side, 'CV')] = rng.uniform(0.2, 3.5, 12)
        lab[(side, 'VaR 99%')] = mean * rng.uniform(2.5, 6, 12)
    fx['loss-lab'] = (lab, TableSpec())
    # numbers only, too many columns for a 41.4em budget even at scale 0.6:
    # the overrun case (house style's document budget)
    rng = np.random.default_rng(122)
    fx['wide-numbers'] = (
        pd.DataFrame(rng.uniform(1e6, 1e7, (4, 20)),
                     columns=[f'Column {i}' for i in range(20)]),
        TableSpec())
    fx['long'] = (Fabricator(seed=123).make(250, 's2ff'),
                  TableSpec(max_rows=30))
    # --- width regressions, from the retired dev/check-widths.qmd
    # a long heading wraps to its widest word instead of widening its column
    fx['long-headings'] = (pd.DataFrame({
        'Cumulative Incurred Loss': [1234.5, 2345.6, 3456.7],
        'Cumulative Paid Loss': [1000.0, 2000.0, 3000.0],
        'Case Outstanding Reserve': [234.5, 345.6, 456.7],
    }, index=pd.Index([2022, 2023, 2024], name='Accident Year')),
        TableSpec(year_cols=['Accident Year']))
    # stub values set at exactly their natural width stay on one line
    fx['stub-fits'] = (pd.DataFrame({
        'Paid': [1234.5, float('nan'), 1234.5],
        'Incurred': [-89.0, 12.3, -76.7],
    }, index=pd.MultiIndex.from_tuples(
        [(2020, 'Sub 1'), (2020, 'Sub 2'), ('Total', '')],
        names=['Year', 'Sub'])), TableSpec())
    # em dash, percent, SI micro and ISO dates, each measured at its true width
    fx['glyph-widths'] = (pd.DataFrame({
        'loss ratio': [0.458, 0.612, float('nan'), 0.397],
        'missing': [float('nan'), 1.5, float('nan'), 2.5],
        'as of': pd.to_datetime(['2024-01-15', '2024-06-30',
                                 '2025-01-15', '2025-06-30']),
        'tiny': [1.2e-6, 3.4e-6, 5.6e-6, 7.8e-6],
    }, index=['alpha', 'beta', 'gamma', 'delta']),
        TableSpec(ratio_cols=['loss ratio']))
    # a group label wider than its columns widens the last one it covers
    spanner = Fabricator(seed=42).make(6, 'ff', column_groups=2)
    spanner.columns = pd.MultiIndex.from_tuples([
        ('A Notably Long Group Label', 'paid'),
        ('A Notably Long Group Label', 'incurred'),
        ('Short', 'paid'), ('Short', 'incurred')][:len(spanner.columns)])
    fx['long-spanner'] = (spanner, TableSpec())
    # --- long headings over narrow data: the column is as wide as the
    # heading's longest word, and the heading stacks on as many lines as it
    # needs, however much room the table has to spare
    fab = Fabricator(seed=124)
    fx['long-head-ratios'] = (fab.make(6, 'rrrr', metric_name_spec='s5s6s4s7'),
                              TableSpec(ratio_cols='all'))
    rng = np.random.default_rng(125)
    flags = Fabricator(seed=125).make(6, 'rrrrr', metric_name_spec='s6s4s7s5s3')
    flags = flags.apply(lambda c: rng.choice(['Y', 'N'], size=len(c))).astype(str)
    fx['long-head-flags'] = (flags, TableSpec())
    counts = Fabricator(seed=126).make(6, 'iii', metric_name_spec='s4s6s5')
    fx['long-head-counts'] = (counts.abs() // 1000, TableSpec())
    fx['long-head-groups'] = (
        Fabricator(seed=127).make(6, 'rr', column_groups=2, metric_name_spec='s5s6'),
        TableSpec(ratio_cols='all'))
    # nine long headings over Y/N and counts: wider than the budget even with
    # every heading at its longest word
    rng = np.random.default_rng(128)
    many = Fabricator(seed=128).make(6, 'r' * 9, metric_name_spec='s5s4s6s5s7s4s5s6s4')
    for k, c in enumerate(many.columns):
        many[c] = (rng.choice(['Y', 'N'], size=len(many)) if k % 2 == 0
                   else rng.integers(0, 400, size=len(many)))
    fx['long-head-many'] = (many, TableSpec())
    # --- sideways: the Loss Lab shape with five statistics a side, about
    # 70em at full size, for a sidewaystable whose budget is the text height
    rng = np.random.default_rng(129)
    wide_cols = pd.MultiIndex.from_product(
        [['Gross', 'Net'], ['Mean', 'SD', 'CV', 'VaR 99%', 'TVaR 99%']])
    wide = pd.DataFrame(index=lab_idx, columns=wide_cols, dtype=float)
    for side in ('Gross', 'Net'):
        mean = rng.uniform(1e6, 3e7, 12)
        cv = rng.uniform(0.2, 3.5, 12)
        wide[(side, 'Mean')] = mean
        wide[(side, 'SD')] = mean * cv
        wide[(side, 'CV')] = cv
        wide[(side, 'VaR 99%')] = mean * rng.uniform(2.5, 6, 12)
        wide[(side, 'TVaR 99%')] = wide[(side, 'VaR 99%')] * rng.uniform(1.1, 1.6, 12)
    fx['wide-lab'] = (wide, TableSpec())
    return fx
