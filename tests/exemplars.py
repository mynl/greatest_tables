"""Hand-authored exemplar TableDocs shared by tests and make_goldens.py.

These are the [ir-core] goldens: schema-validating documents exercising the
IR surface (stubs, spans, break depths, flags, raw values incl. meaningful
null, math/html cells). Engine-generated goldens arrive with [engine].
"""

from greater_tables import Cell, Column, FormatSpec, HeadCell, Row, TableDoc, stamp

GENERATOR = 'greater_tables tests'


def loss_dev() -> TableDoc:
    """Rich exemplar: 2 stub levels, 2 head levels, spans, flags, raw."""
    dec1 = FormatSpec(kind='dec', digits=1, group=True, scale=0.001,
                      negative='paren')
    doc = TableDoc(
        caption='Loss development by year',
        label='tbl-loss-dev',
        notes=('Amounts in USD thousands.',),
        n_stub_levels=2,
        n_head_levels=2,
        columns=(
            Column(key='c0', name=('Year',), dtype='int', align='l',
                   role='stub', level=0, tag='year',
                   format=FormatSpec(kind='year')),
            Column(key='c1', name=('Sub',), dtype='string', align='l',
                   role='stub', level=1, wrap=True),
            Column(key='c2', name=('Group A', 'Paid'), dtype='float',
                   align='r', raw=True, format=dec1),
            Column(key='c3', name=('Group A', 'Incurred'), dtype='float',
                   align='r', raw=True, format=dec1),
            Column(key='c4', name=('Group B', 'Paid'), dtype='float',
                   align='r', raw=True, break_depth=0, format=dec1),
        ),
        head=(
            (HeadCell(colspan=2), HeadCell(text='Group A', colspan=2),
             HeadCell(text='Group B')),
            (HeadCell(text='Year'), HeadCell(text='Sub'),
             HeadCell(text='Paid'), HeadCell(text='Incurred'),
             HeadCell(text='Paid')),
        ),
        body=(
            Row(cells=(
                Cell(text='2020', rowspan=2), 'Sub 1',
                Cell(text='1,234.5', raw=1234.5),
                Cell(text='(89.0)', raw=-89.0, flags=('neg',)),
                Cell(text='250.0', raw=250.0))),
            Row(break_depth=1, cells=(
                'Sub 2',
                Cell(text='—', raw=None),
                Cell(text='12.3', raw=12.3),
                Cell(text='4.5', raw=4.5))),
            Row(break_depth=0, flags=('total',), cells=(
                Cell(text='Total', colspan=2),
                Cell(text='1,234.5', raw=1234.5),
                Cell(text='(76.7)', raw=-76.7, flags=('neg',)),
                Cell(text='254.5', raw=254.5))),
        ),
    )
    return stamp(doc, GENERATOR)


def minimal() -> TableDoc:
    """Flat headerless exemplar with math and html cells, no raw values."""
    doc = TableDoc(
        n_stub_levels=0,
        n_head_levels=0,
        columns=(
            Column(key='c0', name=('item',), dtype='string', align='l',
                   wrap=True),
            Column(key='c1', name=('value',), dtype='string', align='c'),
        ),
        head=(),
        body=(
            Row(cells=('Ruin probability',
                       Cell(text=r'\psi(u) = \Pr(U_t < 0)', math=True))),
            Row(cells=('Reference',
                       Cell(text='<a href="https://example.org">doc</a>',
                            html=True))),
            Row(cells=('Plain', 'row')),
        ),
    )
    return stamp(doc, GENERATOR)


EXEMPLARS = {'loss-dev': loss_dev, 'minimal': minimal}
