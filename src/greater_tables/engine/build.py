"""``build(data, spec) -> TableDoc`` — the semantic engine orchestrator.

Accepts a DataFrame, Series, list of rows, or a markdown pipe table. Never
mutates its input. Everything semantic is decided here — dtypes, tags,
formats, alignment, hierarchy, flags — and nothing stylistic.
"""

from __future__ import annotations

import math
import re
import warnings
from dataclasses import replace
from pathlib import Path
from typing import Any, Hashable

import pandas as pd

from .._version import __version__
from ..ir import Cell, Column, FormatSpec, HeadCell, Row, TableDoc
from ..mathspans import whole_cell
from ..spec import TableSpec
from . import dtypes as dt
from . import structure as st
from .formats import apply_format, infer_numeric_format, parse_sugar
from .hashing import stamp

__all__ = ['build']


def build(data, spec: TableSpec | None = None) -> TableDoc:
    """Build a stamped table document from data plus a semantic spec.

    Parameters
    ----------
    data
        DataFrame, Series, list of row-lists (``spec.header_row`` promotes
        the first), or a markdown pipe-table string (caption/label/alignment
        extracted and used where the spec leaves them unset).
    spec
        Semantic specification; defaults to ``TableSpec()``.

    Returns
    -------
    TableDoc
        Validated, hash-stamped document.

    Notes
    -----
    A DataFrame with default RangeIndex columns is treated as headerless;
    an unnamed RangeIndex row index is auto-hidden unless
    ``spec.show_index`` says otherwise.
    """
    spec = spec or TableSpec()
    df, spec = _ingest(data, spec)

    caption, notes = spec.caption, list(spec.notes)
    total = len(df)
    if spec.max_rows is not None and total > spec.max_rows:
        df = df.iloc[:spec.max_rows]
        notes.append(f'Showing first {spec.max_rows} of {total} rows.')

    # --- stub (index) side
    show = spec.show_index if spec.show_index is not None \
        else not _trivial_index(df.index)
    n_stub = df.index.nlevels if show else 0
    stub_names: list[Hashable] = []
    stub_series: list[pd.Series] = []
    if show:
        frame = df.index.to_frame(index=False)
        stub_names = [n if n is not None else f'level_{k}'
                      for k, n in enumerate(df.index.names)]
        stub_series = [frame.iloc[:, k] for k in range(n_stub)]

    # --- head side
    data_cols = list(df.columns)
    headerless = isinstance(df.columns, pd.RangeIndex) and df.columns.name is None
    n_head = 0 if headerless or not data_cols else df.columns.nlevels
    data_names = [tuple(str(x) for x in c) if isinstance(c, tuple)
                  else (str(c),) for c in data_cols]

    # --- per-column semantics (stubs first, then data — visual order).
    # 'all' means all *data* columns; explicit lists/regex may also hit stubs.
    all_labels = stub_names + data_cols

    def _sel(selector):
        return dt.resolve_cols(selector,
                               data_cols if selector == 'all' else all_labels)

    tags = {name: _sel(getattr(spec, f'{name}_cols'))
            for name in ('ratio', 'year', 'date', 'raw')}
    html_set = _sel(spec.html_cols)
    unbreakable = _sel(spec.unbreakable)
    aligners = dt.build_aligner_map(spec, stub_names, data_cols)

    columns: list[Column] = []
    col_specs: list[FormatSpec | None] = []
    col_dtypes: list[str] = []
    series_all = stub_series + [df.iloc[:, j] for j in range(len(data_cols))]
    raw_set = _resolve_raw(spec, data_cols, df)
    cbd = st.column_break_depths(data_names)
    defaults = format_defaults(spec)
    _check_formatter_keys(spec, all_labels)

    for i, (label, ser) in enumerate(zip(all_labels, series_all)):
        is_stub = i < n_stub
        dtype = dt.column_dtype(ser)
        tag = dt.semantic_tag(label, tags)
        fspec = _resolve_format(label, ser, dtype, tag, spec, defaults)
        name = ((str(label),) if is_stub else data_names[i - n_stub])
        columns.append(Column(
            key=f'c{i}',
            name=name,
            dtype=dtype,
            align=dt.alignment(label, is_stub=is_stub, dtype=dtype, tag=tag,
                               aligners=aligners),
            role='stub' if is_stub else 'data',
            level=i if is_stub else None,
            tag=tag,
            wrap=dt.wrap_hint(dtype, tag, label, unbreakable),
            break_depth=cbd.get(i - n_stub) if not is_stub else None,
            format=fspec if isinstance(fspec, FormatSpec) else None,
            raw=(not is_stub and label in raw_set),
        ))
        col_specs.append(fspec)
        col_dtypes.append(dtype)

    # --- head assembly
    head: list[tuple[HeadCell, ...]] = []
    for level in range(n_head):
        cells: list[HeadCell] = []
        if n_stub:
            if level < n_head - 1:
                cells.append(HeadCell(colspan=n_stub))
            else:
                cells.extend(_head_cell(str(n)) for n in stub_names)
        merge = spec.sparsify_columns and level < n_head - 1
        cells.extend(_head_cell(t, s)
                     for t, s in st.head_groups(data_names, level, merge))
        head.append(tuple(cells))

    # --- body assembly
    index_tuples = [t if isinstance(t, tuple) else (t,) for t in df.index] \
        if show else []
    depths = st.break_depths(index_tuples) if show else [None] * len(df)
    layout = st.stub_layout(depths, n_stub, spec.sparsify) if show \
        else [{} for _ in range(len(df))]

    body: list[Row] = []
    for i in range(len(df)):
        cells: list[Cell] = []
        for level in sorted(layout[i]):
            span = layout[i][level]
            cells.append(_make_cell(
                index_tuples[i][level], col_specs[level], col_dtypes[level],
                spec, html=stub_names[level] in html_set, rowspan=span))
        for j, label in enumerate(data_cols):
            k = n_stub + j
            cells.append(_make_cell(
                df.iloc[i, j], col_specs[k], col_dtypes[k], spec,
                html=label in html_set,
                raw_dtype=col_dtypes[k] if label in raw_set else None,
                extra=_user_cell_flags(spec, i, label, df.iloc[i, j])))
        body.append(Row(cells=tuple(cells),
                        break_depth=depths[i],
                        flags=tuple(_user_row_flags(spec, i, df, len(df)))))

    doc = TableDoc(
        caption=caption,
        label=spec.label,
        notes=tuple(notes),
        n_stub_levels=n_stub,
        n_head_levels=n_head,
        columns=tuple(columns),
        head=tuple(head),
        body=tuple(body),
    )
    return stamp(doc, f'greater_tables {__version__}')


