# Pending — greater_tables (GT2)

Open items that are not step plans (those are `plan-*.md`). Dated
2026-07-31, v1.10.0. Delete a line when it is done, not when it is decided.

## [rtd] Set up Read the Docs — **PENDING, Steve to action**

The docs tree, `.readthedocs.yaml`, and the `docs` extra are all in place and
build clean locally (`uv sync --extra docs`, then `docs\make.bat html`).
What remains is account-side and cannot be done from here:

1. Push this repo to GitHub (`mynl/greatest_tables`, remote already set).
2. On readthedocs.org: **Import a Project** → `mynl/greatest_tables`, and set
   the project slug to **`greater-tables`** (decided 2026-07-31 — the docs URL
   should match the name people `pip install`, not the repo codename). GT 5.x
   keeps `greater-tables-project`, so there is no clash.
3. Confirm the build picks up `.readthedocs.yaml` (Python 3.13, `pip install
   .[docs]`, PDF format on).
4. Check the resulting URLs, which are already baked into `pyproject.toml`
   and both READMEs:
   - https://greater-tables.readthedocs.io/en/latest/
   - https://greater-tables.readthedocs.io/en/latest/versions.html
5. Add the RTD webhook (automatic on GitHub import) so pushes rebuild.

## [artwork] Replace the placeholder docs artwork

`docs/_static/greater-tables-logo.png` and `favicon.ico` are copies of the
5.x artwork, standing in until Steve draws the GT2 set. Also worth adding a
`docs/img/` example figure (the 5.x docs led with one) once the demo tables
are final — `demo.html` and `demo2.html` are the obvious sources.

## [publish] greater-tables 6.0 on PyPI

Sequenced after [aggregate-api] adoption settles: cut `6.0.0rc1` first so the
server can pin it explicitly while plain installs still resolve to 5.3, then
6.0.0. Pre-flight: `uv build`, check the sdist/wheel contents, `twine check`,
confirm the README renders on the PyPI preview, and confirm 5.3's frozen repo
banner still points at the right place.

## [python-floor] Reconsider `requires-python = ">=3.13"`

Reported upstream by aggregate_api (their `dev/TODO.md`): the 3.13 floor
forced *their* floor up from 3.11, and nothing in this source obviously needs
3.13 (no PEP 695 syntax, no 3.13-only stdlib). 5.3 shipped `>=3.10`, so a
published 6.0 with a 3.13 floor is a real adoption tax. Proposal: drop to
3.11 or 3.12, verified by running the suite under `uv run --python 3.11`
before changing the metadata (and add the matching classifiers). Steve's
call — it is a published-metadata decision, not a code one.

## [raw-coverage] `include_raw` vs `irToGridInput` — two reported gaps

Both from the aggregate_api adoption; the first is filed in full as
`dev/note-from-aggregate-api-include-raw.md`.

1. **String data columns throw.** `include_raw='data'` resolves to numeric,
   date and bool data columns, but `irToGridInput` demands raw on *every*
   data column and throws on the first string one — so the documented pairing
   fails on any frame with a string column outside the stub (3 of their 12
   frames). Their workaround is the explicit list form. Preferred fix, and I
   agree with it: have the adapter fall back to `cell.text` for a string
   column, since a string's formatted text *is* its value and there is
   nothing to re-infer. Also make the error name a fix that is not what the
   caller already did.
2. **Stub columns carry no raw at all**, so a numeric index reaches the grid
   as text and sorts lexically (10, 2, 200). Wanted: `include_raw='all'`, or
   extend `'data'` to cover stubs.

Worth deciding both at once, since they are the same knob. Note also that
`include_raw=True` currently behaves as `'data'` while the `TableSpec`
docstring reads broader — fix the docstring or the behavior.

## [ci] GitHub Actions

Nothing runs on push yet. Minimum useful workflow: `uv sync`, `pytest`
(159 tests, ~20 s), `npm run build` + a walker transcript check, and the
`schema/ir-v1.json` diff guard. Wait until the repo is actually pushed.
