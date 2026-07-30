"""Column dtype discovery, semantic tags, alignment, and wrap hints.

Arrow-aware via ``pandas.api.types`` predicates — dtypes are trusted, never
coerced (the greater_tables float-coercion loop does not come along).
"""

from __future__ import annotations

import re
from typing import Any, Hashable

import pandas as pd
from pandas.api.types import (
    is_bool_dtype, is_datetime64_any_dtype, is_float_dtype, is_integer_dtype,
    is_string_dtype,
)

from ..ir import Alignment, Dtype, Tag
from ..spec import ColSelector, TableSpec

__all__ = ['alignment', 'column_dtype', 'resolve_cols', 'semantic_tag', 'wrap_hint']


def column_dtype(ser: pd.Series) -> Dtype:
    """Classify a series into an IR dtype.

    Datetime columns whose values all sit at midnight classify as ``date``;
    any time-of-day component makes them ``datetime``.
    """
    dtype = ser.dtype
    if is_datetime64_any_dtype(dtype):
        valid = ser.dropna()
        if len(valid) and (valid.dt.normalize() == valid).all():
            return 'date'
        return 'datetime'
    if is_bool_dtype(dtype):
        return 'bool'
    if is_integer_dtype(dtype):
        return 'int'
    if is_float_dtype(dtype):
        return 'float'
    if is_string_dtype(dtype):
        return 'string'
    return 'object'


def resolve_cols(selector: ColSelector, columns: list[Hashable]) -> set[Hashable]:
    """Resolve a column selector to a set of labels from ``columns``.

    A list matches labels exactly (and leaf names for tuple labels);
    ``'all'`` matches everything; any other string is a regex searched
    against the leaf name and the full label.
    """
    if selector is None:
        return set()
    if isinstance(selector, str):
        if selector == 'all':
            return set(columns)
        pattern = re.compile(selector)
        return {c for c in columns
                if pattern.search(str(c[-1] if isinstance(c, tuple) else c))
                or pattern.search(str(c))}
    wanted = set(selector)
    out = set()
    for c in columns:
        if c in wanted or (isinstance(c, tuple) and c[-1] in wanted):
            out.add(c)
    return out


def semantic_tag(col: Hashable, tags: dict[str, set[Hashable]]) -> Tag | None:
    """Return the winning semantic tag for a column (GT ladder order)."""
    for name in ('ratio', 'year', 'date', 'raw'):
        if col in tags[name]:
            return name  # type: ignore[return-value]
    return None


def alignment(col: Hashable, *, is_stub: bool, dtype: Dtype, tag: Tag | None,
              aligners: dict[Hashable, str]) -> Alignment:
    """Alignment ladder: user > stub-left > year-center > raw-left >
    date-center > numeric-right > left."""
    if col in aligners and aligners[col] in ('l', 'r', 'c'):
        return aligners[col]  # type: ignore[return-value]
    if is_stub and tag is None:
        return 'l'
    if tag == 'year':
        return 'c'
    if tag == 'raw':
        return 'l'
    if tag == 'date' or dtype in ('date', 'datetime'):
        return 'c'
    if tag == 'ratio' or dtype in ('int', 'float'):
        return 'r'
    return 'l'


def wrap_hint(dtype: Dtype, tag: Tag | None, col: Hashable,
              unbreakable: set[Hashable]) -> bool:
    """Prose (string/object, untagged) columns may wrap; everything else not."""
    if col in unbreakable:
        return False
    return dtype in ('string', 'object') and tag is None


def build_aligner_map(spec: TableSpec, stub_names: list[Hashable],
                      data_cols: list[Hashable]) -> dict[Hashable, str]:
    """Normalize spec.aligners to a label → 'l'/'r'/'c' map.

    A positional 'lrc' string covers stub columns first, then data columns
    (matching the visual order).
    """
    if spec.aligners is None:
        return {}
    if isinstance(spec.aligners, str):
        ordered: list[Any] = list(stub_names) + list(data_cols)
        return dict(zip(ordered, spec.aligners))
    return dict(spec.aligners)