# --------------------------------------------------------------- ingestion

def _ingest(data, spec: TableSpec) -> tuple[pd.DataFrame, TableSpec]:
    """Normalize input to a DataFrame; markdown may fill unset spec fields."""
    if isinstance(data, pd.DataFrame):
        return data, spec
    if isinstance(data, pd.Series):
        return data.to_frame(), spec
    if isinstance(data, str):
        return _from_markdown(data, spec)
    if isinstance(data, list):
        if spec.header_row and data:
            df = pd.DataFrame(data[1:], columns=data[0])
        else:
            df = pd.DataFrame(data)
        return df, spec
    raise TypeError(f'cannot build a table from {type(data).__name__}')


def _from_markdown(txt: str, spec: TableSpec) -> tuple[pd.DataFrame, TableSpec]:
    """Parse a markdown pipe table (greater_tables MD2DF salvage).

    Extracted caption / ``{#tbl-label}`` / alignment markers fill spec
    fields the user left unset.
    """
    table_m = re.search(r'((?:\|.*\|\s*(?:\n|$))+)', txt, re.DOTALL)
    if table_m is None:
        raise ValueError('no markdown table found')
    caption_m = re.search(r'^(?:table)?:\s*(.+)', txt, re.MULTILINE | re.IGNORECASE)
    caption = caption_m.group(1).strip() if caption_m else None
    label = None
    if caption:
        lab = re.search(r'\{#(tbl[:a-zA-Z0-9_-]+)\}', caption)
        if lab:
            label = lab.group(1)
            caption = caption.replace(lab.group(0), '').strip()

    lines = re.sub(r'^\||\|$', '', table_m.group(1).strip(),
                   flags=re.MULTILINE).split('\n')
    lines[0] = '|'.join(re.sub(r'^\*\*?|\*\*?$', '', c.strip())
                        for c in lines[0].split('|'))
    align_row = lines.pop(1)
    aligners = ''
    for token in (t.strip() for t in align_row.split('|')):
        if token.startswith(':') and token.endswith(':'):
            aligners += 'c'
        elif token.startswith(':'):
            aligners += 'l'
        elif token.endswith(':'):
            aligners += 'r'
    rows = [[c.strip() for c in line.split('|')] for line in lines]
    df = pd.DataFrame(rows[1:], columns=rows[0])

    return df, replace(
        spec,
        caption=spec.caption if spec.caption is not None else caption,
        label=spec.label if spec.label is not None else label,
        aligners=spec.aligners if spec.aligners is not None else (aligners or None),
    )


