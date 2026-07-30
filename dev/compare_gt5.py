"""Side-by-side migration check: greater_tables 5.x vs greatest_tables.

Renders representative fixtures through both packages into one HTML page.
GT 5.x is pulled into an ephemeral environment so its import side effects
(global warnings filters etc.) never touch the project venv:

    uv run --with greater-tables==5.3.0 python dev/compare_gt5.py

Writes ``compare-gt5.html`` at the repo root (gitignored — a review
artifact, regenerate at will). Eyeball the pairs; the GT2 column is the
committed-golden behavior, differences are either 5.x bugs, documented GT2
deviations (see CHANGELOG 1.1.0/1.5.0), or regressions to investigate.
"""

import html
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'tests'))

from greatest_tables import build, render_html  # noqa: E402
from registry import fixtures  # noqa: E402

SAMPLE = ['plain', 'row-mi-2', 'both-mi', 'wide-floats', 'totals', 'dates',
          'ratios', 'wrap-high']


def old_html(df, spec):
    """Render via greater_tables 5.x; failures become visible in the page."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            from greater_tables import GT as GT5
        gt = GT5(df, caption=spec.caption or '', tikz=False, large_ok=True,
                 ratio_cols=list(spec.ratio_cols)
                 if isinstance(spec.ratio_cols, (list, tuple)) else
                 spec.ratio_cols)
        return gt.html
    except Exception as exc:  # noqa: BLE001 — comparison page, show the error
        return f'<pre>greater_tables failed: {html.escape(str(exc))}</pre>'


def main() -> None:
    fx = fixtures()
    blocks = []
    for name in SAMPLE:
        data, spec = fx[name]
        new = render_html(build(data, spec), css='none')
        old = old_html(data, spec) if not isinstance(data, (str, list)) \
            else '<pre>(non-DataFrame input)</pre>'
        blocks.append(f'''<h2>{name}</h2>
<div class="pair">
<div><h3>greater_tables 5.x</h3>{old}</div>
<div><h3>greatest_tables (GT2)</h3>{new}</div>
</div>''')
    from greatest_tables.render.css import css_text
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>greater_tables 5.x vs greatest_tables</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2em; }}
.pair {{ display: flex; gap: 3em; align-items: flex-start;
        margin-bottom: 2em; }}
.pair > div {{ flex: 1; overflow-x: auto; }}
h2 {{ font-family: monospace; margin-top: 2em; }}
h3 {{ font-size: 0.9em; opacity: 0.6; }}
{css_text()}
</style></head><body>
<h1>Migration check: greater_tables 5.x vs greatest_tables</h1>
{chr(10).join(blocks)}
</body></html>'''
    out = ROOT / 'compare-gt5.html'
    out.write_text(page, encoding='utf-8', newline='\n')
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
