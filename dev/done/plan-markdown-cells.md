# [markdown-cells] Inline markdown in table cells: `*em*`, `**strong**`, `` `code` ``

Status: drafted 2026-10-21 at 7.0.0, at Steve's request, with every design question ruled.
Revised 2026-10-21 at 7.6.2 after review: six fixes (see **Review fixes**). The revision accounts
for what landed since the draft: per-face glyph widths (7.2.0), boxed number cells (7.3.0) and
heading balance (7.6.0). It runs after `dev/plan-retire-matrix.md`, so it ports markdown to one
TikZ engine, the tabular.

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

`engine/build.py` `_from_markdown` parses the pipe table into a DataFrame of strings. Along the
way it takes a caption, a `{#tbl-...}` label and the alignment row. It also strips stars from the
ends of each header cell. **The strip is broader than a bold wrapper:** the regex
`^\*\*?|\*\*?$` removes one *or* two stars at either end.

- `**Total**` becomes `Total`, as intended, since headers are bold already.
- `*Note*` becomes `Note`, losing the italic.
- `Revenue*` becomes `Revenue`, losing a footnote marker.

After that the cells are plain strings, and nothing remembers they were markdown. Observed at
7.0.0 for the table above plus a math cell:

```
tex:   *alpha*  & uses `col\_name` & 1.25 \\
       **beta** & p*q and 0.23**   &  2.5 \\
html:  *alpha*      uses `col_name`
text:  *alpha*   uses `col_name`
```

All three renderers print the markers literally. TeX is worse than literal: it sets each backtick
as an opening quote, so `` `col_name` `` comes out as ‘col_name‘. Math already works, through the
shared rule in `mathspans.py`. Every renderer, the width estimator and the JavaScript walker
(`js/src/gt-render.js`) apply it identically.

Two neighbors this plan must respect:

- **`TableSpec.html_cols`** is the precedent for markup in cells. It is a column selector that
  sets `Cell.html`, which HTML passes through and TeX strips to text.
- **A pipe table's columns are all strings.** The Value column above is dtype `string`, wraps,
  is never formatted, and so is not boxed by 7.3.0's number box. That is out of scope here, but
  it means a bolded total such as `**3.75**` is an ordinary markdown cell.

## The change

### Rulings (Steve, 2026-10-21)

- **No guessing from content.** Markdown comes only from a markdown string input. A DataFrame's
  index labels, column labels and cells may or may not hold markdown. A significance star
  (`0.23**`), a footnote marker (`Revenue*`) or a product (`a*b*c`) cannot be told from markup by
  looking, so a DataFrame needs an explicit argument.
- **`markdown_cols`**, a `TableSpec` column selector parallel to `html_cols`. A markdown string
  input defaults it to every column; a DataFrame defaults it to none.
- **A selected column's header is markdown too.** `markdown_cols` marks a column's body cells and
  its leaf header cell, and an index level's stub cells and stub header.
- **The caption follows the same rule.** A markdown string input's caption (its `Table:` line) is
  markdown. Any other caption is markdown only when the caller says so, with
  `markdown_caption=True`.
- **The text renderer shows markdown as typed.** Markdown is plain text already, and the box
  drawing reads fine around it.

### Review fixes (2026-10-21, at 7.6.2)

1. **Header stars.** The strip narrows to a complete `**...**` wrapper. Everything else in a
   header goes through the rule: `*Note*` sets bold italic, and `Revenue*` keeps its star.
2. **Bold width.** `_BOLD_PERCENT` went in 7.2.0. A strong run is measured in the face's bold
   table.
3. **Code width.** The code font is not the table face that `tikz_font` names. It is the
   document's monospace font, so code runs take a fixed `_MONO_MILLI = 610` per character.
4. **Heading balance.** 7.6.0's heading balance builds its word list from the raw heading text,
   markers included. It goes through the same marker-free measurement.
5. **`html_cols`.** A markdown string's default of every column excludes the `html_cols`, and only
   an explicit overlap raises.
6. **Acceptance.** It gains the per-face compile test, its baseline is the version before this
   plan, and its code-width check covers both preambles.

### [rule] One inline-markdown rule, in a new `markdownspans.py`

A sibling of `mathspans.py`, built on it. One function, `runs(text, math=True)`, splits a cell's
text into a flat list of runs, each `(kind, style, text)`:

- `kind` is one of `text`, `math` or `code`;
- `style` is one of None, `em` or `strong`.