# ------------------------------------------------------------------ helpers

def _trivial_index(index: pd.Index) -> bool:
    return (isinstance(index, pd.RangeIndex) and index.name is None
            and index.start == 0 and index.step == 1)


_DEFAULT_FIELDS = ('float_format', 'int_format', 'ratio_format',
                   'date_format', 'table_float_format')


def format_defaults(spec) -> dict[str, FormatSpec | None]:
    """Parse the house-default fields once per build (sugar → FormatSpec).

    Doing it here rather than per column means a bad sugar string raises once,
    naming the field, instead of N times from inside the column loop.
    """
    out: dict[str, FormatSpec | None] = {}
    for name in _DEFAULT_FIELDS:
        value = getattr(spec, name)
        if value is None:
            out[name] = None
        elif callable(value):
            raise TypeError(
                f'TableSpec.{name} takes format sugar, a mapping or a '
                'FormatSpec, not a callable — a house rule has to be '
                'expressible in YAML. Use formatters={col: fn} for a callable.')
        else:
            try:
                out[name] = parse_sugar(value)
            except ValueError as exc:
                raise ValueError(f'TableSpec.{name}: {exc}') from None
    return out


# the warning points at the caller's line, outside the package
_PACKAGE = str(Path(__file__).resolve().parent.parent)


def _check_formatter_keys(spec, labels) -> None:
    """Warn on a ``formatters`` key that matches no column: it changes
    nothing and would otherwise say nothing.

    ``'all'`` is the likely one, since the column selectors accept it. It is
    not accepted here: one formatter over every column would reach the dates
    and the text, and a float format for the whole table already exists.
    A warning, not a log record, so a caller that quiets the package logger
    (house style does) still sees it.
    """
    known = set(labels) | {lab[-1] for lab in labels if isinstance(lab, tuple)}
    for key in spec.formatters:
        if key in known:
            continue
        hint = (" For every float column use float_format, or table_float_format "
                "to override per-column entries too." if key == 'all' else '')
        warnings.warn(f'formatters key {key!r} matches no column and is ignored.{hint}',
                      skip_file_prefixes=(_PACKAGE,))


