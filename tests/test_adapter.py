"""irToGridInput adapter: TableDoc → CsvGrid input shape (node round-trip)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from greatest_tables import TableSpec, build, canonical_json

from registry import fixtures

ROOT = Path(__file__).parent.parent
NODE = shutil.which('node')
pytestmark = pytest.mark.skipif(NODE is None, reason='node not available')


def _run(doc_bytes: bytes, tmp_path: Path):
    path = tmp_path / 'doc.json'
    path.write_bytes(doc_bytes)
    return subprocess.run(
        [NODE, str(ROOT / 'js' / 'adapter-check.mjs'), str(path)],
        capture_output=True, text=True, encoding='utf-8', cwd=ROOT)


def test_flattens_hierarchy_with_raw(tmp_path):
    data, _ = fixtures()['both-mi']
    doc = build(data, TableSpec(include_raw='data'))
    result = _run(canonical_json(doc), tmp_path)
    assert result.returncode == 0, result.stderr
    grid = json.loads(result.stdout)

    n_stub = doc.n_stub_levels
    assert len(grid['columns']) == len(doc.columns)
    assert any(' / ' in c for c in grid['columns'])       # joined name paths
    assert len(grid['records']) == len(doc.body)
    # stubs un-sparsify: covered rows repeat the carried value
    r0, r1 = grid['records'][0], grid['records'][1]
    assert r1[0] == r0[0] and r1[0] != ''
    # data cells carry raw numbers, not formatted strings
    assert all(isinstance(r[n_stub], (int, float)) for r in grid['records'])
    # formats map to csv-grid sugar; alignment string covers all columns
    assert any(f in (',.0f', ',d', ',.2f') for f in grid['formats'] if f)
    assert len(grid['align']) == len(doc.columns)


def test_requires_raw(tmp_path):
    data, spec = fixtures()['both-mi']            # include_raw off
    result = _run(canonical_json(build(data, spec)), tmp_path)
    assert result.returncode == 1
    assert "include_raw='data'" in result.stderr


def test_null_raw_becomes_empty(tmp_path):
    import pandas as pd
    df = pd.DataFrame({'v': [1.5, None, -2.0]})
    doc = build(df, TableSpec(include_raw='data'))
    result = _run(canonical_json(doc), tmp_path)
    assert result.returncode == 0, result.stderr
    grid = json.loads(result.stdout)
    assert grid['records'][1][0] == ''            # null → empty, not 'None'
