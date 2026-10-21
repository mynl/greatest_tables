# Pending — greater_tables

Open items only; delete a section when it is done, not when it is decided.
Completed work is recorded in `CHANGELOG.md`, plans in `dev/done`. Last
reviewed 2026-10-21 at 7.4.0.

## [gallery] Defects the gallery shows, not yet planned

From `dev/done/plan-gt7-review.md`, Findings (2026-10-21); the plan holds the
detail and the fixture for each.

1. Quarto adds `table table-sm table-striped small` to GT's HTML table, and
   `gt.css` does not reset Bootstrap's striping shadow or the smaller font:
   every Quarto HTML page with a GT table is striped. Emit
   `data-quarto-disable-processing="true"`, or reset in `render/css.py`.
2. A headerless table gets a doubled top rule, both engines.
3. Matrix engine: spanner labels ignore `tikz_scale`; verticals cross spanner
   labels at break depth 1 or more and stop 1.4pt short of the bottom frame
   (strict expected failures in `tests/test_tikz_geometry.py`). Held because
   the matrix output is byte-identical to 6.1.0 by design; fix or retire.
4. The estimate is Times; under STIX Two prose wraps at its natural width,
   and so do labels held at it ("Unit 1" in `wide-lab`). The main defect left
   in house-style PDFs. `dev/plan-font-metrics.md`.

## [head-balance] Long headings over narrow data — proposal, Steve to rule

A column is as wide as its heading's longest word, so a six-word heading over
a Y/N column stacks four or five lines deep however much room the table has
(gallery section "Long headings", the `long-head-*` fixtures). Proposed rule
for the TikZ layout: with a budget, spend spare width on the column whose
heading has the most lines, widening it just enough to drop a line, until the
room runs out or every heading fits in two lines; without a budget, widen
each to the narrowest width that sets its heading in three. About 60 lines in
`render/tikz_layout.py` plus tests; it changes widths, and so output, for any
table with a long heading. HTML not yet compared: the browser sizes columns
itself.

## [rtd-slug] Read the Docs slug — **open, Steve to decide**

The 6.0 docs publish under the existing **`greater-tables-project`** slug, so
every URL in `pyproject.toml`, `README.md` and `docs/index.rst` points there.

The plan of 2026-07-31 was `greater-tables`, matching the name people
`pip install`. That did not happen, and **an RTD slug cannot be renamed** —
it is fixed from the project Name at creation and the Name field afterwards
is cosmetic. Getting `greater-tables` means creating a *new* RTD project with
that exact Name (the import form prefills the repo name, `greatest_tables`,
so it has to be overridden at that moment), then repointing five URLs:

- `pyproject.toml` — `Documentation` and `Changelog`
- `README.md` — the migration link, the Documentation section, the RTD badge
- `docs/index.rst` — the RTD badge

Because the first two are PyPI release metadata, that change needs a version
bump; PyPI will not accept a re-upload of an existing version. 6.0.0 and
7.0.0 both shipped under the old slug.

## [artwork] Optional: an example figure for the docs landing page

The GT2 logo and favicon set in `docs/_static/` are final (confirmed
2026-08-05) and wired up via `html_logo` / `html_favicon`. What is still
missing is a `docs/img/` example figure — the 5.x docs led with one — now
that the demo tables are settled. `demo.html` and `demo2.html` are the
obvious sources. Nice to have, not a release blocker.

## [ci] GitHub Actions

Nothing runs on push yet, and the docs no longer claim otherwise (6.0.0b1
reworded two "in CI" claims to "the test suite"). Minimum useful workflow:
`uv sync`, `pytest` (428 tests, ~25 s) on 3.12/3.13/3.14, `npm run build` +
a walker transcript check, and the `schema/ir-v1.json` diff guard. The 3.12
floor in `pyproject.toml` is **declared but untested** — a matrix build is
what would actually verify it. Unblocked: the repo is public. The suite now
compiles TeX (tectonic) and reads PDFs (pdfplumber), so CI needs tectonic
or must skip those tests, as they already do when it is missing.

