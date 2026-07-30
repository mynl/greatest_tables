"""Walker conformance: node harness transcripts must match committed goldens.

Also guards the solver copy against drift from its csv-grid source when that
repo is present on this machine.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
GOLDEN = ROOT / 'tests' / 'golden' / 'transcript'
NODE = shutil.which('node')
CSV_GRID_UTIL = Path('C:/S/AI/csv-viewer/src/grid/util.js')


@pytest.mark.skipif(NODE is None, reason='node not available')
def test_transcripts_match_goldens(tmp_path):
    subprocess.run(
        [NODE, str(ROOT / 'js' / 'transcript.mjs'), '--out', str(tmp_path)],
        check=True, capture_output=True, cwd=ROOT)
    names = sorted(p.name for p in GOLDEN.glob('*.jsonl'))
    assert names, 'no committed transcripts — run tests/make_goldens.py'
    for name in names:
        assert (tmp_path / name).read_bytes() == (GOLDEN / name).read_bytes(), name


def _extract(source: str, fn: str) -> str:
    """Pull one top-level function body out of a JS file, whitespace-normalized."""
    m = re.search(rf'^(?:export )?function {fn}\(.*?^\}}', source,
                  re.MULTILINE | re.DOTALL)
    assert m, f'function {fn} not found'
    text = re.sub(r'^(?:export )?', '', m.group(0))
    return re.sub(r'\s+', ' ', text).strip()


@pytest.mark.skipif(not CSV_GRID_UTIL.exists(),
                    reason='csv-grid source not on this machine')
def test_solver_copy_matches_csv_grid():
    """The solveWidths copy in gt-render.js must not drift from csv-grid."""
    ours = (ROOT / 'js' / 'src' / 'gt-render.js').read_text(encoding='utf-8')
    theirs = CSV_GRID_UTIL.read_text(encoding='utf-8')
    for fn in ('solveWidths', 'equalRiskWidths', 'coverageWidths',
               'concaveEnvelope'):
        assert _extract(ours, fn) == _extract(theirs, fn), \
            f'{fn} drifted — re-copy from csv-grid util.js and re-review'
