/* DOM-transcript conformance harness.
 *
 * Renders every golden IR fixture with gt-render.js under linkedom and emits
 * one JSON line per cell: {s, r, c, tag, rowspan?, colspan?, classes, text}
 * (classes sorted; span fields only when > 1), preceded by a meta line with
 * caption/label/hash/notes. The Python HTML renderer must byte-match these
 * transcripts in [notebook-html] — that is the shared conformance contract.
 *
 * Run from the repo root:
 *   node js/transcript.mjs --write            regenerate committed goldens
 *   node js/transcript.mjs --out DIR          write to DIR (used by pytest)
 *
 * The walker runs with defaults: no katex (math renders as \(tex\) source),
 * allowHtml off (html cells render as their source text) — both sides of the
 * conformance contract record source, not rendered markup.
 */

import { readdirSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseHTML } from 'linkedom';

import { renderTable } from './src/gt-render.js';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const IR_DIR = join(ROOT, 'tests', 'golden', 'ir');
const OUT_DEFAULT = join(ROOT, 'tests', 'golden', 'transcript');

function transcribe(doc) {
    const { document } = parseHTML('<!doctype html><html><body></body></html>');
    const { el } = renderTable(doc, { document });
    const lines = [];
    const meta = {
        caption: typeof doc.caption === 'object' && doc.caption !== null
            ? doc.caption.text : (doc.caption ?? null),
        label: doc.label ?? null,
        hash: doc.hash ?? null,
        notes: doc.notes ?? [],
    };
    lines.push(JSON.stringify(meta));
    for (const [s, sel] of [['head', 'thead tr'], ['body', 'tbody tr'],
                            ['foot', 'tfoot tr']]) {
        el.querySelectorAll(sel).forEach((tr, r) => {
            let c = 0;
            for (const cell of tr.children) {
                const rec = { s, r, c, tag: cell.tagName.toLowerCase() };
                const rowspan = Number(cell.getAttribute('rowspan') || 1);
                const colspan = Number(cell.getAttribute('colspan') || 1);
                if (rowspan > 1) rec.rowspan = rowspan;
                if (colspan > 1) rec.colspan = colspan;
                rec.classes = (cell.className || '').split(/\s+/)
                    .filter(Boolean).sort();
                rec.text = cell.textContent;
                lines.push(JSON.stringify(rec));
                c += colspan;
            }
        });
    }
    return lines.join('\n') + '\n';
}

const outIdx = process.argv.indexOf('--out');
const outDir = outIdx >= 0 ? process.argv[outIdx + 1] : OUT_DEFAULT;
mkdirSync(outDir, { recursive: true });

let count = 0;
for (const file of readdirSync(IR_DIR).sort()) {
    if (!file.endsWith('.json')) continue;
    const doc = JSON.parse(readFileSync(join(IR_DIR, file), 'utf-8'));
    const name = basename(file, '.json');
    writeFileSync(join(outDir, `${name}.jsonl`), transcribe(doc),
                  { encoding: 'utf-8' });
    count += 1;
}
console.log(`wrote ${count} transcripts to ${outDir}`);
