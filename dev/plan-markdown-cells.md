# [markdown-cells] Inline markdown in table cells: `*em*`, `**strong**`, `` `code` ``

Status: drafted 2026-10-21 at 7.0.0, at Steve's request. Every design question is ruled; ready to
execute.

## Goal

Steve's commonest route into greater_tables is a markdown pipe table typed into a Quarto or
writedown cell:

```python
GT("""
| Item     | Note              | Value |
|:---------|:------------------|------:|
| *alpha*  | uses `col_name`   |  1.25 |
| **beta** | the base case     |   2.5 |
""")
```

The cells are markdown, and every renderer should set them as such: italic, bold and code in HTML
and TeX alike. A DataFrame gets the same treatment only when the caller asks for it, column by
column.

## Current behavior

`engine/build.py` `_from_markdown` parses the pipe table into a DataFrame of strings, taking a
caption, a `{#tbl-...}` label and the alignment row along the way, and strips a `**` wrapper from
each header cell (headers are bold already). After that the cells are plain strings and nothing
remembers they were markdown. Observed at 7.0.0 for the table above plus a math cell:

```
tex:   *alpha*  & uses `col\_name` & 1.25 \\
       **beta** & p*q and 0.23**   &  2.5 \\
html:  *alpha*      uses `col_name`
text:  *alpha*   uses `col_name`
```

All three renderers print the markers literally. TeX is worse than literal: it sets each backtick
as an opening quote, so `` `col_name` `` comes out as ‘col_name‘. Math already works, through the
shared rule in `mathspans.py`, which every renderer, the width estimator and the JavaScript walker
(`js/src/gt-render.js`) apply identically.

The precedent for markup in cells is `TableSpec.html_cols`: a column selector that sets
`Cell.html`, which HTML passes through and TeX strips to text.

## The change

### Rulings (Steve, 2026-10-21)

- **No guessing from content.** Markdown comes only from a markdown string input. A DataFrame's
  index labels, column labels and cells may or may not hold markdown, and a significance star
  (`0.23**`), a footnote marker (`Revenue*`) or a product (`a*b*c`) cannot be told from markup by
  looking, so a DataFrame needs an explicit argument.
- **`markdown_cols`**, a `TableSpec` column selector parallel to `html_cols`. A markdown string
  input defaults it to every column; a DataFrame defaults it to none.
- **A selected column's header is markdown too.** `markdown_cols` marks a column's body cells and
  its leaf header cell, and an index level's stub cells and stub header.
- **The caption follows the same rule.** A markdown string input's caption (its `Table:` line) is
  markdown; any other caption is markdown only when the caller says so, with
  `markdown_caption=True`.
- **The text renderer shows markdown as typed.** Markdown is plain text already, and the box
  drawing reads fine around it.

### [rule] One inline-markdown rule, in a new `markdownspans.py`

A sibling of `mathspans.py`, built on it. One function, `runs(text, math=True)`, splits a cell's
text into a flat list of runs, each `(kind, style, text)` with `kind` one of `text`, `math`,
`code` and `style` one of None, `em`, `strong`. A flat list rather than a tree keeps every
consumer a simple loop, the JavaScript port included.

The rule is stricter than CommonMark, for the reason the math rule is stricter than TeX: a table
is full of asterisks that are not markup.

1. **Code spans first.** A single backtick, non-empty content with no backtick, a single
   backtick. The content is literal: no math, no emphasis. So `` `$x$` `` stays code.
2. **Math next**, by `mathspans.segments`, unchanged. A star inside math (`$a*b$`) is math.
3. **`**strong**`, then `*em*`**, over what remains, with code and math runs as atoms that may sit
   inside an emphasis (`*see $x$*` is an italic run around a math run).
4. **Word boundaries.** An opening marker must start a word (preceded by the start, whitespace or
   opening punctuation) and be followed by a non-space; a closing marker must end a word
   (preceded by a non-space, followed by the end, whitespace or punctuation). No emphasis inside a
   word. CommonMark sets `a*b*c` as a<em>b</em>c; this rule leaves it alone, and leaves
   `0.23**`, `Revenue*` and `2 * 3 * 4` alone too.
