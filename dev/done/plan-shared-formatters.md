# [shared-formatters] Column formats shared across a document's tables

Status: drafted 2026-10-22 at 8.1.0 (`7d39bb7`), at Steve's request. **Ruled 2026-10-22:** the
recommendation on each of the three questions under **Questions for Steve** is a decision, and a
fourth question raised at review (the warning's location, under **Execution log**) was ruled in.
Executed as 8.2.0.

## Goal

A document states its per-column formats once, and every table that has the column takes them.
A table without the column builds without a warning. A format written for one table still warns
when its column is missing: that check arrived in 7.4.0 and stays, because Steve asked on
2026-10-22, of the alternative that warned only on `'all'`, "are the other issues silently
ignored? I can't have that yet".

The rule adopted that day, while diagnosing aggregate's format sheets: **a shared declaration
applies where it matches and stays quiet; an entry written for one table must match or warn.**
greater_tables has no way to express the first half for formats. This plan adds one, and fixes a
silent loss in the `GT` facade found on the way.

## Current behavior

Verified 2026-10-22 against 8.1.0, using the pattern the quickstart teaches (`docs/quickstart.rst`
lines 151 to 170, "one YAML file can govern a whole document"):

```yaml
# house.yaml
float_format: ',.2f'
formatters: {paid: {kind: dec, digits: 1, negative: paren}}
```

```python
myGT = partial(GT, config_path='house.yaml')
```

| Call | Result |
|---|---|
| `myGT(a)`, where `a` has `paid` | `paid` takes the house rule: `1234.6`, `(20.0)` |
| `myGT(b)`, where `b` has no `paid` | `UserWarning: formatters key 'paid' matches no column and is ignored.` |
| `myGT(a, formatters={'x': 3})` | a warning for `'x'` only, and `paid` loses the house rule without a word: `1,234.56`, `-20.00` |

Three faults, from three places:

1. **The warning.** `engine/build.py` `_check_formatter_keys` (line 306) warns for every key of
   `TableSpec.formatters` that is not a label of the table (a stub name, a data column, or the
   leaf of a tuple column). A config file serves many tables, but its `formatters` reach the build
   as the table's own, so every table without `paid` warns.
2. **The silent replacement.** `compat.py` `GT.__init__` (lines 75 and 76) builds the spec as
   `merged.update({k: v for k, v in kwargs.items() if v is not None})`, so a `formatters` mapping
   passed at the call replaces the file's whole mapping instead of adding to it, and `paid` loses
   its format without a word. The class docstring describes `config_path` as "YAML TableSpec
   defaults which explicit arguments override", which reads as key by key. `aligners` and
   `row_flags`, in their mapping forms, lose entries the same way.
3. **`functools.partial`.** `partial(GT, formatters={'size': ...})`, which is how archivum builds
   its `qd`, warns on every table without `size`. A call passing its own `formatters` replaces the
   partial's mapping inside `partial`, before `GT` runs, so no merge in `GT` can recover it. This
   case needs a separate field, not a better merge.

Not affected: the column tags (`ratio_cols` and the rest) go through `engine/dtypes.py`
`resolve_cols`, which intersects a list with the table's labels and ignores a label the table
lacks; and the house defaults per kind (`float_format` and the rest) have no column key at all.

**Exposure today.** A search of `D:\Projects` and `V:\dev` on 2026-10-22 found no project of
Steve's calling GT's `config_path` or `load_spec`, apart from greater_tables' own docs and tests
and one scratch notebook under `D:\Projects\Hacks`. archivum's `partial` is the one live case, and
archivum is still on 5.2.1. aggregate's format sheets break the same rule from another direction
and are fixed inside aggregate (see **Consumers**). So a behavior change here costs Steve's
projects almost nothing; the reason to do it is the public API, whose quickstart teaches the
pattern that warns.

## The change

One feature, one bump: the steps below do not stand alone and land in one commit.

### Questions for Steve

1. **The name.** Recommended: `shared_formatters`. It is the rule's own word, and it reads right
   at both sites: `partial(GT, shared_formatters={...})` and `shared_formatters:` in a house file.
   Considered:
   - `default_formatters`, the working name in conversation on 2026-10-22. It is one letter from
     5.x `default_formatter`, a retired option that set a fallback f-string for every column
     (`docs/migration.md` line 185). `GT` still accepts that name and warns "GT: ignoring unknown
     option 'default_formatter' (gone in greater_tables)", so a dropped `s` would produce a
     warning about the wrong thing, for an option that meant something else.
   - `house_formatters`. It fits the spec docstring's "house defaults, one per kind" for
     `float_format` and the rest, but "house" also names house style and `HouseStyle`, which are
     renderer settings that never reach the engine.
2. **What `formatters:` in a config file means.** Recommended, (A): no change. `formatters` is per
   table and checked wherever it comes from; a house file writes `shared_formatters:` for formats
   meant for every table, and the unmatched-key warning gains a hint naming that field. The
   alternative, (B), was proposed in conversation on 2026-10-22: `GT(config_path=...)` moves a
   file's `formatters` into `shared_formatters`. This draft rejects it. `config.py` (line 1)
   documents a spec file as "project defaults or per-table", so under (B) one file would mean one
   thing through `GT(config_path=...)` and another through `build(df, load_spec(...))`; and
   `write_template(path, gt.spec)`, which dumps one table's settings for reuse, would turn checked
   entries into unchecked ones on the way back in. (A) gives each field one meaning everywhere.
   Its cost: an existing house file with `formatters:` keeps warning until renamed, and the hint
   gives the fix. No such file exists in Steve's projects.
3. **How far the merge reaches.** Recommended: every field whose file value and call value are
   both mappings merges key by key, the call winning. Today that is `formatters`,
   `shared_formatters`, `aligners` in its mapping form, and `row_flags` in its mapping form;
   anything else replaces, as now. A positional `aligners` string cannot merge with a mapping, so
   it replaces either way. The narrower option merges only the two format maps and leaves the same
   silent loss in `aligners`.

### [spec] The field

`TableSpec.shared_formatters` (`spec.py`), placed after `formatters` (line 130), with the same
value types (FormatSpec, mapping, sugar string, int, callable) and an empty dict as default. The
docstring entry, after `formatters` (lines 62 to 69):

> Per-column formats for every table that has the column, keyed and matched as `formatters` is.
> A key the table lacks is skipped without a warning, which makes this the place for formats
> shared by a document's tables: a config file, or a `functools.partial` of `GT`. An entry in
> `formatters` wins over one here. Nothing checks the keys, so a misspelled one does nothing and
> raises nothing; a format written for one table goes in `formatters`, which warns.

### [engine] Resolution

In `engine/build.py`:

- **Parse once per build.** Beside `format_defaults(spec)` (called at line 108), parse every
  non-callable `shared_formatters` value with `parse_sugar`. A bad value raises `ValueError`
  naming `TableSpec.shared_formatters[<key>]`, at the first table built, whether or not that table
  has the column. The keys go unchecked; the values do not.
- **Lookup order** in `_resolve_format` (line 326): `formatters[label]`, `formatters[leaf]`,
  `shared_formatters[label]`, `shared_formatters[leaf]`, where the leaf is a tuple label's last
  element. A table's own entry beats a shared one even when it matches only by leaf. The result
  fills the existing `user` slot, so nothing else in resolution moves: the kind still comes from
  the tag or the dtype, `table_float_format` still sits above both maps on the untagged float
  line, and the house default and the built-in still sit below.
- **`'all'`.** `_check_formatter_keys` (line 306) also warns on a `shared_formatters` key `'all'`
  that is not a label, with the existing `float_format` hint. It is the one key that is a mistake
  whatever the table, since the column selectors accept it and the format maps do not.
- **The hint.** The warning for any other unmatched `formatters` key gains one sentence: "A format
  meant for every table that has the column goes in shared_formatters, which skips a table
  without it."

### [facade] The merge

`compat.py` `GT.__init__`, lines 75 and 76: where the file's value and the call's value for a
field are both `Mapping`s, the spec takes `{**file_value, **call_value}`; otherwise the call's
value replaces, as now. In the class docstring, the `config_path` sentence becomes: explicit
arguments override the file, key by key for a mapping. The docstring also names
`shared_formatters` as the field for a `partial`, and notes that a call passing
`shared_formatters` to a `partial` that set it replaces the partial's mapping (Python's rule for
`partial`, outside `GT`).

