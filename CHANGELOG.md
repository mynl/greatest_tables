# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versioning is semantic.

## [7.1.4] - 2026-10-21

### Fixed

- A `sidewaystable` or `sidewaysfigure` container with no `tikz_latex` is placed `[p]`. Left bare
  it took the document's default placement, and where that is `H`, as in house style, rotating
  cannot place it and the table vanished from the PDF without an error.

## [7.1.3] - 2026-10-21

### Changed

- A TikZ width budget no longer narrows a column of labels, one whose longest cell is at most
  three words ("Portfolio A", "40M xs 10M"); the table scales instead. Prose still narrows first.
  Budgeted tables whose stub or label columns used to wrap now keep them on one line and may set
  at a smaller scale, or report an overrun where narrowing used to hide one.

## [7.1.2] - 2026-10-21

### Fixed

- A TikZ width budget is met at `tikz_scale`, the scale the table is set at. Below 1, as house
  style's 0.9 ceiling is, columns were narrowed to fit the budget at full size and the table then
  set at 0.9: a tenth of the line went empty while short labels wrapped (the Loss Lab layer
  column broke "40M xs 10M" over three lines). Such tables now wrap less and run up to a tenth
  wider, never past the budget.
- An overrun suggests `sidewaystable`, with the budget at the text height, not `sidewaysfigure`.

## [7.1.1] - 2026-10-21

### Fixed

- Tabular TikZ engine: a group label's underline reaches the stub rule. With one stub column it
  stopped half an em short.
- Tabular TikZ engine: a heading has the matrix's room above the rule under it, about 3.4pt where
  it had 1.8pt. Heads are about 1.6pt a row taller; tabular output changes for every table.

## [7.1.0] - 2026-10-21

**Rendered output changes for the default `tabular` TikZ engine**: every table with a header row
sets differently, by up to half an em. Rebuilt documents will move. The `matrix` engine is unchanged.

### Fixed

- Vertical rules sit in the middle of the column gap. Header cells came out half an em wider than
  their columns after the stub's double gap, pushing every data column right of its rule, so rules
  touched right-aligned numbers and the widest stub word. Tables are half an em narrower.
- A vertical between groups that share a label above starts under that label's underline instead
  of running through it (`Gross` and `Net` over `Paid` and `Incurred`).
- Stub headers line up with their column instead of sitting half an em off.

### Added

- `tests/test_tikz_geometry.py` compiles fixtures and measures where rules land against the words,
  with pdfplumber (a new dev dependency). Two matrix defects are recorded there as expected
  failures: verticals through spanner labels, and verticals 1.4pt short of the bottom frame.

## [7.0.1] - 2026-10-21

### Fixed

- A TikZ table still wider than `max_table_width_em` at the foot of the scale ladder logs at
  ERROR, not WARNING. House style sets the `greater_tables` logger to ERROR to hide the routine
  ladder steps, which hid real overruns too; those now show. Rendered output is unchanged.

## [7.0.0] - 2026-08-10

**TeX math just works — inline, in headers, everywhere.** GT5 could set
`the survival $\psi(u)$ falls` mid-sentence; the 6.0 rewrite silently lost
that, kept only whole-cell math, and never flagged math in a column header
at all. Both are back, on one shared rule
(`src/greater_tables/mathspans.py`) used by the builder, all four
renderers *and* the width estimator — so what is measured is what is set.
Major version because `TableSpec.math` is gone (see Removed).

### Added

- **Inline `$...$` / `$$...$$` spans in any text**: body cells, stub cells,
  column headers, captions and notes, through TikZ (both engines), HTML, the
  JS walker (KaTeX called per span) and the width estimator. `\$` is a
  literal dollar; renderers spend the escape and re-escape for their target
  (`\$100` → `\$100` in TeX, `$100` in HTML).
- **Math in column headers.** `HeadCell.math` was in the IR from 6.0 and
  every renderer honored it — only the builder never set it. A header now
  behaves exactly like a body cell, whole-cell (`$\beta$`) and inline
  (`formula $f(x)$`) alike; the text renderer prints math headers with
  their `$`s restored.
- **`TableDoc.math: 'auto' | 'off'`** (default `'auto'`, omitted from
  canonical JSON — no golden or hash churn). The document-level escape
  hatch for hand-authored/foreign IR whose dollars are all literal (ticker
  tables): `'off'` stops delimiter *detection* in every renderer and the
  estimator; explicit `Cell.math` flags are still honored. The builder
  always emits the default.
- Fixture `inline-math` exercising the full matrix — inline and whole-cell
  math in body, stub, header, caption and notes beside currency and an
  escaped dollar — plus `tests/test_inline_math.py` (39 tests) and compile
  coverage under tectonic in both TikZ engines.

### Changed

- **The math rule is stricter than GT5's, deliberately.** Delimiters must be
  tight against their content (`$ loose $` and `$x $` are prose now — the
  6.x whole-cell detector accepted them), no interior `$`, and a closing
  `$` followed by a digit reads as currency. Consequence: **GT5's currency
  bug is fixed** — `$10 to $20` and `$5-$10` set as escaped prices, never
  as `10to` in math italic. The accepted corner: `$x$2` reads as currency;
  write `$x$ 2`.
- **Whole-cell display math `$$x$$` is now detected** (6.x only matched
  single-`$`); display spans render with each target's *inline* delimiters —
  display primitives misbehave inside a table cell.
- The width estimator (`render/textlength.py`) segments with the shared
  rule instead of its GT5 loose-regex copy, closing the
  estimator-vs-renderer disagreement on currency cells (`'$10 to $20'`
  measured 3278 milli-em as phantom math; literal glyphs are 4478).
  `display_milli` / `token_milli` gain a `math` flag; `_milli_math` is now
  public `math_milli`.

### Removed

- **`TableSpec.math`.** Detection is always on — that is what "just works"
  means — so the spec knob goes; `TableSpec(math=...)` now raises
  `TypeError`. The `'off'` escape hatch moved into the IR as
  `TableDoc.math` (see Added). Also dropped from the YAML config template
  hints.

### Fixed

- Math in column headers (never detected in 6.x — `build.py` constructed
  `HeadCell` without ever running the detector).
- The text renderer now decorates head cells, so a math header prints as
  `$\beta$` instead of silently dropping its delimiters.
- The walker renders notes through the same cell path as Python (they were
  plain `textContent`), so a note's math renders in the browser too.
- Escaped dollars inside math-adjacent prose no longer emit a stray
  backslash in TeX (`escaped \$100` renders as “escaped $100”).

### Notes

- `\(...\)` / `\[...\]` are **not** recognized — write the `$` forms. GT5's
  TeX path protected `\[...\]` (deliberate) while `\(...\)` only ever
  worked by accident in HTML; if `\[...\]` is ever wanted back it is a
  contained change in `mathspans.py`. A literal `\$` *inside* a math span
  is also unsupported (`[^$]` excludes it) — use `\mathdollar`.
- The walker's inline regex uses lookbehind: Safari ≥ 16.4. It is a
  visually-identical lockstep twin of the Python pattern, enforced by the
  DOM-transcript conformance goldens; `GT_RENDER_VERSION` is now `7.0.0`.
- Zero committed goldens changed; the only golden additions are the new
  `inline-math` fixture's files. `schema/ir-v1.json` gains the `math`
  document field.

## [6.2.0] - 2026-08-10

**The tabular TikZ engine is now the default.** The side-by-side review that
6.1.0 was waiting on came back clean, so the fast engine is what you get
without asking. Invisible in the output, 30x in the build.

### Changed

- **`HouseStyle.tikz_engine` now defaults to `'tabular'`** (was `'matrix'`).
  Every TikZ render — `render_tikz`, `GT.tikz`, whatever `Etcher` compiles —
  takes the one-node tabular path unless told otherwise: about 9 ms of TeX per
  table against 290 ms, measured over 159 real tables.

  Two reasons to keep asking for `'matrix'`: output that must stay
  byte-identical to 6.1.0, and `tikz_post_process` TeX that addresses cells by
  pgf node name — the tabular is one node for the whole table. Both engines
  remain fully supported; switching is one `HouseStyle` field.

