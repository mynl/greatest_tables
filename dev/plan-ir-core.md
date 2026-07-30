# [ir-core] — IR models, hashing, Fabricator, test harness

Step 1 of `design.md`. Delivers version 1.0.0.

## Deliverables

1. Repo bootstrap: hatchling/uv pyproject, `src/greatest_tables` layout, venv junction to
   `V:\dev\greatest-tables\.venv`, CLAUDE.md, README, CHANGELOG, .gitignore, dev/ plan docs.
2. `ir.py` — frozen pydantic models: `TableDoc`, `Column`, `Row`, `Cell`, `HeadCell`,
   `FormatSpec`. Write model `extra='forbid'`; read path (`TableDoc.read()`) tolerant
   (`extra='ignore'` semantics) so newer producers stay readable. Bare-string cell shorthand
   accepted on input, emitted on canonical dump. Validators: `n_head_levels == len(head)`,
   stub/level consistency, span values >= 1, closed flag vocab.
3. `engine/hashing.py` — `canonical_json(obj)` (sorted keys, compact, NFC, repr floats) and
   `doc_hash(doc)` (sha256 12-hex over canonical bytes excluding `hash` + `generator`).
4. `fabricator.py` — port of GT `fabrications.py` with fixes (see CHANGELOG 1.0.0); data files
   `data/words-12.md`, `data/tex_list.csv` carried as package data. Deterministic under seed,
   including datetime columns (fixed `now` reference).
5. `schema/ir-v1.json` — committed `TableDoc.model_json_schema()` export + drift-guard test.
6. Tests: exemplar golden IR docs under `tests/golden/ir/` (hand-authored, round-trip
   byte-equal), hash stability, must-ignore read path, Fabricator determinism (same seed →
   identical df).

## Acceptance

- `uv run pytest` green.
- `schema/ir-v1.json` committed and guarded.
- Golden exemplar docs committed; re-serialization is byte-identical.
- Note: full fixture-driven goldens (Fabricator → build() → IR) arrive with [engine], since
  they need the engine. Here goldens are hand-authored exemplars validating the schema.
