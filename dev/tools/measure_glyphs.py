"""Check the TextLength glyph table against real TeX metrics.

The table in ``render/textlength.py`` is Times/newtx metrics in milli-ems.
This compiles a probe that measures every character with ``\\settowidth`` in
the same font Etcher uses, and reports entries that are missing or off::

    uv run python dev/tools/measure_glyphs.py [--out DIR] [--chars STR]

Reports, per character, the table value against roman and bold measurements.
Nothing is written back — paste the corrections in deliberately, so the
committed table stays a reviewed artifact rather than a generated one.

Requires ``tectonic`` on PATH. Also useful after a font change: swap the
preamble below and re-measure.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
from greater_tables.render.textlength import (  # noqa: E402
    _DEFAULT_WIDTH, _WIDTH_TABLE,
)
from greater_tables.render.tikz import _escape  # noqa: E402

# the table's own domain plus the punctuation and symbols a table can meet
EXTRA = ('%+=/*@#&<>_' '°±×÷−…‰£€§¶†‡•ºª–—' '0123456789')

PREAMBLE = r"""\documentclass[11pt, border=5mm]{standalone}
\usepackage[T1]{fontenc}
\usepackage{newtxtext,newtxmath}
\usepackage{amsfonts}\usepackage{amsmath}\usepackage{tikz}
\newlength{\gtl}
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=None,
                    help='working directory (default: a temp dir)')
    ap.add_argument('--chars', default='',
                    help='extra characters to measure')
    args = ap.parse_args()

    chars = sorted(set(_WIDTH_TABLE) | set(EXTRA) | set(args.chars))
    body = []
    for i, c in enumerate(chars):
        # a space measures nothing on its own: bracket it and subtract
        if c.isspace() or c == '\xa0':
            probe, base = 'x' + ('~' if c == '\xa0' else c) + 'x', 'xx'
            body.append(rf'\settowidth{{\gtl}}{{{base}}}'
                        rf'\typeout{{GT|base|{i}|\the\gtl}}')
            body.append(rf'\settowidth{{\gtl}}{{\bfseries {base}}}'
                        rf'\typeout{{GT|baseb|{i}|\the\gtl}}')
        else:
            probe = _escape(c)
        body.append(rf'\settowidth{{\gtl}}{{{probe}}}'
                    rf'\typeout{{GT|rm|{i}|\the\gtl}}')
        body.append(rf'\settowidth{{\gtl}}{{\bfseries {probe}}}'
                    rf'\typeout{{GT|bf|{i}|\the\gtl}}')

    with tempfile.TemporaryDirectory() as tmp:
        out = args.out or Path(tmp)
        out.mkdir(parents=True, exist_ok=True)
        tex = out / 'measure_glyphs.tex'
        tex.write_text(
            PREAMBLE + '\\begin{document}\n'
            r'\settowidth{\gtl}{\hspace{1em}}\typeout{GT|em|-1|\the\gtl}'
            '\n' + '\n'.join(body) + '\n\\mbox{probe}\n\\end{document}\n',
            encoding='utf-8', newline='\n')
        subprocess.run(['tectonic', '--keep-logs', '--outdir', str(out),
                        str(tex)], capture_output=True, text=True)
        log_path = out / 'measure_glyphs.log'
        if not log_path.exists():
            raise SystemExit('tectonic produced no log — is it on PATH?')
        log = log_path.read_text(encoding='utf-8', errors='replace')

    got = {(k, int(i)): float(v) for k, i, v in
           re.findall(r'GT\|(\w+)\|(-?\d+)\|([\d.]+)pt', log)}
    em = got[('em', -1)]
    print(f'1em = {em}pt   (table default for unknown glyphs: {_DEFAULT_WIDTH})')
    print(f'{"char":<8}{"code":<9}{"table":>7}{"roman":>7}{"bold":>7}  note')

    missing, wrong, ratios = [], [], []
    for i, c in enumerate(chars):
        rm, bf = got.get(('rm', i)), got.get(('bf', i))
        if rm is None or bf is None:
            continue
        if c.isspace() or c == '\xa0':
            rm -= got[('base', i)]
            bf -= got[('baseb', i)]
        rm_m, bf_m = round(rm / em * 1000), round(bf / em * 1000)
        if rm_m > 0:
            ratios.append(bf_m / rm_m)
        table = _WIDTH_TABLE.get(c)
        if table is None:
            note, _ = 'MISSING', missing.append((c, rm_m))
        elif abs(table - rm_m) > 15:
            note, _ = f'off by {rm_m - table:+d}', wrong.append((c, table, rm_m))
        else:
            continue
        print(f'{c!r:<8}U+{ord(c):04X}  {str(table):>7}{rm_m:>7}{bf_m:>7}  {note}')

    if not missing and not wrong:
        print('\nglyph table agrees with the font everywhere measured.')
    else:
        print(f'\n{len(missing)} missing, {len(wrong)} off by more than 15:')
        for c, w in missing:
            print(f"    {c!r}: {w},")
        for c, t, w in wrong:
            print(f"    {c!r}: {w},   # was {t}")
    ratios.sort()
    if ratios:
        n = len(ratios)
        print(f'\nbold/roman per glyph: median {ratios[n // 2]:.3f}  '
              f'p90 {ratios[int(0.9 * n)]:.3f}  max {ratios[-1]:.3f}  '
              '(render.tikz._BOLD_PERCENT covers headers)')


if __name__ == '__main__':
    main()
