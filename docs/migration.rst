Migrating from greater_tables 5.x
=================================

The import name does not change, and the common call still works::

   from greater_tables import GT
   GT(df, caption='Exhibit 1', ratio_cols=['lr'], year_cols='year')

:class:`~greater_tables.compat.GT` is a thin compatibility facade over the
new engine — constructor-compatible where that still makes sense, not
bug-for-bug. It is deliberately *thin*: options that were really renderer
opinions, or that the new architecture makes meaningless, are gone.

Staying on 5.x
--------------

5.3 is frozen, complete, and stays installable from PyPI forever. Pin it::

   pip install "greater-tables<6"

That is what the major version is for. Its source and issue archive remain at
`mynl/greater_tables_project <https://github.com/mynl/greater_tables_project>`__.

What carries over
-----------------

``caption``, ``label``, ``aligners``, ``formatters``, ``unbreakable``,
``ratio_cols``, ``year_cols``, ``date_cols``, ``raw_cols``, ``show_index``,
``config_path``, ``sparsify``, ``sparsify_columns``, ``header_row``,
``pef_lower``, ``pef_upper``. Any other
:class:`~greater_tables.spec.TableSpec` field can also be passed through the
facade as a keyword.

``formatters`` accepts the 5.x shapes: a callable, a format string
(``'{x:.1%}'``), or an int meaning "this many decimals".

.. warning::

   **A bare int now groups.** ``formatters={'paid': 2}`` gives ``1,234.57``
   in 6.0 where 5.x gave ``1234.57``, because GT2 groups whenever it chooses
   the format for you. Write ``'.2f'`` for the ungrouped form. This is the
   one silent behavior change in the facade — everything else either works
   or warns.

Unrecognized keywords **warn and are ignored** rather than raising, so an old
call site keeps working while you clean it up.

What changed
------------

Rule widths and other style knobs
    ``hrule_widths``, ``vrule_widths``, ``table_hrule_width``,
    ``table_vrule_width``, ``spacing``, ``padding_trbl``, ``font_body``,
    ``font_head``, ``font_caption``, ``caption_align``, ``header_alignment``,
    ``table_font_pt_size`` — these are renderer opinions, and renderer
    opinions no longer travel with the table. They live in
    :class:`~greater_tables.spec.HouseStyle` (TikZ) and CSS custom properties
    (HTML), where a theme can set them once for a document instead of a
    caller setting them per table.

Width machinery
    ``max_table_inch_width``, ``table_width_mode``,
    ``table_width_header_adjust``, ``table_width_header_relax``, ``equal`` —
    gone. The HTML renderer emits no widths at all and lets the browser
    measure; TikZ estimates internally. Width negotiation was the source of
    most of 5.x's surprises.

Default format strings
    ``default_integer_str``, ``default_float_str``, ``default_ratio_str`` and
    ``default_date_str`` have direct equivalents: ``int_format``,
    ``float_format``, ``ratio_format`` and ``date_format`` on
    :class:`~greater_tables.spec.TableSpec`. They take the same sugar plus a
    :class:`~greater_tables.ir.FormatSpec`, they are YAML-expressible, and
    each replaces only its own kind's built-in. ``table_float_format``
    survives with its 5.x precedence — it beats even a per-column entry —
    narrowed to *untagged float* columns, so ratio, year and date columns are
    immune. ``default_formatter`` is gone: there is no single fallback across
    dtypes, which is what makes the four named defaults predictable.

    The resolution order per column is its **kind** (semantic tag if it has
    one, else dtype), then within that kind: ``formatters[col]`` → the house
    default → the built-in. Setting ``float_format`` turns float *inference*
    off entirely, including the automatic SI/engineering switch.

The 50-row raise
    ``large_ok`` / ``large_warning`` are gone. ``max_rows`` (default 200)
    truncates with a note instead of raising. A table you actually want to
    scroll belongs in an interactive grid.

TikZ is computed lazily
    5.x built the TikZ rendering eagerly even when only HTML was wanted.
    Every rendering on ``GT`` is a lazily cached property, so the HTML path
    never pays for TeX.

No import side effects
    Importing the package no longer sets pandas options or installs warnings
    filters (5.x turned some ``RuntimeWarning``\ s into errors process-wide).
    If you relied on that, set it yourself.

``tabs``, ``debug``, ``tex_to_html``, ``cast_to_floats``, ``max_str_length``
    Dead or subsumed. Math detection is automatic (``math='auto'`` on the
    spec); TeX in string cells is recognized and rendered by each renderer.

New in 6.0
----------

Things worth adopting once the port is done:

- ``build(df, spec)`` returns a :class:`~greater_tables.ir.TableDoc` you can
  hash, cache, store, and send over HTTP (see :doc:`ir`).
- ``include_raw`` ships raw values alongside formatted text for clients.
- ``row_flags`` / ``cell_flags`` mark totals, subtotals, emphasis and muted
  rows semantically — no post-processing rendered markup to add classes.
- ``notes`` for table footnotes; ``label`` for Quarto cross-references.
- The bundled JS walker renders the same table client-side, and
  ``irToGridInput(doc)`` hands it to csv-grid for interactive use.
- ``max_table_width_em`` on :class:`~greater_tables.spec.HouseStyle` is the
  heir to 5.x's ``max_table_inch_width`` — a target, not a guarantee, since
  columns that cannot wrap hold their natural width.
- ``g`` format sugar (``'.3g'``), where ``digits`` counts significant
  figures rather than decimal places.
- ``text_ascii_rules`` on ``HouseStyle`` draws the text rendering without
  box-drawing characters, for LaTeX verbatim blocks and legacy consoles.
- The display bundle is target-aware — see :ref:`quickstart:notebooks and
  quarto`. A Quarto PDF render gets TikZ, everything else gets HTML, and
  ``text/plain`` always rides along so a table never silently vanishes.

Checking a port
---------------

The text renderer is the quickest way to compare two engines on the same
DataFrame — it strips away all styling and shows only decisions::

   print(GT(df, caption='Check'))     # 6.0
   # vs. 5.x: print(GT(df, caption='Check')) in a pinned environment

``dev/tools/compare_gt5.py`` in the repository does this side by side, running 5.3
in an isolated interpreter (the two versions share an import name, so they
cannot coexist in one process) and emitting an HTML comparison sheet.
