"""Canonical bytes and content hashing for table documents.

Determinism contract: same document content ⇒ same bytes ⇒ same hash, on any
machine, any run. No time salt, no counters. ``hash`` and ``generator`` are
excluded from the hashed form so stamping does not perturb the digest.
"""

from __future__ import annotations

import hashlib
import json

from ..ir import TableDoc, canonical_dict

__all__ = ['canonical_json', 'doc_hash', 'stamp']


def canonical_json(doc: TableDoc, *, include_hash: bool = True) -> bytes:
    """Serialize a document to canonical UTF-8 JSON bytes.

    Sorted keys, compact separators, NFC strings (applied by
    :func:`greater_tables.ir.canonical_dict`), no NaN/Infinity — a raw value
    that is not JSON-representable is an engine bug, surfaced here.

    Parameters
    ----------
    doc
        The document to serialize.
    include_hash
        When False, omit ``hash`` and ``generator`` (the hashed form).
    """
    data = canonical_dict(doc, include_hash=include_hash)
    text = json.dumps(data, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)
    return text.encode('utf-8')


def doc_hash(doc: TableDoc) -> str:
    """Return the 12-hex-char sha256 content hash of a document."""
    return hashlib.sha256(canonical_json(doc, include_hash=False)).hexdigest()[:12]


def stamp(doc: TableDoc, generator: str | None = None) -> TableDoc:
    """Return a copy of ``doc`` with ``hash`` (and optionally ``generator``) set."""
    update: dict[str, str] = {'hash': doc_hash(doc)}
    if generator is not None:
        update['generator'] = generator
    return doc.model_copy(update=update)
