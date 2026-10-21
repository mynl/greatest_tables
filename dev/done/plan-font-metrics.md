# [font-metrics] Measure table text in the face it is set in, and never break a number

Status: drafted 2026-10-19 at 7.0.0 (`fe22956`), at Steve's request from the house-style review.
Ruled and executing from 2026-10-21 (rulings at the foot, the record in **Execution log**). One
change from the draft, agreed in chat: each face carries a measured bold table, not a
`bold_percent` factor.

## Goal

A TikZ table sizes its columns from an estimate of how wide its text will be. Today that estimate
assumes Times, whatever face the document is set in. This plan makes the estimate match the face
the document actually uses, and makes a number hold together on one line even when an estimate
falls short. A third step clears the small format batch that `dev/pending.md` has been carrying.

## Current behavior

- `render/textlength.py` holds `_WIDTH_TABLE`, glyph advance widths in integer milli-ems. Its
  docstring says what they are: Times metrics, exact against the `newtxtext` preamble that `Etcher`
  compiles with (median actual/estimate 1.000 over the fixture corpus, p99 1.007). The same
  docstring states the limitation: "A document set in another face is a different measurement ...
  Either load a Times-metric serif alongside the tables, or accept that."
- `render/tikz_layout.py` gives each column its widest body cell's estimate plus `_WIDTH_PAD`
  (0.1em), floored by the header's widest word widened by `_BOLD_PERCENT` (118, the p99 bold/roman
  ratio measured in newtx).
- `render/tikz_tabular.py`, the default emitter since 6.2.0, emits every column as `p{width}` with
  `\raggedleft`, `\raggedright` or `\centering`. The `matrix` emitter gives every node a
  `text width`. In both, a cell wider than its column wraps, and that includes a number. TeX
  breaks after an explicit hyphen, so `-1.95e-05` breaks after `e-`.
- `dev/plan-column-widths.md` finished its deliverables at 6.0.0a8 and carried one question
  forward: "the font-metric factor ... is that a field, or is 'use a Times-metric serif for TikZ
  output' simply documented as a requirement?" This plan answers it: a field.

### The defect, observed

On 2026-10-18 house style (`D:\Projects\house-style`) set its slides in Fira Sans. A GT
table in the gallery deck broke `-1.95e-05` at its hyphen, with `unbreakable` set or not. The same
table in a document set in STIX Two did not break. (House style has since moved slides to STIX Two, so
its own deck no longer shows the defect; any document set in a sans face still does.)

### Why one factor is not enough

Advance widths in milli-ems, read from the font files in tectonic's bundle with fontTools, against
the table GT uses:

| Text | GT table | STIX Two Text | Latin Modern | Lato | Fira Sans |
|---|---|---|---|---|---|
| `0` | 500 | 495 | 500 | 580 | 558 |
| `-` | 333 | 315 | 333 | 372 | 403 |
| `-1.95e-05` | 3860 | 3814 | 3888 | 4408 | 4108 |
| `Coefficient of variation` | 9387 | 9720 | 10060 | 10131 | 10350 |
| a to z | 11943 | 12502 | 12706 | 12823 | 13120 |
| ratio, a to z | | 1.047 | 1.064 | 1.074 | 1.099 |
| ratio, `-1.95e-05` | | 0.988 | 1.007 | 1.142 | 1.064 |

The ratio differs by character class within a face. STIX Two sets numbers 1% narrower than the
table and lowercase 5% wider. Lato sets numbers 14% wider and lowercase 7% wider. A single factor
would either pad every number column or leave the prose columns short. Fira's numbers run 6.4% over
the table, more than the 0.1em pad absorbs on a nine-character number, which is the observed break.

## The change

### [font-metrics] A metric table per face

- **`HouseStyle.tikz_font: str = 'times'`** names the face the table will be set in, and so the
  metric table the layout reads. It sits with the other TikZ fields. HTML is unaffected, because
  the browser measures. An unknown name raises `ValueError` listing the known ones.
- **Faces shipped:** `'times'`, today's table, unchanged and the default; `'stix-two'` (STIX Two
  Text, the house-style face); `'latin-modern'` (the LaTeX default, what a plain Quarto PDF uses);
  `'lato'`; `'fira-sans'` (the metropolis beamer face).
- **A new module, `render/fonts.py`,** holds one record per face: a roman and a bold milli-em
  width dict. The Times roman table moves there from `textlength.py` unchanged. *As ruled
  2026-10-21:* the bold table replaces the draft's `bold_percent` and the 118% `_BOLD_PERCENT`
  factor. Bold/roman differs by glyph, digits usually 1.00 and lowercase up to 1.15, so any one
  factor either pads every bold number or leaves bold words short.
