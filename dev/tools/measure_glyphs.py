"""Measure a face's glyph widths in TeX, and check a face's table against it.

The TikZ layout sizes columns from per-face glyph tables in
``render/fonts.py``, integer milli-ems, roman and bold. This compiles probes
with tectonic that measure with ``\\settowidth``, in Times (newtx, the face
``Etcher`` compiles with) or in any face named by its font file, which
tectonic resolves from its bundle on any machine::

    uv run python dev/tools/measure_glyphs.py                     # Times: check the table
    uv run python dev/tools/measure_glyphs.py --face stix-two \\
        --font STIXTwoText-Regular.otf --bold STIXTwoText-Bold.otf   # check another face
    ... --emit                                                    # print the face's record
    ... --corpus                                                  # whole cells, the acceptance check

Without ``--emit`` it reports, per character, where the committed table and
the measurement differ by more than 15 milli-ems. With ``--emit`` it prints the
face's ``Face(...)`` record as a Python literal. Nothing is written back: paste
the record in deliberately, so the committed table stays a reviewed artifact
rather than a generated one.

``--corpus`` measures every header (bold) and body (roman) cell of the test
fixtures as a whole string, and reports the actual width over the estimate:
the standard a table meets is a median within 1% of 1.000 and a p99 of at
most 1.02. Cells holding math or html are skipped; math is out of the glyph
tables' scope.

The faces in ``render/fonts.py`` were measured from these files:

========================  =============================  ==========================
face                      --font                         --bold
========================  =============================  ==========================
times                     (newtx, the default preamble)
stix-two                  STIXTwoText-Regular.otf        STIXTwoText-Bold.otf
latin-modern              lmroman10-regular.otf          lmroman10-bold.otf
lato                      Lato-Regular.ttf               Lato-Bold.ttf
fira-sans                 FiraSans-Regular.otf           FiraSans-Bold.otf
========================  =============================  ==========================
"""

from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
from greater_tables import build
from greater_tables.render.fonts import DEFAULT_WIDTH, FACES
from greater_tables.render.textlength import display_milli
from greater_tables.render.tikz_layout import tex_escape

# the punctuation and symbols a table can meet, beyond the Times table's keys
EXTRA = ('%+=/*@#&<>_' '°±×÷−…‰£€§¶†‡•ºª–—' '0123456789')

TIMES_PREAMBLE = r"""\documentclass[11pt, border=5mm]{standalone}
\usepackage[T1]{fontenc}
\usepackage{newtxtext,newtxmath}
\newlength{\gtl}
"""

FILE_PREAMBLE = r"""\documentclass[11pt, border=5mm]{standalone}
\usepackage{fontspec}
\setmainfont{%s}[BoldFont=%s]
\newlength{\gtl}
"""


def compile_probe(preamble: str, body: list[str], out: Path) -> dict:
    """Compile the probe; return ``{(kind, index): points}`` from its log."""
    tex = out / 'measure_glyphs.tex'
    tex.write_text(
        preamble + '\\begin{document}\n'
        r'\settowidth{\gtl}{\hspace{1em}}\typeout{GT|em|-1|\the\gtl}'
        '\n' + '\n'.join(body) + '\n\\mbox{probe}\n\\end{document}\n',
        encoding='utf-8', newline='\n')
    subprocess.run(['tectonic', '--keep-logs', '--outdir', str(out), str(tex)],
                   capture_output=True, text=True, check=False)
    log_path = out / 'measure_glyphs.log'
    if not log_path.exists():
        raise SystemExit('tectonic produced no log — is it on PATH, and does '
                         'the bundle hold the font file?')
    log = log_path.read_text(encoding='utf-8', errors='replace')
    return {(k, int(i)): float(v) for k, i, v in
            re.findall(r'GT\|(\w+)\|(-?\d+)\|([\d.]+)pt', log)}


def probe(kind: str, i: int, text: str, bold: bool = False) -> str:
    series = r'\bfseries ' if bold else ''
    return (rf'\settowidth{{\gtl}}{{{series}{text}}}'
            rf'\typeout{{GT|{kind}|{i}|\the\gtl}}')


def glyphs(preamble: str, chars: list[str], out: Path) -> tuple[dict, dict]:
    """Roman and bold milli-em widths of each character, as measured."""
    body = []
    for i, c in enumerate(chars):
        # a space measures nothing on its own: bracket it and subtract
        if c.isspace() or c == '\xa0':
            text = 'x' + ('~' if c == '\xa0' else c) + 'x'
            body += [probe('base', i, 'xx'), probe('baseb', i, 'xx', True)]
        else:
            text = tex_escape(c, math=False)
        body += [probe('rm', i, text), probe('bf', i, text, True)]
    got = compile_probe(preamble, body, out)
    em = got[('em', -1)]
    roman, bold = {}, {}
    for i, c in enumerate(chars):
        rm, bf = got.get(('rm', i)), got.get(('bf', i))
        if rm is None or bf is None:
            continue
        if c.isspace() or c == '\xa0':
            rm -= got[('base', i)]
            bf -= got[('baseb', i)]
        # a glyph the face lacks sets nothing: leave it to the default width
        if rm > 0:
            roman[c] = round(rm / em * 1000)
        if bf > 0:
            bold[c] = round(bf / em * 1000)
    return roman, bold


