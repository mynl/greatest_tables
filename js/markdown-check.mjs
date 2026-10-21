/* Test helper: run markdownRuns over a JSON list of strings, print the runs.
 * Usage: node js/markdown-check.mjs path/to/cases.json [--math-off]
 * Prints a JSON list holding, per input string, its [kind, style, text]
 * runs, for tests/test_markdown_spans.py to compare with the Python rule. */

import { readFileSync } from 'node:fs';
import { markdownRuns } from './src/gt-render.js';

const cases = JSON.parse(readFileSync(process.argv[2], 'utf-8'));
const mathOn = !process.argv.includes('--math-off');
process.stdout.write(JSON.stringify(cases.map(t => markdownRuns(t, mathOn))));
