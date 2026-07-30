"""Regenerate committed golden files. Explicit recipe, no test-time magic.

Run from the repo root after a deliberate schema or exemplar change::

    uv run python tests/make_goldens.py

Writes tests/golden/ir/<name>.json (canonical bytes) and schema/ir-v1.json.
Review the diff before committing — these files are the IR contract.
"""

import json
from pathlib import Path

from greatest_tables import TableDoc, canonical_json

from exemplars import EXEMPLARS

ROOT = Path(__file__).parent.parent


def main() -> None:
    golden = ROOT / 'tests' / 'golden' / 'ir'
    golden.mkdir(parents=True, exist_ok=True)
    for name, build in EXEMPLARS.items():
        path = golden / f'{name}.json'
        path.write_bytes(canonical_json(build()))
        print(f'wrote {path}')

    schema_path = ROOT / 'schema' / 'ir-v1.json'
    schema = TableDoc.model_json_schema()
    schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + '\n',
                           encoding='utf-8')
    print(f'wrote {schema_path}')


if __name__ == '__main__':
    main()
