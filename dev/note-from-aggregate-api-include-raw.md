# `include_raw='data'` and `irToGridInput` do not compose

Reported 2026-07-31 from the aggregate_api side, during the a35 adoption
(GT 1.9.0). Filed here rather than worked around there, per the handoff
note's hard rule 4.

> **Resolved in 1.11.0 — suggestion 1, as recommended.** `irToGridInput` now
> requires raw only on data columns whose text is *not* their value: a
> `string` (or `object`) dtype column falls through as text, and the throw
> names the dtype and the columns `include_raw='data'` actually covers.
> `include_raw='data'` keeps its meaning, and the documented pairing works.
> Drop the `include_raw=list(df.columns)` workaround when convenient.
> The **stub** half (suggestion 2 / `include_raw='all'`, so a numeric index
> sorts numerically) is still open — see `dev/pending.md`.

## The gap

Both the start-here note and the spec say the IR endpoint must build with
`include_raw='data'`, and that `irToGridInput` throws without it. Both are
true, but `'data'` is **not sufficient**, and the failure is total rather
than partial: one uncovered column throws away the whole document.

- `include_raw='data'` resolves to numeric, date and bool data columns
  (`_resolve_raw` via `dtypes.resolve_cols`, tag `'raw'`). A **string** data
  column gets no raw value.
- `irToGridInput` requires raw on **every** column whose role is `data`,
  string columns included, and throws naming the first one it finds.

So any frame with a string column outside the stub cannot go through the
adapter, even though it was built exactly as documented.

## How it showed up

Three of aggregate_api's Price tab frames, all built with
`include_raw='data'` and all throwing:

```
price.distortion_df   THREW: irToGridInput requires raw values on every data
                             column (missing on c1 "param_name")
reins.table           THREW: ... (missing on c0 "distortion")
reins.distortion_df   THREW: ... (missing on c1 "param_name")
```

`calibrate_distortions` returns a frame whose `param_name` is a string
column, and the reinsurance pricing table carries `distortion` and `basis`
as ordinary string columns rather than as the index.

The five frames that pass are the ones that happen to be all-numeric
outside the stub, which is why a smaller sample would have missed it.

## Workaround in use

`include_raw=list(df.columns)`, the explicit-list form, which does cover
string columns:

```
'data'           raw per data col: {'distortion': False, 'param_name': False, 'P': True}
explicit list    raw per data col: {'distortion': True,  'param_name': True,  'P': True}
True             raw per data col: {'distortion': False, 'param_name': False, 'P': True}
```

Note `include_raw=True` behaves as `'data'` here, though the `TableSpec`
docstring reads as though it might be broader.

## Suggestions, in preference order

1. **Make `irToGridInput` tolerate a string column with no raw**, falling
   back to `cell.text` for it. A string's formatted text *is* its value, so
   there is nothing to recover and nothing to re-infer. This keeps `'data'`
   meaning what it means and makes the documented pairing work.
2. Or add `include_raw='all'` and have the spec and the note name that as
   the requirement instead of `'data'`.
3. Either way the throw could name the fix: it currently advises
   `include_raw='data'`, which is precisely what the caller already did.

## Not a complaint about the adapter

Worth saying: with the explicit list it works on all twelve frames we feed
it, including two-level stubs, spanned headers and the declared percent
formats, and the round trip against the old `FrameResponse` path is cell
for cell identical after csv-grid's own coercion. The only differences left
are thousands separators on stub columns, which csv-grid parses back to the
same number.
