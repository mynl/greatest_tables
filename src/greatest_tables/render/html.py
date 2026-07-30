"""Python HTML renderer: TableDoc → fragment.

Mirrors ``js/src/gt-render.js`` structure and class stamping EXACTLY — the
DOM-transcript conformance goldens (``tests/golden/transcript``) enforce the
agreement, so any change here must be paired with the walker and the goldens
regenerated. Class helpers below are direct ports of the walker's.

Escaping: every ``text`` is HTML-escaped unless the cell carries
``html: true`` and ``allow_html`` is on (the default here — the producer set
that flag deliberately via ``TableSpec.html_cols``; the walker's default is
the opposite because it consumes foreign documents).

Stylesheet policy (dev/design.md): ``css='embed'`` puts the ~2 KB sheet in
every fragment (idempotent — duplicates are no-ops, and a saved notebook
whose first cell was cleared keeps its styles); ``'once'`` embeds only the
first time per process; ``'none'`` for documents that include gt.css
themselves. ``inline_css=True`` flattens the same RULES dict onto style
attributes for HTMX-fragment/email use — no classes required by the host.
"""

from __future__ import annotations

import html as _html
import re

from ..ir import Cell, HeadCell, Row, TableDoc
from . import css as _css

__all__ = ['render_html', 'reset_css_once']

# row rules: gt-break-{d} for d ≤ min(2, stubs-2); column rules: d ≤ 1
_MAX_BREAK = 2
_MAX_VBREAK = 1

_CELL_FLAG_CLASS = {'neg': 'gt-neg', 'emphasis': 'gt-emph', 'muted': 'gt-muted'}
_ROW_FLAG_CLASS = {'total': 'gt-total', 'subtotal': 'gt-subtotal',
                   'emphasis': 'gt-emph', 'muted': 'gt-muted'}

_css_emitted = False


def reset_css_once() -> None:
    """Reset the ``css='once'`` latch (new kernel/document boundary)."""
    global _css_emitted
    _css_emitted = False


def render_html(doc: TableDoc, *, css: str = 'embed',
                inline_css: bool = False, allow_html: bool = True) -> str:
    """Render a table document to an HTML fragment.

    Parameters
    ----------
    doc
        The document.
    css
        ``'embed'`` (default), ``'once'``, or ``'none'``.
    inline_css
        Flatten the stylesheet onto ``style`` attributes (HTMX/email);
        implies ``css='none'``.
    allow_html
        Honor cell ``html: true``. Off ⇒ such cells render as escaped source.
    """
    global _css_emitted
    ncols = len(doc.columns)
    sty = _Styler(inline_css)
    out: list[str] = []

    if not inline_css and css != 'none' and not (css == 'once' and _css_emitted):
        out.append(f'<style>{_css.css_text()}</style>')
        _css_emitted = True

    attrs = ['class="gt"']
    if doc.hash:
        attrs.append(f'data-gt-hash="{doc.hash}"')
    if doc.label:
        attrs.append(f'id="{_esc(doc.label)}"')
    out.append(f'<div {" ".join(attrs)}{sty.attr(".gt")}>')
    out.append(f'<table{sty.attr("table")}>')

    if doc.caption is not None:
        cap = doc.caption if isinstance(doc.caption, Cell) else Cell(text=doc.caption)
        cls, content = _cell_content(cap, ['gt-caption'], allow_html)
        out.append(f'<caption class="{" ".join(cls)}"'
                   f'{sty.attr(".gt-caption")}>{content}</caption>')

    if doc.head:
        out.append('<thead>')
        n_head = len(doc.head)
        for level, row in enumerate(doc.head):
            leaf = level == n_head - 1
            cells = []
            col = 0
            for hc in row:
                colspan = hc.colspan
                cls = _head_classes(doc, col, colspan, leaf, hc)
                cls, content = _cell_content(hc, cls, allow_html)
                span = f' colspan="{colspan}"' if colspan > 1 else ''
                cells.append(f'<th{span} class="{" ".join(cls)}"'
                             f'{sty.th(cls, leaf)}>{content}</th>')
                col += colspan
            out.append('<tr>' + ''.join(cells) + '</tr>')
        out.append('</thead>')

    out.append('<tbody>')
    out.extend(_section(doc, doc.body, sty, allow_html))
    out.append('</tbody>')
    if doc.foot:
        out.append('<tfoot>')
        out.extend(_section(doc, doc.foot, sty, allow_html))
        out.append('</tfoot>')
    out.append('</table>')

    if doc.notes:
        notes = ''.join(f'<div>{_esc(n)}</div>' for n in doc.notes)
        out.append(f'<div class="gt-notes"{sty.attr(".gt-notes")}>{notes}</div>')
    out.append('</div>')
    return '\n'.join(out)


def _section(doc: TableDoc, rows: tuple[Row, ...], sty: _Styler,
             allow_html: bool) -> list[str]:
    ncols = len(doc.columns)
    pending = [0] * ncols
    out: list[str] = []
    for r, row in enumerate(rows):
        row_cls = _row_classes(doc, row)
        cls_attr = f' class="{" ".join(row_cls)}"' if row_cls else ''
        cells = []
        col = 0
        for entry in row.cells:
            cell = entry if isinstance(entry, Cell) else Cell(text=entry)
            while col < ncols and pending[col] > 0:
                col += 1
            if col >= ncols:
                break
            cls = _body_classes(doc, col, cell.colspan, cell)
            cls, content = _cell_content(cell, cls, allow_html)
            span = ''
            if cell.colspan > 1:
                span += f' colspan="{cell.colspan}"'
            if cell.rowspan > 1:
                span += f' rowspan="{cell.rowspan}"'
            cells.append(f'<td data-c="{col}"{span} class="{" ".join(cls)}"'
                         f'{sty.td(cls, row_cls)}>{content}</td>')
            for cc in range(col, min(ncols, col + cell.colspan)):
                if cell.rowspan > 1:
                    pending[cc] = cell.rowspan
            col += cell.colspan
        for cc in range(ncols):
            if pending[cc] > 0:
                pending[cc] -= 1
        out.append(f'<tr data-r="{r}"{cls_attr}>' + ''.join(cells) + '</tr>')
    return out


