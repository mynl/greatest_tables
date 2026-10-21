# Cheat sheet

`GT` call signature:

```python
GT(df,                                   # the data
   caption=..., ratio_cols=..., ...,     # TableSpec fields: WHAT is printed
   style=HouseStyle(...),                # HouseStyle fields: HOW it is printed
   config_path=..., mimes=...)           # GT's own: where defaults come from, what Jupyter publishes
```

## Arguments

**`TableSpec` — what is printed.** Column meaning, number formats, alignment,
totals. Each is a `GT` keyword, or a field of a `TableSpec` passed to `build`.
They travel in the document, so every renderer applies the same decision.

| Group | Fields |
|---|---|
| metadata | `caption`, `label`, `notes` |
| column meaning | `ratio_cols`, `year_cols`, `date_cols`, `raw_cols`, `html_cols`, `unbreakable` |
| column format | `formatters`, `float_format`, `int_format`, `ratio_format`, `date_format`, `table_float_format` |
| engineering notation | `pef_lower`, `pef_upper`, `eng_digits`, `eng_style` |
| alignment | `aligners` |
| rows | `row_flags`, `cell_flags`, `max_rows` |
| structure | `show_index`, `header_row`, `sparsify`, `sparsify_columns` |
| for clients | `include_raw` |

**`HouseStyle` — how it is printed.** Rulings, widths, TikZ geometry. Never a
bare keyword: always
`style=HouseStyle(...)`. Nothing here enters the document. For HTML, the rule
weights and the two widths also exist as CSS custom properties on `.gt`, and CSS
wins; the TikZ fields are TikZ only.

| Group | Fields |
|---|---|
| break line rules | `max_rule_depth`, `max_vrule_depth` |
| rule weights | `frame_rule`, `head_rule`, `stub_rule`, `total_rule`, `spanner_rule`, `hrule_widths`, `vrule_widths` |
| widths | `max_table_width_em`, `max_prose_width_em` |
| TikZ geometry and container | `tikz_engine`, `tikz_scale`, `tikz_column_sep`, `tikz_row_sep`, `tikz_container_env`, `tikz_latex`, `tikz_post_process` |
| text renderer | `text_ascii_rules` |

**`GT`'s own — neither.** Two keywords about the call, plus `style` above:

| Keyword | Does |
|---|---|
| `config_path` | load `TableSpec` defaults from a YAML file; explicit keywords override it |
| `mimes` | pin what `_repr_mimebundle_` publishes, for a target GT cannot detect (`gfm`) |

The test, when you cannot remember: **does it change the table, or how the table
is drawn?** A style field passed as a bare keyword warns (with the fix).
Anything else unknown warns and is ignored, which allows a 5.3 call to keep
working until it is cleaned up.

## The pipeline

```text
df ──build(df, spec)──► TableDoc ──render_html / render_tikz / render_text(doc, style)──► output
```

`GT(df, **spec_fields, style=...)` does both, lazily, and caches each rendering:

```python
gt = GT(df, caption='Exhibit 1', ratio_cols=['lr'], style=HouseStyle(max_table_width_em=41))
gt.doc      # the TableDoc: what the table is, hashable, JSON-serializable
gt.html     # fragment with its stylesheet
gt.tikz     # table environment + tikzpicture
gt.text     # monospace; also print(gt) and repr(gt)
gt          # in Jupyter or Quarto: the right bundle for the target
```

The document never specifies a width, a weight or a font; the renderers decide
those.

## GT70 vs GT53

