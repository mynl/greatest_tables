/* gt-render.js — table-document (IR) walker: JSON → DOM.
 *
 * Zero dependencies, vanilla ES module. Renders the greatest_tables IR
 * (schema/ir-v1.json) into a <div class="gt"> + <table>, stamping the same
 * gt-* semantic classes as the Python HTML renderer — that vocabulary is a
 * tested contract (DOM-transcript conformance goldens).
 *
 * Scope is deliberately narrow: no inference, no sort, no filter, no
 * virtualization. A table you want to sort is an interactive grid — hand it
 * to csv-grid, don't grow this walker.
 *
 * renderTable(doc, opts) → { el, doc, destroy(), toCSV() }
 *   opts.mount      element (or selector) to append into
 *   opts.allowHtml  honor cell html:true (default false — injection-safe)
 *   opts.katex      injected KaTeX object; else math falls back to \(...\)
 *   opts.fit        'equal-risk' | 'coverage' — optional width pass for
 *                   constrained containers (forces single-line ellipsis)
 *   opts.document   Document to use (tests/SSR); defaults to global document
 */

export const GT_RENDER_VERSION = '1.4.0';
export const IR_VERSION_SUPPORTED = 1;

// row rules: gt-break-{d} for d ≤ min(2, stubs-2); column rules: d ≤ 1
const MAX_BREAK = 2;
const MAX_VBREAK = 1;

const CELL_FLAG_CLASS = { neg: 'gt-neg', emphasis: 'gt-emph', muted: 'gt-muted' };
const ROW_FLAG_CLASS = { total: 'gt-total', subtotal: 'gt-subtotal',
                         emphasis: 'gt-emph', muted: 'gt-muted' };

const cellOf = c => (typeof c === 'string' ? { text: c } : c);

export function renderTable(doc, opts = {}) {
    if (doc.ir_version !== IR_VERSION_SUPPORTED) {
        throw new Error(`gt-render supports ir_version ${IR_VERSION_SUPPORTED}, ` +
                        `got ${doc.ir_version}`);
    }
    // canonical JSON omits defaulted fields — restore them
    doc = Object.assign(
        { caption: null, label: null, hash: null, notes: [], foot: [] }, doc);
    const d = opts.document ||
        (typeof document !== 'undefined' ? document : null);
    if (!d) throw new Error('no document available — pass opts.document');

    const cols = doc.columns;
    const el = d.createElement('div');
    el.className = 'gt';
    if (doc.hash) el.setAttribute('data-gt-hash', doc.hash);
    if (doc.label) el.id = doc.label;

    const table = d.createElement('table');
    el.appendChild(table);

    if (doc.caption != null) {
        const cap = d.createElement('caption');
        cap.className = 'gt-caption';
        fillCell(d, cap, cellOf(doc.caption), opts);
        table.appendChild(cap);
    }

    // ---- head
    if (doc.head.length) {
        const thead = d.createElement('thead');
        doc.head.forEach((row, level) => {
            const leaf = level === doc.head.length - 1;
            const tr = d.createElement('tr');
            let col = 0;
            for (const hc of row) {
                const th = d.createElement('th');
                const colspan = hc.colspan || 1;
                if (colspan > 1) th.setAttribute('colspan', String(colspan));
                th.className = headClasses(doc, col, colspan, leaf, hc).join(' ');
                fillCell(d, th, hc, opts);
                tr.appendChild(th);
                col += colspan;
            }
            thead.appendChild(tr);
        });
        table.appendChild(thead);
    }

    // ---- body / foot
    const resolved = [];        // text matrix for click payloads and toCSV
    const rawRes = [];          // raw-value matrix (null where absent)
    const tbody = d.createElement('tbody');
    renderSection(d, tbody, doc, doc.body, resolved, rawRes, opts);
    table.appendChild(tbody);
    if (doc.foot.length) {
        const tfoot = d.createElement('tfoot');
        renderSection(d, tfoot, doc, doc.foot, [], [], opts);
        table.appendChild(tfoot);
    }

    if (doc.notes.length) {
        const notes = d.createElement('div');
        notes.className = 'gt-notes';
        for (const n of doc.notes) {
            const div = d.createElement('div');
            div.textContent = n;
            notes.appendChild(div);
        }
        el.appendChild(notes);
    }

    // ---- delegated click → gt:cellclick (instance root, never document)
    const names = cols.map(c => c.name.join(' / '));
    const onClick = ev => {
        const td = ev.target.closest && ev.target.closest('td');
        if (!td || !el.contains(td) || !td.hasAttribute('data-c')) return;
        const r = Number(td.parentElement.getAttribute('data-r'));
        const c = Number(td.getAttribute('data-c'));
        const row = {};
        names.forEach((n, j) => { row[n] = resolved[r] ? resolved[r][j] : undefined; });
        el.dispatchEvent(new CustomEvent('gt:cellclick', {
            bubbles: true,
            detail: { r, c, key: cols[c].key, name: names[c],
                      text: td.textContent, row },
        }));
    };
    el.addEventListener('click', onClick);

    if (opts.mount) {
        const host = typeof opts.mount === 'string'
            ? d.querySelector(opts.mount) : opts.mount;
        if (host) host.appendChild(el);
    }
    if (opts.fit) fitWidths(el, table, doc, resolved, opts.fit);

    return {
        el,
        doc,
        destroy() {
            el.removeEventListener('click', onClick);
            el.remove();
        },
        toCSV({ values = false } = {}) {
            const lines = [names.map(csvEscape).join(',')];
            doc.body.forEach((row, r) => {
                lines.push(cols.map((col, j) => {
                    if (values && col.raw) {
                        const raw = rawRes[r][j];
                        return raw == null ? '' : csvEscape(String(raw));
                    }
                    return csvEscape(resolved[r][j] ?? '');
                }).join(','));
            });
            return lines.join('\n') + '\n';
        },
    };
}

