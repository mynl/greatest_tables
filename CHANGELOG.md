# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versioning is semantic.

## [1.0.0] - 2026-07-30

### Added

- [ir-core] Repo bootstrap: hatchling/uv project, `src/greatest_tables` layout,
  venv on the V:\dev dev drive (junction), design and step plan docs under `dev/`.
- `ir.py`: frozen pydantic models for the table document IR, `ir_version` 1 —
  `TableDoc`, `Column`, `Row`, `Cell`, `HeadCell`, `FormatSpec`. Write model rejects
  unknown fields; the read path (`TableDoc.read()`) ignores them so newer producers
  stay readable. Bare-string cell shorthand supported and canonicalized on dump.
- `engine/hashing.py`: canonical JSON (sorted keys, compact separators, NFC
  normalization, shortest round-trip floats) and `doc_hash` — sha256 over the
  canonical bytes with `hash`/`generator` excluded. Deterministic: no time salt.
- `fabricator.py`: synthetic DataFrame generator ported from greater_tables
  `fabrications.py`. Fixed in transit: `oversample` recursion passed arguments
  positionally-wrong; `random()` had a `'s' 'i'` literal-concatenation typo; the
  documented `missing` parameter now exists and is wired to `_insert_missing`;
  scipy dependency replaced with `rng.negative_binomial`; datetime columns are
  deterministic under a seed (fixed `now` reference passed through, no wall-clock
  reads); dead `random_date_within_last_n_years` (referenced `self` from a
  staticmethod) removed.
- `schema/ir-v1.json`: committed JSON Schema export of `TableDoc`, with a test that
  fails when the models drift from the committed schema.
- Test suite: exemplar golden IR documents (round-trip byte-equality), hash
  stability, read-path must-ignore, Fabricator determinism.

### Notes

- IR `ir_version` is decoupled from the package version and only bumps on breaking
  schema change.
