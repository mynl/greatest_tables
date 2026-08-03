"""The CSS contract: one RULES dict → committed ``assets/gt.css``.

Single source of truth for the class vocabulary shared by the Python HTML
renderer and the JS walker (conformance transcripts enforce the agreement).
The [notebook-html] inline flattener consumes the same dict, so the sheet
and inline styles cannot diverge.

Principles (dev/design.md): selectors double the wrapper class (``.gt.gt``)
to beat JupyterLab/Quarto host rules without ``!important``; per-table
scalars ride as custom properties with defaults declared on ``.gt``; colors
default to ``currentColor``/transparent so an embedded fragment has no color
opinion; no widths anywhere — ``gt-nowrap``/``gt-wrap`` express intent and
the browser measures.

Semantic classes:

- alignment ``gt-l gt-r gt-c`` (right implies tabular numerals)
- role ``gt-stub gt-data``; ``gt-stub-end`` marks the last stub cell of a row
  (carries the stub/body vertical rule, spanning cells carry it for covered
  rows automatically)
- wrapping ``gt-nowrap gt-wrap``
- row breaks ``gt-break-0/1/2`` — border-top on the row's *own* cells only,
  so rowspan-covered stub columns are skipped and the rule starts exactly at
  the changed column
- column-group breaks ``gt-vbreak-0/1`` (border-left)
- flags ``gt-total gt-subtotal gt-emph gt-muted gt-neg``; ``gt-math``
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

__all__ = ['RULES', 'VARIABLES', 'css_text', 'write_asset']

# custom-property defaults, declared on the wrapper; HouseStyle/themes override
VARIABLES: dict[str, str] = {
    '--gt-pad-v': '0.25em',
    '--gt-pad-h': '0.6em',
    # widths: the table's ceiling and one wrapping column's, the CSS side of
    # HouseStyle.max_table_width_em and .max_prose_width_em. There are no
    # per-column widths here by design — gt-nowrap pins the columns that must
    # not be narrowed and the browser measures the rest, with better metrics
    # than any estimate of ours.
    '--gt-max-width': 'none',
    '--gt-prose-max': '18em',
    '--gt-rule-frame': '1.2pt solid',
    '--gt-rule-head': '0.7pt solid',
    '--gt-rule-0': '0.5pt solid',
    '--gt-rule-1': '0.35pt solid',
    '--gt-rule-2': '0.2pt solid',
    # column-group verticals: same defaults as the row rules, but their own
    # properties so one can be softened or removed without the other
    '--gt-vrule-0': '0.5pt solid',
    '--gt-vrule-1': '0.35pt solid',
    '--gt-rule-stub': '0.5pt solid',
    '--gt-rule-total': '0.7pt solid',
    '--gt-rule-spanner': '0.35pt solid',
    '--gt-neg-color': 'inherit',
    '--gt-caption-align': 'left',
}

RULES: dict[str, dict[str, str]] = {
    '.gt': {
        **VARIABLES,
        'width': 'fit-content',
        'max-width': 'var(--gt-max-width)',
        'line-height': '1.3',
    },
    '.gt.gt table': {
        'border-collapse': 'collapse',
        'table-layout': 'auto',
        'border-top': 'var(--gt-rule-frame)',
        'border-bottom': 'var(--gt-rule-frame)',
    },
    '.gt.gt .gt-caption': {
        'caption-side': 'top',
        'text-align': 'var(--gt-caption-align)',
        'font-weight': '600',
        'padding': '0 var(--gt-pad-h) 0.4em 0',
    },
    '.gt.gt td, .gt.gt th': {
        'padding': 'var(--gt-pad-v) var(--gt-pad-h)',
        'vertical-align': 'top',
        'background': 'transparent',
        'border': 'none',
    },
    '.gt.gt th': {'font-weight': '600'},
    '.gt.gt thead tr:last-child th': {'border-bottom': 'var(--gt-rule-head)'},
    # full-width underline beneath a group label, spanning its columns
    # edge-to-edge; adjacent groups' rules meet at the gt-vbreak vertical
    '.gt.gt th.gt-spanner': {'border-bottom': 'var(--gt-rule-spanner)'},
    '.gt.gt .gt-l': {'text-align': 'left'},
    '.gt.gt .gt-r': {
        'text-align': 'right',
        'font-variant-numeric': 'tabular-nums',
    },
    '.gt.gt .gt-c': {'text-align': 'center'},
    '.gt.gt .gt-nowrap': {'white-space': 'nowrap'},
    '.gt.gt .gt-wrap': {
        'max-width': 'var(--gt-prose-max)',
        'overflow-wrap': 'break-word',
    },
    '.gt.gt .gt-stub-end': {'border-right': 'var(--gt-rule-stub)'},
    '.gt.gt tr.gt-break-0 > td': {'border-top': 'var(--gt-rule-0)'},
    '.gt.gt tr.gt-break-1 > td': {'border-top': 'var(--gt-rule-1)'},
    '.gt.gt tr.gt-break-2 > td': {'border-top': 'var(--gt-rule-2)'},
    '.gt.gt .gt-vbreak-0': {'border-left': 'var(--gt-vrule-0)'},
    '.gt.gt .gt-vbreak-1': {'border-left': 'var(--gt-vrule-1)'},
    '.gt.gt tr.gt-total > td': {
        'font-weight': '600',
        'border-top': 'var(--gt-rule-total)',
    },
    '.gt.gt tr.gt-subtotal > td': {'font-weight': '600'},
    '.gt.gt .gt-emph': {'font-weight': '600'},
    '.gt.gt .gt-muted': {'opacity': '0.6'},
    '.gt.gt .gt-neg': {'color': 'var(--gt-neg-color)'},
    '.gt.gt .gt-math': {'white-space': 'nowrap'},
    '.gt.gt .gt-notes': {
        'font-size': '0.85em',
        'opacity': '0.75',
        'padding-top': '0.3em',
    },
    # fit mode (walker option): solver widths assume single-line ellipsis cells
    '.gt.gt.gt-fit td, .gt.gt.gt-fit th': {
        'white-space': 'nowrap',
        'overflow': 'hidden',
        'text-overflow': 'ellipsis',
    },
}


def css_text() -> str:
    """Serialize RULES to the stylesheet, deterministically."""
    lines = ['/* generated from greater_tables.render.css — do not edit */']
    for selector, props in RULES.items():
        body = ' '.join(f'{k}: {v};' for k, v in props.items())
        lines.append(f'{selector} {{ {body} }}')
    return '\n'.join(lines) + '\n'


def asset_path() -> Path:
    """Path of the committed stylesheet inside the package."""
    return Path(str(files('greater_tables').joinpath('assets', 'gt.css')))


def write_asset() -> Path:
    """Regenerate the committed ``assets/gt.css`` (explicit recipe)."""
    path = asset_path()
    path.write_text(css_text(), encoding='utf-8', newline='\n')
    return path
