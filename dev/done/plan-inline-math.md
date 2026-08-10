# Plan: inline math everywhere — index, body, columns

**Status:** proposed, 2026-08-10; revised same day after review against the
GT5 source (`C:/S/TELOS/Python/greater_tables_project`) · **Target:** 7.0.0
(removing `spec.math` is semver-major)

## Goal

TeX math just works, with nothing asked of the user:

- in the **index/stub**, the **body**, and the **column headers** — all three;
- as a **whole cell** (`$\psi(u)$`) *and* **inside a sentence**
  (`the survival function $\psi(u)$ falls`) — again all three;
- if a cell needs escaping for some other reason, that is the user's job, not
  the package's.

## Context: GT5 did this, the rewrite lost it

### What GT5 did

`greater_tables` 5.3.0, `utilities.py:161-186`:

```python
math_pattern = re.compile(r"(\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\])", re.DOTALL)
def escape_non_math(s):
    return (s.replace("\\", r"\textbackslash{}")
             .replace("%", r"\%").replace("_", r"\_"))
parts, last_end = [], 0
for m in math_pattern.finditer(text):
    start, end = m.span()
    parts.append(escape_non_math(text[last_end:start]))
    parts.append(m.group())          # math part, unescaped
    last_end = end
parts.append(escape_non_math(text[last_end:]))
```

Split the string on math spans, escape only the gaps, pass math through
untouched. `escape_df_tex` then applied it to the frame, **`df.index` and
`df.columns`** — which is why math in a column name worked. The HTML path had
the matching pass, `clean_html_tex`, rewriting `$...$` → `\(...\)` and
`$$...$$` → `\[...\]`. A second helper, `clean_name`, escaped column names by
splitting on `$` and treating **odd-numbered pieces as math** (dollar parity).

GT5's rule was loose: any `$...$`, non-greedy, no constraint on what sits
next to the delimiters. Measured against 5.3.0:

```
'costs $10 to $20 and 50% off_now'  →  'costs $10 to $20 and 50\% off\_now'
```

`$10 to $` was taken as a math span and passed through unescaped, so TeX sets
`10to` in math italic. **GT5 had the currency bug** — it just rarely bit,
because a false span usually contains nothing that needed escaping. Worth
knowing before we port it verbatim.

On the bracket forms, from the same source: the TeX pattern protected
`\[...\]` but **not** `\(...\)` — a `\(x\)` cell was prose-escaped into
`\textbackslash{}(x\textbackslash{})` and mangled. The HTML pass left both
forms untouched in the assembled document, where MathJax happened to render
them. So `\[...\]` was deliberate in TeX and passive in HTML; `\(...\)`
worked only by accident, only in HTML. (`clean_html_tex` ran over the whole
assembled HTML text, which is why math worked everywhere in that path.)

### What the 6.0.0 rewrite did

Replaced span-splitting with a single build-time boolean. `engine/build.py:27`:

```python
_MATH_RE = re.compile(r'^\$([^$]+)\$$')
```

Anchored both ends, no interior `$`: the whole cell is math, or none of it is.
`_make_cell` strips the delimiters and sets `Cell.math=True`; every renderer
re-delimits for its own target (`$...$`, `\(...\)`, KaTeX) and otherwise
escapes the text wholesale. This bought real things — a semantic flag the
walker and KaTeX can use, math-aware width estimation, escaping that is no
longer a user setting (`tikz_escape_tex` is gone; see `docs/migration.md:304`).
It also silently dropped inline math and math in headers.

### The split-brain state today

`render/textlength.py` is a direct port of GT5's `TextLength` and **still uses
GT5's loose span splitter** (`textlength.py:83`). So the width estimator
believes in inline math while the renderers do not. That is one model
half-replaced, not two independent bugs, and it shows up as measurable
disagreement:

```
'$10 to $20'  → estimator 3278 milli-em, literal glyphs 4478
```

### Measured 6.2.0 behavior

| location | whole cell `$x$` | inline `a $x$ b` |
|---|---|---|
| body cell | ✅ `math=True` | ❌ escaped literally |
| index / stub cell | ✅ `math=True` | ❌ escaped literally |
| column header | ❌ never flagged | ❌ escaped literally |

Headers never get the detector at all: `build.py:132-137` constructs
`HeadCell(text=t)` and `HeadCell.math` stays `False` forever. Everything
downstream is already wired — `cell_tex`, `_cell_content` and the walker's
`fillCell` all accept a `HeadCell` and honor `.math`; only the builder never
sets it. Confirmed by hand-setting the flag: all four renderers did the right
thing.

## The rule

One shared pattern, replacing both the anchored build-time regex and the loose
estimator one. Math must be **tight against its delimiters** — no whitespace
just inside — with no interior `$`, and a closing `$` may not be followed by a
digit:

```python
MATH_RE = re.compile(
    r'(?<!\\)\$\$(?!\s)([^$]*[^$\s])\$\$(?!\d)'      # display  $$...$$
    r'|(?<!\\)\$(?!\s)([^$]*[^$\s])(?<!\\)\$(?!\d)'  # inline   $...$
)
```

