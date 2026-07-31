"""Text renderer — the conformance oracle.

Reads *only* the TableDoc. Anything this renderer cannot draw is data
missing from the IR, which is the point: it keeps the IR honest. Output is
deterministic monospace text with box-drawing rules.

Semantics made visible: break depths draw partial horizontal rules starting
at the changed stub column (depth ≤ n_stub_levels − 2, the shared renderer
policy); rowspan/colspan cells span; row flags appear in a right gutter;
math cells render as ``$tex$``; emphasis/muted cells as ``*text*``/``~text~``.
"""

from __future__ import annotations

from ..ir import Cell, HeadCell, Row, TableDoc

__all__ = ['render_text']

GAP = 2            # spaces between columns
STUB_GAP = 3       # ' │ ' between stub block and data block


def render_text(doc: TableDoc) -> str:
    """Render a table document to monospace text."""
    ncols = len(doc.columns)
    lines: list[str] = []
    if doc.caption:
        cap = doc.caption if isinstance(doc.caption, str) else _decorate(doc.caption)
        if doc.label:
            cap += f' {{#{doc.label}}}'
        lines.append(cap)
        lines.append('')
    if ncols == 0:
        lines.append('(empty table)')
        return '\n'.join(lines + [''])

    body_grid, body_rows = _place(doc.body, ncols)
    foot_grid, foot_rows = _place(doc.foot, ncols)
    widths, gaps = _solve_widths(doc, body_grid, foot_grid)
    total = sum(widths) + sum(gaps)

    lines.append('━' * total)
    for level, row in enumerate(doc.head):
        leaf = level == len(doc.head) - 1
        lines.append(_head_line(row, doc, widths, gaps, leaf))
        if not leaf:
            rule = _spanner_line(row, widths, gaps, total)
            if rule.strip():
                lines.append(rule)
    if doc.head:
        lines.append('━' * total)
    lines.extend(_section_lines(doc, doc.body, body_grid, widths, gaps))
    if doc.foot:
        lines.append('━' * total)
        lines.extend(_section_lines(doc, doc.foot, foot_grid, widths, gaps))
    lines.append('━' * total)
    for note in doc.notes:
        lines.append(f'Note: {note}')
    return '\n'.join(lines + [''])


# ---------------------------------------------------------------- placement

def _place(rows: tuple[Row, ...], ncols: int):
    """Expand rows into an occupancy grid of (cell, is_origin, col_span)."""
    n = len(rows)
    grid: list[list[tuple[Cell, bool] | None]] = [[None] * ncols for _ in range(n)]
    norm_rows: list[list[Cell]] = []
    for r, row in enumerate(rows):
        cells = [c if isinstance(c, Cell) else Cell(text=c) for c in row.cells]
        norm_rows.append(cells)
        col = 0
        for cell in cells:
            while col < ncols and grid[r][col] is not None:
                col += 1
            if col >= ncols:
                break
            for rr in range(r, min(n, r + cell.rowspan)):
                for cc in range(col, min(ncols, col + cell.colspan)):
                    grid[rr][cc] = (cell, rr == r and cc == col)
            col += cell.colspan
    return grid, norm_rows


def _decorate(cell: Cell) -> str:
    text = cell.text
    if cell.math:
        text = f'${text}$'
    if 'emphasis' in cell.flags:
        text = f'*{text}*'
    if 'muted' in cell.flags:
        text = f'~{text}~'
    return text


# ------------------------------------------------------------------- widths

