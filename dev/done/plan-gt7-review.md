# [gt7-review] Get 7.0 sorted: a guide, a gallery, correct rules, correct widths

Status: drafted 2026-10-20 at 7.0.0 (`fe22956`); executing from 2026-10-21. The punch list Steve asked for after a long gap
away from the project, written so a fresh reader can execute any step without the conversation.
Steps are independent of one another except where a step says it depends on the gallery.

## Goal

greater_tables 7.0 works, is used daily through house style (`D:\Projects\house-style`, whose
`house_style()` returns a `HouseStyle`; the two names are distinct) and the aggregate Loss Lab,
and has not been looked at as a whole since the 6.0 rewrite. Four things want doing:

1. Steve needs to be able to use it without asking. The 6.0 rewrite replaced the 5.3 constructor
   and `Configurator` with two objects, `TableSpec` and `HouseStyle`, and the split has never
   stuck.
2. The test corpus needs to cover the shapes real documents use, chiefly deep row indexes, and
   there needs to be one place to look at every shape rendered to HTML and PDF side by side.
3. Vertical rules in the default `tabular` TikZ engine have been seen landing in the wrong place.
4. PDF tables have been seen coming out too wide.

Inline markdown in cells (`*em*`, `**strong**`, `` `code` ``) is a separate plan,
`dev/plan-markdown-cells.md`.

## Current behavior

- **Docs.** `docs/quickstart.rst` is the how-to, `docs/design.rst` the how-it-works, and
  `docs/migration.md` the complete 5.3 option map, 47 fields long. None of them is the one-screen
  answer to "which object does this option go on, and what was it called in 5.3". Steve's own
  notes on the subject are `human-hints.md`, a practice he has retired, and
  `dev/writedown-examples.qmd`, a scratch check of his understanding.
- **Fixtures.** `tests/registry.py` holds 26 fixtures. Row indexes go to three levels
  (`fx-row-mi-3`, `fx-deep-stub`), column groups to two. There is no fixture with a total row
  inside a grouped index, none that overruns a width budget, and none with four stub levels.
  `dev/check-widths.qmd` is the standing visual review for widths only, with a generic Quarto
  preamble (newtxtext, article, tectonic). `dev/tools/make_example_qmd.py` generates a 20-recipe
  Quarto file in the blog's format.
- **Vertical rules, tabular engine.** `render/tikz_tabular.py` draws each vertical as a TikZ
  `\draw` from the node's north-west corner at an x it computes: the column separation, plus the
  widths of the columns to the left rounded to the two decimals TeX sees, plus the gaps between
  them, with a special case for column 1, which carries a double gap. The horizontal rules are
  booktabs rules inside the tabular, so TeX places them. The tests compile every fixture and check
  the TeX structurally; nothing measures where a drawn rule lands against the cells.
- **Widths.** `HouseStyle.max_table_width_em` defaults to None, so a bare `GT(df)` in a PDF gets
  natural widths and no narrowing at all. House style sets it to the text width, 41.4em for a
  document and 34.7em for a slide, with `tikz_scale=0.9`. The estimator assumes Times metrics and runs tight in other faces, and a
  number can break at a hyphen when an estimate falls short. Those two are the subject of
  `dev/plan-font-metrics.md`, drafted 2026-10-19 and unruled.

## The change

### [guide] A cheat sheet page in the docs

One short page, `docs/cheatsheet.md`, first in the toctree after the quickstart. It states the one
question that decides where an option goes (does it change the table, or how the table is drawn),
draws the pipeline in four boxes, and then gives a table of the fifteen or so things Steve
actually does, each as "I want", "5.3", "7.0". It is a page to keep open, not a reference: the
reference is the migration page, which it links. The page is also the seed of the blog post
below. No version bump; a docs commit.

Done in the first session. Steve reviews it. Every question the page fails to answer is either a
line to add or an API smell to fix.

### [gallery] One Quarto document rendering every shape to HTML and PDF

A new `dev/gallery/` holding `gallery.qmd` and a committed copy of house style under
`_extensions/house/`, installed with `quarto add D:\Projects\house-style` from that directory, as
house style prescribes for a standalone note. House style does not live in the GT repo in spirit,
but a standalone note has no other way to find it, and house style's own README says to commit the
installed copy. `dev/gallery/_output/` and the freeze directories are gitignored.

The document declares four formats: `house-pdf`, `house-html`, `pdf` and `html`. The first two
render through house style, the last two through the blog's generic setup, the preamble lifted
from `dev/check-widths.qmd`. The Python setup cell tries `from style import GT`, house style's
wrapper with the house budget, and falls back to `greater_tables.GT` with an explicit
`HouseStyle(max_table_width_em=...)` for the generic formats. Render one format at a time:

