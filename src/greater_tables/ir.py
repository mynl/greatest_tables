"""Table-document IR: frozen pydantic models, ``ir_version`` 1.

The IR is the contract between the semantic engine and every renderer
(Python HTML, TikZ, text, and the JS walker). It carries *semantics only*:
no widths, no rule weights, no CSS, no fonts.

Two access paths with different strictness:

- **Write** (producer): construct models directly; unknown fields raise
  (``extra='forbid'``), so producer typos surface immediately.
- **Read** (consumer): :meth:`TableDoc.read` strips unknown fields before
  validation, so documents from a *newer* producer with additive advisory
  fields remain readable ("must ignore" rule).

Canonical serialization lives in :func:`canonical_dict`: deterministic field
presence (defaults omitted), NFC-normalized strings, and the bare-string cell
shorthand. :mod:`greater_tables.engine.hashing` turns that dict into
canonical bytes and the content hash.
"""

from __future__ import annotations

import json
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    'IR_VERSION', 'Alignment', 'Cell', 'Column', 'FormatSpec', 'HeadCell',
    'Row', 'TableDoc', 'canonical_dict',
]

IR_VERSION = 1

Alignment = Literal['l', 'r', 'c']
Role = Literal['stub', 'data']
Dtype = Literal['int', 'float', 'date', 'datetime', 'bool', 'string', 'object']
Tag = Literal['ratio', 'year', 'date', 'raw']
FormatKind = Literal['int', 'dec', 'pct', 'sci', 'gen', 'si', 'eng', 'year',
                     'date', 'str']
Negative = Literal['minus', 'paren']
RowFlag = Literal['total', 'subtotal', 'emphasis', 'muted']
CellFlag = Literal['neg', 'emphasis', 'muted']

_FROZEN = ConfigDict(frozen=True, extra='forbid')


class FormatSpec(BaseModel):
    """Resolved display format for one column.

    Applicable by Python and by the JS walker (Intl.NumberFormat). The
    formatted ``text`` in cells is normative; this spec is informative —
    it lets a client re-render at different precision without redoing the
    engine's column-scanning inference.
    """

    model_config = _FROZEN

    kind: FormatKind
    digits: int | None = Field(default=None, ge=0)
    group: bool = False
    scale: float = 1.0
    prefix: str | None = None
    suffix: str | None = None
    negative: Negative = 'minus'
    null: str = '—'
    zero: str | None = None
    pattern: str | None = None
    # an uppercase exponent marker, 1.95E-05: Python's E and G formats
    upper: bool = False


class Cell(BaseModel):
    """One body/foot cell.

    ``text`` is plain unicode — each renderer applies its own escaping.
    Unless the document says ``math='off'``, ``text`` may contain inline
    ``$...$`` / ``$$...$$`` math spans (and ``\\$`` for a literal dollar);
    a renderer is responsible for segmenting them — the shared rule is
    :mod:`greater_tables.mathspans`. ``raw`` is only present when the owning
    column advertises ``raw: true``; an explicit JSON ``null`` there means a
    missing value, which is distinct from the field being absent (tracked
    via pydantic's fields-set).
    """

    model_config = _FROZEN

    text: str
    raw: float | int | str | bool | None = None
    rowspan: int = Field(default=1, ge=1)
    colspan: int = Field(default=1, ge=1)
    flags: tuple[CellFlag, ...] = ()
    math: bool = False
    html: bool = False


class HeadCell(BaseModel):
    """One header cell; level is implicit in its row position within ``head``."""

    model_config = _FROZEN

    text: str = ''
    colspan: int = Field(default=1, ge=1)
    align: Alignment | None = None
    flags: tuple[CellFlag, ...] = ()
    math: bool = False
    html: bool = False


class Row(BaseModel):
    """One body/foot row.

    ``cells`` holds only the *uncovered* columns — a stub cell with
    ``rowspan`` in an earlier row covers its column here, exactly as HTML
    ``<td rowspan>`` semantics. A cell that is plain text with no other
    attributes may be a bare string (the shorthand; canonicalized on dump).

    ``break_depth`` is the shallowest stub level whose value changed versus
    the previous row (0 = outermost). House style maps depth to rule weight;
    the IR never names a weight.
    """

    model_config = _FROZEN

    cells: tuple[Cell | str, ...]
    break_depth: int | None = Field(default=None, ge=0)
    flags: tuple[RowFlag, ...] = ()


