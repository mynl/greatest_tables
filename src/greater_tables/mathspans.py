"""Inline-math detection — the one rule every consumer shares.

``$...$`` and ``$$...$$`` spans are recognized anywhere text appears: body
cells, stub cells, column headers, captions and notes. The rule is stricter
than TeX's own so that currency never becomes math:

- delimiters are **tight**: no whitespace just inside either ``$``;
- no interior ``$`` (so ``$10 to $20`` is two prices, not a span);
- a closing ``$`` may not be followed by a digit (``$x$2`` reads as money);
- ``\\$`` is an escaped literal dollar and never opens or closes a span.

Only the ``$`` forms are recognized — ``\\(...\\)`` / ``\\[...\\]`` are not
(GT5's TeX path protected ``\\[...\\]``; see docs/migration.md). Display
``$$...$$`` is detected but each renderer emits its *inline* delimiters:
display math has no business inside a table cell.

The build-time whole-cell detector (:func:`whole_cell`) and every renderer's
escape step (:func:`segments`) use the same pattern, as does the width
estimator — so what is measured is what is set. ``js/src/gt-render.js``
carries a visually identical regex (a lockstep pair; the DOM-transcript
conformance goldens enforce the agreement).
"""

from __future__ import annotations

import re
from collections.abc import Iterator

__all__ = ['MATH_RE', 'segments', 'whole_cell']

MATH_RE = re.compile(
    r'(?<!\\)\$\$(?!\s)([^$]*[^$\s])(?<!\\)\$\$(?!\d)'   # display  $$...$$
    r'|(?<!\\)\$(?!\s)([^$]*[^$\s])(?<!\\)\$(?!\d)'      # inline   $...$
)

_ESCAPED_DOLLAR = re.compile(r'\\\$')


def whole_cell(text: str) -> str | None:
    """The TeX content if the entire string is exactly one math span.

    The closing-delimiter lookbehind makes ``$...\\$`` unmatchable, which is
    the old trailing-backslash guard: a trailing backslash would escape the
    closing delimiter downstream (``$...\\$`` in TeX, ``\\(...\\\\)`` in
    MathJax) — not well-formed math, kept as plain text.
    """
    m = MATH_RE.fullmatch(text)
    if m is None:
        return None
    return m.group(1) if m.group(1) is not None else m.group(2)


def segments(text: str) -> Iterator[tuple[bool, str]]:
    """Split text into ``(is_math, run)`` pairs, in order.

    Math runs have their delimiters stripped. Prose runs have ``\\$``
    unescaped to a literal ``$`` — the escape's only job was to suppress
    detection, and this is where it is spent; each renderer then re-escapes
    the dollar for its own target. A single ``(False, text)`` pair comes
    back when there is no math (including empty text).
    """
    pos = 0
    for m in MATH_RE.finditer(text):
        if m.start() > pos:
            yield False, _ESCAPED_DOLLAR.sub('$', text[pos:m.start()])
        yield True, m.group(1) if m.group(1) is not None else m.group(2)
        pos = m.end()
    if pos < len(text) or pos == 0:
        yield False, _ESCAPED_DOLLAR.sub('$', text[pos:])
