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
``html_cols``, ``markdown_cols``, ``unbreakable``) each accept a list of
labels, the string ``'all'``, or a regex matched against column names.
``markdown_cols`` sets ``*em*``, ``**strong**`` and ```code``` in its cells;
a markdown string input is markdown throughout, caption included, while a
DataFrame is markdown only where it says so, since its stars may be
significance stars or footnote markers:

.. code:: python

   TableSpec(
       ratio_cols='all',                          # regex / list / 'all'
       formatters={'paid': ',.1f', 'count': 0},   # per column
       float_format=',.2f',                       # house rule for all floats
       aligners='llrrc',                          # positional, or {label: 'r'}
       row_flags={-1: ['total']},                 # or a callable (pos, row)
       notes=['Amounts in USD thousands.'],
       include_raw='data',                        # ship raw values for clients
       max_rows=500,                              # truncate with a note
   )

Formats accept both dialects: csv-grid spec strings (``',.1f'``), Python
format strings (``'{x:.1%}'``), a plain int (decimal digits, grouped), a
mapping of :class:`~greater_tables.ir.FormatSpec` fields, an explicit
``FormatSpec``, or — in ``formatters`` only — a callable.

The presentation types are ``f`` decimal, ``d`` integer, ``%`` percent,
``e`` scientific, ``g`` general and ``s`` string, in either dialect. ``g``
follows Python and counts **significant figures**, so ``'.3g'`` gives
``1.23e+03`` for 1234.5 and ``0.00123`` for 0.0012345 — where ``'.3f'``
would give three decimal places in both cases. Uppercase ``G`` and ``E`` are
not parsed.

TeX math just works
-------------------

``$...$`` (and display ``$$...$$``) is math wherever text appears — body
cells, stub cells, column headers, captions and notes; whole-cell
(``$\psi(u)$``) and mid-sentence (``the survival $\psi(u)$ falls``) alike.
There is nothing to configure: each renderer draws its own math (native TeX
in TikZ, MathJax/KaTeX ``\(...\)`` spans in HTML) and escapes the prose
around it.

Currency is safe because the rule is strict: delimiters must be tight
against their content, a span may not contain another ``$``, and a closing
``$`` may not be followed by a digit — so ``$10 to $20`` and ``$5-$10`` set
as prices, escaped for TeX, never italicized. Write ``\$`` for a literal
dollar next to a real span (``escaped \$100 and $y=1$``).

The corners, so they are on record: ``$x$2`` reads as currency (write
``$x$ 2``); space-padded ``$ loose $`` is prose, not math; ``\(...\)`` /
``\[...\]`` are not recognized (write the ``$`` forms); and a ``\$``
*inside* a span is unsupported — use ``\mathdollar``. A document whose
dollars are all literal (a ticker table) can opt out wholesale with the
IR-level ``TableDoc.math='off'``.

House rules, one per kind
-------------------------

``float_format``, ``int_format``, ``ratio_format`` and ``date_format`` are the
5.x ``default_*_str`` settings. Each replaces its own kind's built-in and
loses to an explicit ``formatters`` entry, so the resolution per column is:
its **kind** (semantic tag if it has one, else dtype), then
``formatters[col]`` → the house default → the built-in.

Anything you leave unset is inferred from the column's dtype and its own
statistics — magnitude decides decimals, and a float column spanning many
orders of magnitude switches to engineering notation. Setting
``float_format`` turns that inference off for floats entirely, **including**
the engineering switch: a stated house rule beats a guess, which is what
makes twelve exhibits in one report agree with each other.

``table_float_format`` is the exception that overrides even a per-column
entry, on untagged float columns only. Use it at a call site for a quick
"show me everything at 6 dp" pass; never put it in a config file, where it
would silently defeat every ``formatters`` entry you write later.

Because these are ordinary spec fields, one YAML file can govern a whole
document:

.. code:: yaml

   # house.yaml
   float_format: ',.2f'
   ratio_format: '.1%'
   date_format: '%d %b %Y'
   ratio_cols: 'lr|ratio$'
   formatters: {paid: {kind: dec, digits: 1, negative: paren}}

.. code:: python

   from functools import partial
   from greater_tables import GT, load_spec
   from greater_tables.config import write_template

   myGT = partial(GT, config_path='house.yaml')     # every exhibit, one rule
   spec = load_spec('house.yaml')                   # or the explicit route

   write_template('house.yaml')                     # commented starting point
   write_template('house.yaml', gt.spec)            # this table's actual settings

Unknown keys raise, so typos surface at load. A ``partial`` is also the way to
make a domain-specific ``GT`` — ``partial(GT, year_cols=r'^(year|ay)$',
ratio_cols=r'lr|ratio$')`` — since the column tags are regexes.

Notebooks and Quarto
--------------------

``GT`` implements ``_repr_mimebundle_``, and always publishes ``text/plain``
— every measured consumer renders it, so a table never degrades to silence or
to ``<GT at 0x…>``. What joins it depends on the target:

===================================  ============================
target                               keys published
===================================  ============================
Quarto PDF (``QUARTO_FIG_FORMAT``    ``text/latex, text/plain``
is ``pdf``)
JupyterLab, Quarto HTML, anything    ``text/html, text/plain``
else
===================================  ============================

``text/html`` is omitted on the PDF path on purpose: pandoc prefers html when
offered and its LaTeX writer then discards it, so the table would vanish
entirely. Nothing global is touched on import — no pandas options, no
warnings filters.

.. code:: python

   from greater_tables import GT
   GT(df, caption='Exhibit 1', label='tbl-exhibit-1')   # label = Quarto xref id

One target cannot be detected: ``quarto render --to gfm`` looks exactly like
an HTML render from the environment, and pandoc's commonmark writer leaks raw
html into the markdown. Pin the bundle for the whole build:

.. code:: python

   from functools import partial
   render = partial(GT, mimes=('text/plain',))    # for a gfm document

``mimes=None`` (the default) detects; an explicit tuple publishes exactly
those types. Members are validated at construction, so a typo raises rather
than silently producing a bundle nothing can display.

``repr()`` gives the text table too, which is what makes ``GT`` usable from a
plain script or a REPL.

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

.. _tikz-renderer:

The TikZ renderer
-----------------

The table is one real ``tabular`` inside a single TikZ node. Horizontal rules
come from booktabs, where TeX already knows the row positions; vertical rules
are drawn from the node's corners at offsets ``greater_tables`` computes
itself. The node carries its own macros, so the document needs nothing beyond
the packages below. The body is a literal ``tabular``, so a typesetter who
does not use TikZ can lift it by deleting the wrapper.

**Packages.** ``tikz``, ``booktabs`` and ``array``, and no TikZ library.
:class:`~greater_tables.Etcher` supplies them. Quarto's default LaTeX
template loads ``booktabs`` and ``array`` only when the document holds a
markdown table, so a document should name them in its preamble.

**It does not break across pages:** a TikZ node is one unbreakable box.

**Name the face.** TeX needs the column widths before it sets the table, so
``greater_tables`` estimates them from glyph widths measured in the face the
table will be set in. Set ``HouseStyle.tikz_font`` to the document's face:
``'times'`` (the default, and what ``Etcher`` compiles with), ``'stix-two'``,
``'latin-modern'`` (a plain Quarto PDF), ``'lato'`` or ``'fira-sans'``. Left
at Times, a table in STIX Two or Latin Modern wraps labels and hyphenates
headings, because lowercase there sets about 5% wider.

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
