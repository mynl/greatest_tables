# Pending — greater_tables (GT2)

Open items only; delete a section when it is done, not when it is decided.
Completed work is recorded in `CHANGELOG.md`, plans in `dev/done`. Last
reviewed 2026-07-31 at 6.0.0a2.

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

Not yet uploaded — `6.0.0a1`/`a2` are local tags. Sequence: alphas while the
aggregate_api adoption settles, then `6.0.0rc1` so the server can pin it
explicitly while plain installs still resolve to 5.3, then 6.0.0. Pre-flight:
`uv build`, check the sdist/wheel contents, `twine check`, confirm the README
renders on the PyPI preview, and confirm 5.3's frozen repo banner still points
at the right place. Steve uploads; Claude never publishes.

## [ci] GitHub Actions

Nothing runs on push yet. Minimum useful workflow: `uv sync`, `pytest`
(160 tests, ~20 s) on 3.11/3.12/3.13, `npm run build` + a walker transcript
check, and the `schema/ir-v1.json` diff guard. Wait until the repo is
actually pushed.

## [cookbook] Consider a docs page from the qmd generator

`dev/tools/make_example_qmd.py` already builds a 20-recipe, hierarchy-heavy
Quarto example. Those recipes are the missing "how do I do X" page in the
Sphinx docs — worth wiring up rather than maintaining two example sets.
Blocked on nothing; just a decision about whether the docs want it.
