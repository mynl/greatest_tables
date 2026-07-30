# [walker] — CSS contract + gt-render.js + conformance harness

Step 3 of `design.md` (see "JS walker" and "CSS architecture" sections).

## Deliverables

1. `render/css.py` — RULES dict (single source of truth) → generated `assets/gt.css`
   (committed) + inline flattener. Class vocabulary: gt-l/r/c, gt-stub/gt-data,
   gt-nowrap/gt-wrap, gt-break-{d}/gt-vbreak-{d}, flag classes, gt-math. `.gt.gt` selector
   doubling; custom properties for per-table scalars; currentColor default palette.
2. `js/src/gt-render.js` — zero-dep vanilla ES walker: `renderTable(doc, opts)` →
   `{el, doc, destroy(), toCSV()}`; textContent default, `allowHtml` gate, katex injection,
   `gt:cellclick` delegated event; optional fit pass with `solveWidths` copied from
   `C:/S/AI/csv-viewer/src/grid/util.js:358-457` (provenance header; CI diff vs source).
3. `js/build.mjs` — esbuild → `assets/gt-render.esm.js` + `.iife.js` (committed).
4. DOM-transcript conformance harness: node + linkedom runs the walker per golden IR fixture,
   emits one JSON line per cell `{r,c,tag,colspan,rowspan,classes(sorted),text}` →
   `tests/golden/transcript/*.jsonl`. Math cells recorded as TeX source (no katex in harness).

## Acceptance

- Walker renders every golden IR fixture; transcripts committed.
- Round-trip: transcripts stable across runs; `ir_version` guard throws on mismatch.
