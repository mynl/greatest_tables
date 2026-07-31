Quickstart
==========

Two ways in: the ``GT`` facade (one object, every rendering, lazily computed)
or the explicit ``build`` / ``render_*`` functions. They do the same work —
``GT`` just holds the document for you.

The facade
----------

.. code:: python

   from greater_tables import GT, Fabricator

   df = Fabricator(seed=42).make(6, 'fdi', index_levels=2)
   gt = GT(df, caption='Demo table')

   gt          # rich display in JupyterLab / Quarto
   gt.html     # HTML fragment, stylesheet embedded
   gt.tikz     # TikZ/LaTeX source
   gt.text     # monospace rendering
   gt.doc      # the table document (the IR)
   print(gt)   # same as gt.text

``print(gt)`` on that table::

   Demo table

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   i_0      i_1      │ turbulence       energy       approval
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   victims  integer  │    217,478  2025-03-27 23:22    68,625
            icons    │   -365,061  2024-07-04 13:11    57,346
            candidly │    101,784  2023-08-04 20:48    76,166
   ──────────────────────────────────────────────────────────
   gossip   integer  │    207,004  2021-05-25 12:53    86,918
            icons    │    101,475  2021-02-03 10:04    52,297
            candidly │     67,528  2024-04-27 07:15    81,821
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Note what the engine decided without being told: text left, numbers right
with thousands separators and no decimals (they are large), dates centered
and ISO-formatted, the repeated outer index value sparsified into a rowspan,
and a rule where the outer index changes — a *break depth*, not a hardcoded
line. Every one of those is a semantic decision that lives in the document,
so all four renderers make the same one.

A ``GT`` is immutable and everything on it is cached: constructing one
computes nothing, and asking for HTML never computes TikZ. To change options,
build a new one.

The explicit API
----------------

.. code:: python

   from greater_tables import build, render_html, render_text, render_tikz, TableSpec

   spec = TableSpec(caption='Loss ratios', ratio_cols='lr|ratio',
                    year_cols=['year'], max_rows=200)
   doc = build(df, spec)      # → TableDoc: validated, hash-stamped

   render_html(doc)           # fragment + <style>
   render_tikz(doc)           # table environment + tikzpicture
   render_text(doc)           # the conformance oracle's view

``build`` never mutates the DataFrame. The same DataFrame and spec always
produce the same document, byte for byte — see :doc:`ir`.

Telling the engine what the columns mean
----------------------------------------

:class:`~greater_tables.spec.TableSpec` is the whole user-facing surface.
Column selectors (``ratio_cols``, ``year_cols``, ``date_cols``, ``raw_cols``,
``html_cols``, ``unbreakable``) each accept a list of labels, the string
``'all'``, or a regex matched against column names:

.. code:: python

   TableSpec(
       ratio_cols='all',                      # regex / list / 'all'
       formats={'paid': ',.1f', 'count': 0},  # csv-grid or GT format sugar
       aligners='llrrc',                      # positional, or {label: 'r'}
       row_flags={-1: ['total']},             # or a callable (pos, row) -> flags
       notes=['Amounts in USD thousands.'],
       include_raw='data',                    # ship raw values for clients
       max_rows=500,                          # truncate with a note
   )

Formats accept both dialects: csv-grid spec strings (``',.1f'``), Python
format strings (``'{x:.1%}'``), a plain int (decimal digits), a callable, or
an explicit :class:`~greater_tables.ir.FormatSpec`. Anything not specified is
inferred from the column's dtype and its own statistics — magnitude decides
decimals, and a float column spanning many orders of magnitude switches to
engineering notation.

Defaults can live in YAML (this project's config format):

.. code:: python

   from greater_tables import load_spec
   from greater_tables.config import write_template

   write_template('tables.yaml')       # commented starting point
   spec = load_spec('tables.yaml')

Unknown keys raise, so typos surface at load.

Notebooks and Quarto
--------------------

``GT`` implements ``_repr_mimebundle_``: JupyterLab and Quarto HTML get the
HTML fragment; a Quarto PDF/LaTeX render gets TikZ. Nothing global is touched
on import — no pandas options, no warnings filters.

.. code:: python

   from greater_tables import GT
   GT(df, caption='Exhibit 1', label='tbl-exhibit-1')   # label = Quarto xref id

The stylesheet is embedded with every fragment by default (~2 KB, idempotent
— safe for saved and cleared notebooks). ``render_html(doc, css='once')``
emits it once per kernel; ``css='none'`` never; ``inline_css=True`` flattens
the same rules onto ``style`` attributes for HTMX fragments and email.

PDF from TikZ
-------------

.. code:: python

   from greater_tables import GT, Etcher

   etcher = Etcher(GT(df).tikz, file_name='exhibit-1')
   etcher.compile()          # → PDF (tectonic by default, pdflatex fallback)

Outputs cache by content hash, so recompiling an unchanged table is free.

In the browser
--------------

The same document renders client-side with the bundled zero-dependency
walker, which ships as package data (``gt-render.esm.js``,
``gt-render.iife.js``, ``gt.css``):

.. code:: python

   from importlib.resources import files
   assets = files('greater_tables') / 'assets'      # serve these

.. code:: javascript

   import { renderTable } from './gt-render.esm.js';
   const t = renderTable(doc, { mount: el, allowHtml: true });
   // t.el, t.doc, t.toCSV(), t.destroy()

Serving the walker from the installed package means it cannot version-skew
against the document the same process emits. See :doc:`design` for the walker
contract and the csv-grid handoff.
