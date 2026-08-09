r"""Side-by-side check of the two TikZ engines: pages, milliseconds, heights.

``HouseStyle.tikz_engine`` chooses between the ``matrix of nodes`` renderer
and the one-node ``tabular`` renderer. They are meant to look the same and
differ only in what they cost TeX, so this tool renders the same corpus both
ways and reports all three things that matter:

- **compare-engines.pdf** — one table per page, matrix above, tabular below.
  The page is deliberately tall (26 in) so a table that outgrows its box is
  *visible* rather than silently dropped, which is exactly how the first
  version of the tabular engine hid a 29-row overflow.
- **compare-engines.md** — per-table compile time for each engine, the
  speedup, and how far the tabular height drifts from the matrix height.
- the same table on stdout.

Run from the repo root with the project env::

    uv run python dev/tools/compare_engines.py
    uv run python dev/tools/compare_engines.py --fab 60 --out dev/out

Corpus, in increasing order of realism: the committed golden IR documents, a
Fabricator sweep covering the shapes the goldens do not (deep stubs, column
groups, prose, math, totals, tall), and ``--corpus DIR`` for a directory of
IR JSON documents. Note the deviation from ``dev/plan-tikz-tabular.md``: a
*rendered* book ``.tex`` cannot be used directly, because its tables are
already matrix output and there is no IR to re-render them from — timing the
two engines against each other needs both to start from the same document.
Dump IR alongside the book to compare against a real corpus.

Heights come from one extra compile per engine: each picture goes into a
``\savebox`` and its dimensions are ``\typeout``-ed to the log, rather than
compiling every table standalone.

Outputs land in ``dev/out`` (gitignored) — review artifacts, regenerate at will.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / 'tests'))

from greater_tables import HouseStyle, TableDoc, TableSpec, build  # noqa: E402
from greater_tables.fabricator import Fabricator                   # noqa: E402
from greater_tables.render.tikz import render_tikz                 # noqa: E402

ENGINES = ('matrix', 'tabular')
IR_DIR = ROOT / 'tests' / 'golden' / 'ir'

# A preamble with the packages a real Quarto PDF build brings, so line
# breaking and rule widths behave the way they do in anger.
PREAMBLE = r"""\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,xcolor,graphicx,microtype}
\usepackage{booktabs,array,multirow}
\usepackage{tikz}
\usetikzlibrary{matrix,calc,fit}
\newcommand{\I}{\vphantom{lp}}
\setlength{\parindent}{0pt}
"""

FILLER = ('Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do '
          'eiusmod tempor incididunt ut labore et dolore magna aliqua.\n\n')

# Shapes the committed goldens do not cover. (name, make kwargs, spec kwargs)
SWEEP: list[tuple[str, dict, dict]] = [
    ('fab-plain',     dict(rows=8, data_spec='sfid'), {}),
    ('fab-numeric',   dict(rows=12, data_spec='f' * 8), {}),
    ('fab-groups-2',  dict(rows=8, data_spec='ff', column_groups=4,
                           column_levels=2), {}),
    ('fab-groups-3',  dict(rows=10, data_spec='fff', column_groups=3,
                           column_levels=3), {}),
    ('fab-deep-stub', dict(rows=20, data_spec='ffi', index_levels=3), {}),
    ('fab-prose',     dict(rows=6, data_spec='w14ff'), {}),
    ('fab-math',      dict(rows=8, data_spec='xff'), {}),
    ('fab-mixed',     dict(rows=10, data_spec='s3dyrfl'), {}),
    ('fab-missing',   dict(rows=10, data_spec='ffff', missing=0.2), {}),
    ('fab-totals',    dict(rows=9, data_spec='fff'),
     dict(row_flags={8: ['total']})),
    ('fab-tall',      dict(rows=32, data_spec='ffi', index_levels=2), {}),
    ('fab-one-col',   dict(rows=8, data_spec='f'), {}),
]

_PIC_RE = re.compile(r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}', re.S)
_BOX_RE = re.compile(r'GTBOX (\d+) ([\d.]+)pt\s*([\d.]+)pt\s*([\d.]+)pt')


# --------------------------------------------------------------- the corpus

def collect(fab: int, corpus: Path | None) -> list[tuple[str, TableDoc]]:
    """Golden IR documents, then a Fabricator sweep, then any extra corpus."""
    docs = [(p.stem, TableDoc.read(p.read_bytes()))
            for p in sorted(IR_DIR.glob('*.json'))]
    fabricator = Fabricator(seed=20260809)
    for i in range(fab):
        name, make_kw, spec_kw = SWEEP[i % len(SWEEP)]
        if i >= len(SWEEP):
            name = f'{name}-{i // len(SWEEP)}'
        df = fabricator.make(**make_kw)
        docs.append((name, build(df, TableSpec(**spec_kw))))
    if corpus:
        docs += [(f'corpus-{p.stem}', TableDoc.read(p.read_bytes()))
                 for p in sorted(corpus.glob('*.json'))]
    # a column-less document renders to a comment, not a picture: nothing to
    # compare, and a bare comment inside \savebox eats its closing brace
    dropped = [n for n, d in docs if not d.columns]
    if dropped:
        print(f'skipping {len(dropped)} table(s) with no columns: '
              f'{", ".join(dropped)}')
    return [(n, d) for n, d in docs if d.columns]


def picture(doc: TableDoc, engine: str) -> str:
    """The bare tikzpicture for a document, float wrapper stripped.

    Floats would drift around the page and ruin a side-by-side, and a
    ``\\savebox`` cannot hold one at all.
    """
    tex = render_tikz(doc, HouseStyle(tikz_engine=engine))
    found = _PIC_RE.search(tex)
    return found.group(0) if found else r'\relax'


# ------------------------------------------------------------------ tectonic

def compile_tex(path: Path, outdir: Path, keep_logs: bool = False) -> float:
    """Compile once; return elapsed seconds. Failures are reported, not raised
    — a table that will not compile is a finding, not a reason to stop."""
    cmd = ['tectonic', '-X', 'compile', str(path), '--outdir', str(outdir),
           '-Zcontinue-on-errors']
    if keep_logs:
        cmd.append('--keep-logs')
    start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        print(f'  ! {path.name} exited {result.returncode}')
        for line in result.stderr.strip().split('\n')[-6:]:
            print(f'    {line}')
    return elapsed


def best_of(path: Path, outdir: Path, runs: int = 2) -> float:
    """Minimum of ``runs`` compiles — the cleanest estimate of the real cost."""
    return min(compile_tex(path, outdir) for _ in range(runs))


def document(body: str, *, paper: str = '') -> str:
    geometry = paper or 'margin=1in'
    return (f'\\documentclass[11pt]{{article}}\n'
            f'\\usepackage[{geometry}]{{geometry}}\n{PREAMBLE}'
            f'\\begin{{document}}\n{body}\n\\end{{document}}\n')


# ------------------------------------------------------------------- heights

def measure(docs, outdir: Path) -> dict[str, dict[str, float]]:
    """Width and height of every table, per engine, from one compile each.

    Each picture is stashed in a ``\\savebox`` whose dimensions go to the log,
    which is far cheaper than compiling every table standalone.
    """
    out: dict[str, dict[str, float]] = {e: {} for e in ENGINES}
    for engine in ENGINES:
        body = ['\\newsavebox{\\gtbox}']
        for i, (name, doc) in enumerate(docs):
            body.append(f'\\savebox{{\\gtbox}}{{{picture(doc, engine)}}}')
            # \space, because TeX swallows the space after a control sequence
            body.append(f'\\typeout{{GTBOX {i} \\the\\wd\\gtbox\\space'
                        f'\\the\\ht\\gtbox\\space\\the\\dp\\gtbox}}')
        body.append('measured.')
        path = outdir / f'measure-{engine}.tex'
        path.write_text(document('\n'.join(body)), encoding='utf-8')
        compile_tex(path, outdir, keep_logs=True)
        log = path.with_suffix('.log')
        text = log.read_text(encoding='utf-8', errors='replace') \
            if log.exists() else ''
        for i, wd, ht, dp in _BOX_RE.findall(text):
            name = docs[int(i)][0]
            out[engine][name] = {'width': float(wd),
                                 'height': float(ht) + float(dp)}
        missing = len(docs) - len(out[engine])
        if missing:
            print(f'  ! {engine}: {missing} of {len(docs)} boxes unmeasured '
                  f'(see {log.name})')
    return out


# -------------------------------------------------------------------- timing

def aggregate_time(docs, outdir: Path) -> dict[str, float]:
    """Whole-corpus compile time per engine, net of a matched baseline."""
    baseline = outdir / 'time-baseline.tex'
    baseline.write_text(document(FILLER * len(docs)), encoding='utf-8')
    compile_tex(baseline, outdir)           # discard: tectonic cold start
    times = {'baseline': best_of(baseline, outdir)}
    for engine in ENGINES:
        body = '\n\n'.join(FILLER + picture(doc, engine) for _, doc in docs)
        path = outdir / f'time-{engine}.tex'
        path.write_text(document(body), encoding='utf-8')
        times[engine] = best_of(path, outdir)
    return times


def per_table_time(docs, outdir: Path, copies: int = 8
                   ) -> dict[str, dict[str, float]]:
    """Milliseconds per table, per engine: ``copies`` of one table per
    document, net of a matched baseline of the same length."""
    baseline = outdir / 'per-baseline.tex'
    baseline.write_text(document(FILLER * copies), encoding='utf-8')
    compile_tex(baseline, outdir)           # discard: cold start
    base = best_of(baseline, outdir)
    out: dict[str, dict[str, float]] = {e: {} for e in ENGINES}
    for k, (name, doc) in enumerate(docs, start=1):
        print(f'  timing {k}/{len(docs)} {name}', flush=True)
        for engine in ENGINES:
            body = '\n\n'.join([FILLER + picture(doc, engine)] * copies)
            path = outdir / f'per-{engine}.tex'
            path.write_text(document(body), encoding='utf-8')
            out[engine][name] = max(
                0.0, (best_of(path, outdir) - base) / copies * 1000)
    return out


# ---------------------------------------------------------------------- pdf

def side_by_side(docs, outdir: Path) -> Path:
    """One page per table: today's matrix above, the tabular below."""
    body = []
    for name, doc in docs:
        shape = f'{len(doc.body) + len(doc.foot)} rows x {len(doc.columns)} cols'
        heads = f'{len(doc.head)} header level(s)'
        body.append(f'\\section*{{{name.replace("_", " ")}}}')
        body.append(f'{shape}, {heads}\\par\\medskip')
        body.append(r'\textbf{matrix --- one pgf node per cell}\par\medskip')
        body.append(picture(doc, 'matrix'))
        body.append(r'\par\bigskip\textbf{tabular --- one node}\par\medskip')
        body.append(picture(doc, 'tabular'))
        body.append(r'\clearpage')
    path = outdir / 'compare-engines.tex'
    # tall on purpose: an overflowing table must be visible, not dropped
    path.write_text(document(
        '\n\n'.join(body),
        paper='margin=0.6in,paperwidth=8.5in,paperheight=26in'),
        encoding='utf-8')
    compile_tex(path, outdir)
    return path.with_suffix('.pdf')


