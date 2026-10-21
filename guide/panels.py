"""Gallery panels: one table shown as HTML and through both TikZ engines.

``show(name)`` takes a fixture from ``tests/registry.py`` (or a ``(data,
spec)`` pair) and returns an object carrying three renderings, and Quarto
keeps the one its format wants, as house style's ``GT`` does:

- ``text/html``: three panels, the HTML table and each engine's TeX compiled
  standalone by ``Etcher`` and converted to SVG with ``pdftocairo -svg``
  (poppler, on PATH through MiKTeX), linked rather than embedded. The
  standalone page is Times at 11pt, so these images are for structure (rules,
  alignment, spans, wrapping), not for width against a text block;
- ``text/latex``: the table twice, ``matrix`` above ``tabular``, placed ``H``
  in the document's own text block, which is where width is judged;
- ``text/plain``: the text renderer.

The style is house style's ``house_style()`` (its document budget and scale
ceiling) with any ``HouseStyle`` fields passed to ``show`` replaced. SVGs are
cached under ``_gallery/`` by a hash of their TeX, so a re-render compiles
only the tables that changed.
"""
from __future__ import annotations

import hashlib
import html
import re
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from greater_tables import (
    Etcher, TableSpec, build, render_html, render_text, render_tikz,
)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'tests'))
from registry import fixtures  # noqa: E402
from style import house_style  # noqa: E402

CACHE = HERE / '_gallery'
FIXTURES = fixtures()
ENGINES = ('matrix', 'tabular')


def _svg(tex: str, alt: str) -> str:
    """An ``img`` of the TeX compiled standalone and converted to SVG.

    A relative link, not a data URI: embedded, two SVGs cost 200 KB a table.
    The rendered HTML sits beside ``_gallery/``, so the link resolves. The
    width is set in points because pdftocairo writes the page size in points
    with no unit, which a browser takes as pixels, three quarters size.
    """
    stem = hashlib.sha256(tex.encode()).hexdigest()[:16]
    svg = CACHE / 'tikz' / f'{stem}.svg'
    if not svg.exists():
        pdf = Etcher(tex, file_name=stem, base_path=CACHE).compile()
        subprocess.run([shutil.which('pdftocairo') or 'pdftocairo', '-svg',
                        str(pdf), str(svg)], check=True, capture_output=True)
    width = re.search(r'<svg[^>]*\bwidth="([\d.]+)"', svg.read_text(encoding='utf-8'))
    size = f' style="width: {width.group(1)}pt"' if width else ''
    return f'<img alt="{alt}" src="{svg.relative_to(HERE).as_posix()}"{size}>'


class Panels:
    """One table in three renderings; see the module docstring."""

    def __init__(self, data, spec, style):
        # no label: the table is emitted twice, and Quarto turns two tables
        # carrying one tbl- label into a float nested inside a float
        self.doc = build(data, spec).model_copy(update={'label': None})
        self.style = style
        self.tex = {e: render_tikz(self.doc, replace(style, tikz_engine=e))
                    for e in ENGINES}

    def _repr_mimebundle_(self, include=None, exclude=None):
        cells = [('HTML', render_html(self.doc, style=self.style))]
        cells += [(f'TikZ {e}', _svg(self.tex[e], f'TikZ {e}'))
                  for e in ENGINES]
        panels = ''.join(
            f'<figure class="gt-panel"><figcaption>{html.escape(label)}'
            f'</figcaption>{body}</figure>' for label, body in cells)
        latex = '\n'.join(
            f'\\par\\medskip\\noindent\\textit{{TikZ {e}}}\\par\n{self.tex[e]}'
            for e in ENGINES)
        return {'text/html': f'<div class="gt-panels">{panels}</div>',
                'text/latex': latex,
                'text/plain': render_text(self.doc)}


def show(fixture, spec=None, **style_changes) -> Panels:
    """Panels for a registry fixture by name, or for ``(data, spec)``.

    Parameters
    ----------
    fixture : str or object
        A name from ``tests/registry.py``, or the data itself.
    spec : TableSpec, optional
        With data, its spec; with a name, a replacement for the fixture's.
    **style_changes
        ``HouseStyle`` fields replaced on house style's ``house_style()``.
        ``tikz_latex`` defaults to ``'H'`` so each table stays under its
        heading.
    """
    if isinstance(fixture, str):
        data, fixture_spec = FIXTURES[fixture]
        spec = spec or fixture_spec
    else:
        data, spec = fixture, spec or TableSpec()
    style_changes.setdefault('tikz_latex', 'H')
    return Panels(data, spec, replace(house_style(), **style_changes))
