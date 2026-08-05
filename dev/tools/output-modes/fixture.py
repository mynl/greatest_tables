"""Shared fixture for the greater_tables output-mode probe.

One deterministic frame, imported by both the Sphinx page and the Quarto page
so every consumer is handed byte-identical input. Nothing here imports
``aggregate``: the question under test is which entry of
``GT._repr_mimebundle_`` each document toolchain selects, which is a
greater_tables contract.

The frame is small on purpose (5 rows, 4 columns, 65 character text rendering)
but keeps the features that break renderers: a two level row stub, a two level
column header with a group span, thousands separators, and negative values.

Two probe surfaces
------------------
:func:`table` returns a real :class:`greater_tables.GT`, whose bundle today
carries ``text/html`` always and ``text/latex`` only under Quarto. There is no
``text/plain``.

:class:`Bundle` is a shim that publishes an *arbitrary* mimebundle over the
same rendered strings. It exists to answer the question the real GT cannot: if
``text/plain`` were on offer, would a consumer take it? Without the shim, a
consumer showing the default repr is ambiguous, since it could mean either
"ignores mimebundles" or "found nothing it could use".
"""

from greater_tables import GT, Fabricator

# Fabricator with a fixed seed is fully deterministic, so a diff between two
# runs of this probe is a toolchain change and never fixture noise.
SEED = 42


def frame():
    """Return the probe DataFrame.

    Returns
    -------
    pandas.DataFrame
        5 rows, 4 columns, two index levels, two column levels.
    """
    return Fabricator(seed=SEED).make(
        5, 'if', index_levels=2, column_groups=2, column_levels=2,
        oversample=3)


def table(caption='Mode probe'):
    """Return the probe frame wrapped in a :class:`greater_tables.GT`.

    Parameters
    ----------
    caption : str
        Table caption, varied per block so the rendered artifacts can be told
        apart by eye.

    Returns
    -------
    greater_tables.GT
    """
    return GT(frame(), caption=caption)


class Bundle:
    """Display object publishing a chosen subset of MIME types.

    Parameters
    ----------
    caption : str
        Caption for the underlying table.
    mimes : sequence of str
        MIME types to publish. ``'text/plain'`` maps to
        :attr:`greater_tables.GT.text`, ``'text/html'`` to
        :attr:`~greater_tables.GT.html`, ``'text/latex'`` to
        :attr:`~greater_tables.GT.tikz`.

    Notes
    -----
    The renderings are the real greater_tables ones. Only the *advertisement*
    is synthetic, so a positive result here transfers directly to a change in
    ``greater_tables.render.notebook.mimebundle``.
    """

    def __init__(self, caption, mimes):
        gt = table(caption)
        source = {'text/plain': lambda: gt.text,
                  'text/html': lambda: gt.html,
                  'text/latex': lambda: gt.tikz}
        self._bundle = {m: source[m]() for m in mimes}

    def _repr_mimebundle_(self, include=None, exclude=None):
        return dict(self._bundle)
