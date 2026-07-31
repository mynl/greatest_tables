# greater_tables (GT2) — Unified Table Toolkit Design

Approved 2026-07-30. Master reference for all step plan docs (`plan-*.md`).

## Context

Two table tools exist today: **greater_tables** (GT, Python, PyPI v5.3.0 — semantic engine +
HTML/TikZ/text renderers, used in Quarto/JupyterLab/blog) and **csv-grid** (CG, vanilla JS
interactive grid + a Python `to_html` emitter, used by aggregate_api's SPA and fiscus's HTMX app).
GT needs a major revamp: exploration confirmed it has no internal table model (semantics tangled
with rendering across a 2230-line god-class), ~3400 lines of dead/duplicate code, a per-table CSS
blob scoped to a time-salted id (no caching, no golden tests possible), and zero tests. CG is
healthy but has no concept of multi-level headers, rowspans, or row emphasis.

**The goal**: one toolkit where Python owns *semantics* (dtypes, format inference, hierarchy,
spans) and each renderer owns *geometry and style* — serving three table meanings:

1. **Interactive HTML** → csv-grid (lives on, minor additive changes)
2. **Static "book quality" HTML** → GT2 Python renderer (Quarto/JL/blog) *and* GT2 JS walker (SPA)
3. **PDF/TeX via TikZ, book quality** → GT2 TikZ renderer

The hinge is a versioned **JSON IR** (intermediate representation — the "table document"):
`build(df, spec) → TableDoc` in Python; four consumers render it.

## Decisions made (user, 2026-07-30)