No signature change: `shared_formatters` reaches `TableSpec` through `**overrides`, like every
spec field without a named parameter.

### [config] Template

`config.py` `_HINTS` (line 57) gains `'shared_formatters'`, with the `paid` example and the
comment `# every table with the column`. The `formatters` hint gains `# this table; warns if
missing`.

### [docs]

- `docs/quickstart.rst`: the house file example (lines 151 to 161) uses `shared_formatters:`,
  followed by two sentences on the split: shared formats for the document, `formatters` for one
  table, which warns on a missing column. The resolution line (lines 135 to 137) becomes
  `formatters[col]` → `shared_formatters[col]` → the house default → the built-in.
- `docs/design.rst` (line 59) and `docs/migration.md` (the resolution paragraph after the table,
  about line 188): the same chain.
- `guide/cheatsheet.qmd`: `shared_formatters` in the column format row (line 32); the resolution
  table (lines 238 to 246) takes `shared_formatters[col]` as the step after `formatters[col]` on
  every row; the `config_path` row (line 58) and both "one set of house rules for a document" rows
  (lines 115 and 173) mention it. Re-render the cheat sheet as `CLAUDE.md` describes.
- `README.md`, the "One set of house rules per document" bullet: one clause naming
  `shared_formatters`.
- `CHANGELOG.md`, 8.2.0, below.

