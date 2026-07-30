# greatest_tables

Semantic table engine. A pandas DataFrame (or CSV or markdown table) goes in; a
versioned, JSON-serializable **table document** (the IR) comes out; renderers turn
that IR into static book-quality HTML (Jupyter/Quarto), TikZ/PDF (Quarto books), plain
text (conformance oracle), or client-side DOM via the bundled JS walker (SPAs).

The IR is the contract: Python owns *semantics* (dtypes, format inference, multi-index
hierarchy, spans, break depths); each renderer owns *geometry and style*. Nothing in
the IR names a width, a rule weight, a font, or a CSS property.

Successor to [greater_tables](https://pypi.org/project/greater-tables/) (which stays
frozen at 5.x); working name `greatest_tables`, publish name TBD. Interactive grids
remain the job of the sibling `csv-grid` project — this package hands tables to it,
it does not compete with it.

## Layout

```
src/greatest_tables/   ir.py (pydantic IR) · spec.py · engine/ · render/ · assets/
js/src/                gt-render.js walker (built into assets/)
tests/                 fixtures (synthetic only) + golden files (ir / text / transcript)
schema/                committed JSON Schema export of the IR (CI diff-guarded)
dev/                   plan docs; moved to dev/done when complete
```

## Status

Under development, step [ir-core]. See `dev/design.md` for the full design and
`CHANGELOG.md` for progress.