```powershell
$env:QUARTO_PYTHON = "V:\dev\greatest-tables\.venv\Scripts\python.exe"
quarto render dev\gallery\gallery.qmd --to house-pdf
quarto render dev\gallery\gallery.qmd --to pdf
```

One section per shape, each with one Fabricator table and two or three lines on what to look for.
The shapes, all seeded so the file reproduces exactly:

- flat index, hidden; flat index, shown and named
- row index at 2, 3 and 4 levels, sparsified; the 3-level one again with `sparsify=False`
- `max_rule_depth` at `'auto'`, `0`, `1` and `None` on the 3-level index
- total and subtotal rows: a total at the foot of a flat table, subtotals inside groups of a
  2-level index, both via `row_flags`
- column groups at 2 and 3 levels, with `max_vrule_depth` at `1`, `0` and `None`
- both hierarchies together, the aggregate Loss Lab shape
- numbers: integers, uniform-decimal floats, engineering SI, aligned exponents, negatives, nulls,
  ratios, years, dates and datetimes
- prose: a long wrapping column beside numbers; two prose columns sharing a budget
- width: a table that fits, one that narrows to fit, one that steps the scale ladder, one that
  cannot fit and overruns
- math in body, header, caption and notes beside currency
- a 60-column-wide-ish stress table, and a 250-row table truncated at `max_rows`

**Every table is shown in all three renderings: HTML, TikZ `matrix`, and TikZ `tabular`** (the
default since 6.2.0). A helper in the setup cell takes one `(data, spec)` pair and emits, per
format:

- **PDF formats:** the table twice, labeled, `HouseStyle(tikz_engine='matrix')` above
  `tikz_engine='tabular'`, in the real text block, so width against the margins is judged here.
- **HTML formats:** a three-panel row: the HTML table, then each engine's TeX compiled
  standalone by `Etcher` and converted to SVG with `pdftocairo -svg` (poppler; on PATH through
  MiKTeX). The helper calls `pdftocairo` itself, because `Etcher.compile(svg=True)` expects a
  two-argument `pdf2svg`. `Etcher` sets its standalone page in Times at 11pt, so the images are
  for structure (rules, alignment, spans, wrapping), not for width against a text block.

Compiles cache by content hash, so a re-render recompiles only the tables that changed. The
gallery shows 7.x only; there is no 5.3 comparison (Steve, 2026-10-21: judge afresh).

Every shape in the gallery that is not already a fixture becomes one in `tests/registry.py`, with
goldens blessed by `tests/make_goldens.py`, so the gallery and the suite cannot drift. The
Fabricator vocabulary file (`data/tex_list.csv`, half the wheel) stays as it is.

Replaces `dev/check-widths.qmd`, whose sections move into the gallery, and
`dev/tools/make_example_qmd.py`, whose recipes do the same. Both are deleted when the gallery
renders in all four formats. `dev/tools/compare_engines.py` stays for its timing report; its
matrix-above-tabular PDF is superseded by the gallery.

### [vrules] Vertical rule placement in the tabular engine, measured

This step is made apparent by tests, not by eye. A new test module, `tests/test_tikz_geometry.py`,
compiles a fixture with tectonic, opens the PDF with `pdfplumber` (a new entry in the `dev`
dependency group, pure Python, it reads lines and glyph boxes with coordinates), and checks:

- every vertical rule's x lies in the gap between two columns' glyph boxes, and the stub rule
  lies between the last stub column and the first data column;
- every vertical rule's top and bottom coincide with the frame rules to within half a point;
- no vertical rule lies on top of a glyph.

The same harness measures the matrix engine, so the two engines are held to the same geometry.
Whatever the measurements show is then fixed in `render/tikz_tabular.py`. The likely suspects are
the column-1 double gap and the `_FRAME_PAD` inset. Horizontal rules are checked the same way at
every `max_rule_depth` on the 3-level fixture: a rule between every pair of rows whose break depth
qualifies and nowhere else.

Depends on the gallery for the deep-stub fixtures; the harness itself does not. Version 7.0.1 if
the only change is a fix, 7.1.0 if the emitter's geometry changes visibly.

### [widths] Why PDF tables come out too wide

Four causes, in the order to check them, and "just look and see" is the brief:

1. **No budget.** A call outside house style gets `max_table_width_em=None`. **Ruled (Steve,
   2026-10-21): the default stays None and the budget is set by the target output.** House style
   already does this, 41.4em for a document and 34.7em for a slide. A library number is wrong
   somewhere: the stock `article` class at 11pt is about 33em, a US letter page with 1-inch
   margins about 43em, and 5.3's 8 inches (about 52em) was wider than both, a sanity cap rather
   than a fit. The cheat sheet and the blog post say to set it.