Measured against the corpus of cases that matter:

| input | spans found |
|---|---|
| `this $x^2$ is a formula and $10 is an amount.` | `$x^2$` |
| `$10 to $20` | *none* |
| `$5-$10` | *none* |
| `costs $5-$10 and $x^2$ too` | `$x^2$` |
| `a 50% cut with $\alpha$ inside` | `$\alpha$` |
| `display $$\int_0^1 f$$ here` | `$$\int_0^1 f$$` |
| `escaped \$100 and $y=1$` | `$y=1$` |
| `$ loose $` | *none* |
| `$\psi(u)$` | whole cell |

This is **stricter than GT5** and fixes GT5's currency bug rather than
inheriting it. The one accepted loss is `$x$2` — math immediately followed by
a digit reads as currency and is left alone; write `$x$ 2` or `${x}$2`.

Three deliberate scope decisions, stated so they read as decisions:

- **`$` forms only.** `\(...\)` and `\[...\]` are not recognized. GT5's TeX
  path protected `\[...\]` (see above), so this drops a real if minor GT5
  capability — one migration line. `\(...\)` never worked in GT5's TeX path,
  so nothing is lost there. If `\[...\]` is ever wanted back it is a
  contained change in the one rule module.
- **Display collapses to inline.** `$$...$$` is recognized but each target
  emits its *inline* delimiters — display math has no business inside a
  table cell, and TeX display primitives misbehave inside a TikZ node.
- **`\$` is consumed, not preserved.** `segments()` yields prose runs with
  `\$` unescaped to a literal `$`; each escaper then re-escapes for its
  target (`\$` in TeX, plain `$` in HTML and text). Without this,
  `escaped \$100` would reach TeX as `\textbackslash{}\$100` and render
  with a stray backslash. The escape's only job is to suppress math
  detection, and segmentation is where it is spent.

One regex nit to carry into implementation: the display branch's closing
`\$\$` needs the same `(?<!\\)` guard the inline branch has (or apply the
existing `endswith('\\')` guard uniformly inside `segments()`), so
content ending in a backslash cannot emit broken TeX. The JS twin uses
lookbehind, which requires Safari ≥ 16.4 — acceptable, but note it in the
walker comment so nobody "simplifies" it away.

## Design

**Segmentation happens at render time, in each renderer's escape step** — the
GT5 shape, because escaping is per-target and only the renderer knows what its
target needs. One helper module owns the rule; each renderer walks its output.

**`Cell.math` stays exactly as it is.** A cell that is entirely math keeps the
fast path: delimiters stripped at build time, flag set, KaTeX and the width
estimator fed directly. Inline segmentation only ever runs on `math=False`,
`html=False` cells — an `html=True` cell is the user's raw markup and may
legitimately contain prices; it keeps its current wholesale treatment in
every renderer, including TikZ's strip-tags-then-escape path. Two paths that
agree on output, no golden churn on existing fixtures.

**`spec.math` is removed; the switch moves into the IR.** Detection is always
on — that is what "just works" means — so the spec knob goes (pydantic will
reject `TableSpec(math=...)` outright; migration note). The escape hatch
survives one level down as a document field,
`TableDoc.math: Literal['auto', 'off'] = 'auto'`: when a document says
`'off'`, renderers, the walker and the width estimator skip *all* math
handling and set every `$` literally. The builder always emits the default;
`'off'` exists for hand-authored and foreign IR — the ticker table. The
field is additive and defaulted, so canonical JSON omits it: no golden
churn, no hash churn, no `ir_version` bump. Two threading consequences to
budget for: the walker's defaults object (`gt-render.js:73`) gains
`math: 'auto'`, and the flag must reach the cell emitters — `cell_tex` and
`tex_escape` today take no document context, so the doc (or the resolved
flag) is passed down; `fillCell` gets it via `opts`.

**The IR contract gains a sentence**, and this is the part to be explicit
about: `Cell.text` / `HeadCell.text` may contain inline math delimiters, and a
renderer is responsible for segmenting them. Document in `ir.py` and
`docs/design.rst` — the walker is a public consumer of this contract.

*Road not taken:* storing span offsets in the IR. It is a schema change, and
every renderer still needs the same emit logic afterwards — the cost without
the saving.

## Work items

- **[rule]** New `src/greater_tables/mathspans.py`: `MATH_RE`, plus
  `segments(text) -> Iterator[tuple[bool, str]]` yielding `(is_math, text)`
  runs with delimiters stripped from the math ones and `\$` unescaped to `$`
  in the prose ones. Add the `(?<!\\)` guard to the display branch's closing
  delimiter. Single source of truth, imported by build, both TikZ engines,
  HTML and textlength.
- **[spec]** Delete `math` from `TableSpec` and its docstring. Breaking for
  anyone passing `math='off'` — pydantic rejects the kwarg — so a migration
  line and a CHANGELOG *Removed* entry.
