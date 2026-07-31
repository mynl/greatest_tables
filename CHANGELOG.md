# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versioning is semantic.

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
