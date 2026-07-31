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

from pathlib import Path

import yaml

from .spec import HouseStyle, TableSpec

__all__ = ['load_spec', 'load_style', 'write_template']


def load_spec(path: str | Path) -> TableSpec:
    """Load a TableSpec from a YAML mapping file."""
    data = yaml.safe_load(Path(path).read_text(encoding='utf-8')) or {}
    if not isinstance(data, dict):
        raise ValueError(f'{path}: expected a YAML mapping of TableSpec fields')
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


def write_template(path: str | Path) -> Path:
    """Write a commented template of the configurable TableSpec fields."""
    path = Path(path)
    lines = [
        '# greater_tables TableSpec — uncomment and edit; see spec.py docs',
        '# caption: My table',
        '# label: tbl-my-table',
        '# notes: [Amounts in USD thousands.]',
        '# show_index: true',
        "# ratio_cols: 'lr|ratio'   # list, 'all', or regex",
        '# year_cols: [year]',
        "# formats: {paid: ',.1f', premium: 0}",
        '# include_raw: false',
        '# max_rows: 200',
        '# sparsify: true',
        '# pef_lower: -3',
        '# pef_upper: 6',
    ]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path