A flat list rather than a tree keeps every consumer a simple loop, the JavaScript port included.

The rule is stricter than CommonMark, for the reason the math rule is stricter than TeX: a table
is full of asterisks that are not markup.

1. **Code spans first.** A single backtick, non-empty content with no backtick, and a single
   backtick. The content is literal: no math, no emphasis. So `` `$x$` `` stays code.
2. **Math next**, by `mathspans.segments`, unchanged. A star inside math (`$a*b$`) is math.
3. **`**strong**`, then `*em*`**, over what remains. Code and math runs are atoms that may sit
   inside an emphasis: `*see $x$*` is an italic run around a math run.
4. **Word boundaries.**
   - An opening marker must start a word: preceded by the start, whitespace or opening
     punctuation, and followed by a non-space.
   - A closing marker must end a word: preceded by a non-space, and followed by the end,
     whitespace or punctuation.
   - No emphasis inside a word. CommonMark sets `a*b*c` as a<em>b</em>c; this rule leaves it
     alone, and leaves `0.23**`, `Revenue*` and `2 * 3 * 4` alone too.
5. **`\*` and `` \` ``** are literal characters and never delimit, as `\$` is for math.
6. **Not supported:**
   - `_` emphasis, which collides with `col_name` and `x_1`;
   - nesting: `***x***` comes out bold with literal stars inside;
   - links;
   - multi-backtick code spans.

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

- **`spec.py`:**
  - `markdown_cols: ColSelector = None`, documented beside `html_cols`;
  - `markdown_caption: bool | None = None`, where None means "markdown when the input is a
    markdown string".
- **`ir.py`:** `markdown: bool = False` on `Cell` and `HeadCell`.
  - The field is additive and canonical JSON omits defaults, so `ir_version` stays 1 and no
    existing golden changes.
  - `schema/ir-v1.json` is regenerated, as 7.4.0 did for `FormatSpec.upper`.
- **`engine/build.py`:**
  - **Defaults.** `_from_markdown` fills the two fields when the caller left them None, the way it
    already fills caption, label and aligners:
    - `markdown_cols` becomes every column *except* those in `html_cols`;
    - `markdown_caption` becomes `True`.

    An explicit `markdown_cols=[]` or `markdown_caption=False` turns either off.
  - **Header stars.** The header strip narrows to a complete `**...**` wrapper:
    `^\*\*(.+)\*\*$` becomes `\1`, and anything else is left for the rule.
  - **Caption.** A markdown caption is emitted as `Cell(text=..., markdown=True)`.
    `TableDoc.caption` already accepts a `Cell`, so the IR needs no caption field. Notes stay
    plain strings: the only note a markdown string produces is the engine's own truncation note.
  - **Marking.**
    - A selected column marks its body cells and its leaf header cell.
    - A selected index level, selected by its name, marks its stub cells and its stub header.
    - Upper column-group header levels are never marked.
    - A markdown string has one header level and no index, so for that route this means every
      cell outside `html_cols`.
  - **Overlap.** A column the caller names in both `html_cols` and `markdown_cols` raises
    `ValueError` at build.

### [renderers] TeX, HTML, CSS, widths

| Run | TeX | HTML | text |
|---|---|---|---|
| em | `\emph{...}` | `<em>...</em>` | as typed |
| strong | `\textbf{...}` | `<strong>...</strong>` | as typed |
| code | `\texttt{...}`, every TeX special escaped | `<code>...</code>`, escaped | as typed |

- **Captions.** `render/tikz_tabular.py` (`\caption`, through `cell_tex`), `render/html.py`
  (`<caption>`, already routed through `_cell_content`) and the walker's caption path apply the
  same mapping to a markdown caption `Cell`.
- **`render/tikz_layout.py` `cell_tex`:**
  - A markdown cell goes through `runs`, each run escaped by the existing `_escape_run`.
    `_TEX_SPECIALS` covers `\`, `&`, `%`, `$`, `#`, `_`, `{`, `}`, `~` and `^`.
  - A total row's `\bfseries` around an `\emph` gives bold italic, which is right.
  - In a column that does not wrap, the cell sits inside 7.3.0's `\makebox` like any other; the
    box holds formatted text and is indifferent to what is inside.
- **`render/html.py` `_cell_content`:**
  - A markdown cell emits tags around escaped text.
  - The tags come from the parse, never from the input, so markdown is injection-safe by
    construction and needs no `allow_html` gate. This matters because the walker's `allowHtml`
    defaults off.
