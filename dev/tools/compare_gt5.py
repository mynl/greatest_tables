"""Side-by-side migration check: greater_tables 5.x vs the GT2 rewrite.

Since the 1.9.0 rename both generations share the import name
``greater_tables``, so 5.x runs in an ISOLATED subprocess (`uv run
--no-project`) and DataFrames cross the boundary as parquet — no name
collision, and 5.x's import side effects (global warnings filters) never
touch the project venv. Run from the repo root with the project env:

    uv run python dev/tools/compare_gt5.py

Writes ``compare-gt5.html`` at the repo root (gitignored — a review
artifact, regenerate at will). The GT2 column is the committed-golden
behavior; differences are either 5.x bugs, documented GT2 deviations (see
CHANGELOG 1.1.0/1.5.0), or regressions to investigate.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / 'tests'))

from greater_tables import build, render_html  # noqa: E402
from greater_tables.render.css import css_text  # noqa: E402
from registry import fixtures  # noqa: E402

SAMPLE = ['plain', 'row-mi-2', 'both-mi', 'wide-floats', 'totals', 'dates',
          'ratios', 'wrap-high']


def old_htmls(frames: dict, tmp: Path) -> dict:
    """Render every sample through 5.3 in an isolated env; return html blobs.

    DataFrames cross as pickles (parquet can't carry MultiIndex columns);
    pinning the child to the parent's exact pandas/numpy makes that safe.
    """
    import numpy as np
    import pandas as pd
    meta = {}
    for name, (df, spec) in frames.items():
        df.to_pickle(tmp / f'{name}.pkl')
        meta[name] = {
            'caption': spec.caption or '',
            'ratio_cols': list(spec.ratio_cols)
            if isinstance(spec.ratio_cols, (list, tuple)) else spec.ratio_cols,
        }
    (tmp / 'meta.json').write_text(json.dumps(meta), encoding='utf-8')
    result = subprocess.run(
        ['uv', 'run', '--no-project', '--with', 'greater-tables==5.3.0',
         '--with', f'pandas=={pd.__version__}',
         '--with', f'numpy=={np.__version__}',
         'python', str(Path(__file__).parent / '_compare_gt5_old.py'), str(tmp)],
        capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        raise RuntimeError(f'5.x child failed: {result.stderr[-800:]}')
    return json.loads((tmp / 'old.json').read_text(encoding='utf-8'))


def main() -> None:
    fx = fixtures()
    frames = {name: fx[name] for name in SAMPLE
              if not isinstance(fx[name][0], (str, list))}
    with tempfile.TemporaryDirectory() as td:
        old = old_htmls(frames, Path(td))
    blocks = []
    for name in SAMPLE:
        data, spec = fx[name]
        new = render_html(build(data, spec), css='none')
        blocks.append(f'''<h2>{name}</h2>
<div class="pair">
<div><h3>greater_tables 5.3</h3>{old.get(name, '<pre>(skipped)</pre>')}</div>
<div><h3>greater_tables 1.9 (GT2)</h3>{new}</div>
</div>''')
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>greater_tables 5.3 vs GT2</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2em; }}
.pair {{ display: flex; gap: 3em; align-items: flex-start;
        margin-bottom: 2em; }}
.pair > div {{ flex: 1; overflow-x: auto; }}
h2 {{ font-family: monospace; margin-top: 2em; }}
h3 {{ font-size: 0.9em; opacity: 0.6; }}
{css_text()}
</style></head><body>
<h1>Migration check: greater_tables 5.3 vs the GT2 rewrite</h1>
{chr(10).join(blocks)}
</body></html>'''
    out = ROOT / 'compare-gt5.html'
    out.write_text(page, encoding='utf-8', newline='\n')
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
