# [column-widths] — header relaxation, shared allocator, table width budget

Restores the width capability deleted in the transition (`transition.md:162`,
"Width machinery — all gone") in the shape GT2 can actually support:
estimate-driven for TikZ, because TeX has no browser to ask; CSS-driven for
HTML, because the browser measures better than our glyph table ever will.

## Decisions (settled 2026-08-03)

- **No truncation, anywhere.** One mode: wrap. Cutting content out of a display
  table is wrong in every backend, and truncation is what forces the ugly paths
  (a floors fork in the allocator, `table-layout: fixed` in HTML, an estimate
  that has to be *right* rather than close). If it is ever wanted it belongs at
  **format** time — a per-column string shortener landing in `Cell.text`,
  visible in the IR — not at layout time.
- Budget lives in `HouseStyle`, renderer-agnostic, em:
  `max_table_width_em: float | None = None` (None = today's behavior). Docstring
  leads with *target, not guarantee*: unbreakable floors win.
- `tikz_prose_max_em` (18) and CSS `--gt-prose-max` (30) unify into
  `HouseStyle.max_prose_width_em = 30.0` — one per-column cap on wrapping
  columns, read directly by TikZ and emitted as the custom property by HTML.
  Applied **before** the budget solve (cap, then narrow).
- Overflow policy: TikZ auto-scales **only** when the floors alone exceed the
  budget, stepping down a fixed ladder (1.0, 0.95, … 0.6) and taking the largest
  step that fits, with a `logging.warning` naming the numbers. Past 0.6 it warns
  and overflows — that is a `sidewaysfigure` conversation, not a scaling one.
- HTML gets a CSS `max-width` and no Python solver. Stub columns participate in
  narrowing like any other prose column; `unbreakable` names the exceptions.
- Milli-em integers throughout the solve (see `textlength.py` header — float
  `sum()` already moved a committed width 0.01em between 3.11 and 3.13; a
  float binary search would move *every* column).

## Progress

- **[header-relax] done** — `6.0.0a5` / `6.0.0a6`. It turned up three things
  that were not in the plan and that the budget work now rests on:
  1. TikZ's `align=left/right/center` is *balanced* ragged and breaks lines
     that fit their column. Every width the renderer computed was being second
     guessed by the line breaker. Fixed by using the `flush` variants.
  2. 30 glyphs were missing from the table, `—` and `%` and `µ` among them.
     Fixed against measured values; the estimator is now exact for newtx.
  3. **The estimate is font-specific** — exact against Times metrics, ~11%
     tight against Latin Modern. See the open question below.
- Next: **[width-solver]**, then the **[tikz-budget]** spike.

## Open question raised by [header-relax]

The budget is expressed in ems and the estimator assumes a Times-metric
serif. In a document set in something else, every width is off by a constant
factor — 11% for Latin Modern — so a table asked to fit 52em would overrun.
A single `HouseStyle` widening factor covers it, and
`dev/tools/measure_glyphs.py` measures the number for any font. Decide when
building **[tikz-budget]**: is that a field, or is "use a Times-metric serif
for TikZ output" simply documented as a requirement?

## Deliverables

1. **[header-relax]** — independent of the budget, worth doing on its own.
   `tikz.py:111` folds the header estimate into the same `wmax[col]` as the
   body, so a column headed *"Cumulative Incurred Loss"* is 9+ em wide over 6em
   numbers, even though its node already has `align=center` and would wrap
   happily. Split into two accumulators: body contributes its full width, the
   **leaf** header level contributes only its **longest token** (×1.15 bold
   adjustment, as now). Upper header levels are spanners — they constrain the
   *group*, not a column, via an `ensure(col, span, width)` helper mirroring
   `text.py:126`. That helper also fixes body `colspan` cells, which TikZ
   excludes from measurement entirely today (a latent overflow that becomes
   visible the moment a budget is set).
   New in `textlength.py`: `token_display_len(s)` — max over whitespace-split
   parts, integer milli-ems like its neighbor.

2. **[width-solver]** — `render/widths.py`, pure, no renderer imports, integer
   milli-ems in and out. Per column: a floor, and for prose columns the sorted
   array of cell widths. Unbreakable columns are fixed at their natural width;
   prose columns have floor = max(longest token, leaf-header longest token,
   minimum). Equal-VaR allocation: binary search the common quantile *q* over 32
   steps so every prose column takes its *q*-th percentile width and the total
   fits — one exceedance probability shared across columns, so no column looks
   uniquely mangled. Returns widths plus a status: `natural` / `solved` /
   `floors-exceed-budget`. Names mirror the JS (`solve_widths`,
   `_equal_risk_widths`) so the two read as one algorithm.

3. **[tikz-budget]** — retain per-column cell arrays (only `wmax` survives
   today), compute the **exact** emitted geometry (Σ text widths + inter-column
   separations + column 1's `inner xsep` + the phantom column — derived from the
   emitted style block, not guessed), then: fits → natural, as now; doesn't →
   solve; floors alone don't → scale ladder.
   **Prerequisite spike:** `tikz_scale` is emitted as `nodes={… scale=…}`, which
   scales node *contents*, while `column sep` sits on the matrix. If separations
   don't scale with it, scale 0.85 does not shrink the table 15% and the ladder
   cannot predict which step fits. Compile a probe through `Etcher` and measure
   before writing tier 3; the answer may push this to a picture-level scale.

4. **[html-maxwidth]** — `.gt` gains `max-width: var(--gt-max-width)` (default
   `none`); the Python renderer stamps `--gt-max-width` and `--gt-prose-max` on
   the wrapper from `HouseStyle`. That is the whole feature: `gt-nowrap` already
   pins the unbreakable columns, so the browser's auto layout narrows exactly
   the prose ones, using real font metrics. `gt-wrap` carries
   `overflow-wrap: break-word`, so HTML has no longest-token floor problem —
   the browser breaks mid-word where TikZ would give an overfull hbox.
   *Optional rider:* the same wrapper-property plumbing closes `pending.md`
   item 3 (no Python route to HTML rule weights). Same mechanism, one pass.

## Acceptance

- A long header over a numeric column no longer widens it: golden shows the
  header wrapped and the column at body width.
- With `max_table_width_em` set and prose columns present, emitted
  Σ widths + separations ≤ budget.
- All-unbreakable table over budget: warns, lands on a ladder step; past 0.6
  warns and overflows rather than shrinking further.
- Python `_equal_risk_widths` and JS `equalRiskWidths` return identical
  allocations on shared fixtures (same conformance pattern as the DOM
  transcripts; the JS copy already has a drift check against csv-grid).
- TikZ goldens re-blessed with a real eyeball pass — [header-relax] moves nearly
  all of them, so a bulk re-bless would hide regressions.
- Round-trip stable across 3.11 / 3.12 / 3.13 (the milli-em discipline).

## Out of scope

Truncation. `tabs` / explicit per-column widths (if ever needed, they enter the
same allocator as pinned floors, not a parallel path). Text-renderer width — its
budget is in characters, so it needs its own field and can reuse the allocator
later. HTML `colgroup` / `table-layout: fixed`.

## Risks

- Scale semantics unknown until the spike; tier 3 is blocked on it.
- The serif glyph table is an estimate, not TeX metrics — the budget is met to
  within a few percent, same as 5.x. Say so in the docstring.
- Golden churn from [header-relax] is large by construction.

Version: `6.0.0a5`.