| I want | 5.3 | 7.0 |
|--|--|--|
| a caption and a Quarto cross-reference | `GT(df, caption=, label=)` | the same |
| footnotes under the table | — | `notes=['Amounts in USD thousands.']` |
| hide or show the index | `show_index=False` | `show_index=False`. Default `None` hides a trivial unnamed `RangeIndex` and shows everything else |
| ratio columns as percent | `ratio_cols=['lr']` | the same, or a regex: `ratio_cols='lr\|ratio$'` |
| years without commas | `year_cols=['year']` | the same |
| two decimals on one column | `formatters={'paid': 2}` → `1234.57` | `formatters={'paid': 2}` → `1,234.57`. An int groups now. Write `'.2f'` for ungrouped |
| a format string on one column | `formatters={'x': '{x:.1%}'}` | the same, and the short form `',.1f'` works too |
| every float the same way | `default_float_str='{x:,.3f}'` | `float_format=',.3f'`. Turns float inference off, including the engineering switch |
| integers, ratios, dates work the same way | `default_integer_str`, `default_ratio_str`, `default_date_str` | `int_format`, `ratio_format`, `date_format` |
| quick look at everything at 6 dp | `table_float_format` | the same, and it still beats a `formatters` entry. Call site only, never a config file |
| alignment | `aligners='lrr'` | the same, or `aligners={'paid': 'r'}` |
| a column that must not wrap | `unbreakable=['id']` | the same |
| a total row | by hand, after the fact | `row_flags={-1: ['total']}`. Also `subtotal`, `emphasis`, `muted`, by position or callable |
| more than 50 rows without an error | `large_ok=True` | nothing: 7.0 truncates at 200 with a note. `max_rows=None` for everything |
| rules between row groups | `hrule_widths=(1, 0.5, 0)` | `style=HouseStyle(max_rule_depth='auto')` picks the depths; `hrule_widths` the weights. See below |
| verticals between column groups | `vrule_widths=(1, 0, 0)` | `style=HouseStyle(max_vrule_depth=1, vrule_widths=...)`. Needs a MultiIndex on the columns |
| the PDF table is too wide | `tikz_scale=0.8` | `style=HouseStyle(max_table_width_em=41, tikz_scale=0.9)`. Budget first, scale is a ceiling. See below |
| one prose column is too wide | `max_str_length=40` | `style=HouseStyle(max_prose_width_em=18)`. Wraps, never truncates |
| the slow TikZ engine, for node-addressed post-processing | — | `style=HouseStyle(tikz_engine='matrix')` |
| one set of house rules for a document | `config_path='house.yaml'` | the same, or `partial(GT, config_path='house.yaml')` |
| a `quarto render --to gfm` build | — | `GT(df, mimes=('text/plain',))`. The only target GT cannot detect |

Anything not here is on the complete map in {doc}`migration`.

## Rule depth, width budget, math

The three rows above that say "see below".

**Rule depth.** A row's *break depth* is the shallowest index level whose value changed. `'auto'`
rules every break except the innermost level, so a two-level index gets a rule where the outer
value changes and nothing else, and a flat index gets no internal rules at all. An int is literal:
`max_rule_depth=0` on a flat index rules every row whose stub changed. `None` draws none.
`max_vrule_depth` is the same idea for column groups.

**Width.** `max_table_width_em` is a target, not a guarantee, and it is `None` unless you set it:
a bare `GT(df)` in a PDF gets natural widths. With a budget, TikZ narrows the wrapping columns
first, all by the same quantile so each carries the same chance of wrapping, and columns that must
not wrap hold their width. Only when the floors alone exceed the budget does it step `tikz_scale`
down a fixed ladder and logs a warning. `tikz_scale` is the largest scale it may use,
not the size it will use. At 11pt, 455pt of text block is about 41em. HTML hands the number to the
browser as a CSS `max-width` and lets it measure.

**Math and dollars.** `$...$` is math anywhere text appears. Delimiters must be tight against
their content, a span may not contain another `$`, and a closing `$` may not be followed by a
digit, so `$10 to $20` is two prices and `$\psi(u)$` is math. Nothing to configure. Write `\$` for
a literal dollar next to a real span.

## Common idioms

Column selectors are regexes searched against the column name, so anchor one that could match
inside a longer name. Format sugar is lowercase and has no width field: `'.3e'`, not `'7.3E'`.

```python
from functools import partial
from greater_tables import GT, HouseStyle

# columns LR, CR, ER as 0.0% (ratio columns already default to one decimal)
GT(df, ratio_cols=r'^[LCE]R$', ratio_format='.1%')

# every untagged float column at ,.2f, beating any formatters entry
GT(df, table_float_format=',.2f')

# all floats in scientific notation, three decimals: 3.123e+10
GT(df, float_format='.3e')                  # uppercase E is not parsed; see pending

# all numbers to one significant figure: 1e+03, 0.002
GT(df, float_format='.1g', int_format='.1g')

# one named column through my own function; it owns NaN handling and
# does not reach the document, so a client cannot re-render that column
GT(df, formatters={'paid': my_format})

# overall width target, in ems; 41em is an A4 text block at 11pt
GT(df, style=HouseStyle(max_table_width_em=41))

# columns A and B never wrap
GT(df, unbreakable=['A', 'B'])

# width budget and a scale ceiling together: at most 0.9, less if it must
GT(df, style=HouseStyle(max_table_width_em=41, tikz_scale=0.9))

# rule weights by depth slot: 0 none, 0.25 ultra thin ... 1 semithick, 3 ultra thick
GT(df, style=HouseStyle(hrule_widths=(1, 0.5, 0.25), vrule_widths=(0.5, 0.25, 0.25)))

# a document-wide GT with its house rules baked in
house_GT = partial(GT, ratio_cols=r'^[LCE]R$', year_cols=r'^(year|ay)$',
                   style=HouseStyle(max_table_width_em=41, tikz_scale=0.9))
```

GT does not guess a column's meaning from its name. csv-viewer does (`year`, `id`, money and
percent words in the header), because it has only a header to go on; GT has the dtype and the
values, and a publication table wants the tag stated. The `partial` above is the way to state it
once.
