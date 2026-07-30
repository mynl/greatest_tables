# [engine] — semantic engine + text oracle

Step 2 of `design.md` (see "Python package layout" and "The IR (v1)" sections).

## Deliverables

1. `spec.py` — `TableSpec` (semantics: caption/label/notes, ratio/year/date/raw col tags as
   list|'all'|regex, per-column format sugar, row_flags/cell_flags, include_raw, max_rows,
   sparsify switches) and `HouseStyle` (renderer opinions; never in the IR).
2. `engine/dtypes.py` — dtype discovery + semantic tag resolution (GT vocabulary kept).
3. `engine/formats.py` — sugar parsing (csv-grid spec strings `',.1f'` AND GT f-strings
   `'{x:.1%}'`) + resolution ladder: user > tag > dtype > str; salvage `make_float_formatter`
   column-stats inference (digits by |mean| magnitude, eng outside 10^pef bounds). Resolution
   returns FormatSpec data objects — no closures (kills the late-binding bug).
4. `engine/structure.py` — Indexing + Sparsify salvage, ONE implementation: row break_depths,
   stub rowspans, head colspans, column break_depths.
5. `engine/build.py` — `build(df, spec) -> TableDoc`; never mutates df; ingest df/Series/
   list/markdown (CSV via pathlib in facade later).
6. `render/text.py` — text oracle reading ONLY the TableDoc; box-drawing per GT formats.py
   concept. Anything it can't draw = data missing from the IR.
7. Fixture registry: Fabricator-driven named fixtures (plain, 2/3-level row MI, 2-level col MI,
   both, negatives, dates, ratios, big ints, nulls, math/html cells, flags, empty, headerless,
   colspan totals). Golden IR JSON per fixture (byte-equal) + golden text per fixture.

## Acceptance

- `uv run pytest` green; goldens committed and stable across runs/machines.
