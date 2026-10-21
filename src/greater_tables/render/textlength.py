"""Character-based display-width estimation (greater_tables TextLength salvage).

Lives in the TikZ renderer's orbit only — TeX genuinely needs geometry ahead
of rendering; the HTML paths let the browser measure. Widths are em
estimates from a per-face glyph table; ``$...$`` spans are token-counted TeX.

**The tables are in** :mod:`.fonts`, roman and bold for each face, and every
function here takes the face by name, ``'times'`` by default. Times is what
``Etcher`` compiles against (``newtxtext``): measured there, the estimate is
exact — median actual / estimate 1.000 over the fixture corpus, p99 1.007. A
document set in another face needs that face's table: in Times metrics,
STIX Two lowercase runs about 5% over and Latin Modern about 6%, so columns
come out tight and labels wrap. ``HouseStyle.tikz_font`` names the face.

Glyph widths are held as **integer milli-ems** and accumulated as integers,
converted to ems only at the end. Summing the float ems directly is not
reproducible across interpreters: CPython 3.12 gave ``sum()`` Neumaier
compensated summation, so 'apples' totalled 2.5549999999999997 on 3.11 and
2.555 on 3.13 — one ULP apart, but on opposite sides of the 2 dp rounding
the TikZ renderer applies, which moved a committed column width by 0.01em.
Integer accumulation is exact on every version, so the TeX goldens are
interpreter-independent. Callers doing width *arithmetic* (summing columns,
allocating a budget) should therefore work in milli-ems throughout —
:func:`display_milli` and :func:`token_milli` — and divide only to print.

Two measures, because a column has two kinds of floor: :func:`display_milli`
is the width the text wants on one line, :func:`token_milli` the width of its
widest unbreakable token. TeX will not hyphenate inside a word, so a wrapping
column narrower than its longest token gives an overfull hbox.
"""

from __future__ import annotations

import html
import re

from ..mathspans import segments
from .fonts import DEFAULT_WIDTH, face

__all__ = ['display_milli', 'math_milli', 'text_display_len',
           'token_display_len', 'token_milli']

TEX_SIMPLE_GLYPHS = {
    'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta',
    'iota', 'kappa', 'lambda', 'mu', 'nu', 'xi', 'omicron', 'pi', 'rho',
    'sigma', 'tau', 'upsilon', 'phi', 'chi', 'psi', 'omega', 'infty', 'sum',
    'prod', 'int', 'cup', 'cap', 'vee', 'wedge', 'forall', 'exists', 'neg',
    'leq', 'geq', 'neq', 'approx', 'to', 'leftarrow', 'rightarrow',
}
TEX_WIDE = {'frac', 'sqrt', 'sum', 'int', 'prod'}
TEX_SPACING = {'quad', 'qquad', ',', ';', ' ', '!'}

_EM = 1000                      # milli-ems per em

_TAG_RE = re.compile(r'<[^>]*>')
_TOKEN_RE = re.compile(r'\\[a-zA-Z]+|[a-zA-Z0-9]|.')


def _glyphs(font: str, bold: bool) -> dict[str, int]:
    """The milli-em glyph table for a face, roman or bold."""
    f = face(font)
    return f.bold if bold else f.roman


def _sum(text: str, glyphs: dict[str, int]) -> int:
    return sum(glyphs.get(c, DEFAULT_WIDTH) for c in text)


def text_display_len(s: str, font: str = 'times', bold: bool = False) -> float:
    """Estimate display width in ems: plain text, ``$math$``, HTML entities."""
    return display_milli(s, font=font, bold=bold) / _EM


def token_display_len(s: str, font: str = 'times', bold: bool = False) -> float:
    """Em width of the widest unbreakable token — a wrap column's floor."""
    return token_milli(s, font=font, bold=bold) / _EM


def estimate_math_width(tex: str) -> float:
    """Token-count a TeX math fragment into an em estimate."""
    return math_milli(tex) / _EM


def display_milli(s: str, math: bool = True, font: str = 'times',
                  bold: bool = False) -> int:
    """Display width in milli-ems — the exact, integer accumulation.

    ``math`` gates ``$``-span interpretation (mathspans, the same rule the
    renderers emit by, so what is measured is what is set); pass False for a
    ``TableDoc.math='off'`` document or html-flag text, where every ``$``
    is a glyph. ``font`` names the face (``render.fonts``) and ``bold``
    picks its bold table; math spans are priced from the roman one.
    """
    if not isinstance(s, str):
        s = str(s)
    glyphs = _glyphs(font, bold)
    if '$' not in s and '<' not in s and '&' not in s:
        return _sum(s, glyphs)
    if not math:
        return _milli_prose(s, glyphs)
    return sum(math_milli(run, font) if is_math else _milli_prose(run, glyphs)
               for is_math, run in segments(s))


def token_milli(s: str, math: bool = True, font: str = 'times',
                bold: bool = False) -> int:
    """Widest whitespace-delimited token in milli-ems.

    A ``$...$`` span counts as one token: math is set as a box and does not
    break at spaces the way surrounding prose does. ``font`` and ``bold`` as
    for :func:`display_milli`.
    """
    if not isinstance(s, str):
        s = str(s)
    glyphs = _glyphs(font, bold)
    if '$' not in s and '<' not in s and '&' not in s:
        return max((_sum(tok, glyphs) for tok in s.split()), default=0)
    widest = 0
    for is_math, run in (segments(s) if math else [(False, s)]):
        if is_math:
            widest = max(widest, math_milli(run, font))
        else:
            decoded = html.unescape(_TAG_RE.sub('', run))
            for tok in decoded.split():
                widest = max(widest, _sum(tok, glyphs))
    return widest


def _milli_prose(run: str, glyphs: dict[str, int]) -> int:
    """Prose width: tags stripped, entities decoded, glyphs accumulated."""
    return _sum(html.unescape(_TAG_RE.sub('', run)), glyphs)


def math_milli(tex: str, font: str = 'times') -> int:
    """TeX math fragment width in milli-ems, letters priced from ``font``."""
    glyphs = _glyphs(font, False)
    width = 0
    for tok in _TOKEN_RE.findall(tex):
        if tok.startswith('\\'):
            name = tok[1:]
            if name in TEX_SIMPLE_GLYPHS:
                width += 600
            elif name in TEX_WIDE:
                width += 1500
            elif name in TEX_SPACING:
                width += 400
            else:
                width += 1000
        elif tok in '{}':
            continue
        elif tok in '^_':
            width += 300
        else:
            width += glyphs.get(tok, DEFAULT_WIDTH)
    return width
