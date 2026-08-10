The table document (IR v1)
==========================

The IR is the contract between the engine and every renderer, and between a
server and a browser. It is a JSON object; in Python it is a frozen pydantic
:class:`~greater_tables.ir.TableDoc`. It carries semantics only — no widths,
no rule weights, no CSS, no fonts.

The committed JSON Schema lives at ``schema/ir-v1.json`` in the repository and
is diff-guarded against the live models by the test suite, so an accidental
IR change cannot ship quietly.

Shape
-----

.. code:: text

   TableDoc
     ir_version      1
     generator       "greater_tables 6.0.0"      informative, excluded from the hash
     hash            12 hex chars                content hash of everything else
     caption, label, notes
     n_stub_levels, n_head_levels
     columns[]       Column                      stub columns first
     head[][]        HeadCell                    one array per header level
     body[]          Row
     foot[]          Row                         rarely used, in v1 regardless

Column
    ``key`` (``"c0"``, positional), ``name`` (the **full header path as a
    list** — no lossy ``.``-joined flattening), ``role`` (``stub`` | ``data``),
    ``level``, ``dtype``, ``tag`` (``ratio`` | ``year`` | ``date`` | ``raw``),
    ``align`` (``l`` | ``r`` | ``c``), ``wrap``, ``break_depth`` (column-group
    boundary at the left edge), ``format`` (the resolved spec), ``raw``
    (whether body cells in this column carry raw values).

Row
    ``cells`` — only the *uncovered* columns, exactly like HTML ``rowspan``
    semantics: a stub cell spanning three rows appears in the first of them
    and the other two simply have fewer cells. ``break_depth`` is the
    shallowest stub level whose value changed versus the previous row (0 =
    outermost); house style maps depth to rule weight. ``flags`` come from a
    closed vocabulary: ``total``, ``subtotal``, ``emphasis``, ``muted``.

Cell
    ``text`` (plain unicode, **unescaped** — each renderer escapes for its own
    target; unless the document says ``math='off'`` it may carry inline
    ``$...$`` spans, which renderers segment via
    :mod:`greater_tables.mathspans`), optional ``raw``,
    ``rowspan``/``colspan``, ``flags`` (``neg``, ``emphasis``, ``muted``),
    ``math`` (whole-cell TeX source without delimiters), ``html`` (default
    false; the walker additionally requires ``allowHtml``, so injection is
    off by default). A cell that is plain text with no other attributes
    serializes as a bare string — the shorthand roughly halves the payload.

FormatSpec
    ``{kind, digits, group, scale, prefix, suffix, negative, null, zero,
    pattern}`` with ``kind`` one of ``int``, ``dec``, ``pct``, ``sci``,
    ``gen``, ``si``, ``eng``, ``year``, ``date``, ``str``. Applicable by
    Python and by about forty lines of ``Intl.NumberFormat`` JavaScript.
    ``digits`` means decimal places for every kind except ``gen``, python's
    ``g``, where it counts significant figures.

Rules that matter
-----------------

**Text is normative, format is informative.** ``cell.text`` is what the table
says. ``column.format`` lets a client re-render at different precision
without redoing the engine's column-scanning inference — but a client that
re-renders and disagrees is wrong, not the document. This defuses
cross-language rounding ties instead of pretending they do not exist.

**Raw values are opt-in.** ``include_raw`` in the spec is off by default:
``True``/``'data'`` carries raw values for numeric, date, and bool data
columns, or pass an explicit column list. Rendering paths never pay the
roughly 2× payload; a client that will hand the table to an interactive grid
(or re-sort it) asks for them.

**Determinism.** ``hash`` is sha256 over the canonical JSON — sorted keys,
NFC-normalized strings, ``repr`` floats, defaults omitted, no time salt.
The same DataFrame and spec produce the same bytes on every machine, which is
what makes golden-file tests, HTTP caching, and ``ETag``/``If-None-Match``
round-trips real. No element ids are emitted unless a Quarto ``label`` is set.

**Versioning.** Readers must ignore unknown fields, so additive fields may
only ever be advisory; anything content-bearing (``foot``, body ``colspan``)
shipped in v1 even though it is rarely used. The write path is strict
(``extra='forbid'``, so producer typos surface immediately) and the read path
is lenient (:meth:`~greater_tables.ir.TableDoc.read` strips unknown fields
first). Consumers throw on an ``ir_version`` they do not recognize rather
than guessing.

Working with documents
----------------------

.. code:: python

   from greater_tables import build, canonical_json, doc_hash, TableDoc

   doc = build(df, spec)
   doc.hash                        # '3f2a9c1b7e04' — content hash
   payload = canonical_json(doc)   # deterministic UTF-8 bytes
   again = TableDoc.read(payload)  # lenient read path

   doc.columns[0].format           # FormatSpec(kind='dec', digits=1, group=True)
   doc.body[3].flags               # ('total',)

Serving one over HTTP is three lines, and ``doc.hash`` is the ETag:

.. code:: python

   return Response(canonical_json(doc), media_type='application/json',
                   headers={'ETag': doc.hash})
