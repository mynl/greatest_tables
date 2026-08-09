# [speedup] — the TikZ backend costs ~400 ms/table, and ~2 ms is reachable

Findings from profiling the TikZ backend against a real corpus (the
`aggregate-reproductions` book, 159 GT tables) on 2026-08-08. Written as a
handoff: the measurements are here so the next round does not have to re-derive
them, and so the two ideas that *look* obvious and are wrong get rejected once.

Headline: `matrix of nodes` costs **~400 ms per table** in TeX. On the
reproductions book that is ~69 s of a measured 131 s LaTeX pass — roughly half
the compile. A prototype that keeps every capability lands at **~2 ms**.

## Measured (2026-08-08)

40 tables per document, tectonic, warm bundle cache, two runs each, per-table
cost net of a matched baseline document. Shape 8x6 unless noted.

| Rendering | ms/table | Body reads as a table? | Page breaks? |
|---|---:|---|---|
| `tabular` inside **one** TikZ node, rules drawn from known widths | **2** | yes — it *is* a `tabular` | no |
| `tabular` + booktabs, fixed `p{4.69em}` widths | 21 | yes | yes (`longtable`) |
| `tabular` + booktabs, natural `l r r ...` | 52 | yes | yes |
| explicit `\node at (x,y)`, 48 nodes, no matrix library | 354 | no | no |
| **`matrix of nodes` — what GT emits today** | **380–434** | partly (`\&` grid) | no |
| `nicematrix` `NiceTabular` + `\CodeAfter` | 400 | yes | yes |
| `tabularray` with `hline`/`vline` spans | 791 | yes | yes |

The 434 figure is from 40 real GT tikzpictures harvested out of the rendered
book (mean shape 7.4 x 6.5); 380 is a synthetic 8x6. Same thing.

## The finding that explains every row

**Cost is ~7–9 ms per addressable pgf cell node, and nothing else.**

- 48 cells x ~7.4 ms ~ 354 ms, which is what explicit `\node at (x,y)` measures.
- `matrix of nodes` adds only ~7% on top of that. The matrix library's layout
  pass is **not** the expense; materializing the nodes is.
- `nicematrix` (400) and `tabularray` (791) are the same story: both give every
  cell a node, both land in the same band.
- `tabular` alone (21) creates no nodes and is two orders of magnitude cheaper.
- Fixed `p{}` widths are *faster* than natural `l`/`r` (21 vs 52) because a
  stated width skips TeX's measurement pass. GT already computes these widths,
  so the estimate work in `render/widths.py` pays off twice.

So the design question is not "which table package" but **"does every cell need
to be a node?"** For GT the answer is no: nodes exist only so rules can be
anchored to cell corners. One node with known geometry serves the same purpose.

## Constraints — do not trade these away

1. **The emitted body must stay cut-and-paste-able as a table.** This is
   load-bearing, not cosmetic: the `.tex` goes to typesetters who do not use
   TikZ, and they lift the `&` / `\\` grid straight into their own `tabular`.
   Any design that scatters content across per-cell statements is disqualified
   regardless of speed.
2. Precise column widths — already solved, see `dev/plan-column-widths.md`.
3. Arbitrary rules, specifically the ones plain booktabs cannot express:
   vertical rules at an offset from a column boundary, spanning a chosen row
   range. This is the reason TikZ was chosen and it must survive.
   Current form, from a rendered table:
   `\path[draw,semithick] ([xshift=0.5em]m-1-1.south east) -- (... |- m.south);`

## Recommendation: one node, real `tabular` inside

```latex
\begin{tikzpicture}
\node[inner sep=0pt] (t) {\begin{tabular}{>{\raggedright\arraybackslash}p{4.69em}%
                                          >{\raggedleft\arraybackslash}p{3.31em}...}
stub & a & b & c & d & e \\
225,000 & 0.5189 & 0.5193 & ... \\
\end{tabular}};
\draw[semithick] (t.north west) -- (t.north east);
\draw[semithick] ([xshift=5.19em]t.north west) -- ([xshift=5.19em]t.south west);
\end{tikzpicture}
```

Why this wins on every axis that matters:

- **~2 ms/table**, ~200x faster than today.
- The body is a literal `tabular`. That is *better* for handoff than the current
  `\&` matrix — conversion becomes "delete the wrapper", where today it is five
  transformations (strip the tikzpicture and its option block, translate each
  `column N/.style={... text width=X}` into a colspec entry, `\&` -> `&`, drop
  the `\matrix (name) [...] {...};` wrapper, rewrite the `\path` rules).