function renderSection(d, parent, doc, rows, resolved, rawRes, opts) {
    const ncols = doc.columns.length;
    const pending = new Array(ncols).fill(0);   // rows still covered per column
    const carry = new Array(ncols).fill('');    // text carried down rowspans
    rows.forEach((row, r) => {
        const tr = d.createElement('tr');
        tr.setAttribute('data-r', String(r));
        const trCls = rowClasses(doc, row).join(' ');
        if (trCls) tr.className = trCls;
        const texts = carry.slice();
        const raws = new Array(ncols).fill(null);
        let col = 0;
        for (const entry of row.cells) {
            const cell = cellOf(entry);
            while (col < ncols && pending[col] > 0) col++;
            if (col >= ncols) break;
            const colspan = cell.colspan || 1;
            const rowspan = cell.rowspan || 1;
            const td = d.createElement('td');
            td.setAttribute('data-c', String(col));
            if (colspan > 1) td.setAttribute('colspan', String(colspan));
            if (rowspan > 1) td.setAttribute('rowspan', String(rowspan));
            td.className = bodyClasses(doc, col, colspan, cell).join(' ');
            fillCell(d, td, cell, opts);
            tr.appendChild(td);
            for (let cc = col; cc < Math.min(ncols, col + colspan); cc++) {
                texts[cc] = cell.text;
                if ('raw' in cell) raws[cc] = cell.raw;
                if (rowspan > 1) {
                    pending[cc] = rowspan;
                    carry[cc] = cell.text;
                }
            }
            col += colspan;
        }
        for (let cc = 0; cc < ncols; cc++) {
            if (pending[cc] > 0 && --pending[cc] === 0) carry[cc] = '';
        }
        resolved.push(texts);
        rawRes.push(raws);
        parent.appendChild(tr);
    });
}

function fillCell(d, node, cell, opts) {
    if (cell.math) {
        node.classList.add('gt-math');
        if (opts.katex) {
            opts.katex.render(cell.text, node, { throwOnError: false });
        } else {
            node.textContent = `\\(${cell.text}\\)`;
        }
    } else if (cell.html && opts.allowHtml) {
        node.innerHTML = cell.text;
    } else {
        node.textContent = cell.text;
    }
}

