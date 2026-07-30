# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versioning is semantic.

## [1.1.0] - 2026-07-30

### Added

- [engine] `spec.py`: `TableSpec` (semantics: caption/label/notes, semantic column
  tags as list|'all'|regex, per-column format sugar, aligners, row/cell flags,
  include_raw, max_rows, sparsify switches, pef bounds) and `HouseStyle` stub.
- `engine/dtypes.py`: arrow-aware dtype classification (date vs datetime split on
  time-of-day), selector resolution, GT alignment ladder, wrap hints.
- `engine/formats.py`: format sugar parsing accepting both csv-grid spec strings
  (`',.1f'`, `'year'`, `'eng'`, strftime) and GT f-strings (`'{x:.1%}'`); the
  salvaged column-statistics float inference; pure `apply_format` incl.
  engineering/SI notation and paren-negative accounting style.
- `engine/structure.py`: the single implementation of hierarchy logic — row break
  depths, stub rowspan layout, header colspan groups, column-group break depths.
- `engine/build.py`: `build(data, spec) -> TableDoc` for DataFrame / Series /
  list / markdown pipe table (caption/`{#tbl-label}`/alignment extracted). Never
  mutates input. Auto neg flags, `$...$` math detection, html_cols, JSON-safe raw
  values (big ints as strings, ISO dates, NaN→null).
- `render/text.py`: the conformance oracle — box-drawing renderer reading only
  the TableDoc: spans, partial rules at break depths, flag gutter, math markers.
- Fixture registry (18 fixtures, all Fabricator-generated or tiny synthetics) with
  committed golden IR and golden text files; 72 tests total.
- `.gitattributes` guards golden files from newline conversion; version now single-
  sourced from `_version.py` (hatchling dynamic).

### Changed

- Deliberate deviations from greater_tables 5.x behavior: engineering format is a
  column-level decision (5.x switched per cell, mixing formats within a column);
  missing values render as an em dash in formatted columns; the >50-row raise is
  replaced by `max_rows` truncation with an appended note; `'all'` selectors cover
  data columns only; format resolution returns data objects, structurally killing
  the 5.x late-binding closure bug.
- pytest cache moved to the V:\dev drive via junction (NAS path denies the cache
  dir creation rename).

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
