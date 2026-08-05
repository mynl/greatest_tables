# Migrating from greater_tables 5.x

The import name does not change, and the common call still works:

```python
from greater_tables import GT
GT(df, caption='Exhibit 1', ratio_cols=['lr'], year_cols='year')
```

{class}`~greater_tables.compat.GT` is a thin compatibility facade over the new
engine — constructor-compatible where that still makes sense, not bug-for-bug.
It is deliberately *thin*: options that were really renderer opinions, or that
the new architecture makes meaningless, are gone.

This page is the complete map. Every 5.x option, what it did, and where it
went, compiled from 5.3's `config.py` `Configurator` (47 fields, with its own
`Field(description=...)` text as the source for "what it did") and `core.py`'s
`GT.__init__` signature.

## Staying on 5.x

5.3 is frozen, complete, and stays installable from PyPI forever. Pin it:

```bash
pip install "greater-tables<6"
```

That is what the major version is for. Its source and issue archive remain at
[mynl/greater_tables_project](https://github.com/mynl/greater_tables_project).

## What carries over

`caption`, `label`, `aligners`, `formatters`, `unbreakable`, `ratio_cols`,
`year_cols`, `date_cols`, `raw_cols`, `show_index`, `config_path`, `sparsify`,
`sparsify_columns`, `header_row`, `pef_lower`, `pef_upper`. Any other
{class}`~greater_tables.spec.TableSpec` field can also be passed through the
facade as a keyword.

`formatters` accepts the 5.x shapes: a callable, a format string
(`'{x:.1%}'`), or an int meaning "this many decimals".

Unrecognized keywords **warn and are ignored** rather than raising, so an old
call site keeps working while you clean it up.

```{warning}
**Three silent default changes.** Everything else either works or warns.

- **A bare int now groups.** `formatters={'paid': 2}` gives `1,234.57` where
  5.x gave `1234.57`, because GT2 groups whenever it chooses the format for
  you. Write `'.2f'` for the ungrouped form.
- **`show_index` defaults to `None`**, which auto-hides a trivial unnamed
  `RangeIndex`. Pass `True` to force the index to show.
- **`header_row` defaults to `False`.** Pass `header_row=True` for
  list-of-lists input that carries a header row.
```

## The two objects

The split is the whole design: semantics (what the table *means*) stay in
Python and travel in the IR; geometry and style (what it *looks like*) belong
to each renderer. Most deletions below are options that crossed that line.

| Marker | Meaning |
|---|---|
| **TableSpec** | Semantics that ride with the table. `TableSpec(...)` → `build(df, spec)`, or the same keyword on the `GT` facade. YAML-loadable via `load_spec`. |
| **HouseStyle** | Renderer opinions — rule depth, weights, TikZ geometry. Never enters the IR. Pass it to any renderer or to the facade: `GT(df, style=HouseStyle(...))`, `render_html(doc, style=...)`, `render_text(doc, style)`, `render_tikz(doc, style)`; YAML via `load_style(path)`. |
| **CSS** | A custom property on the `.gt` wrapper, set in your own stylesheet or a theme block. Defaults live in `render/css.py::VARIABLES`. |
| **engine** | No longer a knob: the engine decides per column from dtype and column statistics. Override per column with `TableSpec.formatters`. |
| **gone** | Deleted, with no replacement. The "Notes" column says what to do instead, if anything. |

## HouseStyle in full

Everything on `HouseStyle`, and who actually reads it:

| field                | default              | read by            | controls                                                       |
| -------------------- | -------------------- | ------------------ | -------------------------------------------------------------- |
| `max_rule_depth`     | `'auto'`             | **all four**       | which stub depths get a horizontal rule                        |
| `max_vrule_depth`    | `1`                  | HTML, TikZ, walker | which column-group depths get a vertical                       |
| `max_prose_width_em` | `18.0`               | HTML, TikZ         | how wide one *wrapping* column may get (HTML: `--gt-prose-max`) |
| `max_table_width_em` | `None`               | HTML, TikZ         | total width to aim for (HTML: `--gt-max-width`)                |
| `text_ascii_rules`   | `False`              | text               | `=` `-` `\|` `<<flag>>` instead of box drawing                  |
| `hrule_widths`       | `(0.5, 0.25, 0.25)`  | TikZ               | weight per depth slot (HTML: `--gt-rule-0/1/2`)                |
| `vrule_widths`       | `(0.25, 0.25, 0.25)` | TikZ               | weight per vrule slot (HTML: `--gt-vrule-0/1`) — `[2]` is dead |
| `frame_rule`         | `1.0`                | TikZ               | table top and bottom (`--gt-rule-frame`)                       |
| `head_rule`          | `1.0`                | TikZ               | under the header block (`--gt-rule-head`)                      |
| `stub_rule`          | `1.0`                | TikZ               | the stub/body vertical divider (`--gt-rule-stub`)              |
| `total_rule`         | `0.75`               | TikZ               | above rows flagged `total` (`--gt-rule-total`)                 |
| `spanner_rule`       | `0.5`                | TikZ               | cmidrule under a column-group label (`--gt-rule-spanner`)      |
| `tikz_scale`         | `1.0`                | TikZ               | `scale=` on the matrix nodes — **not** the whole picture        |
| `tikz_column_sep`    | `1.0`                | TikZ               | column gap, em                                                 |
| `tikz_row_sep`       | `0.25`               | TikZ               | row gap, em                                                    |
| `tikz_container_env` | `'table'`            | TikZ               | `table` / `figure` / `sidewaysfigure`                          |
| `tikz_latex`         | `None`               | TikZ               | float placement, e.g. `'ht'`                                   |
| `tikz_post_process`  | `''`                 | TikZ               | TeX injected into the environment                              |

Weight scale: `0` don't draw · `0.25` ultra thin · `0.5` very thin · `0.75`
thin · `1` semithick · `1.5` thick · `2` very thick · `3` ultra thick.

So the honest summary is: **four fields are portable, one is text-only, the
other thirteen are TikZ.** HTML's equivalents are CSS custom properties, and it
has four more with no `HouseStyle` counterpart at all — `--gt-pad-v`,
`--gt-pad-h`, `--gt-neg-color`, `--gt-caption-align`.

`tikz_scale` deserves its footnote. It rides on the matrix *nodes*, so node
contents scale and the matrix column separations do not — a table at
`scale=0.5` is about 0.60 of its full width, not half. Measured, the emitted
width is exactly

```
width(s) = s · (sum of column widths + 2 × tikz_column_sep) + ncols × tikz_column_sep + ~0.7em
```

which is the model `max_table_width_em` uses to pick an autoscale step. The
`~0.7em` is the rules overhanging the matrix bounding box; it is flat in both
column count and table width.

### Vertical rules

There are only two kinds of vertical in a GT2 table, and GT2 never draws a
grid line between every column.

**1. The stub/body divider.** Always present when there is a stub — the `│` in
text, `gt-stub-end` in HTML, `stub_rule` in TikZ. Not depth-driven, no on/off
switch beyond setting its weight to `0` (TikZ) or `--gt-rule-stub: none`
(HTML).

**2. Column-group verticals** — the `max_vrule_depth` family. Same two-part
split as the horizontals:

```python
GT(df, style=HouseStyle(max_vrule_depth=0))     # outermost group boundaries only
GT(df, style=HouseStyle(max_vrule_depth=None))  # none at all
```

weight from `vrule_widths` (TikZ) or `--gt-vrule-0/1` (HTML). Those got their
own properties in a3 precisely so you can do this:

```html
<style>.gt { --gt-vrule-0: none; --gt-vrule-1: none; }</style>
```

— verticals off, row rules untouched. Before a3 they shared `--gt-rule-0/1`,
so you could not have one without the other.

**The constraint worth knowing:** these need a **MultiIndex on the columns**.
The engine reports a boundary only at depth ≤ `n_levels − 2`, so a flat column
header produces no verticals whatever you set `max_vrule_depth` to. That is
the asymmetry with rows — `max_rule_depth=0` on a single-level index rules
every changed row, but there is no vertical equivalent, because the filter
sits in the engine rather than the render policy. And only two slots exist, so
a third-level group boundary reuses the lighter weight.

**Text has no group verticals at all** — only the stub divider. If you are
using `render_text` as the check, verticals are the one thing it will not show
you.

## `GT.__init__` arguments that were not `Configurator` fields

| 5.x argument | Default | What it did | GT2 home | Notes |
|---|---|---|---|---|
| `df` | — | DataFrame, Series, list of lists, markdown table string, or namedtuple | `build(data, spec)` / `GT(data)` | Same inputs except namedtuple, which is gone. Markdown ingest still parses the caption, `{#tbl-id}` label, and `:---`/`---:` alignment. |
| `caption` | `''` | Table caption | **TableSpec** `.caption` | 5.x also picked up a `df.gt_caption` attribute if the argument was empty; that magic is gone — pass the caption. |
| `label` | `''` | Quarto cross-reference id | **TableSpec** `.label` | Emits `id=` on the wrapper; no element ids at all when unset. |
| `aligners` | `None` | dict col → `'l'/'r'/'c'`, or a positional string | **TableSpec** `.aligners` | Same two shapes. |
| `formatters` | `None` | dict col → callable, `'{x:...}'` string, or int digits | **TableSpec** `.formatters` | Same name, now a real spec field rather than a shim. Also takes csv-grid sugar (`',.1f'`), a `FormatSpec`, and a mapping of its fields (the YAML form). ⚠️ **A bare int now groups**: `{'paid': 2}` gives `1,234.57` where 5.x gave `1234.57` — write `'.2f'` for the old result. |
| `tabs` | `None` | Column widths in characters or ems | **gone** | Width machinery deleted; see the width block below. The `Configurator` field was already commented out in 5.3. |
| `unbreakable` | `None` | Columns that must not wrap | **TableSpec** `.unbreakable` | Sets `wrap=False` → `gt-nowrap`. |
| `ratio_cols` | `None` | Columns to format as percentages | **TableSpec** `.ratio_cols` | All four `*_cols` selectors take a list, `'all'`, or a regex, as before. |
| `year_cols` | `None` | Integer years — no thousands separator | **TableSpec** `.year_cols` | Also forces center alignment. |
| `date_cols` | `None` | Force date treatment | **TableSpec** `.date_cols` | |
| `raw_cols` | `None` | Pass through unformatted | **TableSpec** `.raw_cols` | Distinct from `include_raw`, which is about shipping machine values to a client. |
| `show_index` | `True` | Show the index as stub columns | **TableSpec** `.show_index` | ⚠️ **Default changed to `None`** = auto-hide a trivial unnamed `RangeIndex`. Pass `True` to force it. |
| `config` | `None` | A `Configurator` instance | **gone** | GT2's equivalent object is `TableSpec`, passed directly to `build`. |
| `config_path` | `None` | YAML config file | **TableSpec** via `load_spec(path)` | Still a keyword on the `GT` facade. YAML is a flat mapping of `TableSpec` field names; unknown keys **raise** so typos surface. `config.write_template()` writes a commented starting point. |
| `**overrides` | — | Any `Configurator` field | facade only | Names matching a `TableSpec` field pass through; anything else **warns and is ignored**, so old call sites keep working while you clean them up. |

## `Configurator` fields

### Default formats

| 5.x option | Default | What it did | GT2 home | Notes |
|---|---|---|---|---|
| `default_integer_str` | `'{x:,d}'` | Format f-string for integers | **TableSpec** `.int_format` | The direct equivalent, and YAML-able. Unset, the built-in is `FormatSpec(kind='int', group=True)`. |
| `default_float_str` | `'{x:,.3f}'` | Format f-string for floats | **TableSpec** `.float_format` | The direct equivalent. Left unset, decimals come from each column's own magnitude — better for one table, inconsistent across a document, which is exactly what this field is for. Setting it also turns off the automatic SI/engineering switch. |
| `default_date_str` | `'%Y-%m-%d'` | strftime pattern for dates | **TableSpec** `.date_format` | Covers the date tag and both the date and datetime dtypes, so it also drops the time component from datetimes. ISO if unset. |
| `default_ratio_str` | `'{x:.1%}'` | Format for ratio columns | **TableSpec** `.ratio_format` | `ratio_cols` → `FormatSpec(kind='pct', digits=1)`, the same as 5.x; `ratio_format` changes every ratio column at once. |
| `default_formatter` | `None` | Fallback formatter f-string | **gone** | There is no single fallback across dtypes — the four named defaults above are per kind, which is what makes them predictable. |
| `table_float_format` | `None` | One float format for the whole table, overriding per-column | **TableSpec** `.table_float_format` | Same meaning and the same precedence: it beats an explicit `formatters` entry. Narrowed in one way — it reaches only **untagged float** columns, so `ratio_cols`/`year_cols`/`date_cols` are immune. Never written into a config template, on purpose. |

The resolution order per column is its **kind** (semantic tag if it has one,
else dtype), then within that kind: `formatters[col]` → the house default →
the built-in. Setting `float_format` turns float *inference* off entirely,
including the automatic SI/engineering switch.

### Rules and lines

All five became renderer opinions. Nothing about a rule weight enters the IR;
the *semantics* that drive them (`break_depth` per row and column, `total` row
flags) are computed by the engine and each renderer maps them to weights.

| 5.x option | Default | What it did | GT2 home | Notes |
|---|---|---|---|---|
| `table_hrule_width` | `1` | Top, bottom and header rules | **HouseStyle** `.frame_rule` / **CSS** `--gt-rule-frame` | |
| `table_hbaserule_width` | `1` | Rule under the header block | **HouseStyle** `.head_rule` / **CSS** `--gt-rule-head` | |
| `table_vrule_width` | `1` | Vertical rule between index and body | **HouseStyle** `.stub_rule` / **CSS** `--gt-rule-stub` | |
| `hrule_widths` | `(0, 0, 0)` | Three weights for MultiIndex row-group rules | **HouseStyle** `.hrule_widths` `(0.5, 0.25, 0.25)` / **CSS** `--gt-rule-0/1/2` | Now driven by row `break_depth` — the shallowest stub level that changed — instead of being drawn at every level unconditionally. |
| `vrule_widths` | `(0, 0, 0)` | Three weights for column-group verticals | **HouseStyle** `.vrule_widths` `(0.25, 0.25, 0.25)` / **CSS** `--gt-vrule-0/1` | Driven by column `break_depth`; `HouseStyle.max_vrule_depth` caps how deep, `None` turns them off. |

### Structure

| 5.x option | Default | What it did | GT2 home | Notes |
|---|---|---|---|---|
| `sparsify` | `True` | Merge repeated index values | **TableSpec** `.sparsify` | Unchanged, same default. Emits real `rowspan`s. |
| `sparsify_columns` | `True` | Merge repeated header prefixes | **TableSpec** `.sparsify_columns` | Unchanged. Emits `colspan`s plus a spanner rule under each group label. |
| `header_row` | `True` | For list input, promote row 0 to headers | **TableSpec** `.header_row` | ⚠️ **Default changed to `False`.** Pass `header_row=True` for list-of-lists input that carries a header row. |

### Spacing, fonts, caption

| 5.x option | Default | What it did | GT2 home | Notes |
|---|---|---|---|---|
| `spacing` | `'medium'` | Padding preset: tight / medium / wide | **CSS** `--gt-pad-v` `0.25em`, `--gt-pad-h` `0.6em` | The three presets are gone; set the two properties. |
| `padding_trbl` | `None` | Manual padding, four sides | **CSS** same two properties | Reduced to vertical/horizontal — per-side padding on a table cell was never worth the API. |
| `font_body` | `0.9` | Body font size (em) | **gone** | The fragment now inherits the host page's font entirely — no size opinion at all, which is what stopped it fighting JupyterLab and Quarto. Set `.gt { font-size: 0.9em }` yourself if you want the 5.x look. |
| `font_head` | `1.0` | Header font size (em) | **gone** | Headers are `font-weight: 600`, size inherited. |
| `font_caption` | `1.1` | Caption font size (em) | **gone** | Caption is `font-weight: 600`, size inherited. |
| `font_bold_index` | `False` | Bold the index columns | **gone** | Style `.gt .gt-stub` yourself. |
| `caption_align` | `'center'` | Caption alignment | **CSS** `--gt-caption-align` | ⚠️ **Default changed to `left`.** |
| `tex_to_html` | `None` | Hook mapping non-math TeX/markdown to HTML | **gone** | Math is auto-detected (`math='auto'`) and each renderer draws it — MathJax/KaTeX in HTML, native in TikZ. For genuine HTML in a cell, use `TableSpec.html_cols`. |

### Engineering format

| 5.x option | Default | What it did | GT2 home | Notes |
|---|---|---|---|---|
| `pef_precision` | `3` | Digits after the decimal in engineering format | **TableSpec** `.eng_digits` | Plus `eng_style` (`'si'` suffixes or `'exp'` aligned exponents), which 5.x had no way to choose. |
| `pef_lower` | `-3` | Use engineering format below `10**pef_lower` | **TableSpec** `.pef_lower` | Unchanged, same default. Now a **column-level** decision (the column's mean magnitude), not per cell. |
| `pef_upper` | `6` | Use engineering format above `10**pef_upper` | **TableSpec** `.pef_upper` | Unchanged, same default. Default display is SI suffixes (µ m k M G T…); aligned `e+00` exponents are the `'eng'` sugar opt-in. |

### Ingest and limits

| 5.x option | Default | What it did | GT2 home | Notes |
|---|---|---|---|---|
| `cast_to_floats` | `True` | Cast non-int, non-date columns to float where possible | **gone** | The engine trusts the dtypes it is given — 5.3 had already backed away from this for PyArrow. |
| `max_str_length` | `-1` | Truncate stringified objects | **gone** | No truncation: cutting content out of a display table is the wrong trade. Long prose wraps at `max_prose_width_em` / `--gt-prose-max` (18em). |
| `large_ok` | `False` | Allow rendering tables over the limit | **gone** | Replaced by `TableSpec.max_rows`. |
| `large_warning` | `50` | **Raise** above this many rows | **TableSpec** `.max_rows` (default `200`) | ⚠️ It no longer raises: it truncates and appends a note saying so. `max_rows=None` for unlimited. |
| `debug` | `False` | Extra reporting; internal id in the caption | **gone** | `doc.hash` is a stable 12-hex content id, also emitted as `data-gt-hash` on the wrapper. Logging is standard `logging`. |

### Width machinery — rebuilt, smaller

5.x negotiated column widths in Python for every backend. GT2 does not, and
the division of labor is the point: **TikZ estimates**, because TeX has no
browser to ask; **HTML states a limit and lets the browser measure**, because
it measures the real font and we can only guess at it; the **JS walker** can
run a canvas-measured solver for a constrained container.

`max_table_width_em` is the heir to `max_table_inch_width`, in ems rather than
inches — every other geometry field is ems, and inches mean nothing without a
font size. **It is a target, not a guarantee.** Columns that cannot wrap —
numbers, dates, anything tagged or listed in `TableSpec.unbreakable` — keep
their natural width whatever the budget says. What the budget narrows is the
prose, and:

- **TikZ** allocates with one shared quantile, so every prose column carries
  the same chance of wrapping, then distributes the remainder proportionally
  so the budget is met rather than merely respected. If even the floors do not
  fit, `tikz_scale` steps down a coarse ladder (1.0, 0.95 … 0.6) and says so
  through `logging`; past 0.6 it warns and suggests `sidewaysfigure` instead
  of shrinking into illegibility. A prose column is never narrowed past its
  widest single word — TeX will not hyphenate inside one.
- **HTML** emits `--gt-max-width` and stops there. `gt-nowrap` already pins
  the columns that must not be narrowed, so the browser narrows exactly the
  prose ones. No solver runs on that path and none should.

One caveat with teeth: the TikZ estimate is **Times metrics**, exact against
`newtxtext` (what `Etcher` compiles with) and about 11% tight against Latin
Modern, the LaTeX default a plain Quarto PDF uses — where a long heading may
hyphenate. Load a Times-metric serif alongside the tables, or expect slightly
tight columns. Use `newtxtext` alone; `newtxmath` collides with Quarto's math
setup.

| 5.x option | Default | What it did | GT2 home | Notes |
|---|---|---|---|---|
| `equal` | `False` | Force equal column widths | **gone** | |
| `max_table_inch_width` | `8.0` | Target table width in inches | **HouseStyle** `.max_table_width_em` | Ems, not inches: at 11pt, 8in is about 52em. Advisory — see above. |
| `table_width_mode` | `'explicit'` | explicit / natural / breakable / minimum | **partly** `.max_table_width_em` | "natural" is the default (no budget) and the browser's `table-layout: auto`; "explicit" is a budget; `renderTable(doc, {fit})` is the measured client-side case. No mode switch survives — you set a number or you don't. |
| `table_width_header_adjust` | `0.1` | Share of width given to headers | **gone** | Headers no longer compete for width: a heading floors its column at its widest *word* and wraps, so there is nothing to apportion. |
| `table_width_header_relax` | `10.0` | Extra characters allowed per heading | **gone** | Same reason. |
| `table_font_pt_size` | `11` | Point size, used for width estimation | **Etcher** `font_size=11` | Survives only where it is real: the standalone LaTeX document Etcher compiles. |
| `header_alignment` | `'few'` | few / center | **gone** | Was marked `NYI!! TODO` in 5.3 and never implemented. Header cells follow their column's alignment. |

### TikZ

| 5.x option | Default | What it did | GT2 home | Notes |
|---|---|---|---|---|
| `tikz` | `True` | Compute TikZ output at all | **gone** | Every rendering is a lazily cached property, so the HTML path never pays for TeX. This option existed to work around that; the waste is gone by construction. |
| `tikz_scale` | `1.0` | Scale factor | **HouseStyle** `.tikz_scale` | |
| `tikz_column_sep` | `1` | Column separation | **HouseStyle** `.tikz_column_sep` | em units. |
| `tikz_row_sep` | `0.25` | Row separation | **HouseStyle** `.tikz_row_sep` | em units. |
| `tikz_container_env` | `'table'` | table / figure / sidewaysfigure | **HouseStyle** `.tikz_container_env` | |
| `tikz_latex` | `None` | Placement args for `\begin{table}[…]` | **HouseStyle** `.tikz_latex` | |
| `tikz_post_process` | `''` | Extra commands at the bottom of the picture | **HouseStyle** `.tikz_post_process` | |
| `tikz_hrule` | `None` | Explicit list of row indices to rule | **gone** | Rules follow row `break_depth` and the `total` flag. If you were hand-placing a rule above a total row, use `row_flags={-1: ['total']}` and it is drawn everywhere, in every renderer. |
| `tikz_vrule` | `None` | Explicit list of column indices to rule | **gone** | Follows column `break_depth`. |
| `tikz_escape_tex` | `True` | Escape `%`, `_`, `\` outside math | **gone** | Cells carry plain unicode in the IR and **each renderer escapes for its own target**; math rides in a separate `math` flag. Escaping is no longer a user decision. |

## New in 6.0 — no 5.x equivalent

| Option | What it does |
|---|---|
| `TableSpec.notes` | Footnotes under the table, in every renderer. |
| `TableSpec.html_cols` | Columns whose cells carry raw HTML (renderers still gate on their own allow-html). |
| `TableSpec.row_flags` | Mark rows `total` / `subtotal` / `emphasis` / `muted`, by position or a callable. Semantic — this is what deleted aggregate_api's BeautifulSoup post-pass. |
| `TableSpec.cell_flags` | Same per cell. The `neg` flag is stamped automatically. |
| `TableSpec.math` | `'auto'` detects `$…$` string cells as math; `'off'` disables. |
| `TableSpec.include_raw` | Ship machine values alongside formatted text, for clients. Data columns only. |
| `HouseStyle.max_rule_depth` | How deep the hierarchy is ruled. `'auto'` (default) rules every break except the innermost stub level — no rules on a single-level index, depth 0 only on two levels, depths 0 and 1 on three. An int is literal, so `0` on a single-level index rules every row whose stub changed; `None` draws no internal rules. `max_vrule_depth` is the same for column-group verticals. The walker takes the same values as `opts.maxRuleDepth`. |
| `HouseStyle.total_rule`, `.spanner_rule` | Weights for the rule above a total row and under a column-group label. |
| `HouseStyle.max_prose_width_em` | How wide one wrapping column may get (18em). TikZ reads it; HTML emits it as `--gt-prose-max`. |
| `HouseStyle.max_table_width_em` | Total table width to aim for — advisory, since unbreakable columns hold their natural width. TikZ narrows prose then autoscales; HTML hands it to the browser as `--gt-max-width`. |
| `HouseStyle.text_ascii_rules` | Draw the text rendering without box-drawing characters, for LaTeX verbatim blocks and legacy consoles. |
| `g` format sugar | `'.3g'` and `'{x:.3g}'`, where `digits` counts significant figures rather than decimal places. |
| Target-aware display bundle | A Quarto PDF render gets TikZ, everything else gets HTML, and `text/plain` always rides along so a table never silently vanishes. `GT(..., mimes=...)` pins it for a target GT cannot detect. See {ref}`quickstart:notebooks and quarto`. |
| `build(df, spec) → TableDoc` | A document you can hash, cache, store, and send over HTTP. See {doc}`ir`. |

## Porting recipes

**The common call is unchanged.**

```python
from greater_tables import GT
GT(df, caption='Exhibit 1', ratio_cols=['lr'], year_cols='year')
```

**A table that used to raise on 50 rows** now truncates at 200 with a note:

```python
GT(df, max_rows=None)          # or any int
```

**Rule weights** are no longer per table. For TikZ:

```python
from greater_tables import build, render_tikz, HouseStyle, TableSpec
render_tikz(build(df, TableSpec()), style=HouseStyle(hrule_widths=(1, 0.5, 0)))
```

For HTML, set the properties once for the document:

```css
.gt { --gt-rule-0: 1pt solid; --gt-pad-v: 0.15em; --gt-caption-align: center; }
```

**Checking a port** — the text renderer strips styling and shows only
decisions, which makes it the fastest diff between the two engines:

```python
print(GT(df, caption='Check'))
```

`dev/tools/compare_gt5.py` in the repository does this side by side, running
5.3 in an isolated interpreter (both generations share the import name, so
they cannot coexist in one process) and writing an HTML comparison sheet.