### [tests]

In `tests/test_formats.py` beside the unmatched-key tests (lines 234 to 249), and in
`tests/test_house_rules.py` and `tests/test_compat.py`:

- a shared entry formats a table that has the column, and a table without it builds under
  `warnings.simplefilter('error')`;
- `formatters` beats `shared_formatters` on the same label; a `formatters` leaf entry beats a
  `shared_formatters` full tuple label;
- a shared key matches a tuple column by its leaf;
- a callable in `shared_formatters` formats its column (the `partial` case);
- a bad sugar value in `shared_formatters` raises naming the key, on a table without that column;
- `'all'` in `shared_formatters` warns;
- an unmatched `formatters` key warns with the new hint, and `'all'` keeps its own hint;
- the three calls of **Current behavior**, with the house file rewritten to `shared_formatters`:
  `myGT(b)` builds without a warning, `myGT(a, formatters={'x': 3})` sets `paid` as `(20.0)`, and
  a misspelled call key still warns;
- the merge: file `formatters` plus call `formatters` give the union, the call winning on a common
  key; file and call `aligners` mappings merge; a call `aligners` string replaces a file mapping;
- `test_house_yaml_round_trip` (`test_house_rules.py`, line 124) follows the quickstart to
  `shared_formatters`, and `write_template` round-trips a spec that sets both maps.

No golden moves: no fixture sets a format map through a config file. The IR does not change,
since a shared format resolves into the same `Column.format`, so `schema/ir-v1.json` and the
walker are untouched.

## Files

`src/greater_tables/spec.py`, `engine/build.py`, `compat.py`, `config.py`, `_version.py`;
`tests/test_formats.py`, `tests/test_house_rules.py`, `tests/test_compat.py`;
`docs/quickstart.rst`, `docs/design.rst`, `docs/migration.md`, `guide/cheatsheet.qmd`,
`README.md`, `CHANGELOG.md`.

## Version and output

8.2.0, a minor: a new public field. Draft CHANGELOG entry:

```markdown
## [8.2.0] - YYYY-MM-DD

### Added

- `shared_formatters`: per-column formats for every table that has the column, skipped without
  a warning where it does not. The place for a document's formats in a config file or a
  `partial(GT, ...)`; `formatters` stays per table and still warns on a missing column.

### Changed

- **Output changes.** `GT(df, config_path=...)`: a mapping passed at the call (`formatters`,
  `aligners`, `row_flags`) adds to the file's mapping key by key instead of replacing it, so a
  table that sets `formatters` at the call keeps the file's other entries.
- The warning for a `formatters` key that matches no column points to `shared_formatters`.
```

## Consumers