2. **A silent overrun.** Numbers never wrap, so a table of enough number columns overruns its
   budget once the scale ladder reaches 0.6. Measured at 7.0.0 through house style's `GT`, a 4-row
   table of values in the millions against 41.4em: 8 columns set at scale 0.9, 12 at 0.65, 16 at
   0.6, and 20 at 0.6 overruns, at 46.8em of column width before separations.
   `tikz_layout._fit_budget` logs both the ladder step and the overrun at WARNING, and house style
   sets the `greater_tables` logger to ERROR to hide the ladder steps, which its comment calls
   "the design working, not a fault". That hides the overrun too. Fix: the overrun logs at ERROR,
   the ladder step stays at WARNING. One line, a patch bump, with a test that the overrun record
   is at ERROR.
3. **The estimate is tight in a non-Times face.** `dev/plan-font-metrics.md` [font-metrics].
4. **A number breaks at a hyphen.** `dev/plan-font-metrics.md` [numbers-hold].

The gallery's width section is where "look and see" happens. Then execute the font-metrics plan,
once its open questions are ruled; the questions are at its foot and are short.

### [housekeeping]

- `dev/plan-column-widths.md` finished its deliverables at 6.0.0a8. Move it to `dev/done/`.
- `dev/pending.md` was last reviewed at 6.0.0a4 and still carries the 6.0 publish, RTD and CI
  sections. Delete what is done, keep [formats] until the font-metrics plan lands it, and keep
  [ci] and [cookbook]; the cookbook item is answered by the gallery.
- `human-hints.md` is retired. Anything in it still true goes to the cheat sheet or the
  CHANGELOG, and the file is deleted. (The project `CLAUDE.md` line saying to leave it alone is
  updated in the same commit.)
- `dev/writedown-examples.qmd` was a scratch check and is deleted once the gallery covers its
  cases.

### [blog] "Using greater_tables 7" on the blog

A post on ConvexConsiderations, written after the gallery exists so it can lift tables from it.
It is the permanent home for the things Steve always forgets: the one question, the cheat-sheet
table, the width budget and scale ladder, the two TikZ engines, math and currency, the Quarto
bundle. The cheat-sheet page is its first draft. Out of scope for this repo beyond pointing to the
gallery; tracked here so the sequence is visible.

## Files

| File | Step | Change |
|---|---|---|
| `docs/cheatsheet.md`, `docs/index.rst` | [guide] | new page, toctree entry |
| `dev/gallery/gallery.qmd`, `dev/gallery/_extensions/house/` | [gallery] | new |
| `tests/registry.py`, `tests/golden/*` | [gallery] | new fixtures and goldens |
| `dev/check-widths.qmd`, `dev/tools/make_example_qmd.py` | [gallery] | deleted when superseded |
| `tests/test_tikz_geometry.py`, `pyproject.toml` | [vrules] | new module; `pdfplumber` in the dev group |
| `src/greater_tables/render/tikz_tabular.py` | [vrules] | whatever the measurements say |
| `src/greater_tables/render/tikz_layout.py`, `tests/test_widths.py` | [widths] | overrun at ERROR |
| `dev/plan-font-metrics.md` | [widths] | executes as its own plan |
| `dev/done/plan-column-widths.md`, `dev/pending.md`, `human-hints.md`, `CLAUDE.md` | [housekeeping] | move, prune, delete |

## Acceptance

- [guide] Steve reads the cheat sheet and can answer "spec or style?" for every option on it
  without opening another page.
- [gallery] `quarto render dev\gallery\gallery.qmd --to <f>` succeeds for all four formats, and
  every new shape has a fixture whose goldens pass.
- [vrules] The geometry tests pass on every fixture in both engines, and a deliberate one-step
  error in the x arithmetic makes them fail.
- [widths] An overrun logs at ERROR and shows through house style's logger setting; the
  font-metrics plan executed or explicitly deferred.
- [housekeeping] `git status` clean of the three untracked files; `dev/` holds only unstarted plans.

## Execution log

- 2026-10-20: plan written; [guide] delivered the same session as a docs commit.
- 2026-10-21: [widths] default budget ruled (stays None, set per target) and the silent
  overrun added as cause 2; [gallery] shows every table in HTML and both TikZ engines; markdown
  in cells split out to `dev/plan-markdown-cells.md`. The cheat sheet has moved to
  `guide/cheatsheet.qmd` with house style installed beside it, uncommitted: Steve's work in
  progress.
- 2026-10-21: execution started (Steve: "run the GT7 plan"). [widths] cause 2, the silent
  overrun, fixed in 7.0.1.
