"""Drift guard: the committed JSON Schema must match the live models.

A failure here means the IR changed. That is a deliberate, reviewed act:
regenerate with ``uv run python tests/make_goldens.py``, review the diff,
and decide whether the change is additive-advisory (fine) or content-bearing
(requires an ir_version bump per dev/design.md).
"""

import json
from pathlib import Path

from greater_tables import TableDoc

SCHEMA = Path(__file__).parent.parent / 'schema' / 'ir-v1.json'


def test_schema_unchanged():
    committed = json.loads(SCHEMA.read_text(encoding='utf-8'))
    live = json.loads(json.dumps(TableDoc.model_json_schema()))
    assert live == committed, (
        'IR schema drifted from schema/ir-v1.json — see this test\'s docstring')