- **`render/css.py`:** a `.gt.gt code` rule resetting color, background and padding to inherit.
  Quarto themes (cosmo included) color and shade `code`, and a greater_tables table carries no
  color.
- **Widths, in `render/tikz_layout.py` (`_measured`, `_display_milli`, `_token_milli`):** a
  markdown cell is measured as it sets, markers removed, in `style.tikz_font`.
  - **Strong runs** use the face's bold table, `display_milli(..., bold=True)`.
  - **Em runs** use the roman table. Italic is narrower than roman in all five faces, measured
    2026-10-21 over the alphabet and digits: Times 0.964, STIX Two 0.969, Latin Modern 0.978,
    Lato 0.944, Fira Sans 0.993.
  - **Code runs** use `_MONO_MILLI = 610` per character. Measured `\texttt` advances: Etcher's
    newtx preamble 0.525em, Latin Modern Mono 0.525em, house style's DejaVu Sans Mono 0.602em.
    One constant, rounded up from the widest, never runs short and leaves a narrower code font
    up to 16% slack. A per-face mono table would be the wrong key, since `tikz_font` names the
    text face, not the code face.
- **Heading balance, in `render/tikz_layout.py`:** the word list built in `layout()` for
  `_balance_headings` comes from the same measurement, markers removed and code at
  `_MONO_MILLI`. Today it splits the raw `hc.text`, so a marked-up heading would count its
  markers.
- **`render/text.py`:** no change.

### [walker] The JavaScript port

`js/src/gt-render.js` renders cells from the IR with its own copy of the math regex, kept in step
with Python by the DOM-transcript conformance goldens.

- `runs` is ported beside `mathSegments`.
- `fillCell` gains a markdown branch that builds `em`, `strong` and `code` elements.

Without the port, the aggregate Loss Lab, which uses the walker, would show asterisks that the
Python HTML does not. The walker builds its tables in the browser, after Quarto has run, so
7.6.1's Quarto opt-out does not concern it.

### [tests]

- **`tests/test_markdown_spans.py`:** the table of cases above, plus the same cases through each
  renderer's escape step.
- **`tests/registry.py`:**
  - The existing `markdown` fixture gains a row with em, strong, code and a math cell, and a
    header `*Note*` beside one ending in a footnote star.
  - A new `markdown-df` fixture is a DataFrame with `markdown_cols` on one text column and a
    significance-star column left unselected.
  - Goldens are re-blessed with `tests/make_goldens.py` for every renderer, the transcript
    included.
- **`tests/test_tikz_geometry.py`:**
  - Both markdown fixtures join `FACE_TABLES`, so `test_text_holds_in_its_face` compiles them in
    all five faces and checks that nothing hyphenates or wraps. That is the width check for
    bold, italic and code in every face.
  - A second compile sets the code fixture with house style's `\setmonofont{DejaVuSansMono.ttf}`.
- **Compile smoke tests:** the one in `tests/test_tikz_tabular.py` runs over every fixture, so
  the new ones compile without further code.

## Files

| File | Step | Change |
|---|---|---|
| `src/greater_tables/markdownspans.py` | [rule] | new |
| `src/greater_tables/spec.py`, `ir.py`, `engine/build.py`, `schema/ir-v1.json` | [engine] | field, flag, build, header strip, schema |
| `src/greater_tables/render/tikz_layout.py` | [renderers] | `cell_tex`, measurement, heading word list, `_MONO_MILLI` |
| `src/greater_tables/render/tikz_tabular.py`, `html.py`, `css.py` | [renderers] | emit |
| `js/src/gt-render.js`, `src/greater_tables/assets/gt-render.*.js` | [walker] | port, rebuilt with `npm run build` |
| `tests/test_markdown_spans.py`, `tests/registry.py`, `tests/test_tikz_geometry.py`, `tests/golden/*` | [tests] | new and re-blessed |
| `CHANGELOG.md`, `src/greater_tables/_version.py` | all | one minor bump for the plan |

## Version and output

One minor bump, assigned when the plan executes. Rendered output changes in two places:

- markdown string input whose cells hold `*`, `**` or a backtick, where the literal markers were
  the defect;
- markdown string headers carrying a star other than a full `**...**` wrapper, which now keep it
  or set it as emphasis.

The CHANGELOG says so, since a rebuilt document changes.

