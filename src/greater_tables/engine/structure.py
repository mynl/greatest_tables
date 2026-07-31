"""Table structure: row break depths, stub rowspans, head colspans.

The single implementation of the hierarchy logic (greater_tables derived it
independently per backend). Everything here is pure functions over plain
Python sequences — no pandas mutation, no rendering concerns.
"""

from __future__ import annotations

from typing import Hashable, Sequence

__all__ = ['break_depths', 'column_break_depths', 'head_groups', 'stub_layout']


def break_depths(tuples: Sequence[tuple]) -> list[int | None]:
    """Per row, the shallowest level whose value changed vs. the row above.

    Row 0 is None (top edge is structural). A row identical to its
    predecessor is also None — no boundary at all.
    """
    out: list[int | None] = [None]
    for prev, cur in zip(tuples, tuples[1:]):
        depth = None
        for level, (a, b) in enumerate(zip(prev, cur)):
            if a != b:
                depth = level
                break
        out.append(depth)
    return out


def stub_layout(depths: Sequence[int | None], n_levels: int,
                sparsify: bool) -> list[dict[int, int]]:
    """Which stub cells each row emits, and with what rowspan.

    Returns one dict per row mapping stub level → rowspan for the levels
    that start a run at that row (HTML ``<td rowspan>`` semantics: covered
    rows omit the cell entirely). Without sparsify every row emits every
    level with span 1.
    """
    n_rows = len(depths)
    if not sparsify:
        return [{lvl: 1 for lvl in range(n_levels)} for _ in range(n_rows)]
    out: list[dict[int, int]] = []
    for i in range(n_rows):
        cells: dict[int, int] = {}
        for level in range(n_levels):
            starts = i == 0 or (depths[i] is not None and depths[i] <= level)
            if not starts:
                continue
            span = 1
            for j in range(i + 1, n_rows):
                if depths[j] is not None and depths[j] <= level:
                    break
                span += 1
            cells[level] = span
        out.append(cells)
    return out


def head_groups(names: Sequence[tuple], level: int,
                merge: bool) -> list[tuple[str, int]]:
    """Header cells for one level: (text, colspan) runs over data columns.

    Adjacent columns group only while their *full prefix* through ``level``
    matches — the same leaf label under different parents never merges.
    The deepest level is never merged (distinct columns stay distinct);
    callers pass ``merge=False`` there and when sparsify_columns is off.
    """
    out: list[tuple[str, int]] = []
    last_prefix: tuple | None = None
    for name in names:
        text = str(name[level]) if level < len(name) else ''
        prefix = name[:level + 1]
        if merge and out and prefix == last_prefix:
            out[-1] = (out[-1][0], out[-1][1] + 1)
        else:
            out.append((text, 1))
        last_prefix = prefix
    return out


def column_break_depths(names: Sequence[tuple]) -> dict[int, int]:
    """Data-column positions carrying a column-group boundary at their left edge.

    Depth = shallowest head level that changes between column j-1 and j.
    Only genuine *group* boundaries are reported (depth ≤ n_levels − 2);
    leaf-level changes are just "next column".
    """
    out: dict[int, int] = {}
    if not names:
        return out
    n_levels = max(len(n) for n in names)
    for j in range(1, len(names)):
        prev, cur = names[j - 1], names[j]
        for level in range(min(len(prev), len(cur))):
            if prev[level] != cur[level]:
                if level <= n_levels - 2:
                    out[j] = level
                break
    return out
