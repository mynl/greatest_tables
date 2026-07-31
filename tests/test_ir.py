"""IR model tests: round-trip byte-equality, must-ignore reads, validators."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from greater_tables import (
    Cell, Column, HeadCell, Row, TableDoc, canonical_json, doc_hash, stamp,
)

from exemplars import EXEMPLARS

GOLDEN = Path(__file__).parent / 'golden' / 'ir'


@pytest.fixture(params=sorted(EXEMPLARS))
def exemplar(request):
    return request.param, EXEMPLARS[request.param]()


def test_golden_bytes(exemplar):
    """Committed goldens match freshly built exemplars byte-for-byte."""
    name, doc = exemplar
    golden = (GOLDEN / f'{name}.json').read_bytes()
    assert canonical_json(doc) == golden


def test_roundtrip(exemplar):
    """read(canonical) re-canonicalizes to identical bytes."""
    _, doc = exemplar
    data = canonical_json(doc)
    assert canonical_json(TableDoc.read(data)) == data


def test_shorthand_equivalence():
    """A bare-string cell and a text-only Cell canonicalize identically."""
    def make(cell):
        return TableDoc(n_stub_levels=0, n_head_levels=0,
                        columns=(Column(key='c0', name=('x',),
                                        dtype='string', align='l'),),
                        head=(), body=(Row(cells=(cell,)),))
    assert canonical_json(make('hello')) == canonical_json(make(Cell(text='hello')))
    # and the emitted form is the bare string
    payload = json.loads(canonical_json(make(Cell(text='hello'))))
    assert payload['body'][0]['cells'] == ['hello']


def test_raw_null_is_meaningful():
    """Explicit raw=None serializes as null; unset raw is absent."""
    with_null = Cell(text='—', raw=None)
    without = Cell(text='—')
    doc = TableDoc(n_stub_levels=0, n_head_levels=0,
                   columns=(Column(key='c0', name=('x',), dtype='float',
                                   align='r', raw=True),),
                   head=(), body=(Row(cells=(with_null,)),
                                  Row(cells=(without,))))
    payload = json.loads(canonical_json(doc))
    assert payload['body'][0]['cells'][0] == {'raw': None, 'text': '—'}
    assert payload['body'][1]['cells'][0] == '—'


def test_must_ignore_unknown_fields():
    """Documents from a newer producer (extra fields everywhere) still read."""
    base = EXEMPLARS['loss-dev']()
    data = json.loads(canonical_json(base))
    data['future_advisory'] = {'anything': 1}
    data['columns'][0]['sparkline_hint'] = [1, 2, 3]
    data['columns'][2]['format']['locale'] = 'en-US'
    data['head'][0][1]['tooltip'] = 'group A'
    data['body'][0]['density'] = 'compact'
    data['body'][0]['cells'][0]['confidence'] = 0.9
    doc = TableDoc.read(json.dumps(data))
    assert canonical_json(doc) == canonical_json(base)


def test_write_model_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        Column(key='c0', name=('x',), dtype='string', align='l', bogus=1)


def test_read_rejects_unsupported_version():
    data = json.loads(canonical_json(EXEMPLARS['minimal']()))
    data['ir_version'] = 99
    with pytest.raises(ValueError, match='ir_version'):
        TableDoc.read(json.dumps(data))


def test_validators():
    col = Column(key='c0', name=('x',), dtype='string', align='l')
    stub = Column(key='c0', name=('x',), dtype='string', align='l',
                  role='stub', level=0)
    with pytest.raises(ValidationError, match='n_head_levels'):
        TableDoc(n_stub_levels=0, n_head_levels=2, columns=(col,),
                 head=(), body=())
    with pytest.raises(ValidationError, match='stub'):
        TableDoc(n_stub_levels=0, n_head_levels=0, columns=(stub,),
                 head=(), body=())
    with pytest.raises(ValidationError, match='level'):
        TableDoc(n_stub_levels=1, n_head_levels=0,
                 columns=(Column(key='c0', name=('x',), dtype='string',
                                 align='l', role='stub', level=3),),
                 head=(), body=())
    with pytest.raises(ValidationError):
        HeadCell(colspan=0)


def test_hash_stability_and_exclusions():
    """Same content ⇒ same hash; generator/hash never perturb the digest."""
    a, b = EXEMPLARS['loss-dev'](), EXEMPLARS['loss-dev']()
    assert a.hash == b.hash == doc_hash(a)
    restamped = stamp(a, 'a completely different generator 9.9.9')
    assert restamped.hash == a.hash
    assert doc_hash(a.model_copy(update={'hash': None})) == a.hash