- **aggregate.** Its format sheet fix,
  `V:\worktrees\aggregate_REFACTOR\dev\plan-format-sheet-block-filter.md`, stands as written and
  does not wait for this release. aggregate has each block's labels in hand when it reads the
  sheet, filters its patterns against them already, and needs nothing new from greater_tables to
  filter its exact entries the same way. After 8.2.0, passing the sheet as `shared_formatters`
  and deleting that filter is an optional tidy.
- **aggregate-api.** `V:\dev\aggregate-api\dev\plan-greater-tables-8.md` is unaffected.
  `tables.py` `frame_spec` filters its `FORMATS` to the frame itself; the same optional tidy
  applies.
- **archivum.** When it leaves 5.2.1, its `qd` passes `shared_formatters` in the `partial`.

## Not done

- Warning only on `'all'`: rejected 2026-10-22, since every other misspelled key would then do
  nothing and report nothing.
- Reporting shared keys that matched no table across a whole document. That is a real typo
  signal, but it needs state across builds, which greater_tables does not keep. Possible later as
  an explicit call.

## Acceptance

- The three calls of **Current behavior**, with the house file using `shared_formatters`: `myGT(b)`
  builds under `warnings.simplefilter('error')`; `myGT(a, formatters={'x': 3})` sets `paid` as
  `1234.6` and `(20.0)`; `myGT(a, formatters={'piad': 1})` warns naming `'piad'`, with the hint.
- `uv run pytest` is green, about 980 tests plus the new ones.
- The cheat sheet renders and shows the new rows; `uv run --extra docs sphinx-build -b html docs
  docs/_build/html` adds no warning.

## Execution log

Executed 2026-10-22 as 8.2.0, one commit.

**Review findings, ruled in by Steve the same day ("yes to all four").**

- The **Current behavior** table said `myGT(a, formatters={'x': 3})` raised no warning. Rerun at
  8.1.0, it warns for `'x'`, which matches no column; the silent loss of `paid` is as stated. The
  row is corrected above.
- [warning location] Built through `GT`, the unmatched-key warning pointed at
  `functools.py:1126`, not at the caller's line: `GT.doc` is a `cached_property`, whose
  `__get__` frame lies outside the package, so `skip_file_prefixes` stopped there. The fix adds
  the `functools` source file to the skipped prefixes. Ruled into this bump as the fourth
  question.
- The merge removes one way of clearing a file's mapping: a call passing `formatters={}` used to
  empty it and now adds nothing. Accepted; the `GT` docstring says so.

**Divergences.**

- [docs] The cheat sheet's resolution table keeps its four steps, with one sentence above it
  saying each `formatters[col]` stands for `formatters[col]` then `shared_formatters[col]`. The
  planned extra column overflowed the PDF: inline code does not wrap, so `shared_formatters[col]`
  ran into the next column on every row.
- [docs] The cheat sheet needed four more edits for accuracy beyond the planned rows: the "two
  things to notice" paragraph, the key-matching paragraph (shared keys skip quietly; a table's own
  entry wins even by leaf), the "every format field takes the same input" sentence, and the
  callable row of the format strings table (`formatters` and `shared_formatters` only).
- [spec] The `float_format` and `table_float_format` docstring entries name `shared_formatters`
  beside `formatters`, and the `formatters` entry states that a key matching no column warns.
- [config] The `formatters` template hint shortened to `{paid: ',.1f'}   # this table; warns if
  missing`; the `paid` mapping example moved to the `shared_formatters` hint.
- [engine] The parse is a function `shared_formats(spec)` beside `format_defaults(spec)`, named in
  the same style, and `_resolve_format` takes its result as a new argument. Neither is exported.
- [CHANGELOG] Two bullets beyond the draft: house files with `formatters:` keep warning until
  renamed, and the warning-location fix under Fixed.

**Checks run.** `uv run pytest`: 987 passed, 9 skipped (983 collected before; 13 new tests).
`uv run --extra docs sphinx-build -b html docs docs/_build/html`: build succeeded, no warnings;
also a fresh `-E -q` build to a scratch directory, no output. The cheat sheet renders to HTML and
PDF; the PDF's resolution table fits. A 121pt overfull alignment later in the cheat sheet PDF is
not this change: the 8.1.0 cheat sheet renders it too (123pt).