## Acceptance

- The Goal's example renders italic, bold and code in HTML, in TeX, and as typed in text. A
  `Table: *x*` caption on it renders italic in HTML and TeX.
- A markdown header `*Note*` sets bold italic and `Revenue*` keeps its star.
- A DataFrame with `caption='*x*'` and no `markdown_caption` keeps its literal stars.
- A markdown string with `html_cols=['Note']` builds, Note as html and the rest as markdown;
  `markdown_cols=['Note'], html_cols=['Note']` raises.
- Every case in the [rule] table holds in Python and in the walker (conformance goldens).
- A DataFrame with no `markdown_cols` renders byte-identically to the version before this plan:
  every pre-existing golden passes unchanged except `markdown`.
- **Code width:** a code column's TikZ estimate is never narrower than its compiled width,
  checked in Etcher's preamble and with DejaVu Sans Mono, and at most 20% wider.
- `test_text_holds_in_its_face` passes with the markdown fixtures in all five faces.

## Execution log

- 2026-10-21: drafted at 7.0.0; header and caption questions ruled the same day.
- 2026-10-21: reviewed at 7.6.2; the six review fixes folded in, and the plan reordered after
  `dev/plan-retire-matrix.md`.
- 2026-10-22: reviewed again at 8.0.0 and executed as **8.1.0**, one commit for the one bump the
  plan assigns. Divergences:
  - **Flag only where it matters.** A selected cell, header or caption carries `markdown=True`
    only when its text holds a star or a backtick (`_has_markers` in `build.py`). Text without
    either splits into one plain run and sets exactly as unmarked text, so the flag would change
    nothing but the IR's size, and plain cells keep the bare-string shorthand.
  - **Python and JavaScript read alike.** The closing boundary is a negative lookahead and both
    sides use dotall: Python's `$` also matches before a final newline and JavaScript's does not,
    and the two dots exclude different line ends. Code and math atoms stand in as private-use
    characters while emphasis is parsed; text already holding one sets without emphasis.
  - **Walker checks.** `markdownRuns` is exported from `gt-render.js`, and
    `js/markdown-check.mjs` lets `test_markdown_spans.py` compare every rule case, plus edge
    cases, with math on and off. The DOM transcript gains an `inline` field, `[tag, text]` per
    em, strong or code element, written only when a cell has one, so existing transcripts are
    unchanged and the goldens tell em from strong. `GT_RENDER_VERSION` goes from 7.0.0 to 8.1.0.
  - **CSS.** `.gt.gt code` sets `padding: 0` and `background: transparent` rather than
    `inherit`, which would pull in the cell's own padding. Inline CSS mode (`inline_css=True`)
    does not style `code`: the styler resolves only the selectors on `td` and `th`.
  - **Compile smoke test.** The plan said the one in `test_tikz_tabular.py` runs over every
    fixture; it runs over a named list, which now includes both markdown fixtures.
  - **Heading balance.** A markdown heading's words come from `_markdown_words`; a heading with
    `$` stays out of the balance, as it does unmarked.
  - **Fixtures.** The `markdown` fixture keeps its plain caption, which `test_engine.py` pins;
    the `Table: *x*` caption is tested in `test_markdown_spans.py`. Its alignment assertion
    widened to the two new columns.
  - **Code width, measured.** Etcher's newtx preamble sets code in Latin Modern Mono, 0.525em;
    DejaVu Sans Mono is 0.602em. House style loads DejaVu with `Scale=MatchLowercase`, which
    against STIX Two only narrows it, so the 0.61em estimate stays on the safe side there too.
  - **Docs.** Not in the plan's Files: the quickstart's selector paragraph names
    `markdown_cols`, the gallery describes the markdown fixture and shows `markdown-df`, and the
    config template carries hints for the two new fields.
- Acceptance, 2026-10-22: the Goal's example, the `Table: *x*` caption, the header stars, the
  literal DataFrame caption and the `html_cols` overlap are tests in `test_markdown_spans.py`;
  every rule case holds in Python and in the walker; `tests/make_goldens.py` changed only the
  `markdown` goldens and added `markdown-df`'s, so every other golden is byte-identical to 8.0.0;
  `test_code_width_holds` passes in both preambles; `test_text_holds_in_its_face` passes with both
  markdown fixtures in all five faces; `uv run pytest` 973 passed, 10 skipped; the gallery
  rendered in all four formats with no TeX errors.