- Rules stay fully arbitrary: GT already knows every column width, therefore
  every rule offset, so no measurement is needed from TeX at all. Cumulative
  widths become `xshift` values directly.
- Alignment maps cleanly: `align=flush left/right/center` ->
  `>{\raggedright|\raggedleft|\centering\arraybackslash}`. `\arraybackslash` is
  mandatory — without it `\raggedright` redefines `\\` and every row ends wrong.
  Needs the `array` package.

### What it does not fix

A TikZ node is one unbreakable box, so long tables still cannot break across
pages — unchanged from today. In the reproductions corpus that is **7 of 159
tables over 25 rows** (median 7, 90th percentile 15, max 31). If page breaking
is ever wanted those tables need a `longtable` body, which cannot live inside a
node; booktabs rules and `\cmidrule` are the fallback for them.

## Rejected, with reasons

- **Explicit `\node at (x,y)` per cell.** Measured at 354 ms — a 7% gain, not
  the win it looks like — *and* it destroys constraint 1. Rejected twice over.
  This was my suggestion and it was wrong on both counts.
- **`tabularray`.** 791 ms, worse than the status quo, despite being the package
  usually recommended for exactly this problem.
- **Plain booktabs everywhere.** 21 ms and page-breakable, but cannot express
  offset vertical rules (constraint 3). Still worth having as an emitter for
  tables that need no such rule — see open question 3.
- **TikZ externalization** (`\usetikzlibrary{external}`) — would cache each
  picture as its own PDF and make re-renders nearly free, but needs
  shell-escape, and tectonic support is unverified. Parked, not dismissed.

`nicematrix` is the fallback, not a rejection: 400 ms (no better than today) but
it gets clean handoff, page breaks, and `\CodeAfter` TikZ rules anchored on cell
nodes. If the one-node geometry turns out fiddly, this keeps every capability at
today's price. Verified: `NiceTabular` -> plain `tabular` is two edits (drop the
`\CodeAfter` block, rename the environment) with **zero content lines touched**,
and the converted file compiles.

## Open questions

1. **Does the one-node geometry reproduce current output exactly?** The 2 ms
   measurement used synthetic rule offsets. It has to be proven against the real
   width solver — do cumulative `p{}` widths plus `\tabcolsep` land the rules
   where `matrix of nodes` puts them today? This is the whole risk of the plan.
2. **`inner xsep` / `column sep`.** The matrix emitter carries these as node
   options; in a `tabular` they fold into the width or into `\tabcolsep`. Needs
   a decision so widths stay consistent with `plan-column-widths.md`.
3. **Two emitters or one?** A booktabs emitter (21 ms, page-breakable) for
   tables needing no offset rules, one-node TikZ for the rest. Buys page breaks
   for the long simple tables but adds a code path.
4. Does `tikz_scale` (the 1.0 -> 0.6 ladder) still apply cleanly when the body
   is a `tabular` rather than a matrix? Scaling a node scales its contents, so
   probably yes, but the floors arithmetic should be re-checked.
5. Verify visual fidelity, not just compile time. Nothing here checked that the
   rendered tables *look* the same — only that a PDF was produced.

## Related defect worth fixing regardless

`render/tikz.py` appends `\I` (a `\vphantom{lp}` strut) to every header cell,
and defines it in `TIKZ_PREAMBLE`. But that string is injected **only** by
`render/etcher.py`, the standalone compiler — never when a table is embedded in
a Quarto document. The consuming document must therefore define `\I` itself, and
nothing in GT says so.

Leave it undefined and every header cell raises `Undefined control sequence`,
which destroys the enclosing TikZ node ("A node must have a (possibly empty)
label text"), which spills the strut body `lp` into `nullfont`. One missing
macro, three classes of error, and the diagnosis is far from obvious. Options:
emit the `\newcommand` inline with each table (idempotent via `\providecommand`),
or document it loudly in the embedding instructions. Related: `render/notebook.py`
switches to `text/latex` when `QUARTO_FIG_FORMAT == 'pdf'`, which is what makes
this fire in PDF builds only.

## Method, for reproduction

Build N copies of one table into a document with the real preamble; compile with
`tectonic -X compile --outdir ... -Zcontinue-on-errors`; subtract a baseline
document of the same length containing only paragraph text. Discard the first
compile (tectonic cold-start dominates: an early run showed an empty baseline
at 11.8 s against 8.8 s for 40 booktabs tables, which is backwards). Two runs per
variant, take the minimum. Real GT tikzpictures are harvestable straight out of
a rendered book `.tex` by scanning between `\begin{tikzpicture}` and
`\end{tikzpicture}`.
