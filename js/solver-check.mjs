/* Test helper: run the JS width solver over cases given as JSON on stdin,
 * print its answers as JSON. Lets tests/test_widths.py hold the Python port
 * in render/widths.py against this copy — the two must not drift.
 * Usage: echo '[{"samples":[[1,2]],"floors":[1],"budget":5,"mode":"equal-risk"}]' | node js/solver-check.mjs */

import { solveWidths } from './src/gt-render.js';

let raw = '';
for await (const chunk of process.stdin) raw += chunk;

try {
    const cases = JSON.parse(raw);
    process.stdout.write(JSON.stringify(cases.map(
        c => solveWidths(c.samples, c.floors, c.budget, c.mode))));
} catch (err) {
    process.stderr.write(String(err.message || err));
    process.exit(1);
}
