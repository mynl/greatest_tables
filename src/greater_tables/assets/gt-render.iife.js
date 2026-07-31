var GtRender = (() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, { get: all[name], enumerable: true });
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

  // js/src/gt-render.js
  var gt_render_exports = {};
  __export(gt_render_exports, {
    CELL_PAD: () => CELL_PAD,
    GT_RENDER_VERSION: () => GT_RENDER_VERSION,
    IR_VERSION_SUPPORTED: () => IR_VERSION_SUPPORTED,
    MIN_COL: () => MIN_COL,
    default: () => gt_render_default,
    irToGridInput: () => irToGridInput,
    renderTable: () => renderTable,
    solveWidths: () => solveWidths
  });
  var GT_RENDER_VERSION = "1.10.0";
  var IR_VERSION_SUPPORTED = 1;
  var MAX_BREAK = 2;
  var MAX_VBREAK = 1;
  var CELL_FLAG_CLASS = { neg: "gt-neg", emphasis: "gt-emph", muted: "gt-muted" };
  var ROW_FLAG_CLASS = {
    total: "gt-total",
    subtotal: "gt-subtotal",
    emphasis: "gt-emph",
    muted: "gt-muted"
  };
  var cellOf = (c) => typeof c === "string" ? { text: c } : c;
  function renderTable(doc, opts = {}) {
    if (doc.ir_version !== IR_VERSION_SUPPORTED) {
      throw new Error(`gt-render supports ir_version ${IR_VERSION_SUPPORTED}, got ${doc.ir_version}`);
    }
    doc = Object.assign(
      { caption: null, label: null, hash: null, notes: [], foot: [] },
      doc
    );
    const d = opts.document || (typeof document !== "undefined" ? document : null);
    if (!d) throw new Error("no document available \u2014 pass opts.document");
    const cols = doc.columns;
    const el = d.createElement("div");
    el.className = "gt";
    if (doc.hash) el.setAttribute("data-gt-hash", doc.hash);
    if (doc.label) el.id = doc.label;
    const table = d.createElement("table");
    el.appendChild(table);
    if (doc.caption != null) {
      const cap = d.createElement("caption");
      cap.className = "gt-caption";
      fillCell(d, cap, cellOf(doc.caption), opts);
      table.appendChild(cap);
    }
    if (doc.head.length) {
      const thead = d.createElement("thead");
      doc.head.forEach((row, level) => {
        const leaf = level === doc.head.length - 1;
        const tr = d.createElement("tr");
        let col = 0;
        for (const hc of row) {
          const th = d.createElement("th");
          const colspan = hc.colspan || 1;
          if (colspan > 1) th.setAttribute("colspan", String(colspan));
          th.className = headClasses(doc, col, colspan, leaf, hc).join(" ");
          fillCell(d, th, hc, opts);
          tr.appendChild(th);
          col += colspan;
        }
        thead.appendChild(tr);
      });
      table.appendChild(thead);
    }
    const resolved = [];
    const rawRes = [];
    const tbody = d.createElement("tbody");
    renderSection(d, tbody, doc, doc.body, resolved, rawRes, opts);
    table.appendChild(tbody);
    if (doc.foot.length) {
      const tfoot = d.createElement("tfoot");
      renderSection(d, tfoot, doc, doc.foot, [], [], opts);
      table.appendChild(tfoot);
    }
    if (doc.notes.length) {
      const notes = d.createElement("div");
      notes.className = "gt-notes";
      for (const n of doc.notes) {
        const div = d.createElement("div");
        div.textContent = n;
        notes.appendChild(div);
      }
      el.appendChild(notes);
    }
    const names = cols.map((c) => c.name.join(" / "));
    const onClick = (ev) => {
      const td = ev.target.closest && ev.target.closest("td");
      if (!td || !el.contains(td) || !td.hasAttribute("data-c")) return;
      const r = Number(td.parentElement.getAttribute("data-r"));
      const c = Number(td.getAttribute("data-c"));
      const row = {};
      names.forEach((n, j) => {
        row[n] = resolved[r] ? resolved[r][j] : void 0;
      });
      el.dispatchEvent(new CustomEvent("gt:cellclick", {
        bubbles: true,
        detail: {
          r,
          c,
          key: cols[c].key,
          name: names[c],
          text: td.textContent,
          row
        }
      }));
    };
    el.addEventListener("click", onClick);
    if (opts.mount) {
      const host = typeof opts.mount === "string" ? d.querySelector(opts.mount) : opts.mount;
      if (host) host.appendChild(el);
    }
    if (opts.fit) fitWidths(el, table, doc, resolved, opts.fit);
    return {
      el,
      doc,
      destroy() {
        el.removeEventListener("click", onClick);
        el.remove();
      },
      toCSV({ values = false } = {}) {
        const lines = [names.map(csvEscape).join(",")];
        doc.body.forEach((row, r) => {
          lines.push(cols.map((col, j) => {
            if (values && col.raw) {
              const raw = rawRes[r][j];
              return raw == null ? "" : csvEscape(String(raw));
            }
            return csvEscape(resolved[r][j] ?? "");
          }).join(","));
        });
        return lines.join("\n") + "\n";
      }
    };
  }
  function renderSection(d, parent, doc, rows, resolved, rawRes, opts) {
    const ncols = doc.columns.length;
    const pending = new Array(ncols).fill(0);
    const carry = new Array(ncols).fill("");
    rows.forEach((row, r) => {
      const tr = d.createElement("tr");
      tr.setAttribute("data-r", String(r));
      const trCls = rowClasses(doc, row).join(" ");
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
        const td = d.createElement("td");
        td.setAttribute("data-c", String(col));
        if (colspan > 1) td.setAttribute("colspan", String(colspan));
        if (rowspan > 1) td.setAttribute("rowspan", String(rowspan));
        td.className = bodyClasses(doc, col, colspan, cell).join(" ");
        fillCell(d, td, cell, opts);
        tr.appendChild(td);
        for (let cc = col; cc < Math.min(ncols, col + colspan); cc++) {
          texts[cc] = cell.text;
          if ("raw" in cell) raws[cc] = cell.raw;
          if (rowspan > 1) {
            pending[cc] = rowspan;
            carry[cc] = cell.text;
          }
        }
        col += colspan;
      }
      for (let cc = 0; cc < ncols; cc++) {
        if (pending[cc] > 0 && --pending[cc] === 0) carry[cc] = "";
      }
      resolved.push(texts);
      rawRes.push(raws);
      parent.appendChild(tr);
    });
  }
  function fillCell(d, node, cell, opts) {
    if (cell.math) {
      node.classList.add("gt-math");
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
    const cls = [
      `gt-${col.align}`,
      col.role === "stub" ? "gt-stub" : "gt-data",
      col.wrap ? "gt-wrap" : "gt-nowrap"
    ];
    if (col.break_depth !== void 0 && col.break_depth !== null && col.break_depth <= MAX_VBREAK) {
      cls.push(`gt-vbreak-${col.break_depth}`);
    }
    return cls;
  }
  function headClasses(doc, col, colspan, leaf, hc) {
    const cls = [];
    const first = doc.columns[col];
    const nStub = doc.n_stub_levels;
    if (hc.align) cls.push(`gt-${hc.align}`);
    else if (!leaf || colspan > 1) cls.push("gt-c");
    else if (first) cls.push(`gt-${first.align}`);
    else cls.push("gt-l");
    cls.push(first && col < nStub ? "gt-stub" : "gt-data");
    if (!leaf && hc.text) cls.push("gt-spanner");
    if (nStub > 0 && col + colspan === nStub) cls.push("gt-stub-end");
    const bd = first && first.break_depth;
    if (col >= nStub && bd !== void 0 && bd !== null && bd <= MAX_VBREAK) {
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
    if (lastStub) cls.push("gt-stub-end");
    for (const f of cell.flags || []) {
      if (CELL_FLAG_CLASS[f]) cls.push(CELL_FLAG_CLASS[f]);
    }
    return cls;
  }
  function rowClasses(doc, row) {
    const cls = [];
    const d = row.break_depth;
    if (d !== void 0 && d !== null && d <= Math.min(MAX_BREAK, doc.n_stub_levels - 2)) {
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
  function irToGridInput(doc) {
    if (doc.ir_version !== IR_VERSION_SUPPORTED) {
      throw new Error(`irToGridInput supports ir_version ${IR_VERSION_SUPPORTED}, got ${doc.ir_version}`);
    }
    const cols = doc.columns;
    for (const c of cols) {
      if ((c.role || "data") === "data" && !c.raw) {
        throw new Error(
          `irToGridInput requires raw values on every data column (missing on ${c.key} "${c.name.join(" / ")}") \u2014 build the document with include_raw='data'`
        );
      }
    }
    const ncols = cols.length;
    const records = [];
    const pending = new Array(ncols).fill(0);
    const carry = new Array(ncols).fill("");
    for (const row of doc.body) {
      const rec = carry.slice();
      let col = 0;
      for (const entry of row.cells) {
        const cell = cellOf(entry);
        while (col < ncols && pending[col] > 0) col++;
        if (col >= ncols) break;
        const colspan = cell.colspan || 1;
        const rowspan = cell.rowspan || 1;
        const value = "raw" in cell ? cell.raw === null ? "" : cell.raw : cell.text;
        for (let cc = col; cc < Math.min(ncols, col + colspan); cc++) {
          rec[cc] = value;
          if (rowspan > 1) {
            pending[cc] = rowspan;
            carry[cc] = value;
          }
        }
        col += colspan;
      }
      for (let cc = 0; cc < ncols; cc++) {
        if (pending[cc] > 0 && --pending[cc] === 0) carry[cc] = "";
      }
      records.push(rec);
    }
    return {
      columns: cols.map((c) => c.name.join(" / ")),
      records,
      formats: cols.map((c) => cgFormatSpec(c.format)),
      align: cols.map((c) => c.align).join("")
    };
  }
  function cgFormatSpec(f) {
    if (!f) return null;
    const d = f.digits;
    const dot = d !== void 0 && d !== null ? `.${d}` : "";
    switch (f.kind) {
      case "int":
        return f.group ? ",d" : "d";
      case "dec":
        return (f.group ? "," : "") + dot + "f";
      case "pct":
        return dot + "%";
      case "sci":
        return dot + "e";
      case "si":
      case "eng":
        return "eng";
      case "year":
        return "year";
      case "date":
        return f.pattern || "%Y-%m-%d";
      case "str":
        return "s";
      default:
        return null;
    }
  }
  var _canvas = null;
  function fitWidths(el, table, doc, resolved, mode) {
    const d = el.ownerDocument;
    const win = d.defaultView;
    if (!win || !d.createElement("canvas").getContext) return;
    if (!_canvas) _canvas = d.createElement("canvas");
    const ctx = _canvas.getContext("2d");
    if (!ctx) return;
    const style = win.getComputedStyle(table);
    ctx.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    const pad = 2 * parseFloat(style.fontSize || "16") * 0.6 + 2;
    const ncols = doc.columns.length;
    const arrays = [];
    const floors = [];
    for (let j = 0; j < ncols; j++) {
      const widths = resolved.map((row) => ctx.measureText(row[j] ?? "").width + pad);
      widths.sort((a, b) => a - b);
      arrays.push(widths);
      ctx.font = `600 ${style.fontSize} ${style.fontFamily}`;
      const header = doc.columns[j].name[doc.columns[j].name.length - 1] || "";
      floors.push(Math.max(MIN_COL, ctx.measureText(header).width + pad));
      ctx.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    }
    const avail = table.parentElement ? table.parentElement.clientWidth : 0;
    if (!avail) return;
    const solved = solveWidths(arrays, floors, avail, mode);
    const colgroup = d.createElement("colgroup");
    solved.forEach((w) => {
      const col = d.createElement("col");
      col.style.width = `${Math.round(w)}px`;
      colgroup.appendChild(col);
    });
    table.insertBefore(colgroup, table.firstChild);
    table.style.tableLayout = "fixed";
    table.style.width = `${Math.round(solved.reduce((a, b) => a + b, 0))}px`;
    el.classList.add("gt-fit");
  }
  var CELL_PAD = 18;
  var MIN_COL = 50;
  function solveWidths(arrays, floors, avail, mode = "equal-risk") {
    return mode === "coverage" ? coverageWidths(arrays, floors, avail) : equalRiskWidths(arrays, floors, avail);
  }
  function equalRiskWidths(arrays, floors, avail) {
    const pct = (s, q) => s.length ? s[Math.floor(q * (s.length - 1))] : 0;
    const widthsAt = (q) => arrays.map((s, j) => Math.max(floors[j], pct(s, q)));
    const total = (w) => w.reduce((a, b) => a + b, 0);
    const natural = widthsAt(1);
    if (total(natural) <= avail) return natural;
    if (total(widthsAt(0)) >= avail) return widthsAt(0);
    let lo = 0, hi = 1;
    for (let k = 0; k < 32; k++) {
      const mid = (lo + hi) / 2;
      if (total(widthsAt(mid)) <= avail) lo = mid;
      else hi = mid;
    }
    return widthsAt(lo);
  }
  function coverageWidths(arrays, floors, avail) {
    const natural = arrays.map((s, j) => Math.max(floors[j], s.length ? s[s.length - 1] : 0));
    const sum = (a) => a.reduce((x, y) => x + y, 0);
    if (sum(natural) <= avail) return natural;
    if (sum(floors) >= avail) return floors.slice();
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
      const buy = Math.min(s.dw, budget);
      widths[s.j] += buy;
      budget -= buy;
    }
    return widths;
  }
  function concaveEnvelope(sorted, floor) {
    const n = sorted.length;
    let i = 0;
    while (i < n && sorted[i] <= floor) i++;
    const pts = [{ w: floor, cells: i }];
    while (i < n) {
      const w = sorted[i];
      while (i < n && sorted[i] === w) i++;
      pts.push({ w, cells: i });
    }
    const hull = [];
    for (const p of pts) {
      while (hull.length >= 2) {
        const a = hull[hull.length - 2], b = hull[hull.length - 1];
        const cross = (b.w - a.w) * (p.cells - a.cells) - (b.cells - a.cells) * (p.w - a.w);
        if (cross >= 0) hull.pop();
        else break;
      }
      hull.push(p);
    }
    return hull;
  }
  var gt_render_default = renderTable;
  return __toCommonJS(gt_render_exports);
})();