def _resolve_format(label, ser, dtype, tag, spec, defaults):
    """Two steps: what *kind* is this column, then what does that kind wear.

    The kind is its semantic tag if it has one, else its dtype. Each kind
    then resolves top-down: an explicit ``formatters`` entry, the matching
    house default, the built-in. ``table_float_format`` sits above even the
    explicit entry, but only on the float line — a ratio, year or date column
    has been given a kind, so the float sledgehammer never reaches it.
    """
    user = spec.formatters.get(label)
    if user is None and isinstance(label, tuple):
        user = spec.formatters.get(label[-1])
    if user is not None and not callable(user):
        user = parse_sugar(user)

    if tag == 'ratio':
        return user or defaults['ratio_format'] or FormatSpec(kind='pct', digits=1)
    if tag == 'year':
        return user or FormatSpec(kind='year')
    if tag == 'date':
        return user or defaults['date_format'] or FormatSpec(kind='date')
    if tag == 'raw':
        return user
    if dtype == 'int':
        return user or defaults['int_format'] or FormatSpec(kind='int', group=True)
    if dtype == 'float':
        return (defaults['table_float_format'] or user
                or defaults['float_format']
                or infer_numeric_format(ser, pef_lower=spec.pef_lower,
                                        pef_upper=spec.pef_upper,
                                        digits=spec.eng_digits,
                                        style=spec.eng_style))
    if dtype == 'date':
        return user or defaults['date_format'] or FormatSpec(kind='date')
    if dtype == 'datetime':
        return (user or defaults['date_format']
                or FormatSpec(kind='date', pattern='%Y-%m-%d %H:%M'))
    return user


def _make_cell(value, fspec, dtype, spec, *, html: bool = False,
               rowspan: int = 1, raw_dtype: str | None = None,
               extra: tuple = ()) -> Cell:
    """Format one value into a Cell, stamping neg/math/html as needed."""
    if callable(fspec):
        # user-supplied formatter (compat facade path); it owns NaN handling
        try:
            text = str(fspec(value))
        except Exception:
            text = str(value)
    else:
        text = apply_format(value, fspec)
    math_flag = False
    if isinstance(value, str) and not html:
        tex = whole_cell(value)
        if tex is not None:
            text, math_flag = tex, True
    flags = tuple(dict.fromkeys(
        (('neg',) if _is_negative(value, dtype) else ()) + tuple(extra)))
    kwargs: dict[str, Any] = {}
    if raw_dtype is not None:
        kwargs['raw'] = _json_raw(value, raw_dtype)
    return Cell(text=text, rowspan=rowspan, flags=flags, math=math_flag,
                html=html, **kwargs)


def _head_cell(text: str, colspan: int = 1) -> HeadCell:
    """Header text gets the same whole-cell math detection body cells do."""
    tex = whole_cell(text)
    if tex is not None:
        return HeadCell(text=tex, colspan=colspan, math=True)
    return HeadCell(text=text, colspan=colspan)


def _is_negative(value, dtype) -> bool:
    if dtype not in ('int', 'float'):
        return False
    try:
        return not pd.isna(value) and float(value) < 0
    except (TypeError, ValueError):
        return False


def _json_raw(value, dtype):
    """JSON-safe raw value: ISO dates, big ints as strings, no NaN/inf."""
    if pd.isna(value):
        return None
    if dtype in ('date', 'datetime'):
        return pd.Timestamp(value).isoformat()
    if dtype == 'int':
        i = int(value)
        return str(i) if abs(i) >= 2 ** 53 else i
    if dtype == 'float':
        f = float(value)
        return f if math.isfinite(f) else None
    if dtype == 'bool':
        return bool(value)
    return str(value)


def _resolve_raw(spec, data_cols, df) -> set:
    """Columns whose cells carry raw values."""
    if spec.include_raw is False:
        return set()
    if spec.include_raw is True or spec.include_raw == 'data':
        return {c for j, c in enumerate(data_cols)
                if dt.column_dtype(df.iloc[:, j]) in
                ('int', 'float', 'date', 'datetime', 'bool')}
    return dt.resolve_cols(spec.include_raw, list(data_cols))


def _user_row_flags(spec, i, df, n_rows) -> tuple:
    if spec.row_flags is None:
        return ()
    if callable(spec.row_flags):
        return tuple(spec.row_flags(i, df.iloc[i]) or ())
    for pos, flags in spec.row_flags.items():
        if (pos if pos >= 0 else n_rows + pos) == i:
            return tuple(flags)
    return ()


def _user_cell_flags(spec, i, label, value) -> tuple:
    if spec.cell_flags is None:
        return ()
    return tuple(spec.cell_flags(i, label, value) or ())