- **The embedding document now needs `booktabs` and `array`.** `Etcher` loads
  both and Quarto's default LaTeX template already does, so most builds notice
  nothing; a preamble that rolls its own must add them.

- **The `\I` strut trap no longer bites by default.** The tabular engine
  carries its own `\providecommand`, so a Quarto PDF no longer needs
  `\newcommand{\I}{\vphantom{lp}}` in the preamble unless it opts back into
  the matrix. `docs/quickstart.rst` says so where the warning already was.

- **Tests pin the engine they mean.** `tests/test_tikz.py` and the TikZ
  assertions in `test_rules.py` now ask for `'matrix'` explicitly, and
  `make_goldens.py` writes `tests/golden/tikz/` with the matrix style. Both
  golden sets are unchanged on disk — nothing was regenerated, which is the
  point: the matrix output is still byte-for-byte what 6.0.0 emitted.

### Notes

- Still true of both engines: **neither breaks across pages**, a TikZ node
  being one unbreakable box. A `longtable` body remains the follow-on.

## [6.1.0] - 2026-08-09

**A second TikZ engine, about 30x faster, off by default.** Nothing changes
unless you ask for it: `tikz_engine` defaults to `'matrix'` and the matrix
emitter's output is byte-identical to 6.0.0 (guarded by the committed
goldens).

### Added

- **`HouseStyle.tikz_engine`** — `'matrix'` (default) or `'tabular'`.
  `'tabular'` renders one real `tabular` inside a single TikZ node instead of
  a pgf `matrix of nodes`.

  The cost of the matrix emitter is *per addressable pgf node* and nothing
  else: measured over 159 real tables, 291 ms each, against 9 ms for the same
  tables as a single node. Reaching for another table package does not help —
  `nicematrix` and `tabularray` also give every cell a node and land in the
  same band. The nodes only ever existed to anchor rules, and
  `greater_tables` computes every column width itself. So vertical rules are
  drawn from the node's corners at offsets it already knows, and horizontal
  rules become booktabs rules *inside* the tabular, where TeX knows the row
  positions that `greater_tables` cannot (cells wrap). Whole-corpus compile
  on the fixture and Fabricator sweep: 17.3 s to 2.1 s.

  The emitted body is a literal `tabular`, so a typesetter who does not use
  TikZ converts it by deleting the wrapper rather than by five separate
  transformations of a `\&` matrix.

  Headers stay **bottom aligned** — each header cell restates its column as
  `b{}` through `\multicolumn`, since `p{}` is top aligned. Header
  *horizontal* alignment reproduces the matrix exactly, which means centered
  (stub columns flush left) regardless of the column's own alignment: in the
  matrix the `row` style silently beats the `column` style, and this engine
  matches that rather than "fixing" it. Both are covered by tests, not by eye.

  Column groups, spanners, colspans, sparsified stub rowspans, break and total
  rules, `max_table_width_em` and the `tikz_scale` ladder all carry over.
  Measured height drift against the matrix over 36 fixture and Fabricator
  tables: median 0.0%, p90 +1.4%. Five run over the 2% target and every one is
  a two- or three-row table where the absolute difference is under 5pt.

- **`dev/tools/compare_engines.py`** — renders a corpus through both engines
  into one side-by-side PDF, and reports per-table compile time, speedup and
  height drift. Not shipped in the wheel; a review artifact.

- Golden `.tex` for the new engine at `tests/golden/tikz-tabular/`, one per
  IR document, regenerated by `tests/make_goldens.py`.

### Fixed

- **`Etcher` now loads `booktabs` and `array`**, which the tabular engine
  needs. Harmless for the matrix engine.
- **The `\I` trap is documented, and the tabular engine no longer has it.**
  `render/tikz.py` emits a `\I` strut in every header cell but only
  `Etcher`'s standalone template defines it, so a table embedded in a Quarto
  PDF build raises `Undefined control sequence` — which destroys the
  enclosing node ("A node must have a (possibly empty) label text") and
  spills the strut body `lp` into `nullfont`. One missing macro, three
  unrelated-looking errors, and nothing in the docs said so. The matrix
  engine still needs `\newcommand{\I}{\vphantom{lp}}` in the host preamble
  and `docs/quickstart.rst` now says so loudly; the tabular engine carries
  `\providecommand` for its macros inside each picture and needs nothing.

### Changed

- **Internal:** the TikZ layout pass (cell grid, spans, width solve, scale)
  moved to `render/tikz_layout.py`, shared by both emitters. `render_tikz`
  is now a dispatcher; the matrix emitter is `render_tikz_matrix`. No public
  behavior change — `render_tikz`, `table_width`, `TIKZ_PREAMBLE` and
  `W2TIKZ` keep their names and signatures.

### Notes

- **Neither engine breaks across pages.** A TikZ node is one unbreakable box,
  which is as true of the matrix today as of the tabular. A `longtable` body
  for tall tables with no vertical rules is the obvious follow-on and is not
  in this release.
- The tabular engine needs `booktabs` and `array` in the embedding document.
  Quarto's default LaTeX template already loads both.
- `'matrix'` stays the default until the side-by-side has been reviewed on a
  real book. Switching is one `HouseStyle` field.

## [6.0.0] - 2026-08-05

**First stable release of the rewrite.** No code changes since `6.0.0b1` —
this promotes the beta after review.

The alpha and beta series ran while `aggregate_api` adopted the engine; that
adoption is settled, so the surface is now fixed. From here 6.x is additive:
new `TableSpec` / `HouseStyle` fields and new renderers are minor bumps,
anything that changes an existing rendering is not.

### Changed

- `Development Status` classifier moved from `4 - Beta` to
  `5 - Production/Stable`.
