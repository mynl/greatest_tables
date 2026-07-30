"""Regenerate committed golden files. Explicit recipe, no test-time magic.

Run from the repo root after a deliberate schema or exemplar change::

    uv run python tests/make_goldens.py

Writes tests/golden/ir/<name>.json (canonical bytes) and schema/ir-v1.json.
Review the diff before committing — these files are the IR contract.
"""

import json
import shutil
import subprocess
from pathlib import Path

from greatest_tables import TableDoc, build, canonical_json, render_text
from greatest_tables.render.css import write_asset

from exemplars import EXEMPLARS
from registry import fixtures

ROOT = Path(__file__).parent.parent


def main() -> None:
    golden_ir = ROOT / 'tests' / 'golden' / 'ir'
    golden_text = ROOT / 'tests' / 'golden' / 'text'
    golden_ir.mkdir(parents=True, exist_ok=True)
    golden_text.mkdir(parents=True, exist_ok=True)

    for name, make in EXEMPLARS.items():
        path = golden_ir / f'{name}.json'
        path.write_bytes(canonical_json(make()))
        print(f'wrote {path}')

    for name, (data, spec) in fixtures().items():
        doc = build(data, spec)
        ir_path = golden_ir / f'fx-{name}.json'
        ir_path.write_bytes(canonical_json(doc))
        text_path = golden_text / f'{name}.txt'
        text_path.write_text(render_text(doc), encoding='utf-8', newline='\n')
        print(f'wrote {ir_path.name} + {text_path.name}')

    schema_path = ROOT / 'schema' / 'ir-v1.json'
    schema = TableDoc.model_json_schema()
    schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + '\n',
                           encoding='utf-8')
    print(f'wrote {schema_path}')

    print(f'wrote {write_asset()}')

    node = shutil.which('node')
    if node:
        subprocess.run([node, str(ROOT / 'js' / 'transcript.mjs'), '--write'],
                       check=True, cwd=ROOT)
    else:
        print('node not found — transcript goldens not regenerated')


if __name__ == '__main__':
    main()
