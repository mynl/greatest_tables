Design
======

One rule explains the whole package: **Python owns semantics, each renderer
owns geometry and style.** The two meet at a versioned JSON document.

.. code:: text

                                greater_tables
    df / csv / markdown ──► engine ──► TableDoc (pydantic ⇄ canonical JSON, ir_version 1)
                                          │
                ┌─────────────┬───────────┼──────────────┬─────────────┐
                ▼             ▼           ▼              ▼             ▼
           render/html   render/tikz  render/text   JSON over API   (the GT facade
           (JupyterLab/  (Quarto PDF, (conformance       │           wraps all of it)
            Quarto/HTMX)  via Etcher)  oracle)           ▼
                                                   gt-render.js (walker: IR → DOM)

Semantics are the decisions that must not differ between a PDF and a web
page: which columns are numeric, how many decimals each gets, where the
multi-index hierarchy breaks, which cells span, which rows are totals.
Geometry and style are the decisions that must differ: column widths, rule
weights, fonts, padding, colors. The IR carries the first kind and refuses
the second — it never names a width, a rule weight, a font, or a CSS
property.

Why it is built this way
------------------------

greater_tables 5.x had no internal table model: semantics and rendering were
tangled together in a single large class, so the HTML and TikZ paths made
independent decisions about the same table, the per-table CSS was scoped to a
time-salted id (no caching, no golden tests), and a browser client could only
receive a string of HTML. The rewrite makes the model explicit and everything
else a function of it. Consequences worth stating plainly:

- **A table is data.** ``build(df, spec)`` returns a document you can hash,
  cache, diff, store, and send. Rendering is downstream and cheap.
- **Renderers cannot drift apart.** The Python HTML renderer and the JS
  walker must emit identical DOM transcripts for every fixture; the text
  oracle reads only the document, so anything it cannot draw is data missing
  from the IR. Both are enforced in the test suite.
- **Clients get meaning, not markup.** An API ships the document; the browser
  draws it. No server-side HTML blobs, and no post-processing someone else's
  markup to add row emphasis.

The engine
----------

``engine/build.py`` orchestrates and never mutates the input:

``dtypes.py``
    Classify each column (int, float, date, datetime, bool, string, object)
    and apply semantic tags — ratio, year, date, raw — from the spec's
    selectors (list, ``'all'``, or regex).
``formats.py``
    Resolve display format per column: explicit spec override, then tag, then
    dtype, then column statistics. A float column's mean magnitude picks its
    decimals, and a column spanning many orders of magnitude switches to
    engineering notation (SI suffixes by default; aligned exponents on
    request). Accepts csv-grid spec strings and Python format strings as
    input sugar, and resolves both to one :class:`~greater_tables.ir.FormatSpec`.
``structure.py``
    Hierarchy: sparsify repeated stub values into rowspans, repeated header
    prefixes into colspans, and compute *break depths* — for a row, the
    shallowest stub level whose value changed; for a column, a group boundary
    at its left edge. House style maps depth to rule weight. The IR says
    "the outer group changed here", never "draw a 1pt rule here".
``hashing.py``
    Canonical JSON (sorted keys, NFC strings, deterministic float repr,
    defaults omitted) and the 12-hex content hash. No time salt — this is
    what makes golden files, caching, and ETags possible.

Renderers
---------

**HTML** (``render/html.py``) emits no widths at all: ``gt-nowrap`` on
numeric and date columns, a ``max-width`` plus wrapping on prose,
``table-layout: auto``, and the browser measures. Structure rides as
classes — ``gt-l/r/c``, ``gt-stub``/``gt-data``, ``gt-break-{n}``,
``gt-vbreak-{n}``, ``gt-total``, ``gt-neg``, ``gt-math``.

**CSS** (``render/css.py``) is generated from a ``RULES`` dict — the single
source of truth for both the document-level stylesheet (``assets/gt.css``)
and the inline flattener, so the two cannot diverge. Selectors double the
class (``.gt.gt td``) to beat JupyterLab and Quarto host rules without
``!important``. Per-table scalars ride as CSS custom properties on the
wrapper (``--gt-rule-0``, ``--gt-pad-v``, ``--gt-prose-max``, …), so a theme
is an alternate property block. Default colors are ``currentColor`` and
transparent: an embedded fragment has no opinion about your page's light or
dark mode.

**TikZ** (``render/tikz.py``) is a single implementation from the document,
with real colspan support, and owns the only character-based width estimation
in the package (``TextLength``) — PDF has no browser to measure for it.
``Etcher`` compiles the result, tectonic first with a pdflatex fallback, and
caches outputs by content hash.

**Text** (``render/text.py``) is the conformance oracle: a monospace
rendering that reads *only* the document. It is deliberately the dumbest
renderer, which is what makes it useful — if the text view cannot show
something, the information is missing from the IR.

The JS walker
-------------

``js/src/gt-render.js`` builds into ``assets/gt-render.esm.js`` and
``gt-render.iife.js``, shipped as Python package data so an API can serve the
walker straight from the installed package — the walker and the document
emitter cannot version-skew.

.. code:: javascript

   const t = renderTable(doc, { mount, allowHtml, katex, fit });
   // → { el, doc, destroy(), toCSV() }

It always returns an instance handle (never anonymous fire-and-forget), uses
the same ``gt-*`` class vocabulary as the Python renderer, and throws on an
unrecognized ``ir_version``. One delegated click listener on the instance
root dispatches ``gt:cellclick`` custom events. Math cells arrive as TeX and
render through an injected ``katex`` object, or fall back to ``\(...\)`` for
page MathJax. Cell ``html`` flags are honored only when ``allowHtml`` is
passed — injection-safe by default.

The walker does **not** sort, filter, or virtualize, and never will: a table
you want to sort is an interactive grid, which is the sibling ``csv-grid``
project's job. ``irToGridInput(doc)`` hands a document to it whole — build
with ``include_raw='data'`` so the numeric, date and bool columns carry their
values; string columns need nothing, since their text *is* their value — so
one fetch feeds both the static walker and the interactive grid. An optional ``fit`` pass runs canvas ``measureText`` plus a
width solver for constrained containers; the default is natural browser
layout, the same policy as the Python renderer.

Verification
------------

Three layers, all in ``tests/``:

1. **Golden IR** — byte-equal canonical JSON per synthetic fixture. Possible
   only because the hash and serialization are deterministic.
2. **Conformance** — the Python HTML renderer (parsed with stdlib
   ``html.parser``) and the JS walker (run in node under linkedom) must
   produce identical DOM transcripts, one JSON line per cell
   (``{r, c, tag, colspan, rowspan, classes, text}``). Golden text and TeX
   files ride alongside as the human-readable check.
3. **Schema** — ``schema/ir-v1.json`` is committed and diff-guarded against
   the models, so an accidental IR change cannot ship quietly.

All fixtures are synthetic, generated by ``Fabricator``. No real data enters
the repository.
