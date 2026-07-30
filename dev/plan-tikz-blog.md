# [tikz-blog] — TikZ renderer + blog/Quarto migration

Step 6 of `design.md`.

## Deliverables

1. `render/tikz.py` — ONE implementation from TableDoc (salvage the live `make_tikz` knowledge,
   `core.py:1660`, leave the two dead variants and ~125 unreachable lines behind). New
   capability: real colspan support (GT 5.x silently returns '' on non-unique columns).
   `TextLength` char-width estimation lives here and only here.
2. `render/etcher.py` — Etcher salvaged; hardcoded Windows paths and `os.startfile` edges
   cleaned (config-driven tool paths, pathlib).
3. Rule drawing from break_depths + HouseStyle weights (w2tikz mapping preserved).

## Acceptance

- TikZ output for every golden fixture compiles via Etcher (pdflatex available locally).
- Migration check: representative real blog tables rendered through GT 5.x and the GT2 facade;
  text-oracle diff reviewed; HTML eyeballed. greater_tables 5.x stays frozen for old posts.