- **[ir]** `TableDoc.math: Literal['auto', 'off'] = 'auto'`, honored by every
  renderer, the walker and the estimator; thread the flag to `cell_tex` /
  `_cell_content` / `fillCell` (opts) / textlength call sites. Document in
  `ir.py`: builder always emits `'auto'`; `'off'` is the foreign-IR escape
  hatch.
- **[build]** Point the whole-cell detector at the shared rule (anchored form)
  so `$ loose $` classifies the same way everywhere; keep the trailing
  backslash guard. Detection is now unconditional — the `spec.math` gate at
  `build.py:328` goes. Run the same detector over head text in the
  head-assembly loop so `HeadCell.math` is set — 4 lines, and it makes a
  header behave exactly like a body cell.
- **[tikz]** `tikz_layout.tex_escape` walks `segments()`: escape the prose
  runs, emit `$...$` for math runs. Serves both engines and captions/notes.
- **[html]** `html._cell_content` / `_esc` likewise, emitting `\(...\)` and
  `gt-math` per span rather than per cell. Notes already flow through `_esc`
  (`html.py:123`), so they gain math for free — deliberate, to match TikZ.
- **[walker]** Mirror the rule and the per-span emit in
  `js/src/gt-render.js` `fillCell`. **The fiddliest item:** it currently hands
  the whole cell to `katex.render`, so inline needs child nodes — text,
  math span, text — with KaTeX called per span. Notes are plain
  `textContent` today (`gt-render.js:137`) and must get the same per-span
  treatment, or TikZ/HTML notes would render math while walker notes do
  not. Keep the Python and JS regexes visually identical and comment both
  as a lockstep pair (with the Safari ≥ 16.4 lookbehind note).
- **[text]** No change for inline (the text renderer does not escape, so a
  mixed cell already shows verbatim). Fix the one gap: `_decorate` takes
  `Cell` and is not applied to head cells, so a math header prints without
  its `$`s.
- **[measure]** `textlength` uses the shared rule instead of its GT5 copy.
  This is what makes the estimator agree with the renderers.
- **[fixtures]** One new fixture exercising the matrix: inline math in a body
  cell, in a stub label and in a column name; a currency cell; a whole-cell
  formula. This is what the conformance harness needs to have teeth.
- **[goldens]** Regenerate. Expect movement **only** in the new fixture plus
  any header that gains a flag — no committed golden currently has a `$` in a
  header cell (checked), so the header change is golden-neutral.
- **[docs]** `quickstart.rst` gets the rule and the caveats: `$x$2`, no
  `\(...\)`/`\[...\]`, and no way to write a literal `\$` *inside* a math
  span (`[^$]` forbids it; GT5 broke on this too — use `\mathdollar`).
  `migration.md:304` gets inline-math-is-back plus the `spec.math` removal
  and the `\[...\]` drop; `design.rst` gets the IR contract sentence and
  `TableDoc.math`.
- **[release]** 7.0.0, CHANGELOG (Added: inline math, math in headers,
  `TableDoc.math`; Changed: space-padded `$ ... $` no longer detected as
  math; Removed: `spec.math`; Fixed: currency misdetection,
  estimator/renderer disagreement).

## Tests

- **[rule]** Table-driven unit test over the case list above, asserting exact
  spans — the currency rows are the point of it.
- **[matrix]** location × form: {index, body, header} × {whole-cell, inline},
  through TikZ (both engines), HTML and text.
- **[currency]** `$10 to $20`, `$5-$10`, `50% off_now` never become math and
  are correctly escaped in TeX.
- **[escaped-dollar]** `escaped \$100` renders as a literal dollar in every
  target: `\$100` in TeX, `$100` in HTML and text — the unescape-then-
  re-escape round trip, asserted end to end.
- **[off-doc]** A hand-authored doc with `math='off'` and ticker-style
  `$ABC$ $DEF$` text renders every `$` literally in all four outputs, and
  `TableSpec(math='off')` raises — the knob is gone.
- **[measure]** Estimated width of a mixed cell matches what the renderer
  emits, closing the 3278-vs-4478 gap.
- **[conformance]** Python vs walker on the new fixture via the existing
  transcript harness — this is the regression guard against the two regexes
  drifting.
- **[compile]** New fixture compiles under tectonic in both engines.

## Risks

- **Walker drift.** Two languages, one subtle regex. Mitigated by the
  transcript conformance test, which only works if the new fixture lands
  first — do **[fixtures]** before **[walker]**.
- **KaTeX per-span** in the browser is the only genuinely new rendering logic
  here; everything else is porting a known-good shape.
- **Reclassification.** Tightening the whole-cell rule could change an
  existing cell that used loose delimiters — today's anchored regex *does*
  match `$ loose $` and `$x $`, so this is a user-facing behavior change
  (hence the CHANGELOG *Changed* entry), not just a goldens question. The
  committed goldens contain no `$` anywhere (checked), so golden churn is
  expected to be nil; verify rather than assume.
- **Flag threading.** `TableDoc.math` has to reach every emit site —
  `cell_tex`, `_cell_content`, `fillCell`, textlength. A site that misses
  the flag re-creates today's split brain for `'off'` documents; the
  [off-doc] test exercises all four outputs to catch exactly that.