function columnClasses(col) {
    // canonical JSON omits defaulted fields: role/wrap may be absent (= data,
    // no-wrap). Stub columns never carry break_depth, so no role guard needed.
    const cls = [`gt-${col.align}`, col.role === 'stub' ? 'gt-stub' : 'gt-data',
                 col.wrap ? 'gt-wrap' : 'gt-nowrap'];
    if (col.break_depth !== undefined && col.break_depth !== null
        && col.break_depth <= MAX_VBREAK) {
        cls.push(`gt-vbreak-${col.break_depth}`);
    }
    return cls;
}

function headClasses(doc, col, colspan, leaf, hc) {
    const cls = [];
    const first = doc.columns[col];
    const nStub = doc.n_stub_levels;
    if (hc.align) cls.push(`gt-${hc.align}`);
    else if (!leaf || colspan > 1) cls.push('gt-c');   // group rows center
    else if (first) cls.push(`gt-${first.align}`);
    else cls.push('gt-l');
    cls.push(first && col < nStub ? 'gt-stub' : 'gt-data');
    if (nStub > 0 && col + colspan === nStub) cls.push('gt-stub-end');
    const bd = first && first.break_depth;
    if (col >= nStub && bd !== undefined && bd !== null && bd <= MAX_VBREAK) {
        cls.push(`gt-vbreak-${bd}`);
    }
    for (const f of hc.flags || []) {
        if (CELL_FLAG_CLASS[f]) cls.push(CELL_FLAG_CLASS[f]);
    }
    return cls;
}

function bodyClasses(doc, col, colspan, cell) {
    const cls = columnClasses(doc.columns[col]);
    const lastStub = doc.n_stub_levels > 0 && col + colspan === doc.n_stub_levels;
    if (lastStub) cls.push('gt-stub-end');
    for (const f of cell.flags || []) {
        if (CELL_FLAG_CLASS[f]) cls.push(CELL_FLAG_CLASS[f]);
    }
    return cls;
}

function rowClasses(doc, row) {
    const cls = [];
    const d = row.break_depth;
    if (d !== undefined && d !== null
        && d <= Math.min(MAX_BREAK, doc.n_stub_levels - 2)) {
        cls.push(`gt-break-${d}`);
    }
    for (const f of row.flags || []) {
        if (ROW_FLAG_CLASS[f]) cls.push(ROW_FLAG_CLASS[f]);
    }
    return cls;
}