- **Docs URL is
  [greater-tables-project.readthedocs.io](https://greater-tables-project.readthedocs.io/en/latest/),**
  not the `greater-tables` slug earlier entries promised. A Read the Docs
  slug is fixed when the project is created and cannot be renamed, so 6.0
  publishes under the existing project. Moving it means a new RTD project and
  new release metadata, which is a job for the next version — see `[rtd]` in
  `dev/pending.md`. Any `greater-tables.readthedocs.io` link in an entry
  below this one is dead; use the URL above.

### The contract, stated once

- **`ir_version` is 1 and stays 1** for all of 6.x. Readers must ignore
  unknown fields, so additive IR fields can only ever be advisory; anything
  content-bearing needs a version bump. The schema is committed at
  `schema/ir-v1.json` and diff-guarded by the test suite.
- **`greater_tables` 5.3 is frozen and stays on PyPI forever.** Pin
  `greater-tables<6` to stay there; the import name is identical on both, so
  `from greater_tables import GT` works either way. `docs/migration.md` is
  the complete option-by-option map, including the three silent default
  changes (`formatters` ints now group, `show_index` auto-hides,
  `header_row` defaults off).
- Python 3.12+. Runtime dependencies are numpy, pandas, pydantic and PyYAML;
  the JS walker has none.

### Known gaps, carried into 6.x

- **No CI yet.** 428 tests pass locally and the schema and walker transcripts
  are guarded by the suite, but nothing runs on push. The 3.12 floor is
  therefore declared rather than matrix-verified. See `[ci]` in
  `dev/pending.md`.
- `HouseStyle.vrule_widths` is a 3-tuple with only 2 usable slots, and
  `hrule_widths`/`vrule_widths` have no Python route to the HTML weights —
  both in `dev/pending.md` under `[formats]`.
- Uppercase `G`/`E` format sugar is still unparsed.

## [6.0.0b1] - 2026-08-05

Release candidate in all but name: the last look before `6.0.0` goes public
and onto PyPI. No engine changes — this is the public face.

### Changed

- **Python floor raised to 3.12.** `requires-python = ">=3.12"`, classifiers
  now 3.12 / 3.13 / 3.14. The old 3.11 floor was declared but never tested,
  and 3.11 reaches end of life before this package's first stable release
  would benefit from it. **Note:** 3.12 is likewise declared and not yet
  matrix-tested — that is what `[ci]` in `dev/pending.md` is for.
- **`transition.md` is gone, folded into `docs/migration.md`.** The complete
  5.x → 6.0 option map — every `Configurator` field, the full `HouseStyle`
  table, vertical rules, width machinery, porting recipes — was sitting in a
  root-level file that no page linked to and the sdist did not ship, while
  `docs/migration.rst` covered the same ground more thinly. Now one document,
  in the docs, in the sdist. It is MyST markdown rather than reStructuredText
  because it is twelve wide reference tables and RST grid tables would be
  unmaintainable; `myst_parser` was already enabled for the changelog.
- Installation text no longer says "6.0 is not on PyPI yet" (README and the
  docs landing page).

### Fixed

- **`docs/migration` said a bare int does not group.** It does:
  `formatters={'paid': 2}` gives `1,234.57`. That is the one silent behavior
  change from 5.x and the page stated the opposite of the truth. Now a
  warning box, alongside the two other silent default changes (`show_index`,
  `header_row`).
- **Two places claimed CI that does not exist** — `README.md` and
  `docs/ir.rst` both said the schema and transcripts were guarded "in CI".
  They are guarded by the test suite; `design.rst` had it right.
- `docs/ir.rst` listed the `FormatKind` values without `gen` (added in a11).
- `docs/api.rst` omitted `load_style` and `__version__` from the documented
  exports, and never documented `render.widths`.
- README's status block still read `6.0.0a1` and "all seven design steps",
  and its layout listing predated the `text-ascii` and `tikz` golden trees.
- "Licence" → "License" in README and the docs landing page (US spelling).

### Added

- The target-aware display bundle is now described where users will meet it:
  `README.md`, the docs landing page, `design.rst` (with the measured
  reasoning behind the PDF path dropping `text/html`), and migration's
  "New in 6.0".
- `design.rst` documents `render/notebook.py` and the two-charset golden
  trees, and states plainly that the display-bundle probe is run by hand
  rather than in the unit suite.

### Notes

- **JupyterLab verified** by hand (2026-08-05) — a live notebook takes
  `text/html`, as inferred. That was the one unmeasured consumer left over
  from the a9 probe, and it is now closed.
- `CLAUDE.md` is untracked as of this release; it is a personal operating
  procedure, not project documentation.
- CHANGELOG entries before this one still reference `transition.md`. They are
  a historical record of what was true at the time and have been left alone.

## [6.0.0a11] - 2026-08-05

Item 1 of the `[formats]` batch in `dev/pending.md`, lowercase half.

### Added

- **`g` format sugar**, in both dialects — `'.3g'` and `'{x:.3g}'`, analogous
  to `'.3f'`. New `FormatKind` member **`'gen'`**.
- `digits` on a `gen` spec counts **significant figures**, not decimal
  places, because that is what python's `g` presentation type means: `'.3g'`
  renders 1234.5 as `1.23e+03` and 0.0012345 as `0.00123`, where `'.3f'`
  would give three decimals in both cases. Bare `'g'` takes python's own
  default precision of 6.
- `group` still applies, so `',.9g'` gives `1,234,567` — visible only while
  `g` stays in its fixed-point form.
- The JS walker maps `gen` to `.Ng` in `cgFormatSpec`, keeping the two
  implementations in lockstep.

### Changed

- **`schema/ir-v1.json`**: the `FormatKind` enum gains `"gen"`. Additive and
  advisory, so **`ir_version` stays 1** — but note the asymmetry: documents
  written by an older greater_tables still validate here, while a document
  using `gen` fails an older copy of the schema.

### Notes

- Uppercase `G` and `E` remain unparsed, and stay in `dev/pending.md`. They
  are the awkward half — either two more enum members or an `upper: bool` on
  every `FormatSpec`.

## [6.0.0a10] - 2026-08-05

`dev/plan-display-bundle.md`, work item `[ascii-rules]`. Additive: defaults
are untouched and every existing golden is byte-identical.

### Added

- **`HouseStyle.text_ascii_rules`** (default False) — draw the text
  rendering with ASCII only. Motivated by two measured problems: Pygments
  lexes U+2501 as an error token, so a Sphinx LaTeX build emits `Lexing
  literal_block … resulted in an error` once per table and styles the rule
  red in the PDF; and a cp1252 console cannot encode box drawing at all.
- **`render.text.Charset`**, with `UNICODE_CHARS` (default) and
  `ASCII_CHARS`. Every non-ASCII character the renderer draws now lives in
  one frozen dataclass instead of eight literal sites.
- **`tests/golden/text-ascii/`** — a full parallel golden tree, one file per
  fixture, written by `tests/make_goldens.py` alongside the existing ones.

### Notes

- The ASCII set is `=` heavy, `-` light, `|` stub divider, `<<flag>>` row
  gutter. **Heavy and light stay distinct**: collapsing `━` and `─` both to
  `-` would make a frame rule and an internal group break identical, and
  which is which is information the conformance oracle should not lose.
- The row-flag delimiters (`«total»`) were the eighth site, and are easy to
  miss — they sit in a right gutter, not in the rules.
- **Scope is what the renderer draws, not cell text.** Values arrive already
  formatted, so `FormatSpec.null` (an em dash) and the SI suffix ladder (µ)
  still come through and ASCII-mode output is not necessarily `isascii()`.
  Laundering them here would make the oracle disagree with the document it
  is checking; change them on the spec side if a build must be pure ASCII
  end to end. `tests/test_text.py` asserts this limit so it stays deliberate.

## [6.0.0a9] - 2026-08-05

`dev/plan-display-bundle.md`, work items `[plain-in-bundle]`,
`[quarto-target]` and `[bundle-policy]` — one coherent change to what GT
advertises to a display front end. Every decision here comes from a measured
probe of five consumers (Sphinx html/latex, Quarto html/latex/gfm), which
lives at `dev/tools/output-modes/`, not from reasoning about what ought to
happen.

The bundle rules are now:

| target                                | keys published             |
|---------------------------------------|----------------------------|
| Quarto PDF (`QUARTO_FIG_FORMAT == 'pdf'`) | `text/latex`, `text/plain` |
| any other Quarto render, or none      | `text/html`, `text/plain`  |
| caller passed `mimes=`                | exactly what was asked for |

### Added

- **`text/plain` in every mimebundle.** It is the one type all five measured
  consumers render, so a table degrades to the monospace rendering rather
  than to silence. This alone fixes Sphinx HTML and Sphinx LaTeX, which
  prefer `text/plain` and previously fell through to the default repr — with
  no caller-side change. Measured identically under Sphinx 8.2.3 and 9.1.0.
- **`GT.__repr__`** returns the text table. `__str__` already did; without
  the pair, any consumer falling back to `repr()` showed
  `<greater_tables.compat.GT at 0x…>`. This is what makes `GT` usable from a
  plain script or REPL.
- **`render.notebook.quarto_target()`** → `'pdf' | 'other' | None`. `'other'`
  deliberately is not `'html'`: `QUARTO_FIG_FORMAT` is `png` for both html
  and gfm, so the two are indistinguishable from the environment and the
  return type says so rather than hiding it.
- **`GT(..., mimes=...)`**, threaded through to `mimebundle`. `None`
  detects; an explicit tuple publishes exactly those types and suppresses
  detection. Members are validated at construction, so a typo raises instead
  of silently publishing a bundle nothing can display. It exists for the one
  target that cannot be auto-detected — `quarto render --to gfm`, where
  pandoc's commonmark writer prefers html and leaks a raw `<div class="gt">`
  into the markdown. A whole-document policy, so the intended form is
  `render = partial(GT, mimes=('text/plain',))`.

### Changed

**Both of these change output for anyone relying on the old bundle.**

- **An HTML render no longer receives `text/latex`.** `in_quarto()` is true
  for *any* `QUARTO_*` variable, so `quarto render --to html` was computing
  and shipping a TikZ payload that was never used — the exact
  compute-TikZ-then-discard waste this module's design was meant to have
  fixed, reintroduced one level up. The `text/latex` decision now routes
  through `quarto_target()`. `in_quarto()` is unchanged and still exported.
  Net effect on an HTML or notebook render is a speed *gain*: the TikZ pass
  that disappears costs more than the text pass that arrives.
- **A Quarto PDF render no longer receives `text/html`.** A `{html, plain}`
  bundle renders *nothing at all* under Quarto latex — pandoc picks the html
  and the LaTeX writer discards it, silently. Omitting html means a TikZ
  failure degrades to text rather than to an empty page.

### Notes

- `mimebundle`'s existing `tikz=` flag is untouched: `True` still means "also
  give me TikZ" and keeps `text/html`. It is a forcing knob, not a target
  declaration; `mimes=` is the precise control.
- `render_text` runs on every render now, and is bounded by
  `TableSpec.max_rows` (default 200) like every other renderer.
- **Not measured:** JupyterLab itself, which needs a live front end. It is
  expected to behave as Quarto HTML does and prefer `text/html`, but that is
  an inference, not an observation. Worth one manual check before 6.0.0.

## [6.0.0a8] - 2026-08-03

Steps 3 and 4 of `dev/plan-column-widths.md`. 5.x's `max_table_inch_width`
finally has an heir, and it works in TikZ and HTML by the means each medium
actually has.

### Added

- **`HouseStyle.max_table_width_em`** (default None) — a total width to aim
  for. **A target, not a guarantee**, and the docstring leads with that:
  columns that cannot wrap hold their natural width whatever the budget says.
  What the budget can do is narrow the prose columns, and then:
  - **TikZ** solves them with `render.widths` — one shared quantile, so every
    prose column carries the same chance of wrapping — and fills or gives back
    the remainder proportionally so the budget is met, not merely respected.
    When even the floors do not fit, `tikz_scale` steps down a coarse ladder
    (1.0, 0.95 … 0.6) picked with the measured `width(s) = s·T + S` model, and
    says so through `logging`. Past 0.6 it warns, names the shortfall, and
    suggests `sidewaysfigure` rather than shrinking into illegibility.
    Verified by compiling: every fixture lands at or under its budget, within
    0.1em wherever narrowing was possible.
  - **HTML** emits `--gt-max-width` and lets the browser do it. No solver runs
    there and none should: `gt-nowrap` already pins the columns that must not
    be narrowed, so the browser narrows exactly the prose ones — with the real
    font, not our estimate of it.
- `render.tikz.table_width` — the emitted-width model in one place, shared by
  the autoscale arithmetic and the tests.

### Changed

- **`HouseStyle.tikz_prose_max_em` is renamed `max_prose_width_em`** — it
  reads as a sibling of `max_table_width_em` now, and it is no longer
  TikZ-only: HTML emits it as `--gt-prose-max`. One field, both renderers.
- **`--gt-prose-max` defaults to 18em, was 30em**, so the two renderers agree
  on one number. 18em is also the better number on its own merits — roughly
  65 characters, the measure prose is comfortable at, where 30em is nearer
  110. **HTML tables with prose columns will render narrower.** The markup is
  unchanged, so no DOM golden moved; put `.gt { --gt-prose-max: 30em }` in
  your stylesheet for the old look.
- A prose column's floor is now its widest single word, and the cap is a hard
  ceiling that only an unhyphenatable word may beat.

### Notes

- Equal risk cannot narrow a column whose cells *all* overrun the prose cap:
  every quantile lands on the cap, so the bisection has nothing to bite on.
  Such a column is wrapping whatever happens and narrowing it only costs
  height, so the remaining slack is taken proportionally instead. Without
  this, a table of long prose ignored its budget entirely and went straight
  to scaling.
- `transition.md`'s "Width machinery — all gone" section is now out of date —
  `max_table_inch_width` and `table_width_mode` have partial heirs. Left
  alone deliberately: that file has uncommitted edits.

## [6.0.0a7] - 2026-08-03

Step 2 of `dev/plan-column-widths.md`: the allocator, plus the measurement
that unblocks the TikZ budget. **No renderer consumes this yet** — behavior
is unchanged in every output format.

### Added

- **`render/widths.py`** — column-width allocation under a total-width
  budget, ported from the csv-grid solver the JS walker already carries.
  `solve_widths(samples, floors, budget, mode)` returns an `Allocation`
  (widths plus `natural` / `solved` / `over`). Two modes: `equal-risk`, which
  bisects for the one quantile every column is measured at so all columns
  carry the same overflow probability, and `coverage`, which water-fills
  along each column's concave envelope to fit the most cells outright.
  Integers in, integers out, unit-agnostic — milli-ems for TikZ, characters
  for the text renderer later. The budget is text width only; separations are
  the caller's geometry.

  The port differs from csv-grid in one respect, and it is the caller's
  world, not the math: csv-grid narrows a column by **truncating**, so its
  floor is a minimum readable width; a typeset table narrows by **wrapping**,
  so the floor is the widest unbreakable token. Same solver, different floors.
- **`js/solver-check.mjs`** and `tests/test_widths.py` — the Python port and
  the walker's copy must allocate identically, checked on 10 column shapes ×
  both modes. Alongside the existing csv-grid drift check, the three copies
  of this algorithm are now pinned to each other.

### Notes

- **`tikz_scale` does not scale a table uniformly**, which the plan had
  assumed it might. It is a node option, so node contents scale while the
  matrix `column sep` does not. Measured across six scales, width is exactly
  linear — `width(s) = s·T + S`, with `T` = Σ text widths + 2 × column sep
  (column 1's `inner xsep`, which scales) and `S` = ncols × column sep.
  Predictions matched measurement to 0.1pt at every step, so an
  autoscale ladder can pick its step in advance; it just has to use this
  model rather than assuming `width(s) = s · width(1)`.

## [6.0.0a6] - 2026-08-03

Fallout from rendering `6.0.0a5` through Quarto rather than only through
`Etcher`: the estimate was right and the margin was not.

### Fixed

- **Columns are no longer sized to the estimate exactly.** `Sub 1` measures
  2.306em and got a 2.31em column — a 0.17% margin. `Etcher` cleared it; the
  same table in a Quarto document, whose preamble brings microtype and
  friends, broke the line. Every measured requirement now carries
  `render.tikz._WIDTH_PAD`, 0.1em, so line breaking stops depending on the
  host document's package list. This is what the stale `+ source padding`
  comment on that code had always claimed.
- **`_BOLD_PERCENT` 115 → 118.** Measured over the fixture corpus in newtx,
  bold/roman is 1.000 at the median but 1.130 at p99, so real header words
  (`return`, `Incurred`) could exceed the old factor and hyphenate. Digits are
  the same width in both weights, so the common numeric header is unaffected.

### Notes

- **The width estimate is Times metrics, and that is now documented** in
  `render/textlength.py`. It is exact against `newtxtext` — what `Etcher`
  compiles with — and roughly **11% tight against Latin Modern**, the LaTeX
  default a plain Quarto PDF uses, where long headings will hyphenate. Load a
  Times-metric serif alongside the tables or accept slightly tight columns;
  `dev/tools/measure_glyphs.py` re-measures any font. A per-font widening
  factor is the obvious answer and is deliberately deferred to the width
  budget work, where it has somewhere to live.
- `\usepackage{newtxmath}` collides with Quarto's math setup
  (`\arrowvert already defined`) — `newtxtext` alone is what the width
  estimate needs.

## [6.0.0a5] - 2026-08-03

Step 1 of `dev/plan-column-widths.md`: make the TikZ width estimate
trustworthy, which everything else in that plan rests on. No new API.

### Fixed

- **TikZ used TikZ's balanced-ragged alignment, which breaks lines that fit.**
  Columns were emitted with `align=left/right/center`, whose limited
  `\rightskip` stretch makes TeX wrap a cell set to exactly its own natural
  width — measured, a cell needed roughly 0.1em of slack per interword space,
  so `Sub 1` in a 2.31em column came out as `Sub` / `1`. The flush variants
  (`align=flush left`, …) are unlimited raggedness and honor the estimate
  exactly: across every multi-word string in the fixtures, required slack went
  from 0.10–0.20em to **zero**. This is also what the table-level
  `text badly ragged` was already asking for.
- **30 characters were missing from the TextLength glyph table** and silently
  took the 600 milli-em default. The three that matter most to a real table
  were the most wrong: `—` (the missing-value marker, actually **1000**), `%`
  (every ratio column, 833) and `µ` (every SI-suffixed column, 500). `-` was
  also wrong, 500 against a measured 333, so date columns were over-reserved.
  Values measured against newtx; the rest of the table was already exact
  (median actual/estimate 1.000 over 596 fixture strings).

### Changed

- **A column header no longer stretches its column.** Header cells have a text
  width and wrap, so a heading now floors its column at its **widest word**
  rather than its full one-line width: `Cumulative Incurred Loss` over six-em
  numbers took 12.0em and now takes 5.4em, wrapping instead. Header cells
  spanning one column are all measured this way, at any level.
- **Spanning labels are measured at all.** An overlaid group label or body
  `colspan` cell carries no text width and cannot wrap, so it now widens the
  last column it covers if the span — including the separations it crosses —
  cannot hold it. Previously spans contributed nothing to width and overflowed
  silently; the text renderer has always done this.
- TikZ width arithmetic is integer milli-ems throughout, divided only at emit
  time, extending the reproducibility discipline already documented in
  `render/textlength.py` to the column geometry itself.

### Added

- `render.textlength.token_milli` / `token_display_len` — width of a string's
  widest unbreakable token. TeX will not hyphenate inside a word, so this is
  the floor for any wrapping column; `$...$` counts as one token.
- `dev/tools/measure_glyphs.py` — compiles a probe that measures every glyph
  in the table against real font metrics and reports what is missing or off.
  Reports only; corrections are pasted in deliberately so the committed table
  stays a reviewed artifact.

### Notes

- Every TikZ golden moved (alignment keyword on every column, plus the width
  corrections). IR, text, DOM transcripts and CSS are byte-identical.

## [6.0.0a4] - 2026-08-01

Step 2 of two: house rules for formats. 5.x's `default_*_str` settings come
back as real fields, so one YAML file can govern every table in a document
instead of a per-column dict in every call.

### Changed

- **`ratio_cols` renders as percent again** — `FormatSpec(kind='pct',
  digits=1)`, restoring 5.x's `default_ratio_str = '{x:.1%}'`. GT2 had been
  producing `dec`/3, so `0.4576` showed as `0.458` instead of `45.8%`; both
  `transition.md` and `docs/migration.rst` already claimed percent, so the
  docs were describing the intended behavior all along. **To keep the old
  output**: `TableSpec(ratio_format='.3f')` reproduces it exactly.
- **`TableSpec.formats` is renamed `formatters`** — one name, matching
  `aligners`, and the same name 5.x used on its constructor. The
  `compat.GT` translation layer is gone with it. One deliberate difference
  from 5.x: **a bare int now groups** (`formatters={'paid': 2}` →
  `1,234.57`), because GT2 groups whenever it picks the format for you.
  Write `'.2f'` for the ungrouped form — explicit sugar still means exactly
  what it means in Python and csv-grid, where the comma is the grouping flag.
- `infer_numeric_format` takes the engineering digits and style, so the
  hard-coded `si`/3 is now `TableSpec.eng_digits` / `eng_style`.

### Added

- **House defaults on `TableSpec`: `float_format`, `int_format`,
  `ratio_format`, `date_format`.** Each replaces its own kind's built-in and
  loses to an explicit `formatters` entry. They apply to stub columns too,
  and they are YAML-expressible, which is the point: `GT(df,
  config_path='house.yaml')` gives every exhibit in a document the same
  decimals regardless of what its own data looks like. Setting
  `float_format` turns float inference off entirely, including the automatic
  SI/engineering switch — a stated house rule beats a guess.
- **`table_float_format`** — the sledgehammer: every **untagged float**
  column, overriding even a per-column entry. Ratio, year and date columns
  have a kind, so it never reaches them (a ratio is an honorary non-float).
  Default None, and deliberately omitted from `write_template`: it belongs
  at a conscious call site, not in a file where it would silently defeat
  every `formatters` entry you write months later.
- **`eng_digits` (3) and `eng_style`** (`'si'` suffixes or `'exp'` aligned
  exponents) — 5.x's `pef_precision`, plus the style choice it never had.
- **`parse_sugar` accepts a mapping**, so YAML can express a full
  `FormatSpec`: `formatters: {paid: {kind: dec, digits: 1, negative: paren}}`.
  Without it a config file could only say `',.2f'` — exactly what 5.x could
  already say — leaving paren negatives, `scale`, `prefix`/`suffix` and
  custom null/zero strings Python-only.
- **`config.spec_to_yaml(spec)` and `write_template(path, spec=None)`** —
  the template is now generated from the dataclass with a hint per field
  (it covered 12 of 22 and rotted), and passing a spec dumps its *effective*
  values uncommented. That is the round trip 5.x had via
  `GT().config.model_dump()`: `write_template('house.yaml', gt.spec)` → edit
  → `config_path='house.yaml'`.
- **`tests/test_formats.py`** — `parse_sugar`, `infer_numeric_format` and
  `apply_format` had **zero** direct tests; everything rode on goldens.
  Plus `tests/test_house_rules.py` for the ladder and the YAML round trip.

### Fixed

- `load_spec` now converts `notes` from a YAML list to the tuple the
  dataclass holds, so a loaded spec compares equal to a Python-built one and
  the dump/edit/reload round trip actually closes.

## [6.0.0a3] - 2026-08-01

Step 1 of two: rules and the plumbing to reach them. Formats follow in a4.

### Added

- **`render/policy.py`** — `rule_slot()` and `vrule_slot()`, the single
  implementation of "which structural breaks get a rule, and with what
  weight", called by the HTML, TikZ and text renderers and ported line for
  line into the walker. The comparison used to be written out four times.
- **`HouseStyle.max_rule_depth` now does something.** It was declared,
  documented as the knob for this, and read by nothing. `'auto'` (default)
  is the previous behavior — every break except the innermost stub level, so
  no rules on a single-level index, depth 0 only on two levels, depths 0 and
  1 on three. An **int is literal**: `max_rule_depth=0` on a single-level
  index rules every row whose stub changed, which was previously unsayable.
  `None` draws no internal rules at all. `max_vrule_depth` is the sibling for
  column-group verticals.
- **`style=` reaches the renderers.** `render_html`, `render_text`,
  `mimebundle` and `GT(...)` all take a `HouseStyle` now; previously it was
  reachable only through `render_tikz`, so every field on it was dead on the
  HTML path. Passing a `HouseStyle` field name to `GT` as a bare keyword now
  warns with the fix (`style=HouseStyle(tikz_scale=...)`) instead of the
  generic "unknown option".
- **`config.load_style(path)`** — `HouseStyle` had no YAML form, so half the
  house rules were file-able and half Python-only. A separate file from
  `load_spec`'s, because semantics and renderer opinions are separate things.
- Walker: `opts.maxRuleDepth` / `opts.maxVruleDepth`, plus exported
  `ruleSlot`/`vruleSlot`. Style is not in the document by design, so a server
  passes these alongside it, with the theme.
- `--gt-vrule-0/1` CSS custom properties. Column-group verticals borrowed
  `--gt-rule-0/1`, so softening or removing one changed the other; same
  default values, so nothing looks different.
- **`deep-stub` fixture** (5 stub levels) — the depth at which a fixed cap and
  the `n_stub_levels - 2` policy disagree, and the fixture that would have
  caught the bug below. `tests/test_rules.py` checks all four renderers agree
  with the policy across 1-5 stub levels × 5 policies, and compares Python
  against the walker **live** under non-default policies (the committed
  transcripts only ever cover the default).

### Fixed

- **The text oracle drew rules the other three renderers suppressed.**
  `render/text.py` gated on `depth <= n_stub_levels - 2` while HTML, TikZ and
  the walker used `min(2, n_stub_levels - 2)`, so from five stub levels up the
  conformance oracle disagreed with everything it exists to check. Now
  impossible: there is one implementation.
- The first-row guard differed per renderer (text skipped row 0 per section,
  TikZ per body+foot concatenated, HTML and the walker not at all). No
  engine-built document can expose it — `break_depths` returns None for row 0
  — but a hand-authored or foreign one can, and conformance would not have
  caught it because HTML and the walker were wrong together.

### Notes

Nothing changes at default settings: no golden IR, text, TikZ or transcript
file moved. The only regenerated artifacts are `assets/gt.css` (new
properties), the walker build, and the demo pages.

## [6.0.0a2] - 2026-07-31

### Changed

- **`requires-python` drops to `>=3.11`** (was 3.13), with matching
  classifiers. Reported by aggregate_api, whose own floor the 3.13 pin had
  forced up from 3.11; 5.3 shipped `>=3.10`, so a 3.13 floor on a published
  6.0 was pure adoption tax. Verified rather than assumed: the full suite
  runs green on 3.11, 3.12 and 3.13, with byte-identical golden files.
- **`include_raw` on stub columns: closed as won't-fix.** `include_raw`
  means data columns in every form, and no form reaches the stub — an
  explicit list naming the index level does nothing (verified). A client
  that must sort on an index level should `df.reset_index()` before
  `build`, which is the honest shape anyway: a sorted grid has no index
  hierarchy left to respect. `TableSpec.include_raw`'s docstring now says
  so, which also settles the "reads broader than it behaves" complaint.
- `dev/` tidied further: the three working scripts moved to `dev/tools/`
  (paths inside them and the one reference in `docs/migration.rst` updated),
  the resolved aggregate_api report filed under `dev/done`, and
  `dev/pending.md` rewritten to carry only what is actually open.

### Fixed

- **TikZ widths are now identical across Python versions.**
  `render/textlength.py` held its glyph metrics as float ems and summed
  them with `sum()`. CPython 3.12 gave `sum()` Neumaier compensated
  summation, so `'apples'` totalled 2.5549999999999997 on 3.11 and 2.555 on
  3.13 — one ULP apart, but on opposite sides of the 2 dp rounding the TikZ
  renderer applies, which moved a committed column width by 0.01em and made
  a golden `.tex` file fail on 3.11. Metrics are now integer milli-ems
  accumulated as integers and converted to ems once at the end, which is
  exact on every interpreter. Found only because the 3.11 floor change was
  verified by actually running the suite there. No golden file changed on
  3.13; the goldens are now interpreter-independent.

## [6.0.0a1] - 2026-07-31

First pre-release of the rewrite. **The version line switches here** from the
1.x development counter (1.0.0 → 1.11.0, one bump per completed step) to the
published series: this package ships as `greater-tables` **6.0** on the
existing PyPI project, where 5.3 stays frozen and pinnable (`<6`). Further
changes before the release are `6.0.0a2`, `a3`, …

All seven design steps are complete — [ir-core], [engine], [walker],
[aggregate-api], [notebook-html], [tikz-blog], and the [backlog] adapter —
and every plan doc has moved to `dev/done`. Open items are in
`dev/pending.md`; the biggest is that Read the Docs hosting is not yet set up.

### Changed

- Version bumped to `6.0.0a1` in `_version.py` and `GT_RENDER_VERSION`.
  `package.json` spells the same version `6.0.0-a.1`, which is npm's semver
  form of PEP 440's `6.0.0a1` — the two differ in punctuation only.
- `dev/` tidied: `spec-gt2-for-aggregate-api.md` deleted (superseded — the
  adoption landed in aggregate_api a34/a35, and their own notes carry the
  detail), `plan-aggregate-api.md` moved to `dev/done`, and `design.md`'s
  sequencing section records that all steps are complete rather than
  describing them as upcoming.

## [1.11.0] - 2026-07-31

### Fixed

- **`irToGridInput` no longer throws on string data columns.** It required
  raw values on *every* data column, but `include_raw='data'` only covers
  numeric, date and bool ones — so any frame with a string column outside the
  stub failed, built exactly as documented (3 of aggregate_api's 12 frames;
  reported in `dev/note-from-aggregate-api-include-raw.md`). A string's
  formatted text *is* its value, so `string`/`object` columns now fall
  through as text and raw is required only where there is something to
  recover. The throw names the offending dtype and what `include_raw='data'`
  actually covers, instead of advising what the caller already did. The stub
  half of that report — no raw on index columns, so a numeric index sorts
  lexically in csv-grid — is still open, see `dev/pending.md`.

### Changed

- **Engine goldens no longer carry `generator`**, so a version bump stops
  rewriting all 22 of them and burying real IR changes in the churn (verified:
  a faked 9.9.9 bump now changes nothing under `tests/golden`, `demo.html`,
  `demo2.html`, or `schema/`). `generator` is informative and already excluded
  from the content hash. `tests/registry.golden_bytes` is the one place that
  defines the golden byte form, used by both `make_goldens.py` and
  `test_engine.py`; the hand-authored exemplars keep their fixed test
  generator, so the field itself stays covered.

## [1.10.0] - 2026-07-31

### Added

- **LICENSE** — MIT, the same text and holder as greater_tables 5.3, years
  extended to 2025-2026. `pyproject.toml` declares it PEP 639 style
  (`license = "MIT"` + `license-files`), matching 5.3's metadata.
- **Sphinx documentation** in `docs/`, consistent with the 5.x docs (Read the
  Docs theme, autodoc, copy button) minus the extensions deprecated upstream
  (`sphinx-panels`, `recommonmark`, `sphinx-rtd-dark-mode`), plus napoleon
  for the numpy docstrings and intersphinx to python/pandas/numpy. Pages:
  quickstart, design (why the IR exists, engine, renderers, walker,
  verification), IR v1 reference, migration from 5.x (what carries over, what
  died and where it went), API reference, and the CHANGELOG included via
  myst. Builds clean under `-W --keep-going`. `docs/_static` artwork is
  copied from 5.x as a placeholder pending new art.
- **`.readthedocs.yaml`** and a `docs` optional-dependency extra
  (`uv sync --extra docs`). Creating the RTD project itself is pending — see
  `dev/pending.md`; the agreed slug is `greater-tables`, so docs live at
  https://greater-tables.readthedocs.io (matching the PyPI name, not the repo
  codename).
- **`dev/pending.md`** — open items that are not step plans: RTD setup,
  artwork, the 6.0 publish sequence, the `requires-python` floor, stub raw
  values, CI.

### Changed

- **PyPI metadata completed** to match 5.3's shape: author email, keywords,
  classifiers, and `[project.urls]` (Homepage/Documentation/Source
  Code/Changelog/Issues) pointing at `mynl/greatest_tables` and the new RTD
  slug. Explicit sdist include list. README rewritten as the PyPI long
  description: what the package is, how to install it, what 6.0 changes
  versus 5.x, the name story, and the pin (`greater-tables<6`) for anyone
  staying on the frozen engine.

### Fixed

- Leftovers from the 1.9.0 rename: `.gitignore` still un-ignored
  `src/greatest_tables/data/*.csv` (so a *new* package data CSV would have
  been silently ignored), `package.json` `exports` pointed at the old asset
  paths, and README, `dev/design.md`, `dev/plan-aggregate-api.md`, and the
  aggregate_api handoff spec still told readers to `import greatest_tables`.
  Repo, folder, and GitHub keep the `greatest-tables` codename by design;
  only import and distribution names moved.

## [1.9.0] - 2026-07-31

### Changed

- **Package renamed `greatest_tables` → `greater_tables`** (import and
  distribution name; the repo folder keeps the `greatest-tables` codename, so
  editable-path consumers and the V:\dev venv junction are untouched). Done
  now, before any adoption code exists, because the publish decision is:
  **greater-tables 6.0 on the existing PyPI project** — 5.3 stays pinnable
  (semver's whole job), blog imports keep working verbatim via the facade,
  and a `6.0.0rc1` pre-release will unblock the server deploy (explicit pin
  only; plain installs still resolve to 5.3) once aggregate_api adoption
  settles. aggregate_api's spec/brief updated + `dev/note-gt2-rename.md`
  dropped for their agent.
- `dev/compare_gt5.py` reworked for the name collision this creates: 5.3 now
  runs in an isolated `uv run --no-project` child (`_compare_gt5_old.py`),
  DataFrames crossing as pickles with pandas/numpy pinned to the parent's
  versions (parquet cannot carry MultiIndex columns). pyarrow added to the
  dev group.

## [1.8.0] - 2026-07-31

### Added

- **`irToGridInput(doc)`** in gt-render.js (also on the iife global): flattens
  a table document into CsvGrid's input shape — `{columns, records, formats,
  align}`. Stubs un-sparsify (rowspan values repeat down their run),
  multi-level names join with ' / ', data cells emit raw values (null →
  empty), IR FormatSpecs map to csv-grid format-spec strings, alignment
  rides as an 'lrc' string. Requires `include_raw='data'` — throws with a
  clear message otherwise, because parsing formatted text back would be the
  re-inference the IR exists to kill. Hierarchy, flags, and foot rows are
  deliberately dropped: they cannot coexist with sort/filter. csv-grid
  itself is untouched. One IR fetch now feeds both the static walker and the
  interactive grid (the aggregate-api toggle).
- `js/adapter-check.mjs` harness + node round-trip tests (`test_adapter.py`).

## [1.7.1] - 2026-07-31

### Fixed

- Spanner rules now run **full width, edge to edge**: HTML swaps the inset
  background-gradient for a plain `border-bottom` (`--gt-rule-spanner`);
  TikZ extends each rule by the half column-gap on both sides. Adjacent
  groups' rules meet exactly at the group vertical, which separates them —
  the cmidrule-style side trims from 1.7.0 read as gaps, per review.
- TikZ column-group verticals now run the full table height (top frame to
  bottom), matching the HTML `gt-vbreak` border which passes through the
  header rows; previously they started below the parent header level.

## [1.7.0] - 2026-07-31

### Added

- **Spanner rules** in all three renderers: a trimmed rule under every
  labeled column-group header, spanning exactly its columns (the booktabs
  `\cmidrule(lr)` pattern; 5.x never drew these in the live TikZ path).
  HTML/walker stamp `gt-spanner` (underline via inset background gradient —
  a border would merge with adjacent groups and lose the span extent; size
  rides as `--gt-spanner-size`); TikZ draws trimmed `\path` segments
  (`HouseStyle.spanner_rule`, default 0.5); the text oracle draws `─` runs
  under each label with gaps between groups.

### Fixed

- Example qmd HTML: math cells rendered as literal `\(...\)` because the
  document had no markdown math, so Quarto never loaded MathJax. The
  generator now includes inline math in the intro (and pins
  `html-math-method: mathjax`); the stale-file SyntaxWarnings were already
  fixed in 1.6.1 — regenerate with `dev/make_example_qmd.py`.

## [1.6.1] - 2026-07-31

### Added

- `dev/make_example_qmd.py`: generates a Quarto example file (blog-pattern
  blocks ending in `GT(df, ...)`) with a self-contained TikZ preamble; renders
  to HTML and PDF (`pdf-engine: tectonic`). Verified end-to-end: 10 tables,
  both formats. Requires `QUARTO_PYTHON` pointing at the project venv until
  the package is published; venv dev group gains ipykernel/nbformat/nbclient.

### Fixed

- Math auto-detection rejects `$...\$` values whose inner text ends with a
  backslash — the "closing" delimiter is escaped, so treating them as math
  produced unterminated `$` in TeX and broken `\(...\\)` in MathJax. Found by
  a malformed Fabricator TeX entry during PDF rendering; now plain text.
- TikZ header width estimates apply a bold adjustment (×1.15) so long bold
  headers no longer collide across the column gap (the 5.x bold_adjustment,
  now applied where 5.x didn't).

## [1.6.0] - 2026-07-31

### Added

- [tikz-blog] `render/tikz.py`: the single TikZ implementation (5.x carried
  three, two dead), rebuilt from the live `make_tikz` mechanics against the
  IR: matrix-of-nodes with zero-height spacer row, bold header rows with
  bold-italic stub headers, phantom anchor column, rules as anchored `\path`
  segments shifted into the inter-cell gaps — row break rules start at the
  changed stub column, matching HTML/text. **New capability: real colspans**
  — spanning labels are overlaid centered on the span via `calc` midpoints
  (5.x blanked repeats and silently returned '' on non-unique columns).
- `render/textlength.py`: the salvaged character-width oracle (glyph table +
  TeX math token estimation), scoped to the TikZ renderer only.
- `render/etcher.py`: Etcher salvaged and modernized — **tectonic** is the
  default engine (fast, self-caching; the 5.x `.fmt` precompilation dance is
  deleted), pdflatex fallback kept; success judged by the PDF existing, not
  the exit code (MiKTeX exits 1 on recoverable issues). No hardcoded paths,
  no .bat side files, no os.startfile.
- `HouseStyle` gains the TikZ geometry and rule-weight knobs (w2tikz scale).
- Golden `.tex` files per fixture (third renderer oracle); compile smoke
  test via tectonic (skips when unavailable); `GT.tikz` now renders;
  `mimebundle` adds `text/latex` under Quarto or on request.
- `dev/compare_gt5.py`: migration check — renders sample fixtures through
  greater_tables 5.x (in an ephemeral `uv run --with` env, keeping its
  import side effects out of the project venv) and GT2 side by side into
  `compare-gt5.html` (gitignored review artifact).
- 156 tests.

## [1.5.0] - 2026-07-30

### Added

- `dev/spec-gt2-for-aggregate-api.md`: the [aggregate-api] handoff spec
  (mirrored into `T:/worktrees/aggregate_api/dev/plan-gt2-ir-adoption.md`) —
  the adoption work is implemented by the aggregate_api agent.

### Changed

- Engineering display defaults to **SI suffixes** (µ m k M G T, full
  2022-extended ladder q..Q so a column never mixes suffix and exponent
  styles); the empty suffix slot is a no-break space so decimal points stay
  aligned in tabular-nums/monospace rendering. Exponent style remains the
  `'eng'` sugar opt-in and now emits fixed-width `e+00`/`e-00` exponents
  (sign always, two digits) so right-aligned columns line up exactly.

## [1.4.0] - 2026-07-30

### Added

- `demo2.html`: curated showcase — TeX/math cells (page-level MathJax CDN
  typesets the walker's `\(...\)` fallback), long-text wrapping from both
  Fabricator generators ('s' uniform low-variance, 'w' negative-binomial
  high-variance), wide-range floats in engineering format, and the csv-grid
  width solver demonstrated live in both modes (equal-risk and coverage) in a
  560px-constrained container against the natural-layout reference.
- Four showcase fixtures (tex, wrap-low, wrap-high, wide-floats) join the
  registry and therefore all three golden suites (IR, text, DOM transcript);
  125 tests.

### Changed

- Engineering-format inference gains csv-grid's second trigger: a float column
  whose nonzero values span more than a 10^pef_upper magnitude ratio renders as
  engineering even when its mean sits inside the pef bounds (previously such
  columns got fixed decimals and tiny values collapsed to 0.00000).

## [1.3.0] - 2026-07-30

### Added

- [notebook-html] `render/html.py`: Python HTML fragment renderer mirroring the
  walker's structure and class stamping exactly. Escaping by default with an
  `allow_html` gate (producer default on — `html_cols` was the opt-in; walker
  default stays off for foreign documents). Stylesheet policy: `css='embed'`
  (default, idempotent ~2 KB per fragment), `'once'` (per-process latch +
  `reset_css_once()`), `'none'`; `inline_css=True` flattens the same RULES dict
  onto style attributes with `var()` references resolved (HTMX/email path).
- **Conformance proven**: the Python renderer's DOM transcript byte-matches the
  walker's committed transcripts for all 20 goldens (`tests/test_conformance.py`
  + `tests/transcribe.py`, stdlib html.parser). The first run caught a real
  walker bug — `col.role === 'data'` guard broke on canonical JSON's omitted
  defaults, silently dropping `gt-vbreak` classes on body cells. Fixed.
- `render/notebook.py`: `mimebundle` (text/html now; text/latex joins when the
  TikZ renderer lands) and `in_quarto()` env detection.
- `compat.py`: the `GT(df, ...)` facade — greater_tables constructor arguments,
  5.x formatter shapes (callable / `'{x:...}'` string / int = digits without
  grouping), YAML `config_path` with explicit-argument override, unknown options
  warn-and-ignore. Fully lazy cached: nothing computes at construction, TikZ is
  never touched on the HTML path. `.tikz` raises NotImplementedError until
  [tikz-blog].
- `config.py`: YAML TableSpec loading + commented template writer.
- Engine: user formatters may be callables (facade path); callables format text
  but never enter the IR (`Column.format` stays null).
- `demo.html`: self-contained gallery at the repo root — gt.css + iife walker +
  all 20 golden IR documents, rendered client-side on open. Regenerated by
  `tests/make_goldens.py` (which now also rebuilds the walker dist).
- 113 tests total.

## [1.2.0] - 2026-07-30

### Added

- [walker] `render/css.py`: the RULES dict — single source of truth for the shared
  class vocabulary — generating committed `assets/gt.css`. `.gt.gt` selector
  doubling (beats JupyterLab/Quarto host rules without !important), per-table
  custom properties, currentColor-only palette, no widths/fonts. Row rules ride as
  border-top on the row's own cells, so rowspan-covered stub columns are skipped
  and partial rules start exactly at the changed column.
- `js/src/gt-render.js`: zero-dependency ES walker. `renderTable(doc, opts)` →
  `{el, doc, destroy(), toCSV()}` instance handle; textContent by default with an
  `allowHtml` gate (injection-safe); KaTeX injection or `\(...\)` fallback;
  delegated `gt:cellclick` CustomEvent with the full row keyed by column name;
  optional `fit` width pass (canvas measure + solver, forces single-line
  ellipsis). Solver functions copied verbatim from csv-grid `util.js` (3.9.0,
  commit 01a9773) with a provenance header and a drift-guard test that re-diffs
  the copy against the csv-grid source when present.
- `js/build.mjs` (esbuild) → committed `assets/gt-render.esm.js` + `.iife.js`
  (global `GtRender`); root `package.json` for the secondary npm-from-git path.
- DOM-transcript conformance harness (`js/transcript.mjs`, node + linkedom):
  one JSON line per cell over every golden IR fixture → committed
  `tests/golden/transcript/*.jsonl` (20 files). The Python HTML renderer must
  byte-match these in [notebook-html]. pytest wrapper skips when node is absent.
- CSS contract guard tests (asset drift, vocabulary coverage, selector doubling,
  no-geometry/no-color policy).

### Notes

- IR goldens embed the generator version string, so `tests/make_goldens.py` runs
  once per release — the one-line-per-fixture diff doubles as re-validation.
- Version strings now live in `_version.py` (hatchling-dynamic), `package.json`,
  and `GT_RENDER_VERSION` — keep all three in sync at each bump.

## [1.1.0] - 2026-07-30

### Added

- [engine] `spec.py`: `TableSpec` (semantics: caption/label/notes, semantic column
  tags as list|'all'|regex, per-column format sugar, aligners, row/cell flags,
  include_raw, max_rows, sparsify switches, pef bounds) and `HouseStyle` stub.
- `engine/dtypes.py`: arrow-aware dtype classification (date vs datetime split on
  time-of-day), selector resolution, GT alignment ladder, wrap hints.
- `engine/formats.py`: format sugar parsing accepting both csv-grid spec strings
  (`',.1f'`, `'year'`, `'eng'`, strftime) and GT f-strings (`'{x:.1%}'`); the
  salvaged column-statistics float inference; pure `apply_format` incl.
  engineering/SI notation and paren-negative accounting style.
- `engine/structure.py`: the single implementation of hierarchy logic — row break
  depths, stub rowspan layout, header colspan groups, column-group break depths.
- `engine/build.py`: `build(data, spec) -> TableDoc` for DataFrame / Series /
  list / markdown pipe table (caption/`{#tbl-label}`/alignment extracted). Never
  mutates input. Auto neg flags, `$...$` math detection, html_cols, JSON-safe raw
  values (big ints as strings, ISO dates, NaN→null).
- `render/text.py`: the conformance oracle — box-drawing renderer reading only
  the TableDoc: spans, partial rules at break depths, flag gutter, math markers.
- Fixture registry (18 fixtures, all Fabricator-generated or tiny synthetics) with
  committed golden IR and golden text files; 72 tests total.
- `.gitattributes` guards golden files from newline conversion; version now single-
  sourced from `_version.py` (hatchling dynamic).

### Changed

- Deliberate deviations from greater_tables 5.x behavior: engineering format is a
  column-level decision (5.x switched per cell, mixing formats within a column);
  missing values render as an em dash in formatted columns; the >50-row raise is
  replaced by `max_rows` truncation with an appended note; `'all'` selectors cover
  data columns only; format resolution returns data objects, structurally killing
  the 5.x late-binding closure bug.
- pytest cache moved to the V:\dev drive via junction (NAS path denies the cache
  dir creation rename).

## [1.0.0] - 2026-07-30

### Added

- [ir-core] Repo bootstrap: hatchling/uv project, `src/greatest_tables` layout,
  venv on the V:\dev dev drive (junction), design and step plan docs under `dev/`.
- `ir.py`: frozen pydantic models for the table document IR, `ir_version` 1 —
  `TableDoc`, `Column`, `Row`, `Cell`, `HeadCell`, `FormatSpec`. Write model rejects
  unknown fields; the read path (`TableDoc.read()`) ignores them so newer producers
  stay readable. Bare-string cell shorthand supported and canonicalized on dump.
- `engine/hashing.py`: canonical JSON (sorted keys, compact separators, NFC
  normalization, shortest round-trip floats) and `doc_hash` — sha256 over the
  canonical bytes with `hash`/`generator` excluded. Deterministic: no time salt.
- `fabricator.py`: synthetic DataFrame generator ported from greater_tables
  `fabrications.py`. Fixed in transit: `oversample` recursion passed arguments
  positionally-wrong; `random()` had a `'s' 'i'` literal-concatenation typo; the
  documented `missing` parameter now exists and is wired to `_insert_missing`;
  scipy dependency replaced with `rng.negative_binomial`; datetime columns are
  deterministic under a seed (fixed `now` reference passed through, no wall-clock
  reads); dead `random_date_within_last_n_years` (referenced `self` from a
  staticmethod) removed.
- `schema/ir-v1.json`: committed JSON Schema export of `TableDoc`, with a test that
  fails when the models drift from the committed schema.
- Test suite: exemplar golden IR documents (round-trip byte-equality), hash
  stability, read-path must-ignore, Fabricator determinism.

### Notes

- IR `ir_version` is decoupled from the package version and only bumps on breaking
  schema change.