class Column(BaseModel):
    """Descriptor for one visual column, stubs first."""

    model_config = _FROZEN

    key: str
    name: tuple[str, ...]
    dtype: Dtype
    align: Alignment
    role: Role = 'data'
    level: int | None = Field(default=None, ge=0)
    tag: Tag | None = None
    wrap: bool = False
    break_depth: int | None = Field(default=None, ge=0)
    format: FormatSpec | None = None
    raw: bool = False


class TableDoc(BaseModel):
    """The table document — the versioned IR a semantic engine emits.

    ``hash`` is stamped by :func:`greater_tables.engine.hashing.stamp`
    (sha256 over canonical bytes, ``hash`` and ``generator`` excluded).

    ``math`` is the document-wide switch for ``$``-delimiter interpretation
    in every ``text`` field (cells, headers, caption, notes). The builder
    always emits the default ``'auto'``; ``'off'`` is the escape hatch for
    hand-authored and foreign documents whose dollars are all literal (a
    ticker table). ``'off'`` stops renderers *detecting* delimiters — an
    explicit ``Cell.math`` / ``HeadCell.math`` flag is honored regardless.
    """

    model_config = _FROZEN

    ir_version: int = IR_VERSION
    generator: str | None = None
    hash: str | None = Field(default=None, pattern=r'^[0-9a-f]{12}$')
    caption: str | Cell | None = None
    label: str | None = None
    notes: tuple[str, ...] = ()
    math: Literal['auto', 'off'] = 'auto'
    n_stub_levels: int = Field(ge=0)
    n_head_levels: int = Field(ge=0)
    columns: tuple[Column, ...]
    head: tuple[tuple[HeadCell, ...], ...]
    body: tuple[Row, ...]
    foot: tuple[Row, ...] = ()

    @model_validator(mode='after')
    def _check_structure(self) -> TableDoc:
        if self.ir_version != IR_VERSION:
            raise ValueError(
                f'unsupported ir_version {self.ir_version}; this build reads {IR_VERSION}')
        if self.n_head_levels != len(self.head):
            raise ValueError(
                f'n_head_levels={self.n_head_levels} != len(head)={len(self.head)}')
        stubs = [c for c in self.columns if c.role == 'stub']
        if len(stubs) != self.n_stub_levels:
            raise ValueError(
                f'n_stub_levels={self.n_stub_levels} != {len(stubs)} stub columns')
        for i, col in enumerate(self.columns):
            if col.role == 'stub':
                if i >= self.n_stub_levels:
                    raise ValueError(f'stub column {col.key} after data columns')
                if col.level != i:
                    raise ValueError(
                        f'stub column {col.key} has level={col.level}, expected {i}')
        return self

    @classmethod
    def read(cls, source: str | bytes | dict[str, Any]) -> TableDoc:
        """Validate a foreign document, ignoring unknown fields.

        Parameters
        ----------
        source
            JSON text/bytes or an already-parsed dict.

        Returns
        -------
        TableDoc
            The validated document.

        Raises
        ------
        ValueError
            If ``ir_version`` is unsupported or the document is malformed.
        """
        data = json.loads(source) if isinstance(source, (str, bytes)) else source
        if not isinstance(data, dict):
            raise ValueError('table document must be a JSON object')
        version = data.get('ir_version', IR_VERSION)
        if version != IR_VERSION:
            raise ValueError(
                f'unsupported ir_version {version}; this build reads {IR_VERSION}')
        return cls.model_validate(_strip_unknown(data))


# ------------------------------------------------------------- read cleaning

def _keep(data: dict[str, Any], model: type[BaseModel]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k in model.model_fields}


