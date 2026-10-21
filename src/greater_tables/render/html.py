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
from ..mathspans import segments
from ..spec import HouseStyle
from . import css as _css
from .policy import N_RULE_SLOTS, N_VRULE_SLOTS, rule_slot, vrule_slot

__all__ = ['render_html', 'reset_css_once']

_CELL_FLAG_CLASS = {'neg': 'gt-neg', 'emphasis': 'gt-emph', 'muted': 'gt-muted'}
_ROW_FLAG_CLASS = {'total': 'gt-total', 'subtotal': 'gt-subtotal',
                   'emphasis': 'gt-emph', 'muted': 'gt-muted'}

_css_emitted = False


def reset_css_once() -> None:
    """Reset the ``css='once'`` latch (new kernel/document boundary)."""
    global _css_emitted
    _css_emitted = False


def render_html(doc: TableDoc, *, css: str = 'embed',
                inline_css: bool = False, allow_html: bool = True,
                style: HouseStyle | None = None) -> str:
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
    style
        House style. ``max_rule_depth`` and ``max_vrule_depth`` decide which
        breaks get a ``gt-break-{slot}`` / ``gt-vbreak-{slot}`` class. Rule
        *weights* are CSS custom properties (``--gt-rule-{slot}``,
        ``--gt-vrule-{slot}``, ``--gt-rule-frame`` and so on): a weight set
        away from its ``HouseStyle`` default scales its property on this
        table, so ``hrule_widths=(1.0, ...)``, twice the default 0.5, draws
        the 0.5pt rule at 1pt, and 0 draws none. The sheet still governs every
        weight left at its default, so a document theme beats the defaults.
    """
    global _css_emitted
    style = style or HouseStyle()
    math_on = doc.math != 'off'
    ncols = len(doc.columns)
    custom = _width_properties(style) | _rule_properties(style)
    sty = _Styler(inline_css, custom)
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
        cls, content = _cell_content(cap, ['gt-caption'], allow_html, math_on)
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
                cls = _head_classes(doc, col, colspan, leaf, hc,
                                    style.max_vrule_depth)
                cls, content = _cell_content(hc, cls, allow_html, math_on)
                span = f' colspan="{colspan}"' if colspan > 1 else ''
                cells.append(f'<th{span} class="{" ".join(cls)}"'
                             f'{sty.th(cls, leaf)}>{content}</th>')
                col += colspan
            out.append('<tr>' + ''.join(cells) + '</tr>')
        out.append('</thead>')

    out.append('<tbody>')
    out.extend(_section(doc, doc.body, sty, allow_html, style))
    out.append('</tbody>')
    if doc.foot:
        out.append('<tfoot>')
        out.extend(_section(doc, doc.foot, sty, allow_html, style))
        out.append('</tfoot>')
    out.append('</table>')

    if doc.notes:
        notes = ''.join(f'<div>{_span_html(n, math_on)}</div>'
                        for n in doc.notes)
        out.append(f'<div class="gt-notes"{sty.attr(".gt-notes")}>{notes}</div>')
    out.append('</div>')
    return '\n'.join(out)


def _section(doc: TableDoc, rows: tuple[Row, ...], sty: _Styler,
             allow_html: bool, style: HouseStyle) -> list[str]:
    ncols = len(doc.columns)
    pending = [0] * ncols
    out: list[str] = []
    for r, row in enumerate(rows):
        row_cls = _row_classes(doc, row, r == 0, style.max_rule_depth)
        cls_attr = f' class="{" ".join(row_cls)}"' if row_cls else ''
        cells = []
        col = 0
        for entry in row.cells:
            cell = entry if isinstance(entry, Cell) else Cell(text=entry)
            while col < ncols and pending[col] > 0:
                col += 1
            if col >= ncols:
                break
            cls = _body_classes(doc, col, cell.colspan, cell,
                                style.max_vrule_depth)
            cls, content = _cell_content(cell, cls, allow_html,
                                         doc.math != 'off')
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


def _cell_content(cell: Cell | HeadCell, cls: list[str], allow_html: bool,
                  math: bool = True) -> tuple[list[str], str]:
    """Return (classes, inner html) applying math/html handling (walker port)."""
    if cell.math:
        return cls + ['gt-math'], _esc(f'\\({cell.text}\\)')
    if cell.html:
        # user markup: its $s are literal, never segmented
        return (cls, cell.text) if allow_html else (cls, _esc(cell.text))
    return cls, _span_html(cell.text, math)


def _span_html(text: str, math: bool) -> str:
    """Escape prose; with ``math`` on, ``$...$`` spans emit as gt-math spans."""
    if not math or '$' not in text:
        return _esc(text)
    return ''.join(
        '<span class="gt-math">' + _esc('\\(' + run + '\\)') + '</span>'
        if is_math else _esc(run)
        for is_math, run in segments(text))


def _esc(text: str) -> str:
    return _html.escape(text, quote=False)


# ---- class stamping: direct ports of gt-render.js — keep in lockstep

def _column_classes(doc: TableDoc, col: int, max_vrule_depth) -> list[str]:
    c = doc.columns[col]
    cls = [f'gt-{c.align}', 'gt-stub' if c.role == 'stub' else 'gt-data',
           'gt-wrap' if c.wrap else 'gt-nowrap']
    slot = vrule_slot(c.break_depth, max_vrule_depth) if c.role == 'data' else None
    if slot is not None:
        cls.append(f'gt-vbreak-{slot}')
    return cls


def _head_classes(doc: TableDoc, col: int, colspan: int, leaf: bool,
                  hc: HeadCell, max_vrule_depth) -> list[str]:
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
    if not leaf and hc.text:
        cls.append('gt-spanner')                 # cmidrule under groups
    if n_stub > 0 and col + colspan == n_stub:
        cls.append('gt-stub-end')
    bd = first.break_depth if first else None
    slot = vrule_slot(bd, max_vrule_depth) if col >= n_stub else None
    if slot is not None:
        cls.append(f'gt-vbreak-{slot}')
    cls.extend(_CELL_FLAG_CLASS[f] for f in hc.flags if f in _CELL_FLAG_CLASS)
    return cls


def _body_classes(doc: TableDoc, col: int, colspan: int, cell: Cell,
                  max_vrule_depth) -> list[str]:
    cls = _column_classes(doc, col, max_vrule_depth)
    if doc.n_stub_levels > 0 and col + colspan == doc.n_stub_levels:
        cls.append('gt-stub-end')
    cls.extend(_CELL_FLAG_CLASS[f] for f in cell.flags if f in _CELL_FLAG_CLASS)
    return cls


def _row_classes(doc: TableDoc, row: Row, is_first: bool,
                 max_rule_depth) -> list[str]:
    cls: list[str] = []
    slot = None if is_first else rule_slot(row.break_depth, doc.n_stub_levels,
                                           max_rule_depth)
    if slot is not None:
        cls.append(f'gt-break-{slot}')
    cls.extend(_ROW_FLAG_CLASS[f] for f in row.flags if f in _ROW_FLAG_CLASS)
    return cls


# ---- inline styling (fiscus/HTMX/email path) — same RULES dict, flattened

def _width_properties(style: HouseStyle) -> dict[str, str]:
    """Per-table width custom properties, emitted only when they say
    something the stylesheet does not already say.

    This is the whole of the HTML width story. ``gt-nowrap`` already pins the
    columns that must not be narrowed, so a table-level ``max-width`` leaves
    the browser to narrow exactly the prose ones — measuring the real font
    rather than estimating it, which is why no solver runs on this path.
    """
    custom: dict[str, str] = {}
    if style.max_table_width_em is not None:
        custom['--gt-max-width'] = f'{style.max_table_width_em:g}em'
    prose = f'{style.max_prose_width_em:g}em'
    if prose != _css.VARIABLES['--gt-prose-max']:
        custom['--gt-prose-max'] = prose
    return custom


# HouseStyle rule weight → the custom property it scales
_RULE_PROPERTIES = (
    [('frame_rule', None, '--gt-rule-frame'), ('head_rule', None, '--gt-rule-head'),
     ('stub_rule', None, '--gt-rule-stub'), ('total_rule', None, '--gt-rule-total'),
     ('spanner_rule', None, '--gt-rule-spanner')]
    + [('hrule_widths', k, f'--gt-rule-{k}') for k in range(N_RULE_SLOTS)]
    + [('vrule_widths', k, f'--gt-vrule-{k}') for k in range(N_VRULE_SLOTS)])
_BORDER_RE = re.compile(r'^([\d.]+)pt(.*)$')


def _rule_properties(style: HouseStyle) -> dict[str, str]:
    """Per-table rule weights, emitted only where ``style`` departs from the
    ``HouseStyle`` default.

    The TikZ weights and the stylesheet widths are different scales (the
    sheet sets heavier rules for a screen), so a weight is read as a multiple
    of its default: twice the TikZ weight is twice the CSS width, and the
    two renderers stay in proportion.
    """
    default = HouseStyle()
    custom: dict[str, str] = {}
    for field, k, name in _RULE_PROPERTIES:
        weight, base = getattr(style, field), getattr(default, field)
        if k is not None:
            weight, base = weight[k], base[k]
        if weight == base:
            continue
        m = _BORDER_RE.match(_css.VARIABLES[name])
        custom[name] = ('none' if weight == 0 else
                        f'{float(m.group(1)) * weight / base:.3g}pt{m.group(2)}')
    return custom


class _Styler:
    """Resolve RULES onto style attributes when ``inline_css`` is on.

    Understands exactly the selector shapes RULES uses; the vocabulary test
    plus conformance goldens keep this honest. Custom-property references are
    substituted with their VARIABLES defaults (email clients know no vars),
    or with this table's overrides where it has any.

    Per-table custom properties ride on the wrapper in *both* modes — they
    are this table's values, not the sheet's — so ``attr('.gt')`` returns a
    style attribute even when ``inline_css`` is off.
    """

    def __init__(self, active: bool, custom: dict[str, str] | None = None):
        self.active = active
        self.custom = custom or {}

    def attr(self, key: str) -> str:
        props: dict[str, str] = {}
        if self.active:
            props = dict({
                '.gt': {'line-height': _css.RULES['.gt']['line-height'],
                        'width': 'fit-content'},
                'table': _css.RULES['.gt.gt table'],
                '.gt-caption': _css.RULES['.gt.gt .gt-caption'],
                '.gt-notes': _css.RULES['.gt.gt .gt-notes'],
            }.get(key, {}))
            if key == '.gt' and '--gt-max-width' in self.custom:
                # no custom properties in an email client: state it outright
                props['max-width'] = self.custom['--gt-max-width']
        if key == '.gt':
            props = {**self.custom, **props}
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

    def _style(self, props: dict[str, str]) -> str:
        # an email client knows no custom properties, so inline mode drops the
        # declarations and keeps only what they were resolved into
        items = [(k, v) for k, v in props.items()
                 if not (self.active and k.startswith('--'))]
        body = ' '.join(f'{k}: {self._resolve(v)};' for k, v in items)
        return f' style="{body}"' if body else ''

    def _resolve(self, value: str) -> str:
        return _resolve_vars(value, self.custom) if self.active else value


_VAR_RE = re.compile(r'var\((--[a-z-]+)(?:,\s*([^)]+))?\)')


def _resolve_vars(value: str, overrides: dict[str, str] | None = None) -> str:
    """Substitute var(--gt-x) with this table's value, else the sheet default."""
    def sub(m: re.Match) -> str:
        name = m.group(1)
        if overrides and name in overrides:
            return overrides[name]
        return _css.VARIABLES.get(name, m.group(2) or '')
    return _VAR_RE.sub(sub, value)
