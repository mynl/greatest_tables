"""YAML configuration: load a TableSpec (project defaults or per-table).

YAML is this project's single config format (pyproject.toml aside). The file
is a plain mapping of TableSpec field names; unknown keys raise so typos
surface. Callable fields (row_flags, cell_flags) are code, not config.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .spec import TableSpec

__all__ = ['load_spec', 'write_template']


def load_spec(path: str | Path) -> TableSpec:
    """Load a TableSpec from a YAML mapping file."""
    data = yaml.safe_load(Path(path).read_text(encoding='utf-8')) or {}
    if not isinstance(data, dict):
        raise ValueError(f'{path}: expected a YAML mapping of TableSpec fields')
    return TableSpec(**data)


def write_template(path: str | Path) -> Path:
    """Write a commented template of the configurable TableSpec fields."""
    path = Path(path)
    lines = [
        '# greatest_tables TableSpec — uncomment and edit; see spec.py docs',
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