function csvEscape(s) {
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

/* ------------------------------------------------------------------ fit
 * Optional width pass for constrained containers. Measures formatted text
 * with canvas measureText and allocates via solveWidths. Forces single-line
 * nowrap+ellipsis on every column — the solver's objective assumes it.
 * No-op when no canvas/layout is available (e.g. the test DOM). */

let _canvas = null;

function fitWidths(el, table, doc, resolved, mode) {
    const d = el.ownerDocument;
    const win = d.defaultView;
    if (!win || !d.createElement('canvas').getContext) return;
    if (!_canvas) _canvas = d.createElement('canvas');
    const ctx = _canvas.getContext('2d');
    if (!ctx) return;
    const style = win.getComputedStyle(table);
    ctx.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    const pad = 2 * parseFloat(style.fontSize || '16') * 0.6 + 2;

    const ncols = doc.columns.length;
    const arrays = [];
    const floors = [];
    for (let j = 0; j < ncols; j++) {
        const widths = resolved.map(row => ctx.measureText(row[j] ?? '').width + pad);
        widths.sort((a, b) => a - b);
        arrays.push(widths);
        ctx.font = `600 ${style.fontSize} ${style.fontFamily}`;
        const header = doc.columns[j].name[doc.columns[j].name.length - 1] || '';
        floors.push(Math.max(MIN_COL, ctx.measureText(header).width + pad));
        ctx.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    }
    const avail = table.parentElement ? table.parentElement.clientWidth : 0;
    if (!avail) return;
    const solved = solveWidths(arrays, floors, avail, mode);
    const colgroup = d.createElement('colgroup');
    solved.forEach(w => {
        const col = d.createElement('col');
        col.style.width = `${Math.round(w)}px`;
        colgroup.appendChild(col);
    });
    table.insertBefore(colgroup, table.firstChild);
    table.style.tableLayout = 'fixed';
    table.style.width = `${Math.round(solved.reduce((a, b) => a + b, 0))}px`;
    el.classList.add('gt-fit');
}

/* ----------------------------------------------------- column width solver
 * COPIED from csv-grid src/grid/util.js:358-457 (csv-grid 3.9.0, commit
 * 01a9773). Do not edit here — re-diff against the source when csv-grid's
 * solver changes (CI guards the copy). See csv-viewer docs/column-width.md
 * for the derivation. */

export const CELL_PAD = 18;     // padding + border + safety, px
export const MIN_COL = 50;      // absolute floor, px

export function solveWidths(arrays, floors, avail, mode = 'equal-risk') {
    return mode === 'coverage'
        ? coverageWidths(arrays, floors, avail)
        : equalRiskWidths(arrays, floors, avail);
}

function equalRiskWidths(arrays, floors, avail) {
    const pct = (s, q) => s.length ? s[Math.floor(q * (s.length - 1))] : 0;
    const widthsAt = q => arrays.map((s, j) => Math.max(floors[j], pct(s, q)));
    const total = w => w.reduce((a, b) => a + b, 0);

    const natural = widthsAt(1);
    if (total(natural) <= avail) return natural;
    if (total(widthsAt(0)) >= avail) return widthsAt(0);   // floors + scroll

    let lo = 0, hi = 1;                  // f(lo) <= avail < f(hi); f monotone
    for (let k = 0; k < 32; k++) {
        const mid = (lo + hi) / 2;
        if (total(widthsAt(mid)) <= avail) lo = mid; else hi = mid;
    }
    return widthsAt(lo);
}

function coverageWidths(arrays, floors, avail) {
    const natural = arrays.map((s, j) => Math.max(floors[j], s.length ? s[s.length - 1] : 0));
    const sum = a => a.reduce((x, y) => x + y, 0);
    if (sum(natural) <= avail) return natural;            // tight: everything fits
    if (sum(floors) >= avail) return floors.slice();      // floors + scroll

    const widths = floors.slice();
    let budget = avail - sum(floors);
    const segs = [];
    for (let j = 0; j < arrays.length; j++) {
        const env = concaveEnvelope(arrays[j], floors[j]);
        for (let i = 1; i < env.length; i++) {
            const dw = env[i].w - env[i - 1].w;
            const dc = env[i].cells - env[i - 1].cells;
            if (dw > 0 && dc > 0) segs.push({ j, dw, slope: dc / dw });
        }
    }
    segs.sort((a, b) => b.slope - a.slope);
    for (const s of segs) {
        if (budget <= 0) break;
        const buy = Math.min(s.dw, budget);    // partial buy is fine — width is continuous
        widths[s.j] += buy;
        budget -= buy;
    }
    return widths;
}

function concaveEnvelope(sorted, floor) {
    const n = sorted.length;
    let i = 0;
    while (i < n && sorted[i] <= floor) i++;        // free cells at the floor
    const pts = [{ w: floor, cells: i }];
    while (i < n) {                                 // one vertex per distinct width
        const w = sorted[i];
        while (i < n && sorted[i] === w) i++;
        pts.push({ w, cells: i });
    }
    const hull = [];
    for (const p of pts) {
        while (hull.length >= 2) {
            const a = hull[hull.length - 2], b = hull[hull.length - 1];
            // drop b unless it is a strict concave vertex (clockwise turn)
            const cross = (b.w - a.w) * (p.cells - a.cells) - (b.cells - a.cells) * (p.w - a.w);
            if (cross >= 0) hull.pop(); else break;
        }
        hull.push(p);
    }
    return hull;
}

export default renderTable;
