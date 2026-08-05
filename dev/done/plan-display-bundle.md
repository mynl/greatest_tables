# [display-bundle] — text/plain in the mimebundle, honest Quarto detection, ASCII rules

> **DONE 2026-08-05.** `[plain-in-bundle]`, `[quarto-target]`, `[bundle-policy]`
> shipped as 6.0.0a9; `[ascii-rules]` as 6.0.0a10. Implemented as written
> except for three points in `[ascii-rules]`, all decided by Steve:
>
> 1. **Eight literal sites, not six.** The plan missed `«` and `»` at
>    `text.py:228` (the row-flag gutter, already in
>    `tests/golden/text/totals.txt` as `«total»`). ASCII form is `<<total>>`.
> 2. **Heavy and light stay distinct** — `=` and `-`, not `-` for both. The
>    plan's mapping would have made a frame rule and an internal group break
>    identical, losing information the conformance oracle carries today.
> 3. **`s.isascii()` is not assertable** and is not asserted. Cell text
>    arrives already formatted, and two engine choices are non-ASCII:
>    `FormatSpec.null` (`—`, `ir.py:66`) and the SI suffix ladder (`µ`,
>    `engine/formats.py:190`). The tests assert instead that no *drawn*
>    character is non-ASCII, plus an explicit test pinning the limit.
>
> **Probe re-run after the change** (GT 6.0.0a11, Sphinx 9.1.0, Quarto
> 1.6.36, Python 3.14), the verification step this plan asked for:
>
> ```
> consumer     A_print B_expr C_display D_plain E_both
> sphinx html  text    text   text      text    text
> sphinx latex text    text   text      text    text
> quarto html  text    html   html      text    html
> quarto latex text    tikz   tikz      text    DROPPED
> quarto gfm   text    html   html      text    html
> ```
>
> **B and C — the real `GT` — now render in all five consumers.** Sphinx html
> and latex went `REPR` → `text`; gfm went `DROPPED` → `html`.
>
> Two corrections to the predicted table. **Quarto latex E stays `DROPPED`**,
> which the plan did not predict but is correct: E is the *shim*, publishing
> html-plus-plain deliberately, and its vanishing is reading 3 — the very
> thing D3 stops GT itself from doing. And **gfm B/C now emit a raw
> `<div class="gt">`** where they previously emitted nothing. Neither is
> usable markdown; the fix is caller-side, and block D (`text/plain` alone →
> `text` under gfm) is the measured proof that `mimes=('text/plain',)` works.
>
> Still open, carried from the plan's own caveat: **JupyterLab is unmeasured.**
> One manual check in a live notebook before 6.0.0.

Four changes to how greater_tables advertises itself to a display front end.
All four come out of a measured probe, not from reasoning about what ought to
happen, and each one below cites the observation that motivates it.

**Origin.** The `aggregate` library is moving its universal display verb
(`utilities.qd`) onto GT. `qd` has to serve JupyterLab, Quarto to HTML, Quarto
to PDF, Quarto to GitHub-flavored markdown, and a Sphinx `.. ipython::` block
rendered to both HTML and LaTeX. Before designing that switch, the five
consumers were measured against GT 6.0.0a8. The result is that most of the
matrix already works, and the gaps are all on the GT side.

## The evidence

Probe lives in this repo at `dev/tools/output-modes/` (`fixture.py`, `sphinx/`,
`quarto/`, `render.ps1`). Run it with `.\dev\tools\output-modes\render.ps1
[-Clean]`; it uses the repo's own `.venv` and needs the `quarto` binary on PATH.
One Fabricator frame, seed 42, five rows, two stub levels, two column levels,
negatives, 65 character text rendering. Six blocks per page:

- **A** prints `GT.text` to stdout.
- **B**, **C** hand over a real `GT` (bare expression, then `display()`).
- **D**, **E** hand over a shim publishing a chosen mimebundle over the same
  real renderings. Without the shim a consumer showing the default repr is
  ambiguous: it could mean "ignores mimebundles" or "found nothing usable".
- **F** dumps the `QUARTO_*` environment.

Every check reads the *intermediate* artifact (`.html`, `.tex`, `.md`), never a
PDF or a browser, so each one is a grep for a marker. Measured with GT 6.0.0a8,
Sphinx 8.2.3, Quarto 1.6.36, Python 3.14:

```
consumer     A_print B_expr  C_display D_plain E_both
sphinx html  text    REPR    REPR      text    text
sphinx latex text    REPR    REPR      text    text
quarto html  text    html    html      text    html
quarto latex text    tikz    tikz      text    DROPPED
quarto gfm   text    DROPPED DROPPED   text    html
```

`REPR` means the block rendered `<greater_tables.compat.GT at 0x…>` and nothing
else. `DROPPED` means the consumer emitted nothing at all.

The same table came back **byte for byte identical under Sphinx 9.1.0**, run
from this repo's `.venv`. Two Sphinx majors agreeing is worth something: the
readings below are not an artifact of one toolchain build.

