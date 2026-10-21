# [retire-matrix] Remove the `matrix` TikZ engine

Status: drafted 2026-10-21 at 7.6.2. Steve ruled the retirement the same day: "From the tables
you have produced that is no longer needed." Runs before `dev/plan-markdown-cells.md`, so that
plan ports markdown to one TikZ engine, not two.

## Goal

One TikZ engine, the `tabular` one, and none of the code that existed only to let two engines
share a layout. The tabular output does not change by a byte.

## Current behavior

- `HouseStyle.tikz_engine: Literal['matrix', 'tabular'] = 'tabular'` picks the emitter, and
  `render.tikz.render_tikz` dispatches on it.
  - `'matrix'`, the original renderer: `render/tikz.py` (`render_tikz_matrix`, `_emit`), a pgf
    `matrix of nodes` with one node per cell. It has been off by default since 6.2.0.
  - `'tabular'`: `render/tikz_tabular.py`, one real `tabular` inside a single node.
- **Speed.** On DOOB with tectonic, over 48 tables: matrix 9.56s, tabular 0.73s, against 0.63s
  for an empty document. That is about 190ms against 2ms per table, on every TeX pass.
- **Three matrix defects**, recorded as strict expected failures in `tests/test_tikz_geometry.py`
  rather than fixed, because the matrix output was held byte-identical to 6.1.0:
  1. its group labels ignore `tikz_scale`;
  2. its verticals run through group labels at break depth 1 or more;
  3. its verticals stop 1.4pt short of the bottom frame.

  The tabular engine has none of them.
- **The spec docstring keeps matrix for two reasons:** output byte-identical to 6.1.0, and
  `tikz_post_process` TeX that addresses cells by node name. Neither has a user. A search of
  `V:\dev` and `D:\projects` (`.py`, `.qmd`, `.ipynb`, `.yml`, `.yaml`) finds no `tikz_engine`
  setting outside this repository. PMIR's `pmir-gt-format.yaml` sets `tikz_post_process: ''`,
  which the tabular engine honors as well.
- **Shape the matrix forced on shared code**, all in `render/tikz_layout.py`:
  - a `Geometry` class with `MATRIX_GEOMETRY` and `TABULAR_GEOMETRY`, because a matrix pays for
    its column separations outside its scaled node, plus `_RULE_OVERHANG`, the matrix's rules
    hanging past its bounding box;
  - `Layout.grid` starts with the matrix's zero-height spacer row, and `overlays` and
    `body_start` count matrix rows. The tabular emitter undoes both: `lay.grid[1:]` and row
    offsets.
- **Elsewhere:**
  - 43 matrix goldens in `tests/golden/tikz/`;
  - matrix-only tests in `tests/test_tikz.py`, `test_rules.py`, `test_compat.py` and
    `test_tikz_geometry.py`;
  - the matrix panel in the gallery;
  - the "Two TikZ engines" section of `docs/quickstart.rst`;
  - matrix passages in `docs/design.rst` and `docs/migration.md`;
  - `dev/tools/compare_engines.py`.

## The change

### [api] One engine, and a clear error for the old one

- `spec.py`:
  - `tikz_engine: Literal['tabular'] = 'tabular'`. `__post_init__` raises `ValueError` for any
    other value, and for `'matrix'` says: "the matrix TikZ engine was removed in 8.0.0; tabular is
    the only engine. Pin greater-tables<8 to keep it."
  - The field is kept so that a config naming `tabular` still loads, and so that a config naming
    `matrix` fails with that message, not a `TypeError` about an unknown field.
  - The docstring is rewritten for one engine.
- `tikz_post_process`: its docstring drops the matrix sentence. Post-processing TeX can address
  the table's one node, `gt<hash>`.
- `render/tikz.py` keeps the public entry points:
  - `render_tikz` now calls the tabular emitter directly;
  - `TIKZ_PREAMBLE` (`\I`, which the tabular head cells use) and the `W2TIKZ` re-export stay;
  - `table_width` stays and computes the tabular's width;
  - `render_tikz_matrix` and `_emit` are deleted;
  - `render_tikz_tabular` stays in `__all__`, so existing imports keep working.

### [layout] The shared layout becomes the tabular's layout

- `Geometry`, `MATRIX_GEOMETRY` and `_RULE_OVERHANG` go. The tabular decomposition becomes two
  plain functions or constants that `_fit_budget`, the heading balance and `table_width` call:
  - inner: `(ncols + 2) * csep`, or `2 * csep` for one column;
  - unscaled: 0.
- `layout(doc, style)` loses its `geom` parameter.
- `Layout.grid` loses the spacer row. Head rows are `0 .. n_head - 1`, body rows follow, and
  `overlays` and `body_start` use those indices. `tikz_tabular.py` drops `lay.grid[1:]` and its
  offsets.
- The module docstrings of `tikz_layout.py`, `tikz.py` and `tikz_tabular.py` lose the two-engine
  story.

### [tests]

- **Goldens:** `tests/golden/tikz/` (43 files) and the matrix pass in `tests/make_goldens.py` are
  deleted.
