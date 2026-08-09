# [tikz-tabular] a second TikZ engine: one node, one `tabular`, ~30x faster

## Context

`render/tikz.py` emits every table as a pgf `matrix of nodes`. Measured over the
159 GT tables in the `aggregate-reproductions` book (tectonic, min of two runs,
net of a matched baseline document):

| rendering | total | net ms/table |
|---|---:|---:|
| baseline (text only) | 1.49 s | — |
| `matrix of nodes` (today) | 47.79 s | **291** |
| one node, one `tabular` (prototype) | 2.93 s | **9.0** |

The cost is **per addressable pgf cell node** and nothing else — `nicematrix`
and `tabularray` land in the same band because they also give every cell a
node. GT does not need per-cell nodes: nodes exist only so rules can anchor to
cell corners, and GT already computes every column width itself.

`dev/plan-speedup.md` (written in another project) reached the same conclusion.
This plan supersedes it with three corrections found while prototyping:

1. The win is **~30x, not 200x** — the 2 ms figure came from a synthetic table
   with no `\multicolumn`, no `\cmidrule`, and no real rule count.
2. **The plan solves x and never mentions y.** "GT knows every column width,
   therefore every rule offset" is true for *vertical* rules and false for
   *horizontal* ones — GT cannot know row heights, because cells wrap. The fix:
   **horizontal rules go inside the tabular as booktabs; only vertical rules are
   drawn in TikZ.** Booktabs stops being a rejected alternative and becomes half
   the design.
3. Constraint 3 ("arbitrary vertical rules at an offset spanning a row range")
   is overstated. Across all 159 tables *every* vertical rule runs full height
   (`-1-j.north west` -> `|- name.south`) at exactly half the column separation.
   Full-height rules at gap midpoints are trivial from a single node.

Prototype artifacts (scratchpad, not committed): `translate.py` converted all
159 real tables mechanically; `compare.pdf` shows five of them rendered both
ways. Bottom-aligned headers, multi-level spanners, sparsified stub rowspans and
break rules all reproduce.

### Intended outcome

A second, switchable TikZ engine that produces visually equivalent output ~30x
faster, shipped alongside the existing one so both can be compared side by side
before anything becomes the default.

## Scope decision: one emitter for all tables, not "simple only + fallback"

A "simple tables only" split cuts in the wrong place. Multi-level column
headers, spanners and colspans — the things that read as "complex" — are
*easier* in `tabular` (`\multicolumn` + `\cmidrule`) and *hardest* in the matrix
(overlay `\node`s at `$(a)!0.5!(b)$` plus `apply_spans` widening). A complexity
gate would send exactly the wrong tables down the slow path and leave two sets
of visual bugs to chase.

The only axis on which the new form genuinely differs is **height**: a TikZ node
is one unbreakable box. That is equally true of today's matrix, so it is not a
regression and needs no fallback. And because the engine is a `HouseStyle`
field, a per-table escape hatch exists for free if the soak turns something up.

## Hard requirements

- **Bottom-aligned headers.** Non-negotiable. `p{}` is top-aligned, so every
  header cell must restate its column as `b{}` via `\multicolumn{1}{...}`.
  Enforced by a mechanical test, not by eye.
- **Header horizontal alignment reproduces today exactly**: centered, stub
  headers flush left. Today the matrix's `row N/.style` silently beats
  `column N/.style`, so headers are centered regardless of the column's align.
  The colspec must *not* be the source of header alignment.
- **Row height within ~2% of the matrix**, measured on compiled output.

## Design

### Module layout

| file | role |
|---|---|
| `src/greater_tables/render/tikz_layout.py` | **new.** Shared layout: grid build, cell TeX, width measurement/solve, spans, scale. Moved verbatim out of `render_tikz`. |
| `src/greater_tables/render/tikz.py` | `render_tikz` becomes the dispatcher; today's emitter becomes `render_tikz_matrix`, output byte-identical. Re-exports `table_width`, `TIKZ_PREAMBLE`, `W2TIKZ` (imported by `tests/test_tikz.py` and `render/etcher.py`). |
| `src/greater_tables/render/tikz_tabular.py` | **new.** The one-node emitter. |
| `src/greater_tables/spec.py` | `HouseStyle.tikz_engine: Literal['matrix','tabular'] = 'matrix'`. |
| `dev/tools/compare_engines.py` | **new.** Side-by-side PDF + speed report. |

