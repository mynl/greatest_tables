r"""Inline markdown in table cells: ``*em*``, ``**strong**`` and ```code```.

The one rule every consumer shares, built on :mod:`.mathspans`: the TeX and
HTML renderers, the TikZ width estimator and ``js/src/gt-render.js``, which
carries a line-by-line port (``markdownRuns``; ``js/markdown-check.mjs`` and
the DOM-transcript goldens hold the two in step).

A cell's text splits into a flat list of :class:`Run`, each a ``kind``
(``'text'``, ``'math'`` or ``'code'``) and a ``style`` (None, ``'em'`` or
``'strong'``). Flat rather than a tree, so every consumer is a simple loop.

The rule is stricter than CommonMark, for the reason the math rule is
stricter than TeX: a table is full of asterisks that are not markup.

1. **Code spans first**: a single backtick, non-empty content holding no
   backtick, a single backtick. The content is literal, so ```$x$``` stays
   code.
2. **Math next**, by :func:`.mathspans.segments`, unchanged. A star inside
   math (``$a*b$``) is math.
3. **``**strong**``, then ``*em*``**, over what remains. Code and math are
   atoms that may sit inside an emphasis: ``*see $x$*`` is italic text
   around a math run.
4. **Word boundaries.** An opening marker starts a word: it follows the
   start, whitespace or opening punctuation, and precedes a non-space. A
   closing marker ends a word: it follows a non-space and precedes the end,
   whitespace or punctuation. So ``a*b*c``, ``0.23**``, ``Revenue*`` and
   ``2 * 3 * 4`` are left alone.
5. ``\*`` and ``\``` are literal characters and never delimit, as ``\$`` is
   for math.

Not supported: ``_`` emphasis (it collides with ``col_name`` and ``x_1``),
nesting (``***x***`` sets bold with literal stars inside), links, and
multi-backtick code spans.
"""

from __future__ import annotations

import re
from typing import Literal, NamedTuple

from .mathspans import segments

__all__ = ['Run', 'grouped', 'runs']


class Run(NamedTuple):
    """One run of a cell's text, set in one style."""

    kind: Literal['text', 'math', 'code']
    style: Literal['em', 'strong'] | None
    text: str


CODE_RE = re.compile(r'(?<![\\`])`([^`]*[^`\\])`(?!`)')

# A marker opens after the start, whitespace or opening punctuation, and
# closes before the end, whitespace or punctuation other than a star. Both
# are negated classes, which read the same in JavaScript; a bare $ would not,
# since Python's also matches before a final newline. DOTALL likewise, as
# the two languages' dots exclude different line ends.
_OPEN = r'(?<![^\s(\[{"\'“‘])'
_CLOSE = r'(?![^\s.,;:!?)\]}"\'”’…/–—-])'
STRONG_RE = re.compile(_OPEN + r'\*\*(?=\S)(.+?)(?<=[^\s\\])\*\*' + _CLOSE,
                       re.DOTALL)
EM_RE = re.compile(_OPEN + r'\*(?=[^\s*])(.+?)(?<=[^\s\\*])\*' + _CLOSE,
                   re.DOTALL)

# Code and math atoms stand in the text as private-use characters while the
# emphasis rules run, so a marker can open or close on an atom. Text that
# already holds one sets without emphasis rather than risk a collision.
_ATOM = 0xE000
_ATOM_RE = re.compile('([-])')
_ESCAPE_RE = re.compile(r'\\([*`])')


def runs(text: str, math: bool = True) -> list[Run]:
    """Split a cell's text into styled runs.

    Parameters
    ----------
    text
        The cell text, as typed.
    math
        Recognize ``$...$`` spans; False for a ``TableDoc.math='off'``
        document, where every ``$`` is a glyph.

    Returns
    -------
    list of Run
        In order. Text runs have ``\\*`` and ``\\``` unescaped (and ``\\$``
        when ``math`` is on); code and math runs hold their content as typed,
        delimiters stripped. Text with no markup is a single unstyled text
        run, the empty string included.
    """
    tokens: list[str | Run] = []            # text pieces and atoms, in order
    pos = 0
    for m in CODE_RE.finditer(text):
        tokens.extend(_math_tokens(text[pos:m.start()], math))
        tokens.append(Run('code', None, m.group(1)))
        pos = m.end()
    tokens.extend(_math_tokens(text[pos:], math))

    out: list[Run] = []
    if _ATOM_RE.search(text):
        out = [Run('text', None, _unescape(t)) if isinstance(t, str) else t
               for t in tokens if t != '']
        return out or [Run('text', None, '')]

    atoms = [t for t in tokens if isinstance(t, Run)]
    flat, k = [], 0
    for t in tokens:
        if isinstance(t, str):
            flat.append(t)
        else:
            flat.append(chr(_ATOM + k))
            k += 1
    for style, chunk in _styled(''.join(flat)):
        for piece in _ATOM_RE.split(chunk):
            if not piece:
                continue
            if _ATOM_RE.fullmatch(piece):
                out.append(atoms[ord(piece) - _ATOM]._replace(style=style))
            else:
                out.append(Run('text', style, _unescape(piece)))
    return out or [Run('text', None, '')]


def grouped(cell_runs: list[Run]) -> list[tuple[str | None, list[Run]]]:
    """Consecutive runs of one style, together.

    ``*see $x$*`` is one em group holding a text run and a math run, which a
    renderer wraps in one element rather than two.
    """
    out: list[tuple[str | None, list[Run]]] = []
    for run in cell_runs:
        if out and out[-1][0] == run.style:
            out[-1][1].append(run)
        else:
            out.append((run.style, [run]))
    return out


def _math_tokens(text: str, math: bool) -> list[str | Run]:
    """``text`` as prose pieces and math runs."""
    if not math or '$' not in text:
        return [text]
    return [Run('math', None, run) if is_math else run
            for is_math, run in segments(text)]


def _styled(flat: str) -> list[tuple[str | None, str]]:
    """``(style, chunk)`` pairs: strong spans first, then em in the rest."""
    out: list[tuple[str | None, str]] = []
    for strong, chunk in _split(STRONG_RE, flat):
        if strong:
            out.append(('strong', chunk))
        else:
            out.extend(('em' if em else None, c) for em, c in _split(EM_RE, chunk))
    return out


def _split(pattern: re.Pattern, text: str) -> list[tuple[bool, str]]:
    """``(matched, chunk)`` pairs in order; a match gives its content."""
    out, pos = [], 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            out.append((False, text[pos:m.start()]))
        out.append((True, m.group(1)))
        pos = m.end()
    if pos < len(text):
        out.append((False, text[pos:]))
    return out


def _unescape(text: str) -> str:
    return _ESCAPE_RE.sub(r'\1', text)
