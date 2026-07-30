# [notebook-html] — Python HTML renderer + notebook integration + compat facade

Step 5 of `design.md` (see "CSS architecture" section).

## Deliverables

1. `render/html.py` — TableDoc → fragment; html.escape default, `html:true` opt-out; classes
   from the shared vocabulary; stylesheet embedded per fragment by default (~2 KB idempotent),
   `css='once'|'none'` opt-ins, `inline_css=True` flattener for HTMX/email.
2. Conformance: fragment parsed via stdlib html.parser must byte-match the walker's committed
   DOM transcripts per fixture.
3. `render/notebook.py` — `_repr_mimebundle_`: text/html always; text/latex only when
   requested or Quarto detected (QUARTO_* env) — kills GT 5.x's eager-TikZ waste.
4. `compat.py` — `GT(df, caption=..., ratio_cols=..., formatters=...)` facade with lazy cached
   `.doc/.html/.tikz/str()`. Markdown-blob ingest included (GT's md → df path).
5. `config.py` — YAML load for TableSpec/HouseStyle defaults.

## Acceptance

- Transcript conformance green for all fixtures.
- A notebook smoke test: representative fixtures render in JupyterLab without style bleed
  (scoped `.gt.gt`), no per-table id, deterministic output.