`layout(doc, style) -> Layout` returns a dataclass carrying `grid`, `widths`,
`aligns`, `overlays`, `spans`, `spanners`, `scale`, `n_head`, `n_stub`,
`body_start`, `n_body`. Everything in `render/widths.py` and
`render/textlength.py` is untouched and now pays off for both engines.

### What the tabular emitter produces

```latex
\providecommand{\I}{\vphantom{lp}}%
\begin{tikzpicture}
\node[inner sep=0pt, scale=1.0] (t) {%
\setlength{\tabcolsep}{0.5em}%
\setlength{\extrarowheight}{0.25em}%
\begin{tabular}{@{\hspace{1em}}>{\raggedright\arraybackslash}p{4.13em}%
                @{\hspace{2em}}>{\raggedleft\arraybackslash}p{4.69em}...@{\hspace{1em}}}
\toprule
\multicolumn{2}{>{\centering\arraybackslash}b{8.41em}}{\bfseries claims} & ... \\
\cmidrule{2-3}
\multicolumn{1}{>{\raggedright\arraybackslash}b{4.13em}}{\bfseries\itshape class\I} & ... \\
\midrule
Class1 & 5.154 & ... \\
\bottomrule
\end{tabular}};
\draw[semithick] ([xshift=6.63em]t.north west) -- ([xshift=6.63em]t.south west);
\end{tikzpicture}
```

### Rule mapping (all verified in the prototype)

| GT rule | matrix today | tabular |
|---|---|---|
| frame top/bottom | `\path` on matrix bbox | `\toprule[w]` / `\bottomrule[w]` |
| head rule | `\path` at row y | `\midrule[w]` |
| row-break rule from column c | `\path` from `-r-c.west` | `\cmidrule[w]{c-ncols}` |
| total/subtotal rule | `\path` from column 1 | `\cmidrule[w]{1-ncols}` |
| spanner underline, extended ±gap | `\path` ±`gap` | `\cmidrule[w]{c0-c1}` — **no trim**, which spans exactly one `\tabcolsep` (= `gap`) each side. Exact match, not an approximation. |
| stub / column-group verticals | `\path` full height | `\draw` from `t.north west`/`t.south west` at a computed `xshift` |

Weight map `W2RULE`: float weight -> pt width matching pgf's line widths
exactly (`0.25 -> 0.1pt`, `0.5 -> 0.2pt`, `0.75 -> 0.4pt`, `1 -> 0.8pt`,
`1.5 -> 1.2pt`, `2 -> 1.6pt`, `3 -> 2.4pt`), alongside the existing `W2TIKZ`.

### Geometry constants to calibrate

Five, all arithmetic, all of which bit me in the prototype:

1. `\tabcolsep = tikz_column_sep / 2` — puts adjacent `p{}` boxes `csep` apart.
2. `@{\hspace{csep}}` at both outer edges — matches column 1's `inner xsep`
   and makes the frame rules span the same width.
3. `@{\hspace{2*csep}}` **between columns 1 and 2** — column 1's `inner xsep`
   applies on *both* sides, so the col1->col2 gap is `2*csep`, not `csep`.
   Getting this wrong moves the stub rule 1 em. (This is open question 2 in
   `plan-speedup.md`; the answer is arithmetic, not a decision.)
4. `\extrarowheight` from `tikz_row_sep`, then tuned to the 2% height target.
   Use `\extrarowheight`, **not** `\arraystretch` — the latter multiplies
   `\baselineskip` and so inflates every line inside a wrapped cell. My first
   attempt used `\arraystretch{1.25}` and a 29-row table grew 34% and fell off
   the page.
5. `\cmidrule` with no trim for spanners (see table above).

### Width model

