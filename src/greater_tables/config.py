"""YAML configuration: load a TableSpec (project defaults or per-table).

YAML is this project's single config format (pyproject.toml aside). A file is
a plain mapping of field names; unknown keys raise so typos surface. Callable
fields (row_flags, cell_flags) are code, not config.

Two files, because the two objects mean different things: a **spec** file
holds semantics that travel with the table (formats, column tags), a **style**
file holds renderer opinions that do not (rule depth, TikZ geometry). Keeping
them apart is the same split as :mod:`greater_tables.spec`; a single file
with two sections would blur it.
"""

from __future__ import annotations

from dataclasses import asdict, fields
from pathlib import Path

import yaml

from .spec import HouseStyle, TableSpec

__all__ = ['load_spec', 'load_style', 'spec_to_yaml', 'write_template']


def load_spec(path: str | Path) -> TableSpec:
    """Load a TableSpec from a YAML mapping file.

    ``notes`` arrives from YAML as a list and is converted to the tuple the
    dataclass holds, so a loaded spec compares equal to the Python-built one
    (and ``write_template(path, spec)`` round-trips).
    """
    data = yaml.safe_load(Path(path).read_text(encoding='utf-8')) or {}
    if not isinstance(data, dict):
        raise ValueError(f'{path}: expected a YAML mapping of TableSpec fields')
    if isinstance(data.get('notes'), list):
        data['notes'] = tuple(data['notes'])
    return TableSpec(**data)


def load_style(path: str | Path) -> HouseStyle:
    """Load a HouseStyle from a YAML mapping file.

    Tuple-valued fields (``hrule_widths``, ``vrule_widths``) arrive from YAML
    as lists and are converted, so ``hrule_widths: [1, 0.5, 0]`` works.
    """
    data = yaml.safe_load(Path(path).read_text(encoding='utf-8')) or {}
    if not isinstance(data, dict):
        raise ValueError(f'{path}: expected a YAML mapping of HouseStyle fields')
    for key in ('hrule_widths', 'vrule_widths'):
        if isinstance(data.get(key), list):
            data[key] = tuple(data[key])
    return HouseStyle(**data)


# one-line hints, generated into the template beside each field
_HINTS = {
    'caption': 'My table',
    'label': 'tbl-my-table',
    'notes': '[Amounts in USD thousands.]',
    'show_index': 'true          # null = auto-hide a trivial RangeIndex',
    'header_row': 'false         # list input: promote row 0 to headers',
    'ratio_cols': "'lr|ratio$'   # list of labels, 'all', or a regex",
    'year_cols': '[year]',
    'date_cols': '[reported]',
    'raw_cols': '[account_id]    # no formatting at all, left-aligned',
    'html_cols': '[link]',
    'unbreakable': '[note]       # never wrap',
    'aligners': "llrrc          # positional, or {label: 'r'}",
    'formatters': "{paid: ',.1f', premium: {kind: dec, digits: 1, "
                  'negative: paren}}',
    'float_format': "',.2f'      # house default for every float column",
    'int_format': "',d'",
    'ratio_format': "'.1%'",
    'date_format': "'%d %b %Y'   # date tag, date and datetime dtypes",
    'row_flags': None,           # code, not config
    'cell_flags': None,
    'include_raw': "false         # true/'data' or an explicit column list",
    'max_rows': '200           # null = unlimited',
    'sparsify': 'true',
    'sparsify_columns': 'true',
    'pef_lower': '-3            # engineering format below 10**this',
    'pef_upper': '6             # …and above 10**this',
    'eng_digits': '3',
    'eng_style': "si            # or 'exp' for aligned e+00 exponents",
    # table_float_format is deliberately absent: see the docstring
}


def spec_to_yaml(spec: TableSpec) -> str:
    """Serialize a TableSpec's effective values to YAML.

    Raises
    ------
    ValueError
        If ``row_flags`` or ``cell_flags`` holds a callable — code has no
        YAML form, and emitting a function repr would produce a file that
        cannot be loaded back.
    """
    data = asdict(spec)
    for name in ('row_flags', 'cell_flags'):
        if callable(data.get(name)):
            raise ValueError(
                f'TableSpec.{name} is a callable and has no YAML form; '
                'drop it before dumping (it is code, not configuration)')
    data = {k: (list(v) if isinstance(v, tuple) else v)
            for k, v in data.items()}
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False,
                          allow_unicode=True)


def write_template(path: str | Path, spec: TableSpec | None = None) -> Path:
    """Write a YAML TableSpec template, or dump one spec's effective values.

    With ``spec=None`` every field appears commented out with a one-line
    hint — a starting point to copy from. Pass a spec and its **actual**
    settings are written uncommented, so the round trip is
    ``write_template('house.yaml', gt.spec)`` → edit → ``config_path=``.

    ``table_float_format`` is never written: it overrides even per-column
    formatters, which makes it right for a deliberate call site and wrong in
    a file that outlives the reason you set it.
    """
    path = Path(path)
    if spec is not None:
        data = yaml.safe_load(spec_to_yaml(spec)) or {}
        data.pop('table_float_format', None)
        body = yaml.safe_dump({k: v for k, v in data.items() if v is not None},
                              sort_keys=False, default_flow_style=False,
                              allow_unicode=True)
        header = ('# greater_tables TableSpec — effective settings\n'
                  '# load with GT(df, config_path=...) or load_spec(path)\n')
        path.write_text(header + body, encoding='utf-8')
        return path

    lines = ['# greater_tables TableSpec — uncomment and edit',
             '# every field below is optional; see spec.py for the full docs']
    for f in fields(TableSpec):
        hint = _HINTS.get(f.name, '')
        if hint is None:
            lines.append(f'# {f.name}: (callable — code, no YAML form)')
        else:
            lines.append(f'# {f.name}: {hint}')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path
