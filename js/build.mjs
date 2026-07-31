/* Build gt-render.js into the Python package assets (committed dist).
 *
 *   node js/build.mjs
 *
 * Emits src/greater_tables/assets/gt-render.esm.js and .iife.js (global
 * GtRender). The iife exists for script-tag/RequireJS-hostile pages, the
 * same reason csv-grid ships one.
 */

import { buildSync } from 'esbuild';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ENTRY = join(HERE, 'src', 'gt-render.js');
const ASSETS = join(HERE, '..', 'src', 'greater_tables', 'assets');

const common = {
    entryPoints: [ENTRY],
    bundle: true,
    minify: false,          // committed dist stays reviewable
    target: 'es2020',
    legalComments: 'inline',
};

buildSync({ ...common, format: 'esm',
            outfile: join(ASSETS, 'gt-render.esm.js') });
buildSync({ ...common, format: 'iife', globalName: 'GtRender',
            outfile: join(ASSETS, 'gt-render.iife.js') });
console.log('built gt-render.esm.js + gt-render.iife.js');