# ------------------------------------------------------------------- report

def report(docs, sizes, timings, totals) -> str:
    lines = ['| table | cols | rows | matrix | tabular | speedup | '
             'height matrix | height tabular | drift |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    drifts = []
    for name, doc in docs:
        m = sizes['matrix'].get(name, {})
        t = sizes['tabular'].get(name, {})
        hm, ht = m.get('height'), t.get('height')
        if hm and ht:
            drift = (ht - hm) / hm * 100
            drifts.append(drift)
            flag = ' !!' if abs(drift) > 2 else ''
            geom = f'{hm:.1f}pt | {ht:.1f}pt | {drift:+.1f}%{flag}'
        else:
            geom = '- | - | -'
        if timings:
            tm = timings['matrix'].get(name, 0.0)
            tt = timings['tabular'].get(name, 0.0)
            speed = f'{tm / tt:.0f}x' if tt > 0.05 else '-'
            cost = f'{tm:.0f} ms | {tt:.1f} ms | {speed}'
        else:
            cost = '- | - | -'
        lines.append(f'| {name} | {len(doc.columns)} | '
                     f'{len(doc.body) + len(doc.foot)} | {cost} | {geom} |')

    over = sum(1 for d in drifts if abs(d) > 2)
    lines.append('')
    lines.append(f'**{len(docs)} tables.** Whole-corpus compile: matrix '
                 f'{totals["matrix"]:.2f} s, tabular {totals["tabular"]:.2f} s, '
                 f'baseline {totals["baseline"]:.2f} s -- '
                 f'{_speedup(totals):.0f}x on the table cost.')
    if drifts:
        drifts.sort()
        p90 = drifts[min(len(drifts) - 1, int(len(drifts) * 0.9))]
        worst = max(drifts, key=abs)
        lines.append(f'Height drift: median {drifts[len(drifts) // 2]:+.1f}%, '
                     f'p90 {p90:+.1f}%, worst {worst:+.1f}% -- '
                     f'{over} of {len(drifts)} over the 2% target.')
    return '\n'.join(lines) + '\n'


def _speedup(totals: dict[str, float]) -> float:
    matrix = totals['matrix'] - totals['baseline']
    tabular = totals['tabular'] - totals['baseline']
    return matrix / tabular if tabular > 0 else float('nan')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', type=Path, default=ROOT / 'dev' / 'out',
                    help='output directory (default dev/out, gitignored)')
    ap.add_argument('--corpus', type=Path, default=None,
                    help='directory of extra IR .json documents')
    ap.add_argument('--fab', type=int, default=len(SWEEP),
                    help=f'Fabricator tables (default {len(SWEEP)})')
    ap.add_argument('--per-table', dest='per_table', action='store_true',
                    default=None, help='force per-table timing on')
    ap.add_argument('--no-per-table', dest='per_table', action='store_false',
                    help='force per-table timing off')
    ap.add_argument('--no-pdf', action='store_true',
                    help='skip the side-by-side PDF')
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    docs = collect(args.fab, args.corpus)
    print(f'{len(docs)} tables')

    per_table = args.per_table
    if per_table is None:
        per_table = len(docs) <= 40
        if not per_table:
            print(f'per-table timing skipped ({len(docs)} tables > 40); '
                  'pass --per-table to force it')

    if not args.no_pdf:
        print('rendering side by side...')
        print(f'  -> {side_by_side(docs, args.out)}')
    print('measuring...')
    sizes = measure(docs, args.out)
    print('timing whole corpus...')
    totals = aggregate_time(docs, args.out)
    timings = per_table_time(docs, args.out) if per_table else None

    text = report(docs, sizes, timings, totals)
    (args.out / 'compare-engines.md').write_text(text, encoding='utf-8')
    print()
    print(text)
    print(f'-> {args.out / "compare-engines.md"}')


if __name__ == '__main__':
    main()
