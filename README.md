# greater_tables

![commit activity](https://img.shields.io/github/commit-activity/y/mynl/greatest_tables)
![PyPI version](https://img.shields.io/pypi/v/greater-tables)
![documentation](https://img.shields.io/readthedocs/greater-tables-project)
![license MIT](https://img.shields.io/badge/license-MIT-blue)

**Greater Tables** produces high-quality static display tables for journal
articles, books, formal reports, and printed financial statements. A pandas
DataFrame (or CSV, or markdown table) goes in; a clean, typographically sound
table comes out in HTML, LaTeX (via TikZ), or plain text. No sparklines, no
color, no shading: just your data, rendered cleanly.

```python
from greater_tables import GT
GT(df)
```

Between the DataFrame and the page sits a versioned, JSON-serializable
**table document**, the intermediate representation (IR). Python owns
*semantics* (dtypes, format inference, multi-index hierarchy, spans, break
depths); each renderer owns *geometry and style*. Nothing in the IR names a
width, a rule weight, a font, or a CSS property, so the HTML renderer, the
TikZ renderer, the text renderer, and the bundled JavaScript walker all draw
the same table and are conformance tested against each other.

## Installation

```bash
pip install greater-tables
```

Requires Python 3.12+. The import name never changes, so
`from greater_tables import GT` works on every version. Pin
`greater-tables<6` to stay on the frozen 5.3 engine, or `greater-tables<8` to
keep the retired `matrix` TikZ engine.

## Quick look

```python
from greater_tables import GT, Fabricator
gt = GT(Fabricator(seed=42).make(10, 's2fd', index_levels=2), caption='Demo')
gt                      # rich display in JupyterLab / Quarto
print(gt)               # the text rendering
gt.doc                  # the IR, as pydantic models
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

## What it does

- **Formats by meaning, not by hand.** Text left, numbers right with uniform
  decimals per column chosen from the column's magnitude, engineering
  notation for a column spanning many orders of magnitude, years without
  commas, dates in ISO form and centered. Tag columns with `ratio_cols`,
  `year_cols` and the other selectors (a list, `'all'`, or a regex); totals
  and subtotals come from `row_flags`.
- **Hierarchy drawn once, everywhere.** A row MultiIndex is sparsified, with
  rules where an outer level changes (a *break depth*, decided in the IR);
  column MultiIndex groups get spanning labels and optional vertical rules.
- **TeX math just works.** `$...$` is math in body cells, stub cells,
  headers, captions and notes, whole-cell or mid-sentence, while `$10 to $20`
  stays two prices.
- **Inline markdown.** `*em*`, `**strong**` and `` `code` `` set as italic,
  bold and code. A markdown string input is markdown throughout; a DataFrame
  opts in per column with `markdown_cols`, so significance stars and footnote
  markers stay stars.
- **TikZ for print.** One real `tabular` inside a single TikZ node, rules
  from booktabs, verticals drawn in TikZ. The document needs `tikz`,
  `booktabs` and `array`. Set a width budget, `HouseStyle(max_table_width_em=...)`,
  and the table narrows its prose columns first, then scales down to fit, with
  `tikz_scale` as the largest scale it may use. There is no budget by default,
  since the page width belongs to the document: set one per document with
  `functools.partial(GT, style=HouseStyle(...))`. `tikz_font` names the
  document's face so column widths are estimated in its glyphs.
- **The display bundle knows its target.** A notebook or a Quarto HTML render
  gets HTML; a Quarto PDF render gets the TikZ. Every bundle also carries
  `text/plain`, so a table degrades to a readable monospace rendering rather
  than to `<GT object at 0x…>` or to nothing.
- **One set of house rules per document.** Every option is a field of
  `TableSpec` (what the table is) or `HouseStyle` (how it is drawn), and each
  loads from YAML:
  `partial(GT, config_path='spec.yaml', style=load_style('style.yaml'))`.
- **No import side effects.** Importing the package touches no pandas options
  or warnings filters. `max_rows` (default 200) truncates with a note.
- **In the browser.** The zero-dependency walker, `gt-render.js`, ships as
  package data and renders the same document client-side. Interactive grids
  remain the job of the sibling `csv-grid` project; this package does not
  sort, filter, or virtualize, by design.

## Upgrading

**From 7.x.** 8.0 removed the `matrix` TikZ engine, the default before 6.2.
`HouseStyle(tikz_engine='matrix')` logs a warning and renders the `tabular`,
which sets the same table; drop the setting. Several 7.x and 8.x releases
change TikZ geometry or number formatting, so a rebuilt document can differ;
each such release is marked **Output changes** in the
[CHANGELOG](https://github.com/mynl/greatest_tables/blob/main/CHANGELOG.md).

**From 5.x.**
[Migrating from greater_tables 5.x](https://greater-tables-project.readthedocs.io/en/latest/migration.html)
is the complete map: every 5.x option, what it did, and where it went, plus
the three silent default changes to watch for (`formatters` ints now group,
`show_index` auto-hides, `header_row` defaults off). `greater_tables` 5.x
stays available and pinnable on PyPI; its source and issue archive stay at
[mynl/greater_tables_project](https://github.com/mynl/greater_tables_project).

## Documentation

[Read the Docs](https://greater-tables-project.readthedocs.io/en/latest/)
covers the quickstart, design, IR reference, migration notes and API.

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
tests/                 fixtures (synthetic only) + goldens (ir / text / text-ascii / tikz-tabular / transcript)
schema/                committed JSON Schema export of the IR (diff-guarded by the tests)
docs/                  Sphinx documentation
guide/                 Quarto gallery of every fixture, in HTML and TikZ
dev/                   design notes and plans; plans move to dev/done when they execute
```

Runtime dependencies are numpy, pandas, pydantic and PyYAML, nothing else,
and the JS walker has none at all.

## Status

**Stable.** The engine, IR, JS walker, HTML renderer and TikZ renderer are
conformance tested against each other. `ir_version` 1 and the public API
follow semantic versioning: a breaking change bumps the major version, as
8.0 did. See
[`dev/design.md`](https://github.com/mynl/greatest_tables/blob/main/dev/design.md)
for the design,
[`dev/pending.md`](https://github.com/mynl/greatest_tables/blob/main/dev/pending.md)
for what is outstanding, and the
[**CHANGELOG**](https://github.com/mynl/greatest_tables/blob/main/CHANGELOG.md)
for the version-by-version record.
