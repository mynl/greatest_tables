# Pending — greater_tables (GT2)

Open items only; delete a section when it is done, not when it is decided.
Completed work is recorded in `CHANGELOG.md`, plans in `dev/done`. Last
reviewed 2026-08-01 at 6.0.0a4.

## [formats] Batch — small format/style gaps (agreed, not yet scheduled)

Collected as they come up; do them together rather than one version each.

1. **`G`/`E` format sugar.** ~~`g`~~ landed in 6.0.0a11 as `kind='gen'`,
   where `digits` counts significant figures. The uppercase pair is still
   open, and is the awkward half: `E`/`G` need either two more `FormatKind`
   members or an `upper: bool` on `FormatSpec` — the second is tidier but
   touches every kind. Same blast radius as `g` did: `ir.py`, the committed
   `schema/ir-v1.json` (widening an enum — old documents still validate, new
   ones fail an old schema), `apply_format`, and `cgFormatSpec` in the
   walker. `ir_version` stays 1.
2. **`HouseStyle.vrule_widths` is a 3-tuple but only 2 slots exist**
   (`policy.N_VRULE_SLOTS = 2`, CSS has `--gt-vrule-0/1`), so `[2]` is
   unreachable. Either drop to a 2-tuple or add a third vrule slot; the
   horizontal side is consistently 3.
3. **No Python route to HTML rule weights.** `hrule_widths`/`vrule_widths`
   are TikZ-only; the HTML weights are CSS custom properties, so
   `style=HouseStyle(hrule_widths=…)` silently does nothing for HTML. Option:
   emit non-default weights as custom properties on the `.gt` wrapper, so one
   `HouseStyle` governs both renderers. Keep the CSS route primary — a
   document theme should still beat a per-table setting.

## [rtd] Set up Read the Docs — **PENDING, Steve to action**

The docs tree, `.readthedocs.yaml`, and the `docs` extra are all in place and
build clean locally (`uv sync --extra docs`, then `docs\make.bat html`).
What remains is account-side and cannot be done from here:

1. Make `mynl/greatest_tables` **public** — RTD needs it. The repo is already
   pushed; the blocker is visibility, not the push.
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

## [artwork] Optional: an example figure for the docs landing page

The GT2 logo and favicon set in `docs/_static/` are final (confirmed
2026-08-05) and wired up via `html_logo` / `html_favicon`. What is still
missing is a `docs/img/` example figure — the 5.x docs led with one — now
that the demo tables are settled. `demo.html` and `demo2.html` are the
obvious sources. Nice to have, not a release blocker.

## [publish] greater-tables 6.0 on PyPI — **in flight**

`6.0.0` is cut and tagged `v6.0.0` locally. Remaining, all Steve's:

1. `git push mynl main` and `git push mynl v6.0.0`.
2. Flip the repo public.
3. Import on Read the Docs (see `[rtd]`), leaving RTD's *Default branch*
   empty now that GitHub's default is `main`.
4. `twine check dist/*`, confirm the README renders on the PyPI preview,
   then upload.
5. Confirm 5.3's frozen repo banner still points at the right place.

`uv build` and the sdist/wheel content check are done — the sdist carries
`src`, `tests`, `schema`, `js`, `docs` and no `dev/`; the wheel is about
930 KB, half of it `data/tex_list.csv`. **Steve uploads; Claude never
publishes.**

## [ci] GitHub Actions

Nothing runs on push yet, and the docs no longer claim otherwise (6.0.0b1
reworded two "in CI" claims to "the test suite"). Minimum useful workflow:
`uv sync`, `pytest` (428 tests, ~25 s) on 3.12/3.13/3.14, `npm run build` +
a walker transcript check, and the `schema/ir-v1.json` diff guard. The 3.12
floor in `pyproject.toml` is **declared but untested** — a matrix build is
what would actually verify it. Unblocked once the repo is public.

## [cookbook] Consider a docs page from the qmd generator

`dev/tools/make_example_qmd.py` already builds a 20-recipe, hierarchy-heavy
Quarto example. Those recipes are the missing "how do I do X" page in the
Sphinx docs — worth wiring up rather than maintaining two example sets.
Blocked on nothing; just a decision about whether the docs want it.
