"""Character-based display-width estimation (greater_tables TextLength salvage).

Lives in the TikZ renderer's orbit only — TeX genuinely needs geometry ahead
of rendering; the HTML paths let the browser measure. Widths are em
estimates from a serif glyph table; ``$...$`` spans are token-counted TeX.
"""

from __future__ import annotations

import html
import re

__all__ = ['text_display_len']

TEX_SIMPLE_GLYPHS = {
    'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta',
    'iota', 'kappa', 'lambda', 'mu', 'nu', 'xi', 'omicron', 'pi', 'rho',
    'sigma', 'tau', 'upsilon', 'phi', 'chi', 'psi', 'omega', 'infty', 'sum',
    'prod', 'int', 'cup', 'cap', 'vee', 'wedge', 'forall', 'exists', 'neg',
    'leq', 'geq', 'neq', 'approx', 'to', 'leftarrow', 'rightarrow',
}
TEX_WIDE = {'frac', 'sqrt', 'sum', 'int', 'prod'}
TEX_SPACING = {'quad', 'qquad', ',', ';', ' ', '!'}

_WIDTH_TABLE = {
    'a': 0.444, 'b': 0.5, 'c': 0.444, 'd': 0.5, 'e': 0.444, 'f': 0.333,
    'g': 0.5, 'h': 0.5, 'i': 0.278, 'j': 0.278, 'k': 0.5, 'l': 0.278,
    'm': 0.778, 'n': 0.5, 'o': 0.5, 'p': 0.5, 'q': 0.5, 'r': 0.333,
    's': 0.389, 't': 0.278, 'u': 0.5, 'v': 0.5, 'w': 0.722, 'x': 0.5,
    'y': 0.5, 'z': 0.444,
    'A': 0.722, 'B': 0.667, 'C': 0.667, 'D': 0.722, 'E': 0.611, 'F': 0.556,
    'G': 0.722, 'H': 0.722, 'I': 0.333, 'J': 0.389, 'K': 0.722, 'L': 0.611,
    'M': 0.889, 'N': 0.722, 'O': 0.722, 'P': 0.556, 'Q': 0.722, 'R': 0.667,
    'S': 0.556, 'T': 0.611, 'U': 0.722, 'V': 0.722, 'W': 0.944, 'X': 0.722,
    'Y': 0.722, 'Z': 0.611,
    '0': 0.5, '1': 0.5, '2': 0.5, '3': 0.5, '4': 0.5, '5': 0.5, '6': 0.5,
    '7': 0.5, '8': 0.5, '9': 0.5,
    '.': 0.25, ',': 0.25, ':': 0.278, ';': 0.278, '(': 0.333, ')': 0.333,
    '[': 0.333, ']': 0.333, '’': 0.333, '"': 0.444, '!': 0.333, '?': 0.444,
    ' ': 0.25, '\xa0': 0.25, '|': 0.2, '‘': 0.333, '{': 0.48, '}': 0.48,
    '-': 0.5,
}
_DEFAULT_WIDTH = 0.6
_MATH_RE = re.compile(r'(\$\$.*?\$\$)|(\$.*?\$)')
_TAG_RE = re.compile(r'<[^>]*>')
_TOKEN_RE = re.compile(r'\\[a-zA-Z]+|[a-zA-Z0-9]|.')


def _char(c: str) -> float:
    return _WIDTH_TABLE.get(c, _DEFAULT_WIDTH)


def text_display_len(s: str) -> float:
    """Estimate display width in ems: plain text, ``$math$``, HTML entities."""
    if not isinstance(s, str):
        s = str(s)
    if '$' not in s and '<' not in s and '&' not in s:
        return sum(_char(c) for c in s)
    total = 0.0
    for part in _MATH_RE.split(s):
        if not part:
            continue
        if part.startswith('$$') and part.endswith('$$'):
            total += estimate_math_width(part[2:-2])
        elif part.startswith('$') and part.endswith('$'):
            total += estimate_math_width(part[1:-1])
        else:
            decoded = html.unescape(_TAG_RE.sub('', part))
            total += sum(_char(c) for c in decoded)
    return total


def estimate_math_width(tex: str) -> float:
    """Token-count a TeX math fragment into an em estimate."""
    width = 0.0
    for tok in _TOKEN_RE.findall(tex):
        if tok.startswith('\\'):
            name = tok[1:]
            if name in TEX_SIMPLE_GLYPHS:
                width += 0.6
            elif name in TEX_WIDE:
                width += 1.5
            elif name in TEX_SPACING:
                width += 0.4
            else:
                width += 1.0
        elif tok in '{}':
            continue
        elif tok in '^_':
            width += 0.3
        else:
            width += _char(tok)
    return width