5. **`\*` and `` \` ``** are literal characters and never delimit, as `\$` is for math.
6. **Not supported:** `_` emphasis (it collides with `col_name` and `x_1`), nesting
   (`***x***` comes out bold with literal stars inside), links, and multi-backtick code spans.

Cases the tests pin, input on the left:

| Input | Runs |
|---|---|
| `*alpha*` | em `alpha` |
| `**Total**` | strong `Total` |
| `` uses `col_name` `` | text `uses `, code `col_name` |
| `` `$x$` `` | code `$x$` |
| `*see $x$*` | em text `see `, em math `x` |
| `$a*b*c$` | math `a*b*c` |
| `a*b*c`, `0.23**`, `Revenue*`, `2 * 3 * 4`, `*x` | text, unchanged |
| `\*x\*` | text `*x*` |

### [engine] Spec field, IR flag, build

- `spec.py`: `markdown_cols: ColSelector = None`, documented beside `html_cols`, and
  `markdown_caption: bool | None = None`, where None means "markdown when the input is a markdown
  string".
- `ir.py`: `markdown: bool = False` on `Cell` and `HeadCell`. The field is additive and canonical
  JSON omits defaults, so `ir_version` stays 1 and no existing golden changes. `schema/ir-v1.json`
  is regenerated.
- `engine/build.py`:
  - `_from_markdown` fills `markdown_cols='all'` and `markdown_caption=True` when the caller left
    them None, the way it already fills caption, label and aligners. An explicit
    `markdown_cols=[]` or `markdown_caption=False` turns either off.
  - A markdown caption is emitted as `Cell(text=..., markdown=True)`; `TableDoc.caption` already
    accepts a `Cell`, so the IR needs no caption field. Notes stay plain strings: the only note a
    markdown string produces is the engine's own truncation note.
  - A selected column marks its body cells and its leaf header cell; a selected index level
    (selected by its name) marks its stub cells and its stub header. Upper column-group header
    levels are never marked. A markdown string has one header level and no index, so for that
    route this means every cell.
  - A column in both `html_cols` and `markdown_cols` raises `ValueError` at build.
  - The `**` strip on markdown headers stays: a bold header needs no `\textbf`.

### [renderers] TeX, HTML, CSS, widths

| Run | TeX | HTML | text |
|---|---|---|---|
| em | `\emph{...}` | `<em>...</em>` | as typed |
| strong | `\textbf{...}` | `<strong>...</strong>` | as typed |
| code | `\texttt{...}`, every TeX special escaped | `<code>...</code>`, escaped | as typed |

- Captions: `render/tikz.py` and `render/tikz_tabular.py` (`\caption`), `render/html.py`
  (`<caption>`, already routed through `_cell_content`) and the walker's caption path apply the
  same mapping to a markdown caption `Cell`.
- `render/tikz_layout.py` `cell_tex`: a markdown cell goes through `runs`, each run escaped by the
  existing `_escape_run` (`_TEX_SPECIALS` covers `\`, `&`, `%`, `$`, `#`, `_`, `{`, `}`, `~`,
  `^`). A total row's `\bfseries` around a `\emph` gives bold italic, which is right.
- `render/html.py` `_cell_content`: a markdown cell emits tags around escaped text. The tags come
  from the parse, never from the input, so markdown is injection-safe by construction and needs no
  `allow_html` gate; this matters because the walker's `allowHtml` defaults off.
- `render/css.py`: a `.gt.gt code` rule resetting color, background and padding to inherit. Quarto
  themes (cosmo included) color and shade `code`, and a greater_tables table carries no color.
- `render/textlength.py` and `tikz_layout._measured`: a markdown cell is measured as it sets,
  markers removed, strong runs at `_BOLD_PERCENT`, code runs at one monospace advance per
  character. The monospace constant is measured against the `Etcher` preamble with
  `dev/tools/measure_glyphs.py`, as the roman table was. Without this a code column is sized as
  Times and wraps. If `dev/plan-font-metrics.md` lands first, the constant joins its per-face
  table.
- `render/text.py`: no change.

### [walker] The JavaScript port

`js/src/gt-render.js` renders cells from the IR with its own copy of the math regex, kept in step
with Python by the DOM-transcript conformance goldens. `runs` is ported beside `mathSegments`, and
`fillCell` gains a markdown branch that builds `em`, `strong` and `code` elements. Without the port
the aggregate Loss Lab, which uses the walker, would show asterisks that the Python HTML does not.

### [tests]

- `tests/test_markdown_spans.py`: the table of cases above, plus the same cases through each
  renderer's escape step.
- `tests/registry.py`: the existing `markdown` fixture gains a row with em, strong, code and a math
  cell; a new `markdown-df` fixture is a DataFrame with `markdown_cols` on one text column and a
  significance-star column left unselected. Goldens re-blessed with `tests/make_goldens.py` for
  every renderer, the transcript included.
- The compile smoke tests in `tests/test_tikz.py` and `tests/test_tikz_tabular.py` run over every
  fixture, so both engines compile the new ones without further code.

## Files

| File | Step | Change |
|---|---|---|
| `src/greater_tables/markdownspans.py` | [rule] | new |
| `src/greater_tables/spec.py`, `ir.py`, `engine/build.py`, `schema/ir-v1.json` | [engine] | field, flag, build, schema |
| `src/greater_tables/render/tikz_layout.py`, `tikz.py`, `tikz_tabular.py`, `html.py`, `css.py`, `textlength.py` | [renderers] | emit and measure |
| `js/src/gt-render.js` | [walker] | port |
| `tests/test_markdown_spans.py`, `tests/registry.py`, `tests/golden/*` | [tests] | new and re-blessed |
| `CHANGELOG.md`, `src/greater_tables/_version.py` | all | one minor bump for the plan |

## Version and output

One minor bump, assigned when the plan executes. Rendered output changes only for markdown string
input whose cells hold `*`, `**` or a backtick, where the literal markers were the defect; the
CHANGELOG says so anyway, since a rebuilt document changes.

## Acceptance

- The Goal's example renders italic, bold and code in HTML, in TeX through both TikZ engines, and
  as typed in text; a `Table: *x*` caption on it renders italic in HTML and TeX.
- A DataFrame with `caption='*x*'` and no `markdown_caption` keeps its literal stars.
- Every case in the [rule] table holds in Python and in the walker (conformance goldens).
- A DataFrame with no `markdown_cols` renders byte-identically to 7.0.0: every pre-existing golden
  passes unchanged except `markdown`.
- A code column's TikZ width estimate is within 1% of its compiled width in the `Etcher` preamble.

## Execution log

- 2026-10-21: drafted; header and caption questions ruled the same day.
