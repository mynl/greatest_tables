/* Test helper: run irToGridInput on an IR JSON file, print the result.
 * Usage: node js/adapter-check.mjs path/to/doc.json
 * Exits 1 with the error message on stderr when the adapter throws. */

import { readFileSync } from 'node:fs';
import { irToGridInput } from './src/gt-render.js';

try {
    const doc = JSON.parse(readFileSync(process.argv[2], 'utf-8'));
    process.stdout.write(JSON.stringify(irToGridInput(doc)));
} catch (err) {
    process.stderr.write(String(err.message || err));
    process.exit(1);
}
