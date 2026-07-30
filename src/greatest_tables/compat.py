"""``GT`` — the greater_tables constructor-compatible facade.

Thin, not bug-for-bug: the common blog/Quarto call
``GT(df, caption=..., ratio_cols=..., formatters=...)`` works and renders via
the GT2 engine; exotic 5.x config knobs are accepted with a warning and
ignored. Everything is lazy cached — constructing a GT computes nothing, and
TikZ is never computed on the HTML path (the 5.x eager-TikZ waste is gone by
construction).
"""

from __future__ import annotations

import warnings
from dataclasses import fields as _dc_fields
from functools import cached_property

from .config import load_spec
from .ir import TableDoc
from .render.html import render_html
from .render.notebook import mimebundle
from .render.text import render_text
from .spec import TableSpec

__all__ = ['GT']

_SPEC_FIELDS = {f.name for f in _dc_fields(TableSpec)}


class GT:
    """Table facade: data + spec in, renderings out (all lazy, all cached).

    Parameters mirror the greater_tables constructor where they still make
    sense; ``formatters`` accepts the 5.x shapes (callable, ``'{x:...}'``
    format string, or int = decimal digits without grouping). ``config_path``
    loads YAML TableSpec defaults which explicit arguments override.
    Additional keyword arguments naming TableSpec fields pass through;
    unknown ones warn and are ignored (migration aid).
    """

    def __init__(self, data=None, caption=None, label=None, aligners=None,
                 formatters=None, unbreakable=None, ratio_cols=None,
                 year_cols=None, date_cols=None, raw_cols=None,
                 show_index=None, config_path=None, **overrides):
        base = load_spec(config_path) if config_path else TableSpec()
        kwargs = {
            'caption': caption, 'label': label, 'aligners': aligners,
            'unbreakable': unbreakable, 'ratio_cols': ratio_cols,
            'year_cols': year_cols, 'date_cols': date_cols,
            'raw_cols': raw_cols, 'show_index': show_index,
        }
        if formatters is not None:
            kwargs['formats'] = {k: _map_formatter(v)
                                 for k, v in formatters.items()}
        for key, value in overrides.items():
            if key in _SPEC_FIELDS:
                kwargs[key] = value
            else:
                warnings.warn(f'GT: ignoring unknown option {key!r} '
                              '(gone in greatest_tables)', stacklevel=2)
        merged = {f.name: getattr(base, f.name) for f in _dc_fields(TableSpec)}
        merged.update({k: v for k, v in kwargs.items() if v is not None})
        self.spec = TableSpec(**merged)
        self._data = data

    @cached_property
    def doc(self) -> TableDoc:
        """The table document (the IR) — built on first access."""
        from .engine.build import build
        return build(self._data, self.spec)

    @cached_property
    def html(self) -> str:
        """HTML fragment (stylesheet embedded)."""
        return render_html(self.doc)

    @cached_property
    def text(self) -> str:
        """Monospace text rendering (the conformance oracle's view)."""
        return render_text(self.doc)

    @cached_property
    def tikz(self) -> str:
        """TikZ/LaTeX rendering (table environment + tikzpicture)."""
        from .render.tikz import render_tikz
        return render_tikz(self.doc)

    def __str__(self) -> str:
        return self.text

    def _repr_mimebundle_(self, include=None, exclude=None):
        return mimebundle(self.doc)


def _map_formatter(value):
    """Map a 5.x formatter (callable | '{x:...}' | int) to GT2 sugar."""
    if callable(value):
        return value
    if isinstance(value, int):
        return f'{{x:.{value}f}}'    # 5.x meaning: N digits, no grouping
    return value