- **`tests/test_tikz.py`:**
  - The matrix-only tests go: `test_tikz_golden`, `test_structure_loss_dev`,
    `test_alignment_is_flush`, and the matrix `test_compiles`.
  - The width tests stay, pointed at the tabular output, with `widths()` reading `p{...em}` and
    `emitted()` using the tabular width. These are the budget, scale-ceiling, label, prose
    minimum, face, bold-row and heading-balance tests.
  - A test that `tests/test_tikz_tabular.py` already holds in the same form is dropped, not
    duplicated (`test_budget_is_never_exceeded`).
- **`tests/test_tikz_geometry.py`:**
  - `ENGINES` and the engine parameter go, and so do `MATRIX_SPANNER` and `MATRIX_SHORT`.
  - `test_engines_leave_the_same_room_under_the_head` compared the two engines. It becomes an
    absolute check: at least 3pt between the lowest heading and the head rule. Tabular measures
    3.4pt and matrix measured 3.5pt.
- **`tests/test_rules.py`:** two tests count `\path[draw` in matrix output with every other rule
  weight zeroed. They count the tabular's body rule commands instead, `\midrule` and `\cmidrule`
  between body rows, with the same zeroed weights.
- **`tests/test_compat.py`:** the matrix assertion becomes a check that
  `HouseStyle(tikz_engine='matrix')` raises, naming 8.0.0.

### [docs-guide]

- **`docs/quickstart.rst`:**
  - "Two TikZ engines" becomes a short "The TikZ renderer" section.
  - The note about the matrix's `\I` strut on the Quarto PDF path goes.
  - "Packages" names what the tabular needs: `tikz`, `booktabs` and `array`, and no TikZ library.
    That claim is checked under Acceptance.
- **`docs/design.rst`:** the engines passage records the tabular as the engine and the matrix in
  one sentence of history: retired in 8.0.0, and why (the per-node cost).
- **`docs/migration.md`:** the `tikz_scale` row and its footnote describe the tabular, where
  everything inside the one node scales. The matrix description, where column separations did
  not scale and rules overhung by about 0.7em, goes.
- **The gallery:**
  - `guide/panels.py` shows HTML and one TikZ panel.
  - `guide/gallery.qmd` drops its "two engines" text, and both PDF headers drop
    `\usetikzlibrary{matrix,calc,fit}` and the `\I` line.
- **`render/etcher.py`:** its docstring drops the matrix. Its library list is left alone: loading
  an unused library costs nothing, and a user's `tikz_post_process` may rely on one.
- **Deleted:** `dev/tools/compare_engines.py`.
- **`dev/pending.md`:** the [gallery] section, whose one remaining item is the matrix, is deleted.
- **Not touched:** `guide/cheatsheet.qmd` is Steve's work in progress. Lines 51, 115 and 174
  mention `tikz_engine` and the matrix; Steve updates them.

## Files

| File | Step | Change |
|---|---|---|
| `src/greater_tables/spec.py` | [api] | `tikz_engine` narrowed and validated; docstrings |
| `src/greater_tables/render/tikz.py` | [api] | matrix emitter deleted; entry points kept |
| `src/greater_tables/render/tikz_layout.py`, `tikz_tabular.py` | [layout] | one geometry, no spacer row |
| `src/greater_tables/render/etcher.py` | [docs-guide] | docstring |
| `tests/test_tikz.py`, `test_tikz_geometry.py`, `test_rules.py`, `test_compat.py`, `make_goldens.py` | [tests] | as above |
| `tests/golden/tikz/` | [tests] | deleted |
| `docs/quickstart.rst`, `docs/design.rst`, `docs/migration.md` | [docs-guide] | one engine |
| `guide/panels.py`, `guide/gallery.qmd` | [docs-guide] | one TikZ panel |
| `dev/tools/compare_engines.py` | [docs-guide] | deleted |
| `CHANGELOG.md`, `src/greater_tables/_version.py`, `dev/pending.md` | all | the bump |

## Version and output

**8.0.0**, a major version: `tikz_engine='matrix'` and `render_tikz_matrix` were public, and
both are gone. The CHANGELOG puts the breaking change first and gives the pin for anyone who needs
the old engine. Rendered output of the default, and only, engine does not change.

## Acceptance

- Every `tests/golden/tikz-tabular/` file is byte-identical before and after. That is checked
  after [layout] as well as at the end, since the row renumbering is the step that could move
  output.
- `uv run pytest` passes with no expected failures left; the 13 matrix ones are gone.
- `HouseStyle(tikz_engine='matrix')` raises `ValueError` naming 8.0.0 and the pin.
- `rg -i matrix src/` finds only that message and one line of history in a docstring.
- A tabular table compiles in a document whose preamble loads `tikz`, `booktabs` and `array` and
  no TikZ library. That makes the quickstart's Packages claim a test.
- The gallery renders in all four formats with no TeX errors, each table showing HTML and one
  TikZ panel.
- `src/greater_tables/render/` is about 200 lines shorter.

## Consumers

None known: no project under `V:\dev` or `D:\projects` sets `tikz_engine`. House style's
`house-common.tex` already describes the tabular emitter and loads no matrix library. A published
document that asked for the matrix would stop with the message above; rebuilding it on 7.x, or
dropping the setting, restores it.

## Execution log
