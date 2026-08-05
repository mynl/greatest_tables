# greater_tables (GT2)

![](https://img.shields.io/github/commit-activity/y/mynl/greatest_tables)
![](https://img.shields.io/pypi/v/greater-tables)
![](https://img.shields.io/readthedocs/greater-tables)

**Greater Tables** produces high-quality static display tables for journal
articles, books, formal reports, and printed financial statements. A pandas
DataFrame (or CSV, or markdown table) goes in; a clean, typographically sound
table comes out in HTML, LaTeX (via TikZ), or plain text. No sparklines, no
color, no shading: just your data, rendered cleanly.

```python
from greater_tables import GT
GT(df)
```

This project is a ground-up rewrite that publishes as `greater-tables` 6.0.
Between the DataFrame and the page sits a versioned, JSON-serializable
**table document**, the intermediate representation (IR). Python owns *semantics* (dtypes, format
inference, multi-index hierarchy, spans, break depths); each renderer owns
*geometry and style*. Nothing in the IR names a width, a rule weight, a font,
or a CSS property, so the HTML renderer, the TikZ renderer, the text oracle,
and the bundled JavaScript walker all draw the same table and are conformance
tested against each other.

## Installation

```bash
pip install greater-tables
```

6.0 is not on PyPI yet, until it is, `pip install greater-tables` gives you
the frozen 5.3 engine. Install this rewrite from source
(`pip install git+https://github.com/mynl/greatest_tables`), and pin
`greater-tables<6` anywhere you want to stay on 5.x. The import name never
changes: `from greater_tables import GT` works on both.

## Quick look

```python
from greater_tables import GT, Fabricator
gt = GT(Fabricator(seed=42).make(10, 's2fd', index_levels=2), caption='Demo')
gt                      # rich display in JupyterLab / Quarto (HTML)
print(gt)               # text oracle view
gt.doc                  # the IR as pydantic models
gt.tikz                 # TikZ/LaTeX source
```

Or the explicit API, which is the same thing without the facade:

```python
from greater_tables import build, render_html, render_tikz, TableSpec
doc = build(df, TableSpec(caption='Demo', ratio_cols='all'))
render_html(doc)        # fragment + stylesheet
render_tikz(doc)        # table environment + tikzpicture
doc.model_dump_json()   # ship it to the browser; gt-render.js draws it
```

Open `demo.html` for every golden fixture rendered client-side by the walker.

## What 6.0 changes

- **A table document, not a string.** `build(df, spec) → TableDoc`, validated
  pydantic models, canonical JSON, deterministic 12-hex content hash (no time
  salt), JSON Schema committed at `schema/ir-v1.json`. Cacheable, diffable,
  golden-testable, and an ETag for free.
- **Four renderers, one contract.** HTML, TikZ, text, and the zero-dependency
  JS walker (`gt-render.js`, shipped as package data) render from that one
  document; the Python HTML renderer and the walker must produce identical DOM
  transcripts, per fixture, enforced by the test suite.
- **The display bundle knows its target.** In a notebook or Quarto HTML render
  you get HTML; a Quarto PDF render gets TikZ and no HTML, because pandoc
  would prefer the HTML and its LaTeX writer would then throw it away. Every
  bundle also carries `text/plain`, so a table degrades to a readable
  monospace rendering rather than to `<GT object at 0x…>` or to nothing.
- **Semantics stay in Python, style stays in the renderer.** One document-level
  stylesheet generated from a `RULES` dict (or inlined for HTMX/email), a
  `gt-*` class vocabulary, per-table scalars as CSS custom properties.
- **No import side effects**, importing the package no longer touches pandas
  options or warnings filters. No 50-row raise, either: `max_rows` truncates
  with a note.
- **Compat facade.** `GT(df, caption=..., ratio_cols=..., formatters=...)`
  works as before and renders through the new engine, lazily and cached (5.x
  computed TikZ eagerly even on the HTML path). Exotic 5.x config knobs warn
  and are ignored.
- Interactive grids remain the job of the sibling `csv-grid` project,
  `irToGridInput(doc)` hands a table to it whole. This package does not sort,
  filter, or virtualize, by design.

`greater_tables` 5.x stays available and pinnable on PyPI forever; its source
and issue archive stay at
[mynl/greater_tables_project](https://github.com/mynl/greater_tables_project).

## Documentation

[ReadtheDocs](https://greater-tables.readthedocs.io/en/latest/) covers design, IR
reference, migration notes, API.

## Source

[GitHub](https://github.com/mynl/greatest_tables). The repo keeps the
development codename `greatest-tables`; the package it publishes is
`greater-tables`.

## License

MIT.

## The Name

Obviously, the name is a play on the `great_tables` package. I have been
maintaining a set of macros called
[GREATools](https://www.mynl.com/old/GREAT/home.html) (generalized, reusable,
extensible actuarial tools) in VBA and Python since the late 1990s, and call
all my macro packages *GREAT*. The rewrite was codenamed *greatest* while it
grew up next to its parent; the repo kept the codename, the package did not.

## Layout

```
src/greater_tables/    ir.py (pydantic IR) · spec.py · engine/ · render/ · assets/
js/src/                gt-render.js walker (built into assets/)
tests/                 fixtures (synthetic only) + goldens (ir / text / text-ascii / tikz / transcript)
schema/                committed JSON Schema export of the IR (diff-guarded by the tests)
docs/                  Sphinx documentation
dev/                   plan docs; moved to dev/done when complete
```

Requires Python 3.11+. Runtime dependencies are numpy, pandas, pydantic and
PyYAML — nothing else, and the JS walker has none at all.

## Status

**Pre-release (`6.0.0a11`).** All seven design steps are complete: the engine,
IR, JS walker, Python HTML renderer, and TikZ renderer are conformance-tested
against each other, and the first consumer (aggregate_api's SPA) renders
tables client-side from the IR. The alpha series is running while that
adoption settles, so the public API can still shift; `6.0.0` is the point at
which it stops. See `dev/design.md` for the full design, `dev/pending.md` for
what is outstanding, and `CHANGELOG.md` for the version-by-version record.