Five readings, in descending order of consequence.

1. **Sphinx honors `_repr_mimebundle_` and prefers `text/plain`.** B and C fell
   through only because GT publishes no `text/plain`. D and E both rendered the
   text table, in HTML and in LaTeX. E is the decisive one: `text/html` sitting
   in the bundle alongside plain does *not* hijack the selection.
2. **Quarto gfm silently drops a html-only bundle** (B, C). Adding `text/plain`
   does not fix it: E, offered html plus plain, leaked a raw `<div class="gt">`
   into the markdown. Pandoc's commonmark writer prefers html and never looks at
   the plain entry.
3. **Quarto latex drops a html-plus-plain bundle entirely** (E). Pandoc picks
   `text/html`, the LaTeX writer discards raw html, and nothing is emitted. So
   on the PDF path a bundle carrying html is actively worse than one carrying
   plain alone, which renders (D).
4. **A plain-only bundle is universal.** D rendered as text in all five
   consumers, with no override anywhere.
5. **Block F: Quarto names no output format, but `QUARTO_FIG_FORMAT` is a clean
   proxy.** It is `pdf` for latex and `png` for both html and gfm.
   `QUARTO_FIG_DPI` differs (192 html, 96 gfm) but is user-settable, so it is
   not a discriminator. Html and gfm are therefore indistinguishable from the
   environment, which is why gfm needs a caller-side override and cannot be
   auto-detected.

Two smaller observations, both about the text renderer:

6. Sphinx wraps **every** U+2501 as `\PYG{err}{━}`. Pygments lexes the captured
   output as ipython source and classifies the rule as an error token, so the
   build emits `Lexing literal_block … resulted in an error at token: '━'.
   Retrying in relaxed mode` once per block. In `aggregate`'s doc tree that is
   one warning per table, red error styling in the PDF, and a glyph the mono
   font may not carry.
7. A cp1252 stdout raises `UnicodeEncodeError` on the first `print(GT(df).text)`.
   Windows terminals need `PYTHONIOENCODING=utf-8` today.

## Settled (Steve, 2026-08-05)

All five decisions are made. Nothing below is open; implement as written.

**D1. Reading the environment is allowed here.** `CLAUDE.md` says "Do not plan
to use env variables, use config files". That is a preference about
*configuration*, and this is not configuration: it is **detecting the host**,
and Quarto offers no other channel. The carve-out is granted for
`[quarto-target]`. Configuration itself stays in the config file and in
`HouseStyle`, so do not widen this into an env-var settings layer.

**D2. `text/plain` is unconditional.** It is the universal fallback (reading 4),
it does not displace html where html is wanted (readings 1 and 2), and its
absence is the entire cause of reading 1.

The cost concern does not survive contact with the other two items. `render_text`
is bounded by `TableSpec.max_rows` (default 200), the same guard every renderer
sits behind, so the work is capped. And `[quarto-target]` **stops computing TikZ
on every non-PDF render**, which is far more expensive than the text pass it is
replaced by. Net effect on an HTML or notebook render is a speed *gain*, not a
cost. No opt-out flag; `mimes=` (D4) covers the one case where a caller wants
something narrower.

**D3. The PDF path drops `text/html`.** Reading 3 says a `{html, plain}` bundle
renders nothing at all under Quarto latex: pandoc picks the html, the LaTeX
writer discards raw html, and the table vanishes silently. Once
`QUARTO_FIG_FORMAT == 'pdf'` is detected, publish `{text/latex, text/plain}` and
omit html, so a TikZ failure degrades to text rather than to silence.

**D4. The knob is a `mimes` tuple on the `GT` constructor:**
`GT(df, ..., mimes=('text/plain',))`. Chosen over a `HouseStyle` field or a
module-level default because it composes with `functools.partial`, which is the
house way of pinning a per-document rendering policy:

```python
render = partial(GT, mimes=('text/plain',))   # for the whole gfm build
```

Semantics: `mimes=None` (the default) auto-detects per D2 and D3;
an explicit tuple publishes **exactly** those types and suppresses detection
entirely. Validate members against the three known types and raise on anything
else, since a typo would otherwise silently produce an empty bundle.

**D5. ASCII rules are opt-in via `HouseStyle.text_ascii_rules: bool = False`,**
following the existing `tikz_*` precedent for renderer-scoped fields. The
default must stay False: `render_text` is the conformance oracle and every
golden in `tests/golden/text` encodes the current characters.

## Work items

### [plain-in-bundle] — publish text/plain, and fix `__repr__`

`render/notebook.py:mimebundle` returns `{'text/html': …}` plus `text/latex`
under Quarto. Add `'text/plain': render_text(doc, style)` unconditionally (D2).

`compat.py:GT` defines `__str__` returning `self.text` but no `__repr__`, so any
context that falls back to `repr()` shows `<greater_tables.compat.GT at 0x…>`.
Add `__repr__ = __str__`, or an explicit `__repr__` returning `self.text`. This
is what makes GT usable from a plain script or REPL, where `display()` degrades
to `repr()`.