def _cell_content(cell: Cell | HeadCell, cls: list[str],
                  allow_html: bool) -> tuple[list[str], str]:
    """Return (classes, inner html) applying math/html handling (walker port)."""
    if cell.math:
        return cls + ['gt-math'], _esc(f'\\({cell.text}\\)')
    if cell.html and allow_html:
        return cls, cell.text
    return cls, _esc(cell.text)


def _esc(text: str) -> str:
    return _html.escape(text, quote=False)


# ---- class stamping: direct ports of gt-render.js — keep in lockstep

def _column_classes(doc: TableDoc, col: int) -> list[str]:
    c = doc.columns[col]
    cls = [f'gt-{c.align}', 'gt-stub' if c.role == 'stub' else 'gt-data',
           'gt-wrap' if c.wrap else 'gt-nowrap']
    if (c.role == 'data' and c.break_depth is not None
            and c.break_depth <= _MAX_VBREAK):
        cls.append(f'gt-vbreak-{c.break_depth}')
    return cls


def _head_classes(doc: TableDoc, col: int, colspan: int, leaf: bool,
                  hc: HeadCell) -> list[str]:
    cls: list[str] = []
    first = doc.columns[col] if col < len(doc.columns) else None
    n_stub = doc.n_stub_levels
    if hc.align:
        cls.append(f'gt-{hc.align}')
    elif not leaf or colspan > 1:
        cls.append('gt-c')
    elif first:
        cls.append(f'gt-{first.align}')
    else:
        cls.append('gt-l')
    cls.append('gt-stub' if first and col < n_stub else 'gt-data')
    if n_stub > 0 and col + colspan == n_stub:
        cls.append('gt-stub-end')
    bd = first.break_depth if first else None
    if col >= n_stub and bd is not None and bd <= _MAX_VBREAK:
        cls.append(f'gt-vbreak-{bd}')
    cls.extend(_CELL_FLAG_CLASS[f] for f in hc.flags if f in _CELL_FLAG_CLASS)
    return cls


def _body_classes(doc: TableDoc, col: int, colspan: int, cell: Cell) -> list[str]:
    cls = _column_classes(doc, col)
    if doc.n_stub_levels > 0 and col + colspan == doc.n_stub_levels:
        cls.append('gt-stub-end')
    cls.extend(_CELL_FLAG_CLASS[f] for f in cell.flags if f in _CELL_FLAG_CLASS)
    return cls


def _row_classes(doc: TableDoc, row: Row) -> list[str]:
    cls: list[str] = []
    d = row.break_depth
    if d is not None and d <= min(_MAX_BREAK, doc.n_stub_levels - 2):
        cls.append(f'gt-break-{d}')
    cls.extend(_ROW_FLAG_CLASS[f] for f in row.flags if f in _ROW_FLAG_CLASS)
    return cls


# ---- inline styling (fiscus/HTMX/email path) — same RULES dict, flattened

class _Styler:
    """Resolve RULES onto style attributes when ``inline_css`` is on.

    Understands exactly the selector shapes RULES uses; the vocabulary test
    plus conformance goldens keep this honest. Custom-property references are
    substituted with their VARIABLES defaults (email clients know no vars).
    """

    def __init__(self, active: bool):
        self.active = active

    def attr(self, key: str) -> str:
        if not self.active:
            return ''
        props = {
            '.gt': {'line-height': _css.RULES['.gt']['line-height'],
                    'width': 'fit-content'},
            'table': _css.RULES['.gt.gt table'],
            '.gt-caption': _css.RULES['.gt.gt .gt-caption'],
            '.gt-notes': _css.RULES['.gt.gt .gt-notes'],
        }.get(key, {})
        return self._style(props)

    def td(self, cls: list[str], row_cls: list[str]) -> str:
        if not self.active:
            return ''
        props = dict(_css.RULES['.gt.gt td, .gt.gt th'])
        for c in cls:
            props.update(_css.RULES.get(f'.gt.gt .{c}', {}))
        for rc in row_cls:
            props.update(_css.RULES.get(f'.gt.gt tr.{rc} > td', {}))
        return self._style(props)

    def th(self, cls: list[str], leaf: bool) -> str:
        if not self.active:
            return ''
        props = dict(_css.RULES['.gt.gt td, .gt.gt th'])
        props.update(_css.RULES['.gt.gt th'])
        for c in cls:
            props.update(_css.RULES.get(f'.gt.gt .{c}', {}))
        if leaf:
            props.update(_css.RULES['.gt.gt thead tr:last-child th'])
        return self._style(props)

    @staticmethod
    def _style(props: dict[str, str]) -> str:
        if not props:
            return ''
        body = ' '.join(f'{k}: {_resolve_vars(v)};' for k, v in props.items()
                        if not k.startswith('--'))
        return f' style="{body}"' if body else ''


_VAR_RE = re.compile(r'var\((--[a-z-]+)(?:,\s*([^)]+))?\)')


def _resolve_vars(value: str) -> str:
    """Substitute var(--gt-x) references with their VARIABLES defaults."""
    def sub(m: re.Match) -> str:
        return _css.VARIABLES.get(m.group(1), m.group(2) or '')
    return _VAR_RE.sub(sub, value)