def _solve_widths(doc: TableDoc, *grids) -> tuple[list[int], list[int]]:
    ncols = len(doc.columns)
    n_stub = doc.n_stub_levels
    widths = [1] * ncols
    # singleton cells set natural widths
    for row in doc.head:
        col = 0
        for hc in row:
            if hc.colspan == 1:
                widths[col] = max(widths[col], len(hc.text))
            col += hc.colspan
    for grid in grids:
        for r, grow in enumerate(grid):
            for c, entry in enumerate(grow):
                if entry and entry[1] and entry[0].colspan == 1:
                    widths[c] = max(widths[c], len(_decorate(entry[0])))
    gaps = [0] + [STUB_GAP if 0 < n_stub == i else GAP for i in range(1, ncols)]
    # spanning cells may need more room: widen the last spanned column
    def ensure(col: int, span: int, text_len: int) -> None:
        have = sum(widths[col:col + span]) + sum(gaps[col + 1:col + span])
        if text_len > have:
            widths[col + span - 1] += text_len - have
    for row in doc.head:
        col = 0
        for hc in row:
            if hc.colspan > 1:
                ensure(col, hc.colspan, len(hc.text))
            col += hc.colspan
    for grid in grids:
        for r, grow in enumerate(grid):
            for c, entry in enumerate(grow):
                if entry and entry[1] and entry[0].colspan > 1:
                    ensure(c, entry[0].colspan, len(_decorate(entry[0])))
    return widths, gaps


def _pad(text: str, width: int, align: str) -> str:
    if align == 'r':
        return text.rjust(width)
    if align == 'c':
        return text.center(width)
    return text.ljust(width)


# ------------------------------------------------------------------ drawing

def _head_line(row: tuple[HeadCell, ...], doc: TableDoc, widths, gaps,
               leaf: bool) -> str:
    parts: list[str] = []
    col = 0
    for hc in row:
        span_w = (sum(widths[col:col + hc.colspan])
                  + sum(gaps[col + 1:col + hc.colspan]))
        if hc.align:
            align = hc.align
        elif hc.colspan > 1:
            align = 'c'
        elif leaf:
            align = doc.columns[col].align
        else:
            align = 'l'
        parts.append((_gap_str(gaps[col]) if col else '')
                     + _pad(hc.text, span_w, align))
        col += hc.colspan
    return ''.join(parts).rstrip()


def _gap_str(gap: int) -> str:
    return ' │ ' if gap == STUB_GAP else ' ' * gap


def _spanner_line(row: tuple[HeadCell, ...], widths, gaps, total: int) -> str:
    """Underline runs beneath labeled group cells (cmidrule analogue)."""
    chars = [' '] * total
    col = 0
    offset = 0
    for hc in row:
        span_w = (sum(widths[col:col + hc.colspan])
                  + sum(gaps[col + 1:col + hc.colspan]))
        if hc.text:
            for k in range(offset, min(total, offset + span_w)):
                chars[k] = '─'
        offset += span_w + (gaps[col + hc.colspan]
                            if col + hc.colspan < len(widths) else 0)
        col += hc.colspan
    return ''.join(chars).rstrip()


def _section_lines(doc: TableDoc, rows: tuple[Row, ...], grid, widths,
                   gaps) -> list[str]:
    lines: list[str] = []
    total = sum(widths) + sum(gaps)
    for r, row in enumerate(rows):
        depth = row.break_depth
        if (r > 0 and depth is not None
                and depth <= doc.n_stub_levels - 2):
            offset = sum(widths[:depth]) + sum(gaps[:depth + 1])
            lines.append(' ' * offset + '─' * (total - offset))
        parts: list[str] = []
        col = 0
        while col < len(doc.columns):
            entry = grid[r][col]
            if entry is None:
                parts.append((_gap_str(gaps[col]) if col else '')
                             + ' ' * widths[col])
                col += 1
                continue
            cell, origin = entry
            span = cell.colspan
            span_w = sum(widths[col:col + span]) + sum(gaps[col + 1:col + span])
            text = _decorate(cell) if origin else ''
            align = 'c' if span > 1 else doc.columns[col].align
            parts.append((_gap_str(gaps[col]) if col else '')
                         + _pad(text, span_w, align))
            col += span
        line = ''.join(parts)
        if row.flags:
            line = line + '  «' + ','.join(row.flags) + '»'
        lines.append(line.rstrip())
    return lines
