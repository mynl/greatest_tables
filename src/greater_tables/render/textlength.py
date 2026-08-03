"""Character-based display-width estimation (greater_tables TextLength salvage).

Lives in the TikZ renderer's orbit only — TeX genuinely needs geometry ahead
of rendering; the HTML paths let the browser measure. Widths are em
estimates from a serif glyph table; ``$...$`` spans are token-counted TeX.

**The table is Times metrics**, which is what ``Etcher`` compiles against
(``newtxtext``): measured there, the estimate is exact — median actual /
estimate 1.000 over the fixture corpus, p99 1.007. A document set in another
face is a different measurement: Latin Modern, the LaTeX default that a
plain Quarto PDF uses, runs about 11% wider for text (digits only 1.6%), so
columns come out slightly tight and a long heading may hyphenate. Either
load a Times-metric serif alongside the tables, or accept that. Re-measure
any font with ``dev/tools/measure_glyphs.py``.

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

__all__ = ['display_milli', 'text_display_len', 'token_display_len',
           'token_milli']

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

# milli-em glyph widths (0.444em → 444), serif metrics
_WIDTH_TABLE = {
    'a': 444, 'b': 500, 'c': 444, 'd': 500, 'e': 444, 'f': 333,
    'g': 500, 'h': 500, 'i': 278, 'j': 278, 'k': 500, 'l': 278,
    'm': 778, 'n': 500, 'o': 500, 'p': 500, 'q': 500, 'r': 333,
    's': 389, 't': 278, 'u': 500, 'v': 500, 'w': 722, 'x': 500,
    'y': 500, 'z': 444,
    'A': 722, 'B': 667, 'C': 667, 'D': 722, 'E': 611, 'F': 556,
    'G': 722, 'H': 722, 'I': 333, 'J': 389, 'K': 722, 'L': 611,
    'M': 889, 'N': 722, 'O': 722, 'P': 556, 'Q': 722, 'R': 667,
    'S': 556, 'T': 611, 'U': 722, 'V': 722, 'W': 944, 'X': 722,
    'Y': 722, 'Z': 611,
    '0': 500, '1': 500, '2': 500, '3': 500, '4': 500, '5': 500, '6': 500,
    '7': 500, '8': 500, '9': 500,
    '.': 250, ',': 250, ':': 278, ';': 278, '(': 333, ')': 333,
    '[': 333, ']': 333, '’': 333, '"': 444, '!': 333, '?': 444,
    ' ': 250, '\xa0': 250, '|': 200, '‘': 333, '{': 480, '}': 480,
    '-': 333,
    # measured against newtx (dev/tools/measure_glyphs.py). These were all
    # missing before 6.0.0a5 and took the 600 default: '—' is the missing-value
    # marker, '%' rides every ratio column and 'µ' every SI-suffixed one, so
    # the three that matter most to a real table were also the most wrong.
    '#': 500, '%': 833, '&': 778, '*': 500, '+': 564, '/': 278,
    '<': 564, '=': 564, '>': 564, '@': 921, '_': 500,
    '£': 500, '€': 500, '§': 500, '¶': 453, '†': 500, '‡': 500,
    '°': 400, '±': 564, 'µ': 500, '×': 564, '÷': 564, '−': 564,
    'ª': 276, 'º': 310, '•': 350, '–': 500, '—': 1000,
    '…': 1000, '‰': 1000,
}
_DEFAULT_WIDTH = 600
_MATH_RE = re.compile(r'(\$\$.*?\$\$)|(\$.*?\$)')
_TAG_RE = re.compile(r'<[^>]*>')
_TOKEN_RE = re.compile(r'\\[a-zA-Z]+|[a-zA-Z0-9]|.')


def _char(c: str) -> int:
    return _WIDTH_TABLE.get(c, _DEFAULT_WIDTH)


def text_display_len(s: str) -> float:
    """Estimate display width in ems: plain text, ``$math$``, HTML entities."""
    return display_milli(s) / _EM


def token_display_len(s: str) -> float:
    """Em width of the widest unbreakable token — a wrap column's floor."""
    return token_milli(s) / _EM


def estimate_math_width(tex: str) -> float:
    """Token-count a TeX math fragment into an em estimate."""
    return _milli_math(tex) / _EM


def display_milli(s: str) -> int:
    """Display width in milli-ems — the exact, integer accumulation."""
    if not isinstance(s, str):
        s = str(s)
    if '$' not in s and '<' not in s and '&' not in s:
        return sum(_char(c) for c in s)
    total = 0
    for part in _MATH_RE.split(s):
        if not part:
            continue
        if part.startswith('$$') and part.endswith('$$'):
            total += _milli_math(part[2:-2])
        elif part.startswith('$') and part.endswith('$'):
            total += _milli_math(part[1:-1])
        else:
            decoded = html.unescape(_TAG_RE.sub('', part))
            total += sum(_char(c) for c in decoded)
    return total


def token_milli(s: str) -> int:
    """Widest whitespace-delimited token in milli-ems.

    A ``$...$`` span counts as one token: math is set as a box and does not
    break at spaces the way surrounding prose does.
    """
    if not isinstance(s, str):
        s = str(s)
    if '$' not in s and '<' not in s and '&' not in s:
        return max((sum(_char(c) for c in tok) for tok in s.split()), default=0)
    widest = 0
    for part in _MATH_RE.split(s):
        if not part:
            continue
        if part.startswith('$') and part.endswith('$'):
            widest = max(widest, display_milli(part))
        else:
            decoded = html.unescape(_TAG_RE.sub('', part))
            for tok in decoded.split():
                widest = max(widest, sum(_char(c) for c in tok))
    return widest


def _milli_math(tex: str) -> int:
    """TeX math fragment width in milli-ems."""
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
            width += _char(tok)
    return width
