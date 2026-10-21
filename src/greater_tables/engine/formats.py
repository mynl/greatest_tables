"""Format sugar parsing, column-statistics inference, and application.

The resolution ladder (user > semantic tag > dtype) produces
:class:`~greater_tables.ir.FormatSpec` *data objects* — never closures, so
the greater_tables late-binding formatter bug cannot recur. Application is a
pure function of (value, spec).

Sugar accepted, both prior vocabularies:

- csv-grid spec strings: ``','``? ``'.N'``? then one of ``f d % e g s``,
  plus ``'year'``, ``'eng'``, ``'si'``, and strftime patterns for dates.
- GT f-strings: ``'{x:,.1f}'``, ``'{x:.1%}'`` — the python format mini-spec.
- An int means that many decimal digits.

``g`` is the one kind whose ``digits`` counts **significant** figures rather
than decimal places, because that is what python's ``g`` presentation type
means; ``'.3g'`` renders 1234.5 as ``1.23e+03`` and 0.0012345 as
``0.00123``. Uppercase ``G``/``E`` are still unparsed — see ``dev/pending.md``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

import pandas as pd

from ..ir import FormatSpec

__all__ = ['apply_format', 'infer_numeric_format', 'parse_sugar']

_CG_RE = re.compile(r'^(?P<group>,)?(?:\.(?P<digits>\d+))?(?P<kind>[fd%eEsgG])$')
_FSTRING_RE = re.compile(r'^\{x:(?P<spec>[^}]*)\}$')
_PYSPEC_RE = re.compile(r'^(?P<group>,)?(?:\.(?P<digits>\d+))?(?P<kind>[fdeE%gG])?$')

_KIND_MAP = {'f': 'dec', 'd': 'int', '%': 'pct', 'e': 'sci', 'g': 'gen',
             's': 'str', 'E': 'sci', 'G': 'gen'}


def parse_sugar(value: FormatSpec | Mapping | str | int) -> FormatSpec:
    """Normalize a user format override to a FormatSpec.

    Accepts a FormatSpec, a mapping of its fields (the YAML form — the only
    way a config file can reach ``negative='paren'``, ``scale``, ``prefix``,
    ``suffix``, ``null`` or ``zero``), a csv-grid spec string (``',.1f'``,
    ``'.3g'``), a GT f-string (``'{x:.1%}'``, ``'{x:.3g}'``), a strftime
    pattern (``'%d %b %Y'``), the words ``'year'``/``'eng'``/``'si'``, or an
    int (decimal digits, grouped). ``g`` maps to ``kind='gen'``, where
    ``digits`` means significant figures. ``E`` and ``G`` are ``e`` and
    ``g`` with ``upper=True``: ``1.95E-05``.

    Raises
    ------
    ValueError
        If the sugar string is not recognized.
    pydantic.ValidationError
        If a mapping names a field FormatSpec does not have.
    """
    if isinstance(value, FormatSpec):
        return value
    if isinstance(value, Mapping):
        return FormatSpec(**value)
    if isinstance(value, int):
        return FormatSpec(kind='dec', digits=value, group=True)
    if value in ('year', 'eng', 'si'):
        return FormatSpec(kind=value)
    if '%' in value and not _CG_RE.match(value) and '{' not in value:
        # strftime pattern, e.g. '%Y-%m-%d' or '%d %b %Y'
        return FormatSpec(kind='date', pattern=value)
    m = _CG_RE.match(value)
    if m is None:
        f = _FSTRING_RE.match(value)
        if f is not None:
            m = _PYSPEC_RE.match(f.group('spec'))
    if m is None:
        raise ValueError(f'unrecognized format sugar: {value!r}')
    kind = _KIND_MAP.get(m.group('kind') or 'f', 'dec')
    digits = int(m.group('digits')) if m.group('digits') else None
    if kind == 'str':
        return FormatSpec(kind='str')
    return FormatSpec(kind=kind, digits=digits, group=bool(m.group('group')),
                      upper=m.group('kind') in ('E', 'G'))


def infer_numeric_format(ser: pd.Series, *, pef_lower: int = -3,
                         pef_upper: int = 6, digits: int = 3,
                         style: str = 'si') -> FormatSpec:
    """Choose a float column's format from its statistics (GT salvage).

    Digits bucket by mean magnitude (<1 → 5, <10 → 3, <20000 → 2, else 0).
    Engineering notation on either trigger: mean magnitude outside
    ``[10**pef_lower, 10**pef_upper]`` (the GT rule), or nonzero values
    spanning more than ``10**pef_upper`` orders-of-magnitude ratio (the
    csv-grid rule — no single fixed precision serves such a column), rendered
    with ``digits`` decimals in ``style`` (``'si'`` suffixes or ``'exp'``
    aligned exponents). Column-level decision — GT 5.x switched per cell,
    which mixed formats within a column.

    This is the *guess*, and it only runs when the caller has not stated a
    house rule: ``TableSpec.float_format`` (or ``table_float_format``)
    short-circuits it in :func:`greater_tables.engine.build._resolve_format`,
    which is what makes a document's floats consistent across tables.
    """
    valid = ser.dropna()
    valid = valid[[math.isfinite(float(v)) for v in valid]] if len(valid) else valid
    if len(valid) == 0:
        return FormatSpec(kind='dec', digits=2, group=True)
    amean = float(valid.abs().mean())
    absvals = [abs(float(v)) for v in valid if float(v) != 0]
    wide = bool(absvals) and max(absvals) / min(absvals) > 10.0 ** pef_upper
    if amean > 0 and (wide or not 10.0 ** pef_lower <= amean <= 10.0 ** pef_upper):
        # SI suffixes are the default engineering display; eng_style='exp'
        # switches the whole document to aligned e+00 exponents
        return FormatSpec(kind='eng' if style == 'exp' else 'si', digits=digits)
    eng = FormatSpec(kind='eng' if style == 'exp' else 'si', digits=digits)
    if amean < 1:
        digits = 5
    elif amean < 10:
        digits = 3
    elif amean < 20000:
        digits = 2
    else:
        digits = 0
    # A column that shows decimals must not print a nonzero value as zero:
    # 0.00033 under a mean of 4 came out 0.000, which claims a precision the
    # column does not have. Take the decimals the smallest value needs for
    # one significant figure; past the five the buckets ever use, the column
    # spans too much for fixed decimals, and engineering notation it is. A
    # column printed to the unit keeps rounding a stray 0.4 to 0, as a
    # financial table does.
    if digits and absvals:
        need = -math.floor(math.log10(min(absvals)))
        if need > 5:
            return eng
        digits = max(digits, need)
    return FormatSpec(kind='dec', digits=digits, group=True)


# defaults when FormatSpec.digits is None, by kind. 'gen' takes python's own
# default precision for g (6), and counts significant figures, not decimals.
_DEFAULT_DIGITS = {'dec': 2, 'pct': 1, 'sci': 2, 'gen': 6, 'eng': 3, 'si': 3}


def apply_format(value, fs: FormatSpec | None) -> str:
    """Format one value. Pure; NaN-safe; never raises on odd input."""
    if fs is None:
        return '' if pd.isna(value) else str(value)
    if pd.isna(value):
        return fs.null
    if fs.kind == 'str':
        return str(value)
    if fs.kind == 'date':
        return pd.Timestamp(value).strftime(fs.pattern or '%Y-%m-%d')
    if fs.kind == 'year':
        return str(int(value))

    try:
        v = float(value) * fs.scale
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(v):
        return fs.null
    if v == 0 and fs.zero is not None:
        return fs.zero

    digits = fs.digits if fs.digits is not None else _DEFAULT_DIGITS.get(fs.kind, 2)
    negative = v < 0
    mag = abs(v) if fs.negative == 'paren' else v

    if fs.kind == 'int':
        body = f'{round(mag):,d}' if fs.group else f'{round(mag):d}'
    elif fs.kind == 'dec':
        body = f'{mag:,.{digits}f}' if fs.group else f'{mag:.{digits}f}'
    elif fs.kind == 'pct':
        body = (f'{mag * 100:,.{digits}f}%' if fs.group
                else f'{mag * 100:.{digits}f}%')
    elif fs.kind == 'sci':
        body = f'{mag:.{digits}{"E" if fs.upper else "e"}}'
    elif fs.kind == 'gen':
        # digits counts significant figures here, not decimal places
        g = 'G' if fs.upper else 'g'
        body = f'{mag:,.{digits}{g}}' if fs.group else f'{mag:.{digits}{g}}'
    elif fs.kind == 'eng':
        body = _eng(mag, digits)
    elif fs.kind == 'si':
        body = _si(mag, digits)
    else:  # pragma: no cover — kinds are a closed Literal
        body = str(mag)

    body = f'{fs.prefix or ""}{body}{fs.suffix or ""}'
    if negative and fs.negative == 'paren':
        return f'({body})'
    return body


def _exp3(v: float) -> int:
    """Exponent snapped down to a multiple of 3."""
    e = math.floor(math.log10(abs(v)))
    return 3 * math.floor(e / 3)


def _eng(v: float, digits: int) -> str:
    """Engineering notation: mantissa in [1, 1000), exponent multiple of 3.

    Exponents are fixed-width ``e+00``/``e-00`` (sign always, two digits) so
    right-aligned columns line up exactly.
    """
    if v == 0:
        return f'{0:.{digits}f}e+00'
    e3 = _exp3(v)
    return f'{v / 10.0 ** e3:.{digits}f}e{"+" if e3 >= 0 else "-"}{abs(e3):02d}'


# full SI prefix ladder (2022 additions included) so real columns never mix
# suffix and exponent styles mid-column
_SI_SUFFIX = {-30: 'q', -27: 'r', -24: 'y', -21: 'z', -18: 'a', -15: 'f',
              -12: 'p', -9: 'n', -6: 'µ', -3: 'm', 0: '', 3: 'k', 6: 'M',
              9: 'G', 12: 'T', 15: 'P', 18: 'E', 21: 'Z', 24: 'Y', 27: 'R',
              30: 'Q'}


def _si(v: float, digits: int) -> str:
    """SI-suffix notation (1.200M style) — the default engineering display.

    The empty suffix slot (exponent 0) is a no-break space so decimal points
    stay aligned against suffixed neighbours in tabular-nums/monospace
    rendering. Falls back to :func:`_eng` beyond ±10^30.
    """
    if v == 0:
        return f'{0:.{digits}f}{chr(0xa0)}'
    e3 = _exp3(v)
    if e3 not in _SI_SUFFIX:
        return _eng(v, digits)
    return f'{v / 10.0 ** e3:.{digits}f}{_SI_SUFFIX[e3] or chr(0xa0)}'