- **`textlength.py`'s functions take the face** as a keyword with the old behavior as its default:
  `display_milli(s, math=True, font='times')`, and likewise `token_milli`, `text_display_len` and
  `token_display_len`. Every existing caller is unchanged. `tikz_layout.py` passes
  `style.tikz_font` through `_display_milli`, `_token_milli` and `_bold`.
- **The tables are measured, not typed.** `dev/tools/measure_glyphs.py` gains `--font FILE` and
  `--bold FILE`. They swap the newtx preamble for a fontspec one that names a face by file, which
  tectonic resolves from its bundle on any machine. A third option, `--emit NAME`, prints the
  face's record as a Python literal. The record is pasted into `render/fonts.py` by hand and read
  at commit, which keeps the tool's own rule: the committed table is a reviewed artifact, not a
  generated one. The script's import of `_WIDTH_TABLE` moves to the new module.
- **Mathematics is out of scope.** `math_milli` token-counts TeX and prices letters from the text
  table, while TeX sets them in the math font. That estimate is already approximate and stays as
  it is, priced from the chosen face.
- **Output.** The draft promised byte-identical output with the default face. The bold tables
  break that: header floors are now exact bold widths, narrower than 118% of roman, so tables
  with headers move by a fraction of an em. Landed as 7.2.0.

### [numbers-hold] A number never wraps

- A column that does not wrap (IR `Column.wrap` is False: numbers, dates, and anything listed in
  `TableSpec.unbreakable`) emits each body cell inside a box of the column's width:
  `\makebox[<width>em][r]{...}`, with `[l]` or `[c]` for the other alignments. The width is the
  same em value the emitter writes into the column spec, not `\linewidth`, so the two emitters
  behave the same way.
- A box cannot break, so when an estimate is short the number runs into the column gap on the
  side away from its alignment, instead of wrapping. A right-aligned number keeps its right edge,
  so the column still aligns.
- Both emitters: `tabular` cells and `matrix` node text. Header cells are unchanged; they wrap by
  design.
- **Output.** It changes TeX output for every table with a number column, so every TikZ
  golden moves. The CHANGELOG says so, as the project's Deltas require for an output change. A
  table that fits today renders identically on the page.

### [formats] The batch in `dev/pending.md`

The three items under `pending.md`'s [formats] heading, done together in one version as that file
asks, with its section deleted when they land:

1. **`E` and `G` format sugar.** The route is an open question below.
2. **`HouseStyle.vrule_widths` is a 3-tuple with only two slots.** The recommendation is a third
   vertical slot, `--gt-vrule-2` in CSS and `N_VRULE_SLOTS = 3`. That matches the horizontal side,
   and it breaks no caller, where shrinking the public tuple would.
3. **Python reaches HTML rule weights.** Non-default `hrule_widths` and `vrule_widths` are emitted
   as custom properties on the `.gt` wrapper, so one `HouseStyle` governs both renderers. A
   document theme still beats a per-table setting.

## Files

| File | Step | Change |
|---|---|---|
| `src/greater_tables/render/fonts.py` | [font-metrics] | new: one record per face |
| `src/greater_tables/render/textlength.py` | [font-metrics] | the table moves out; functions take `font` |
| `src/greater_tables/render/tikz_layout.py` | [font-metrics], [numbers-hold] | pass the face; box non-wrap cells |
| `src/greater_tables/render/tikz_tabular.py`, `render/tikz.py` | [numbers-hold] | emit the box |
| `src/greater_tables/spec.py` | [font-metrics], [formats] | `tikz_font`, its docstring; `vrule_widths` |
| `dev/tools/measure_glyphs.py` | [font-metrics] | `--font`, `--bold`, `--emit` |
| `tests/test_tikz_tabular.py`, `tests/test_tikz.py` | both | the new cases below |
| `tests/golden/tikz*/` | [numbers-hold] | re-blessed by `tests/make_goldens.py` |
| `ir.py`, `schema/ir-v1.json`, `render/css.py`, `render/policy.py`, `render/html.py` | [formats] | per `pending.md` |
| `CHANGELOG.md`, `src/greater_tables/_version.py`, `dev/pending.md` | each | the bump |

## Acceptance

- **[font-metrics]**
  - `uv run pytest` passes. The goldens move only by the exact bold widths (see Output above).
  - Each new face meets the standard the Times table meets, measured the same way over the fixture
    corpus: the compiled width of each cell against its estimate, with median within 1% of 1.000
    and p99 no more than 1.02.
  - The defect is reproduced and fixed. A table holding `-1.95e-05` in a number column, compiled in
    Lato with `tikz_font='lato'`, keeps the number on one line with no overfull box.
