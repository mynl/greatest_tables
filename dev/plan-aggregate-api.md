# [aggregate-api] — SPA adoption in T:/worktrees/aggregate_api

Step 4 of `design.md`. Work happens in the aggregate_api repo (its own conventions apply).

## Deliverables

1. IR endpoint: `?format=ir` (or Accept-negotiated) beside existing FrameResponse routes,
   `include_raw='data'`; serializers stop `.`-join-flattening the MultiIndex on this path —
   greatest_tables receives the real DataFrame server-side.
2. Serve `gt-render.esm.js` from the installed package via `importlib.resources` (walker and
   IR emitter cannot version-skew).
3. Static toggle renders via `renderTable(doc)` — replaces the `{rows, html}` innerHTML blob
   route (`tables.py` + `/frame/{which}.html`).
4. **Delete the BeautifulSoup row-emphasis post-pass** (`tables.py:113-147`); emphasis rides
   as `row_flags` in the TableSpec.
5. csv-grid keeps the interactive/large-table role (density 65k rows etc.); GT2's `max_rows`
   truncates with a note instead of raising.

## Acceptance

- Dev servers up; portfolio loaded; Static/Interactive toggle shows book-quality table
  rendered client-side from the IR endpoint, row emphasis intact, no bs4 pass in the tree.
- Old `?tables=gt` path and its route deleted (or the comparison formally concluded).
