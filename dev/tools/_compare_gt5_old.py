"""Child of compare_gt5.py — runs under greater-tables 5.3 in isolation.

Reads DataFrames (pickles; pandas/numpy pinned to the parent's versions) +
meta.json from the directory in argv[1] and writes old.json mapping fixture
name → 5.3 html (or an error blob). Must not import anything from this repo
— in this env ``greater_tables`` IS 5.3.
"""

import html
import json
import sys
import warnings
from pathlib import Path

import pandas as pd


def main() -> None:
    tmp = Path(sys.argv[1])
    meta = json.loads((tmp / 'meta.json').read_text(encoding='utf-8'))
    out = {}
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        from greater_tables import GT
    for name, m in meta.items():
        try:
            df = pd.read_pickle(tmp / f'{name}.pkl')
            gt = GT(df, caption=m['caption'], tikz=False, large_ok=True,
                    ratio_cols=m['ratio_cols'])
            out[name] = gt.html
        except Exception as exc:  # noqa: BLE001 — comparison page, show it
            out[name] = f'<pre>greater_tables 5.3 failed: ' \
                        f'{html.escape(str(exc))}</pre>'
    (tmp / 'old.json').write_text(json.dumps(out), encoding='utf-8')


if __name__ == '__main__':
    main()