Fixes: Sphinx HTML, Sphinx LaTeX, and every non-notebook console, all with no
caller-side change.

### [quarto-target] — detect the target, not merely the host

`render/notebook.py:in_quarto` returns True when *any* `QUARTO_*` variable is
set, and `mimebundle` uses it to decide whether to attach `text/latex`. Under
`quarto render --to html` those variables are set too, so every HTML render
today computes and ships a TikZ payload that is never used. That is the exact
"compute-TikZ-then-discard" waste the module docstring says the design
structurally fixed, reintroduced one level up.

Key on `os.environ.get('QUARTO_FIG_FORMAT') == 'pdf'` instead (reading 5).
Keep `in_quarto()` if something else wants it, but the `text/latex` decision
should route through a new, narrower predicate. Suggested name:
`quarto_target()` returning `'pdf' | 'other' | None`, so the html-versus-gfm
ambiguity is visible in the return type rather than hidden.

Per D3 the pdf branch also omits `text/html`, so the three auto-detected
outcomes are:

| target                              | keys published                 |
|-------------------------------------|--------------------------------|
| `QUARTO_FIG_FORMAT == 'pdf'`        | `text/latex`, `text/plain`     |
| any other Quarto render, or none    | `text/html`, `text/plain`      |
| caller passed `mimes=`              | exactly what was asked for     |

### [bundle-policy] — let a caller pin the bundle

Needed because reading 2 cannot be auto-detected: under `--to gfm` the caller
knows it wants plain and GT cannot work it out, since html and gfm are
indistinguishable from the environment (reading 5). `mimebundle()` already takes
a `tikz` parameter, but `GT._repr_mimebundle_` (`compat.py:100`) passes only
`style`, so nothing is reachable from a `GT` instance.

Per D4 the surface is `mimes` on the `GT` constructor, threaded through to
`mimebundle`. `None` auto-detects; an explicit tuple publishes exactly those
types and suppresses detection.

Two cautions. **Do not build a general MIME negotiation layer** behind this: the
only requirement any known caller has is "publish plain only", and reading 4
shows that single case is universally safe. And note that a caller pinning
`mimes` is doing so for a *whole document build* of hundreds of tables, not one
call site, which is why D4 chose a form that partials cleanly rather than a
per-table style field. `aggregate` will drive it from its own
`display.fmt` setting.

### [ascii-rules] — an opt-in ASCII character set for render_text

Six literal sites in `render/text.py`: `━` at lines 50, 59, 63, 66; `│` at 176;
`─` at 189 and 208. Hoist them to a small charset table and select on a
`HouseStyle` flag (D5), with `-`, `|`, `-` as the ASCII forms.

Motivated by readings 6 and 7. It matters for LaTeX output and for Windows
consoles, and neither is a niche path once `aggregate` routes its docs through
GT.

Defaults do not change, so `tests/golden/text` is untouched. The new mode needs
its own goldens.

## Testing

Unit, in GT's own suite, no external toolchain:

- `mimebundle` key sets for each row of the `[quarto-target]` table above,
  asserted as **exact** key sets against a patched `os.environ`.
- `mimes=` overriding detection: an explicit tuple wins even under a pdf
  target, and an unknown MIME string raises.
- `repr(GT(df)) == GT(df).text`.
- `quarto_target()` for each observed case, including "any `QUARTO_` variable
  present but no `QUARTO_FIG_FORMAT`", which is what a future Quarto could do.
- ASCII rules: new goldens, plus an assertion that the default output is
  unchanged and that ASCII output satisfies `s.isascii()`.

Toolchain, manual, not in the pytest run because it needs the Quarto and Sphinx
binaries. The probe now lives at `dev/tools/output-modes/`:

- Re-run `render.ps1` after the change. Expected new table: every consumer
  renders a table in every block, with **one** exception, gfm block E, which
  stays html because that is pandoc's preference and is exactly what the
  `mimes=` override exists to defeat.
- Record the toolchain versions printed at the top of the run. The table above
  is pinned to Quarto 1.6.36 with Sphinx 8.2.3 and 9.1.0.

**Untested, and stated as such:** JupyterLab itself was not measured, since it
needs a live front end. It is expected to behave as Quarto HTML does, preferring
`text/html`, but that is an inference from reading 1 rather than an observation.
Worth one manual check in a live notebook before the version ships.

## Versions

`[plain-in-bundle]`, `[quarto-target]` and `[bundle-policy]` are one coherent
change to the display contract and should land together as **6.0.0a9**, with one
CHANGELOG section describing the new bundle rules as a table of
(target, keys published).

`[ascii-rules]` is independent and additive: **6.0.0a10**.

Note for the CHANGELOG: `[quarto-target]` and D3 are **behavior changes**, not
additions. An HTML render stops receiving `text/latex`, and a PDF render may
stop receiving `text/html`. Both are improvements, and both will change output
for anyone relying on the old bundle.