Per-engine, because the tabular form is genuinely simpler. Everything sits
inside the node, so `scale` scales all of it:

```
tabular:  scale * (sum(widths) + (ncols + 2) * csep)     # ncols >= 2
          scale * (sum(widths) + 2 * csep)               # ncols == 1
matrix:   unchanged — scale*(sum+2csep) + ncols*csep + _RULE_OVERHANG
```

The empirically-fitted `_RULE_OVERHANG = 700` disappears for the tabular engine
(rules sit at the node's own edges). `_fit_budget` takes the width model as a
parameter so the matrix path keeps its exact, tested behavior.

### `\I`

Emitted inline per table as `\providecommand{\I}{\vphantom{lp}}` — idempotent,
and it closes a real defect on the way past: `TIKZ_PREAMBLE` is imported *only*
by `render/etcher.py`, so a table embedded in a Quarto PDF build raises
`Undefined control sequence`, which destroys the enclosing node and spills `lp`
into `nullfont`. `\I` / `vphantom` appears nowhere in `docs/` or `README.md`;
the reproductions book has the `\newcommand` hand-added to its preamble, so
someone has already hit this. It matters *more* in the tabular engine, since
consistent depth is what makes bottom alignment look deliberate.

## Steps

The compare tool lands early, so calibration has a feedback loop.

- **[layout]** Extract `layout()` + `Layout` into `render/tikz_layout.py`.
  Move `_cell_tex`, `_escape`, `_measured`, `_display_milli`, `_token_milli`,
  `_bold`, `_shrink`, `_grow`, `_fit_budget`, `table_width` and the grid/width
  block from `render_tikz`. Pure refactor: `tests/test_tikz.py::test_tikz_golden`
  must still pass byte-identical against all 25 committed goldens.
- **[switch]** `HouseStyle.tikz_engine`; `render_tikz` dispatches to
  `render_tikz_matrix` / `render_tikz_tabular`. Default `'matrix'`.
- **[tabular-engine]** First cut of `render/tikz_tabular.py`: colspec, header
  `\multicolumn{1}{...b{w}}` cells, spanner `\multicolumn{n}` + `\cmidrule`,
  booktabs horizontal rules, TikZ vertical rules, `\providecommand{\I}`.
- **[compare]** `dev/tools/compare_engines.py` — see below. Run it, look at it.
- **[calibrate]** Tune the five constants against the PDF and the height report
  until headers are bottom-aligned, rules land, and height drift is under 2%.
- **[width-model]** Engine-aware `_fit_budget`; verify
  `test_budget_is_never_exceeded` holds for the tabular engine at every budget.
- **[tests]** Goldens + invariants, below.
- **[docs+release]** `docs/` note on `tikz_engine` and the `\I` requirement for
  the matrix engine; CHANGELOG; 6.1.0.

## [compare] the side-by-side deliverable

`uv run python dev/tools/compare_engines.py [--corpus PATH] [--out DIR]`

Inputs, in order of increasing realism:
1. the 25 golden IR docs in `tests/golden/ir/`;
2. a Fabricator sweep (~12 tables) covering multi-level columns, deep stubs,
   prose wrap, math, totals/subtotals, and a deliberately tall table — reusing
   `greater_tables.fabricator.quick_fab` and `tests/registry.py::fixtures`;
3. **optional** `--corpus PATH` pointing at an external rendered book `.tex`
   (e.g. the reproductions book), harvesting `tikzpicture` blocks between
   `\begin{tikzpicture}` and `\end{tikzpicture}`. Read-only, external path,
   never committed — output goes to a gitignored `dev/out/`.

**Output 1 — `compare-engines.pdf`.** One table per page, `matrix` above,
`tabular` below, each labeled with the table name and shape. Rendered on a
deliberately tall page (26 in) so an overflowing table is *visible* rather than
silently dropped — I lost a 29-row table to exactly that in the prototype.

**Output 2 — `compare-engines.md`** (also printed to console):

```
 table          cols  rows   matrix    tabular   speedup   height drift
 loss-dev          6     8    284 ms      8.1 ms     35x    42.1 ->  42.6pt  +1.2%
 fx-both-mi        9    12    377 ms     11.4 ms     33x    88.4 ->  89.9pt  +1.7%
 corpus-016        7    29    612 ms     14.2 ms     43x   470.2 -> 478.1pt  +1.7%
 ---
 159 tables      47.79 s -> 2.93 s      32x overall     drift p90 +1.8%, max +2.4% (1 flagged)
```

- **Timing method** (from `plan-speedup.md`, verified): N copies of the table
  in one document with a realistic preamble; `tectonic -X compile --outdir ...
  -Zcontinue-on-errors`; subtract a matched baseline document of paragraph text;
  **discard the first compile** (tectonic cold start dominates — an early run
  showed an empty baseline slower than 40 tables); two runs, take the minimum.
- **Height/width measurement**: compile each table alone through the existing
  `Etcher` (`documentclass[border=5mm]{standalone}`), then read `/MediaBox
  [0 0 W H]` straight out of the PDF bytes with a regex. Standalone sizes the
  page to the content, so this is exact and needs no new dependency.
- Rows whose drift exceeds 2% are flagged in the report but do **not** fail —
  it is a calibration target to look at, not a build gate.

## Tests

`tests/test_tikz_tabular.py`, new; `tests/make_goldens.py` extended to write
`tests/golden/tikz-tabular/*.tex` for all 25 IR docs.

Structural invariants (cheap, no LaTeX needed):
- **every header cell is `b{`, and no header row contains `p{`** — the
  bottom-alignment requirement, tested mechanically;
- header alignment is `\centering` except stub columns, which are
  `\raggedright` — i.e. *not* taken from the column's align;
- cell count per row equals `ncols` after accounting for `\multicolumn` spans;
- every `\cmidrule` range lies within `1..ncols`;
- `\providecommand{\I}` present exactly once;
- each spanner produces a `\multicolumn{n>1}` and a matching `\cmidrule`;
- `\arraystretch` never emitted (see calibration constant 4).

Reuse/parameterize from `tests/test_tikz.py`: `test_budget_is_never_exceeded`,
`test_budget_respects_the_longest_word`, `test_math_and_escaping`,
`test_nbsp_becomes_tie` and `test_compiles` all become
`@pytest.mark.parametrize('engine', ['matrix', 'tabular'])`.

Regression guard: `test_tikz_golden` must pass unchanged throughout — the
matrix engine's output is byte-identical before and after [layout].

## Out of scope, deliberately

- **Page breaking.** A node is unbreakable, exactly as today. 7 of 159 tables
  exceed 25 rows. The natural follow-on is a bare `tabular`/`longtable` body
  when a table has no vertical rules, but that also needs `Etcher` taught to
  accept input with no `tikzpicture`. A later version.
- **Vertical rules spanning a row range.** Not used anywhere in the corpus;
  the one-node form cannot anchor to rows. Such a table would set
  `tikz_engine='matrix'`.
- **Changing header alignment to follow the column.** Explicitly deferred so
  6.1.0 is a pure speed change, separately revertable from any look change.
- **TikZ externalization.** Needs shell-escape; and at 9 ms/table there is
  nothing left worth caching.

## Verification

1. `uv run pytest tests/ -q` — all green, `test_tikz_golden` byte-identical.
2. `uv run python dev/tools/compare_engines.py` — open `compare-engines.pdf`,
   confirm by eye that headers are bottom-aligned on every page, rules land,
   and column positions match. This is the real acceptance test.
3. `uv run python dev/tools/compare_engines.py --corpus <path to a rendered
   book .tex>` — the 159-table run, for the headline speed and drift numbers.
4. Set `tikz_engine='tabular'` in the reproductions book's config, rebuild, and
   compare the PDF against the current one page by page.

## Release

6.1.0 — both engines live, `matrix` still the default. CHANGELOG entry (Added:
tabular engine + `tikz_engine`; Fixed: `\I` emitted inline; Notes: measured
speedup and the height-drift target). One-line commit,
`6.1.0 add a one-node tabular TikZ engine, ~30x faster, switchable`.
No tag.
