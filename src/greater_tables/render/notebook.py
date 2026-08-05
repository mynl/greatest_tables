"""Notebook/Quarto integration helpers.

The mimebundle always carries ``text/plain``: it is the one type every
measured consumer renders (JupyterLab, Quarto html/latex/gfm, Sphinx
html/latex), so a table degrades to a monospace rendering rather than to
silence or to ``<GT object at 0x…>``. What joins it depends on the target —
``text/html`` normally, ``text/latex`` (the TikZ rendering) under a Quarto
PDF render, never both. Keying on the target is what structurally fixes
greater_tables 5.x's compute-TikZ-then-discard-it-per-repr waste: an HTML
render now computes no TikZ at all.

``text/html`` is excluded on the PDF path deliberately. Pandoc prefers html
when it is offered, and its LaTeX writer then discards the raw html, so a
``{html, latex, plain}`` bundle renders *nothing*; omitting html means a TikZ
failure degrades to text instead of to an empty page.

Detection reads ``QUARTO_FIG_FORMAT``, the only channel Quarto offers. It is
``pdf`` on the PDF path and ``png`` for html and gfm alike, so html and gfm
are indistinguishable from the environment. A gfm build that needs plain only
has to say so with ``mimes`` — see :func:`quarto_target`.
"""

from __future__ import annotations

from collections.abc import Iterable
import os

from ..ir import TableDoc
from ..spec import HouseStyle
from .html import render_html
from .text import render_text
from .tikz import render_tikz

__all__ = ['KNOWN_MIMES', 'in_quarto', 'mimebundle', 'quarto_target',
           'validate_mimes']

HTML = 'text/html'
LATEX = 'text/latex'
PLAIN = 'text/plain'
KNOWN_MIMES = (HTML, LATEX, PLAIN)


def in_quarto() -> bool:
    """True inside a ``quarto render`` (any QUARTO_* env variable set)."""
    return any(k.startswith('QUARTO_') for k in os.environ)


def quarto_target() -> str | None:
    """Which Quarto output is being built: ``'pdf'``, ``'other'``, or None.

    ``QUARTO_FIG_FORMAT`` is the proxy: ``pdf`` on the PDF path, ``png`` for
    both html and gfm. ``'other'`` therefore means "a Quarto render that is
    not PDF" and deliberately not "html" — the environment cannot tell html
    from gfm, and naming it html would hide a real ambiguity. None means no
    Quarto render was detected at all.
    """
    if not in_quarto():
        return None
    return 'pdf' if os.environ.get('QUARTO_FIG_FORMAT') == 'pdf' else 'other'


def validate_mimes(mimes: Iterable[str]) -> tuple[str, ...]:
    """Check an explicit MIME request, returning it as a tuple.

    Raises ``ValueError`` on anything outside :data:`KNOWN_MIMES`: a typo
    would otherwise publish a bundle no consumer can use, and fail silently.
    """
    out = tuple(mimes)
    unknown = [m for m in out if m not in KNOWN_MIMES]
    if unknown:
        raise ValueError(f'mimes: unknown MIME type(s) {unknown}; expected a '
                         f'subset of {KNOWN_MIMES}')
    return out


def mimebundle(doc: TableDoc, *, css: str = 'embed',
               tikz: bool | None = None,
               style: HouseStyle | None = None,
               mimes: Iterable[str] | None = None) -> dict[str, str]:
    """MIME bundle for ``_repr_mimebundle_``.

    ``text/plain`` is always present unless ``mimes`` excludes it. With both
    ``tikz`` and ``mimes`` left at None the published keys are:

    ==================================  ==========================
    target                              keys
    ==================================  ==========================
    ``QUARTO_FIG_FORMAT == 'pdf'``      ``text/latex, text/plain``
    any other Quarto render, or none    ``text/html, text/plain``
    ==================================  ==========================

    Parameters
    ----------
    doc
        The document.
    css
        Stylesheet policy for the HTML entry.
    tikz
        Force ``text/latex`` in or out, bypassing target detection; None
        (default) detects. Forcing it *in* keeps ``text/html`` — it means
        "also give me TikZ", not "this is a PDF render". Use ``mimes`` for
        exact control.
    style
        HouseStyle, forwarded to every renderer (HTML reads only the rule
        depth caps; TikZ reads everything).
    mimes
        Publish exactly these types, suppressing detection entirely and
        overriding ``tikz``. Members are validated against
        :data:`KNOWN_MIMES`. This is the escape hatch for a target GT cannot
        detect — notably Quarto ``--to gfm``, where pandoc prefers html and
        the caller must ask for ``('text/plain',)``.
    """
    if mimes is not None:
        wanted = validate_mimes(mimes)
    elif tikz is None:
        wanted = (LATEX, PLAIN) if quarto_target() == 'pdf' else (HTML, PLAIN)
    else:
        wanted = (HTML, LATEX, PLAIN) if tikz else (HTML, PLAIN)
    build = {
        HTML: lambda: render_html(doc, css=css, style=style),
        LATEX: lambda: render_tikz(doc, style),
        PLAIN: lambda: render_text(doc, style),
    }
    # KNOWN_MIMES order, so the bundle key order does not depend on the caller
    return {m: build[m]() for m in KNOWN_MIMES if m in wanted}