- **Naming — DECIDED 2026-07-31 (v1.9.0)**: the package, import, and distribution name are
  `greater_tables`/`greater-tables`; it will publish as **greater-tables 6.0** (same PyPI
  project; 5.3 stays pinnable forever — that is what the major version is for), with a
  `6.0.0rc1` pre-release once aggregate_api adoption settles so the server can pin it
  explicitly while plain installs keep resolving to 5.3. The repo folder keeps the
  development codename `greatest-tables`, so editable-path deps and the V:\dev venv
  junction are untouched.

  **GitHub arrangement (decided)**: the old repo (greater_tables project) stays up
  holding 5.3, archived with a README banner ("frozen at 5.3; ground-up rewrite lives
  at <est repo>, publishes as greater-tables ≥6.0, same import name — pin `<6` for this
  engine"). This repo pushes to GitHub as the est-named repo and carries 6.0-forward;
  its README already explains the name story. PyPI "points" via per-release metadata:
  add `[project.urls]` (Homepage/Repository → the est repo) when pushing to GitHub —
  the 5.3 release page keeps pointing at the old repo, which is correct, and 6.0's
  page points at the new one. Repo name ≠ package name is fine and common.
- **JS walker lives in this repo** — IR schema and renderer version in lockstep; ships as
  ES module + iife and as Python package data.
- **Compat**: thin `GT(df, ...)` constructor-compatible facade (caption/formatters/ratio_cols etc.,
  `_repr_html_`/`_repr_latex_`), not bug-for-bug; exotic config knobs die.
- **Sequencing**: SPA path first — engine + IR + walker + aggregate_api adoption, then notebook
  HTML, then TikZ/blog.
- **Conventions**: generic CLAUDE.md adopted (copied into repo root).
- **Repo home**: `C:/S/AI/greatest-tables`; venv on `V:\dev\greatest-tables\.venv` via junction.
- **Config format**: YAML (single choice for the project, pyproject.toml aside).

## Architecture

```
                    Python: greater_tables
  df / csv / markdown ──► engine ──► TableDoc (pydantic ⇄ canonical JSON, ir_version 1)
                                        │
              ┌─────────────┬───────────┼──────────────┬─────────────┐
              ▼             ▼           ▼              ▼             ▼
         render/html   render/tikz  render/text   JSON over API   (compat GT facade
         (JL/Quarto/   (Quarto PDF, (conformance       │            wraps all of it)
          HTMX frag)    via Etcher)  oracle)           ▼
                                                 js/gt-render.js (walker: IR → DOM,
                                                  optional canvas-measure + solveWidths)
  csv-grid: unchanged role — interactive grids for flat tables (sort/filter/65k rows)
```

**Division of labor for widths**:
- Python HTML renderer emits **no widths at all** — `gt-nowrap` on numeric/date, `max-width` +
  wrap on prose, `table-layout: auto`; the browser measures.
- JS walker optionally runs canvas `measureText` + `solveWidths` (the ~100 pure lines **copied**
  from `C:/S/AI/csv-viewer/src/grid/util.js:358-457`) for constrained containers. Copy, not
  import — CG doesn't export it from dist and the walker stays zero-dep; CI diffs the two copies.
- TikZ keeps character-based estimation (`TextLength`), scoped inside the TikZ renderer only.

## The IR (v1) — summary

Top-level: `ir_version, generator, hash, caption, label, notes, n_stub_levels, n_head_levels,
columns[], head[][], body[], foot[]` (`generator` e.g. `"greater_tables 1.9.0"`, informative,
excluded from hash). Key rules:

- **Column**: `key` ("c0"… positional), `name` (full header path as list — kills lossy `.`-join
  flattening), `role` (stub|data), `level`, `dtype`, `tag` (ratio|year|date|raw), `align` (l|r|c
  hint), `wrap`, `break_depth` (column-group boundary at left edge), `format` (resolved spec),
  `raw` (bool: do body cells carry raw values).
- **Row**: `cells[]`, `break_depth` (shallowest stub level that changed vs. previous row; house
  style maps depth → rule weight), `flags` (closed vocab: total|subtotal|emphasis|muted).
- **Cell**: `text` (plain unicode, unescaped — each renderer escapes for itself), `raw` (opt),
  `rowspan`/`colspan`, `flags` (neg|emphasis|muted), `math` (TeX without delimiters), `html`
  (default false; walker additionally requires `allowHtml` option — injection-safe by default).
  Bare-string shorthand for plain cells halves payload.
- **FormatSpec** (resolved, applicable by Python and ~40 lines of Intl.NumberFormat JS):
  `{kind: int|dec|pct|sci|si|eng|year|date|str, digits, group, scale, prefix, suffix,
  negative: minus|paren, null, zero, pattern}`. Input sugar accepts both CG's spec strings
  (`',.1f'`) and GT's f-strings (`'{x:.1%}'`). `text` is normative; `format` is informative
  (client re-render is advisory — defuses cross-language rounding ties).
- **raw values opt-in, default off** (`include_raw` in spec) — renderer-only paths never pay the
  ~2× payload; aggregate_api's IR endpoint sets `include_raw='data'`.
- **No widths, no rule weights, no CSS, no fonts anywhere in the IR.**
- **Determinism**: `hash` = sha256 over canonical JSON (sorted keys, NFC, repr floats), no time
  salt — enables golden-file tests and caching. No element ids unless Quarto `label` set.
- **Versioning**: readers must ignore unknown fields ⇒ additive fields may only be advisory;
  content-bearing containers (`foot`, body `colspan`) ship in v1 even though rarely used.
  Pydantic write-model `extra='forbid'`, read path `extra='ignore'`; `model_json_schema()`
  exported to committed `schema/ir-v1.json` with a CI diff-guard.

## Python package layout

```
pyproject.toml         # hatchling backend; uv venv symlinked to V:\dev; py >= 3.13
README.md  CHANGELOG.md
dev/                   # plan-*.md working docs → dev/done when complete
src/greater_tables/
  ir.py                # pydantic TableDoc/Column/Row/Cell/HeadCell/FormatSpec (frozen)
  spec.py              # TableSpec (user semantics) + HouseStyle (renderer opinions) — the
                       # split of today's 48-field Configurator
  engine/              # build.py (orchestrator, never mutates df), dtypes.py (+ratio/year/
                       # date/raw tags: list|'all'|regex), formats.py (sugar parsing +
                       # resolution ladder incl. make_float_formatter's column-stats
                       # inference), structure.py (Indexing+Sparsify salvage — break_depths,
                       # rowspans, colspans, ONE implementation), hashing.py
  render/              # html.py, css.py (RULES dict = single source of truth → assets/gt.css
                       # + inline flattener), notebook.py (_repr_mimebundle_, Quarto env
                       # detection), text.py (oracle), tikz.py (single impl + colspan
                       # support; owns TextLength), etcher.py (salvaged, path edges cleaned)
  assets/              # gt.css, gt-render.esm.js, gt-render.iife.js (committed, built by js/)
  compat.py            # GT(df, ...) facade — lazy cached properties (fixes eager-TikZ waste)
  config.py            # pruned; YAML load kept
  fabricator.py        # test-fixture generator (salvaged — drives all synthetic fixtures)
js/src/gt-render.js + build.mjs (esbuild)
tests/fixtures/  tests/golden/ir/*.json  tests/golden/text/*.txt
tests/golden/transcript/*.jsonl  schema/ir-v1.json
```

API: `doc = build(df, spec); render_html(doc); render_tikz(doc, style=...)`; facade
`GT(df, caption=..., ratio_cols=...)` with `.doc/.html/.tikz/str()`. No import side effects
(today's global `warnings.simplefilter('error', RuntimeWarning)` etc. all die). The >50-row
raise becomes `max_rows` truncate-with-note. ~3k lines vs 6.9k today.

## JS walker (gt-render.js)

- `renderTable(docJson, {mount, allowHtml, katex, fit}) → {el, doc, destroy(), toCSV()}` —
  always returns an instance handle (the fiscus lesson; never anonymous fire-and-forget).
- IR → `<div class="gt">` + `<table>`, same `gt-*` class vocabulary as the Python renderer
  (a tested shared contract). No inference, no sort, no filter, no virtualization — **ever**;
  "I want to sort it" means it's an interactive grid → later `irToGridInput(doc)` adapter hands
  it to csv-grid whole (requires `raw` on all data columns).
- Math: injected `katex` object or `\(...\)` fallback for page MathJax. One delegated click
  listener on the instance root → `CustomEvent('gt:cellclick')`, same shape as fiscus's contract.
- Optional fit pass: canvas measure + copied `solveWidths`; forces nowrap+ellipsis everywhere
  (the solver's objective assumes single-line cells — documented, not fudged). Default = natural
  browser layout, identical policy to the Python renderer.
- Ships: esbuild → `assets/*.js`; aggregate_api serves it from the installed package via
  `importlib.resources` (walker and IR emitter cannot version-skew by construction).

## CSS architecture (Python HTML renderer)

- One document-level sheet `gt.css` (~200 lines) generated from a `RULES` dict; `inline_css=True`
  flattens the same dict (fiscus/HTMX/email path) — cannot diverge.
- Selectors double the class (`.gt.gt td`) to beat JupyterLab/Quarto host rules without
  `!important`; markup carries `class="gt"` once.
- Vocabulary: `gt-l/r/c` alignment, `gt-stub/gt-data` roles, `gt-nowrap`/`gt-wrap`,
  `gt-break-{0,1,2}` (tr border-top) and `gt-vbreak-{d}` from break depths, flag classes
  (`gt-total`, `gt-neg`, …), `gt-math`. `tabular-nums` on right-aligned cells.
- Per-table scalars ride as CSS custom properties on the wrapper (`--gt-rule-0`, `--gt-pad-v`,
  `--gt-prose-max`…); house style = the defaults, themes = alternate property blocks.
- Default colors `currentColor`/transparent — an embedded fragment has no color opinion (fixes
  the prefers-color-scheme fights seen in both consumers).
- Stylesheet embedded with every fragment by default (~2 KB, idempotent — safer than
  once-per-kernel for saved/cleared notebooks); `css='once'|'none'` opt-ins.

## csv-grid changes (minimal, additive)

1. `rowFlags: (record, i) => string[]` option → `csvgrid-row-*` classes on tr (+ default styles).
   Removes aggregate_api's sole reason for dual renderers.
2. `workerUrl` option (bundler-safe; kills the `worker:false` Vite hack).
3. `theme: 'light'|'dark'|'auto'` option now; flip default off `auto` only at next major
   (R htmlwidget/iife consumers rely on current behavior).
4. `CsvGrid.VERSION` static; export `solveWidths` from dist (enables the CI drift-check).
5. IR as input shape: **not now** — the `cols[].values` obligation + flattening make it a poor
   fit; the `irToGridInput` adapter in gt-render.js covers it later. fiscus: unchanged.

## Sequencing (SPA path first)

Each step gets a `dev/plan-<label>.md`; moved to `dev/done` on completion.
Each completed step was a feature version bump (1.x.0) with CHANGELOG entry + one-line commit.

**All seven steps are complete** as of 2026-07-31; every plan is in `dev/done` and the
version line moved from the 1.x development counter to the published 6.0 series
(`6.0.0a1`). Remaining open items live in `dev/pending.md`, not here.

- **[ir-core]**: repo bootstrap; `ir.py`, `hashing.py`, `fabricator.py`; fixture registry;
  golden IR JSONs (byte-equal); committed `schema/ir-v1.json` + CI guard; hash-stability test.
- **[engine]**: `engine/` complete against goldens; `render/text.py` reads only the TableDoc
  (anything it can't draw = data missing from the IR); golden `.txt` files.
- **[walker]**: `css.py` RULES → `gt.css` (walker needs the class contract);
  `js/src/gt-render.js`; DOM-transcript conformance harness (walker run in node under linkedom,
  emits one JSON line per cell `{r,c,tag,colspan,rowspan,classes,text}` → `golden/transcript/`).
- **[aggregate-api]**: IR endpoint (`?format=ir` or Accept-negotiated) with
  `include_raw='data'`, serializers stop flattening the MultiIndex on this path; serve walker
  from installed package; static toggle renders via `renderTable`; **delete the BeautifulSoup
  post-pass** (row emphasis now `row_flags` in the spec); keep csv-grid for interactive/65k rows.
- **[notebook-html]**: `render/html.py` must byte-match the walker's DOM transcripts;
  `_repr_mimebundle_` (TikZ only when requested/Quarto-detected); `compat.GT`.
- **[tikz-blog]**: single TikZ impl from TableDoc with colspan support (new capability; today's
  silently returns `''` on non-unique columns); Etcher (paths cleaned); validate by rendering a
  sample of real blog tables through both packages and diffing text-oracle output.
- **[backlog]**: csv-grid additive release (still open, in the csv-grid repo); `irToGridInput`
  adapter (done, 1.8.0); publish-name decision (done, 1.9.0 — `greater-tables` 6.0).

## Verification

- **Golden IR**: byte-equal canonical JSON per fixture (deterministic hash makes this possible).
- **Conformance**: Python HTML (parsed via stdlib html.parser) and JS walker (node + linkedom)
  must produce identical DOM transcripts per fixture; text oracle rides alongside as the
  human-readable check. Math cells recorded as TeX source (walker run without katex).
- **End-to-end ([aggregate-api])**: run dev servers, load a portfolio, toggle
  static/interactive — book-quality table renders client-side from the IR endpoint, row
  emphasis present without the bs4 pass; compare against the old `?tables=gt` output.
- **Migration check ([tikz-blog])**: side-by-side render of representative blog tables, GT 5.x
  vs GT2 facade, eyeball HTML + diff text output.

## Salvage map (critical existing files)

- `C:/S/TELOS/Python/greater_tables_project/greater_tables/utilities.py` — Sparsify (:456),
  Indexing (:489) → `engine/structure.py`; TextLength (:220) → `render/tikz.py`; Escaping (:108)
  → renderer-side escaping.
- `.../core.py` — format ladder + `make_float_formatter` (:443, column-stats digits + eng
  fallback) → `engine/formats.py`; live `make_tikz` (:1660) knowledge → `render/tikz.py`.
- `.../config.py` — 48-field Configurator → split into TableSpec/HouseStyle (5 dead fields,
  `tabs`, width machinery deleted).
- `.../etcher.py`, `.../fabrications.py` — carried over.
- `C:/S/AI/csv-viewer/src/grid/util.js` — `solveWidths` (:358-457) copied into walker;
  format-spec string language (:42-119) adopted as input sugar.
