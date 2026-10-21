"""Shared renderer policy: which structural breaks get a rule, and how heavy.

The IR states *where* the hierarchy breaks (``Row.break_depth``,
``Column.break_depth``); house style decides which of those breaks are drawn
and with what weight. This module is the one implementation, called by
``html.py``, ``tikz.py`` and ``text.py`` and ported line for line into
``js/src/gt-render.js``.

It exists because three independent copies of the same comparison had already
drifted: ``text.py`` drew a depth-3 rule the other three renderers suppressed,
at five or more stub levels — the conformance oracle disagreeing with the
renderers it exists to check.

Both functions return a *weight slot*, not a boolean, so the depth-to-weight
clamp lives in one place: there are only ``N_RULE_SLOTS`` weights defined
anywhere (``HouseStyle.hrule_widths``, ``--gt-rule-0/1/2``, ``gt-break-0/1/2``),
and a break deeper than the last slot reuses the lightest weight rather than
producing a class no stylesheet knows or an ``IndexError``.
"""

from __future__ import annotations

__all__ = ['N_RULE_SLOTS', 'N_VRULE_SLOTS', 'rule_slot', 'vrule_slot']

N_RULE_SLOTS = 3      # hrule_widths, --gt-rule-0/1/2, gt-break-0/1/2
N_VRULE_SLOTS = 3     # vrule_widths, --gt-vrule-0/1/2, gt-vbreak-0/1/2


def rule_slot(break_depth: int | None, n_stub_levels: int,
              max_rule_depth: int | str | None = 'auto') -> int | None:
    """Weight slot for one row break, or None when no rule is drawn.

    Parameters
    ----------
    break_depth
        ``Row.break_depth`` — the shallowest stub level whose value changed
        from the row above, or None when nothing changed (or for the first
        row of a section). None never rules, under any setting.
    n_stub_levels
        ``TableDoc.n_stub_levels``.
    max_rule_depth
        ``HouseStyle.max_rule_depth``. ``'auto'`` (default) additionally caps
        at ``n_stub_levels - 2``, which suppresses the innermost level — a
        change there is just "next row", so ruling it draws a line between
        every row. An **int is literal**: it caps at that depth and nothing
        else, so ``0`` on a single-level index rules every row whose stub
        changed. None draws no internal rules at all.

    Returns
    -------
    int or None
        Slot in ``0 .. N_RULE_SLOTS - 1`` — the index into
        ``HouseStyle.hrule_widths``, the ``gt-break-{slot}`` class, and the
        ``--gt-rule-{slot}`` custom property — or None for no rule.

    Raises
    ------
    ValueError
        If ``max_rule_depth`` is a string other than ``'auto'``.
    """
    if break_depth is None or max_rule_depth is None:
        return None
    if isinstance(max_rule_depth, str):
        if max_rule_depth != 'auto':
            raise ValueError("max_rule_depth must be 'auto', an int, or None; "
                             f'got {max_rule_depth!r}')
        cap = min(N_RULE_SLOTS - 1, n_stub_levels - 2)
    else:
        cap = int(max_rule_depth)      # literal: not clamped to the slots
    if break_depth > cap:
        return None
    return min(break_depth, N_RULE_SLOTS - 1)


def vrule_slot(break_depth: int | None,
               max_vrule_depth: int | None = 1) -> int | None:
    """Weight slot for one column-group break, or None for no rule.

    Column break depths already have the leaf level filtered out at build
    time (``engine.structure.column_break_depths``), so there is no
    ``n_stub_levels``-style term here — only the user cap and the slot clamp.
    """
    if break_depth is None or max_vrule_depth is None:
        return None
    if break_depth > int(max_vrule_depth):
        return None
    return min(break_depth, N_VRULE_SLOTS - 1)