def corpus() -> list[tuple[str, bool]]:
    """Every plain header (bold) and body (roman) cell text of the fixtures."""
    from registry import fixtures
    seen: dict[tuple[str, bool], None] = {}
    for data, spec in fixtures().values():
        doc = build(data, spec)
        cells = [(c, True) for row in doc.head for c in row]
        cells += [(c, False) for row in list(doc.body) + list(doc.foot)
                  for c in row.cells]
        for c, bold in cells:
            text = getattr(c, 'text', c)
            if (not isinstance(text, str) or not text.strip() or '$' in text
                    or getattr(c, 'html', False) or getattr(c, 'math', False)):
                continue
            seen[(text, bold)] = None
    return list(seen)


def check_corpus(preamble: str, face: str, out: Path) -> None:
    texts = corpus()
    body = [probe('cell', i, tex_escape(t, math=False).replace('\xa0', '~'), b)
            for i, (t, b) in enumerate(texts)]
    got = compile_probe(preamble, body, out)
    em = got[('em', -1)]
    ratios = []
    for i, (t, b) in enumerate(texts):
        actual = got.get(('cell', i))
        estimate = display_milli(t, math=False, font=face, bold=b)
        if actual and estimate:
            ratios.append((actual / em * 1000 / estimate, t, b))
    ratios.sort()
    r = [x for x, _t, _b in ratios]
    n = len(r)
    print(f'{face}: {n} cells, actual/estimate median {statistics.median(r):.3f}  '
          f'p01 {r[int(0.01 * n)]:.3f}  p99 {r[min(n - 1, int(0.99 * n))]:.3f}  '
          f'max {r[-1]:.3f}')
    print('widest over their estimate:')
    for x, t, b in ratios[-8:]:
        print(f'    {x:.3f}  {"bold " if b else "roman"}  {t!r}')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--face', default='times', help='the face key in render/fonts.py')
    ap.add_argument('--font', help='regular font file (default: newtx Times)')
    ap.add_argument('--bold', help='bold font file, with --font')
    ap.add_argument('--emit', action='store_true', help="print the face's record")
    ap.add_argument('--corpus', action='store_true',
                    help='measure whole fixture cells against the estimate')
    ap.add_argument('--out', type=Path, default=None,
                    help='working directory (default: a temp dir)')
    ap.add_argument('--chars', default='', help='extra characters to measure')
    args = ap.parse_args()
    if args.font and not args.bold:
        ap.error('--font needs --bold')
    preamble = (FILE_PREAMBLE % (args.font, args.bold) if args.font
                else TIMES_PREAMBLE)

    with tempfile.TemporaryDirectory() as tmp:
        out = args.out or Path(tmp)
        out.mkdir(parents=True, exist_ok=True)
        if args.corpus:
            check_corpus(preamble, args.face, out)
            return
        times = FACES['times'].roman
        chars = sorted(set(times) | set(EXTRA) | set(args.chars))
        roman, bold = glyphs(preamble, chars, out)

    if args.emit:
        missing = sorted(set(chars) - set(roman))
        print(f"    '{args.face}': Face(")
        for name, table in (('roman', roman), ('bold', bold)):
            items = [f'{c!r}: {w}' for c, w in sorted(table.items())]
            lines, line = [], ''
            for item in items:
                if len(line) + len(item) + 2 > 84:
                    lines.append(line.rstrip())
                    line = ''
                line += item + ', '
            lines.append(line.rstrip().rstrip(','))
            print(f'        {name}={{\n' + '\n'.join(f'            {x}' for x in lines)
                  + '},')
        print('    ),')
        if missing:
            print(f'# not in the face, left to the default {DEFAULT_WIDTH}: '
                  + ' '.join(missing))
        return

    record = FACES.get(args.face)
    print(f'{args.face}: {len(roman)} glyphs measured')
    if record is None:
        print('not in render/fonts.py yet; --emit prints its record')
        return
    for name, table, have in (('roman', roman, record.roman),
                              ('bold', bold, record.bold)):
        off = [(c, have.get(c), w) for c, w in sorted(table.items())
               if have.get(c) is None or abs(have[c] - w) > 15]
        print(f'{name}: ' + ('agrees everywhere measured' if not off
                             else f'{len(off)} missing or off by more than 15'))
        for c, h, w in off:
            print(f'    {c!r}: table {h}, measured {w}')


if __name__ == '__main__':
    main()