- **[numbers-hold]**
  - The same table compiled in Lato with the default `tikz_font='times'`, a deliberate mismatch,
    keeps `-1.95e-05` on one line and right-aligned, overrunning into the column gap.
  - The golden diffs consist only of the box around non-wrap body cells. That is checked
    mechanically by stripping the box and comparing, then by eye on `dev/check-widths.qmd`.
- **[formats]** The tests `pending.md` implies: `E`/`G` formatting in `tests/test_formats.py`; the
  schema diff guard for any IR change; and a third vertical rule weight that reaches the page in
  TikZ and in HTML.

## Consumers

- **house-style** (`D:\Projects\house-style`). Since its 1.11.0, documents and slides are both set
  in STIX Two Text. After [font-metrics] ships to PyPI, house style's `house.py` sets
  `tikz_font='stix-two'` and house style floors `greater_tables>=7.2.0`. That change belongs to the
  house-style repository and is recorded there.
- Everyone else sees no change from [font-metrics]. [numbers-hold] changes the TeX text but not
  the page wherever an estimate already fits.

## Open questions for Steve

Ruled 2026-10-21, "go with yours": every recommendation below as written. Question 1: the work
Steve ruled in the same exchange lands as separate versions, not as steps here (the bold-row fix,
a prose minimum width, and the long-heading balance); `dev/done/plan-gt7-review.md` logs them.
Question 4 was already done (`2f9b005`).

1. **Anything else for GT?** "We need to do some work on GT" (2026-10-18) suggested a list of your
   own. If there is one, it joins this plan as further steps.
2. **`E`/`G` route.** `pending.md` gives two routes: two more `FormatKind` members, or an
   `upper: bool` on `FormatSpec`. Recommendation: `upper`, the tidier of the two. It adds one
   optional IR property, so old documents still validate and `ir_version` stays 1.
3. **Names.** `tikz_font` for the field, `render/fonts.py` for the module, and the face keys
   `times`, `stix-two`, `latin-modern`, `lato`, `fira-sans`. A grep of `src/` and `js/` finds no
   collision.
4. **`dev/plan-column-widths.md`** has finished its deliverables, and this plan closes the one
   question it carried forward. Moving it to `dev/done/` is your call.

## Execution log

### 7.2.0 [font-metrics] - 2026-10-21

- `render/fonts.py`: `Face(roman, bold)` for `times`, `stix-two`, `latin-modern`, `lato` and
  `fira-sans`, 111 glyphs each, every one present in every face. Times roman is the old table,
  moved; every other table was emitted by `dev/tools/measure_glyphs.py --emit` and pasted.
- `HouseStyle.tikz_font`, validated in `__post_init__`, so a bad name fails at construction.
- `textlength`'s functions take `font=` and `bold=`; the layout measures headers bold (stub
  headers are bold-italic, which is narrower than bold in all five faces: 1.5% to 6% over the
  alphabet), and bold rows bold, so 7.1.5's text-column restriction is gone.
- `measure_glyphs.py` gained `--face`, `--font`, `--bold`, `--emit` and `--corpus`. It had been
  importing a `_escape` that `render/tikz.py` no longer has, so it did not run before this.
- Acceptance, `--corpus` over 1,385 fixture cells (header cells bold, body roman), actual width
  over estimate:

  | face | median | p99 | max |
  |---|---|---|---|
  | times | 1.000 | 1.006 | 1.012 |
  | stix-two | 1.000 | 1.000 | 1.002 |
  | latin-modern | 1.000 | 1.007 | 1.016 |
  | lato | 1.000 | 1.002 | 1.007 |
  | fira-sans | 0.992 | 1.004 | 1.004 |

- `tests/test_tikz_geometry.py::test_text_holds_in_its_face` compiles loss-lab, long-head-ratios,
  subtotals, long-head-groups, wrap-low at 30em and a `-1.95e-05` column in a document set in
  each face, with `tikz_font` naming it: nothing hyphenates, "Unit 1" holds, the number holds.
  Sized in Times instead, all four other faces hyphenate headings ("unrep-", "tremen-",
  "formaliza-") and Lato and Fira break `-1.95e-05`, so the test discriminates.
- A consequence to know: with the exact bold, a document in another face that leaves
  `tikz_font` at `'times'` hyphenates headings more than it did under 118%, which had been
  padding them by accident. The CHANGELOG says to set the field.