def _strip_unknown(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively drop fields no model knows — the must-ignore read rule."""
    def cell(c: Any) -> Any:
        return _keep(c, Cell) if isinstance(c, dict) else c

    def head_cell(c: Any) -> Any:
        return _keep(c, HeadCell) if isinstance(c, dict) else c

    def row(r: Any) -> Any:
        if not isinstance(r, dict):
            return r
        r = _keep(r, Row)
        if isinstance(r.get('cells'), list):
            r['cells'] = [cell(c) for c in r['cells']]
        return r

    def column(c: Any) -> Any:
        if not isinstance(c, dict):
            return c
        c = _keep(c, Column)
        if isinstance(c.get('format'), dict):
            c['format'] = _keep(c['format'], FormatSpec)
        return c

    out = _keep(data, TableDoc)
    if isinstance(out.get('caption'), dict):
        out['caption'] = cell(out['caption'])
    if isinstance(out.get('columns'), list):
        out['columns'] = [column(c) for c in out['columns']]
    if isinstance(out.get('head'), list):
        out['head'] = [[head_cell(c) for c in level] if isinstance(level, list)
                       else level for level in out['head']]
    for part in ('body', 'foot'):
        if isinstance(out.get(part), list):
            out[part] = [row(r) for r in out[part]]
    return out


# ------------------------------------------------------- canonical emission

def _nfc(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize('NFC', value)
    if isinstance(value, tuple):
        return [_nfc(v) for v in value]
    return value


def _canonical_model(obj: BaseModel, always: tuple[str, ...]) -> dict[str, Any]:
    """Dump a model keeping ``always`` fields plus non-default ones.

    Canonical form ignores whether a default was passed explicitly — the one
    exception is ``Cell.raw``, where *presence* is meaningful (an explicit
    JSON null means a missing value) and is tracked via the fields-set.
    """
    out: dict[str, Any] = {}
    for name, field in type(obj).model_fields.items():
        value = getattr(obj, name)
        if name not in always:
            if isinstance(obj, Cell) and name == 'raw':
                if 'raw' not in obj.model_fields_set:
                    continue
            elif value == field.get_default():
                continue
        out[name] = _nfc(value)
    return out


def _canonical_cell(cell: Cell | str) -> dict[str, Any] | str:
    if isinstance(cell, str):
        return _nfc(cell)
    d = _canonical_model(cell, always=('text',))
    if list(d) == ['text']:
        return d['text']            # bare-string shorthand
    return d


def _canonical_row(row: Row) -> dict[str, Any]:
    d = _canonical_model(row, always=('cells',))
    d['cells'] = [_canonical_cell(c) for c in row.cells]
    return d


def canonical_dict(doc: TableDoc, *, include_hash: bool = True) -> dict[str, Any]:
    """Return the canonical plain-dict form of a document.

    Deterministic field presence: structural fields always appear; optional
    fields appear only when they differ from their defaults; trivial cells
    collapse to bare strings; all strings are NFC-normalized. Key ordering is
    left to the JSON writer (sorted there).

    Parameters
    ----------
    doc
        The document to canonicalize.
    include_hash
        When False, ``hash`` and ``generator`` are omitted — the form that
        content hashing operates on.
    """
    out: dict[str, Any] = {
        'ir_version': doc.ir_version,
        'n_stub_levels': doc.n_stub_levels,
        'n_head_levels': doc.n_head_levels,
    }
    if include_hash:
        if doc.generator is not None:
            out['generator'] = _nfc(doc.generator)
        if doc.hash is not None:
            out['hash'] = doc.hash
    if doc.caption is not None:
        out['caption'] = (_canonical_cell(doc.caption)
                          if isinstance(doc.caption, Cell) else _nfc(doc.caption))
    if doc.label is not None:
        out['label'] = _nfc(doc.label)
    if doc.notes:
        out['notes'] = [_nfc(n) for n in doc.notes]
    if doc.math != 'auto':
        out['math'] = doc.math
    out['columns'] = [_canonical_column(c) for c in doc.columns]
    out['head'] = [[_canonical_model(c, always=('text',)) for c in level]
                   for level in doc.head]
    out['body'] = [_canonical_row(r) for r in doc.body]
    if doc.foot:
        out['foot'] = [_canonical_row(r) for r in doc.foot]
    return out


def _canonical_column(col: Column) -> dict[str, Any]:
    d = _canonical_model(col, always=('key', 'name', 'dtype', 'align'))
    if col.format is not None:
        d['format'] = _canonical_model(col.format, always=('kind',))
    return d
