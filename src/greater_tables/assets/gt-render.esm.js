// js/src/gt-render.js
var GT_RENDER_VERSION = "8.1.0";
var IR_VERSION_SUPPORTED = 1;
var N_RULE_SLOTS = 3;
var N_VRULE_SLOTS = 3;
function ruleSlot(breakDepth, nStubLevels, maxRuleDepth = "auto") {
  if (breakDepth === void 0 || breakDepth === null || maxRuleDepth === null) return null;
  let cap;
  if (typeof maxRuleDepth === "string") {
    if (maxRuleDepth !== "auto") {
      throw new Error(`maxRuleDepth must be 'auto', an integer, or null; got ${JSON.stringify(maxRuleDepth)}`);
    }
    cap = Math.min(N_RULE_SLOTS - 1, nStubLevels - 2);
  } else {
    cap = Number(maxRuleDepth);
  }
  if (breakDepth > cap) return null;
  return Math.min(breakDepth, N_RULE_SLOTS - 1);
}
function vruleSlot(breakDepth, maxVruleDepth = 1) {
  if (breakDepth === void 0 || breakDepth === null || maxVruleDepth === null) return null;
  if (breakDepth > Number(maxVruleDepth)) return null;
  return Math.min(breakDepth, N_VRULE_SLOTS - 1);
}
var CELL_FLAG_CLASS = { neg: "gt-neg", emphasis: "gt-emph", muted: "gt-muted" };
var ROW_FLAG_CLASS = {
  total: "gt-total",
  subtotal: "gt-subtotal",
  emphasis: "gt-emph",
  muted: "gt-muted"
};
var cellOf = (c) => typeof c === "string" ? { text: c } : c;
var MATH_RE = new RegExp(
  "(?<!\\\\)\\$\\$(?!\\s)([^$]*[^$\\s])(?<!\\\\)\\$\\$(?!\\d)|(?<!\\\\)\\$(?!\\s)([^$]*[^$\\s])(?<!\\\\)\\$(?!\\d)",
  // inline
  "g"
);
function mathSegments(text) {
  const out = [];
  let pos = 0;
  MATH_RE.lastIndex = 0;
  let m;
  while ((m = MATH_RE.exec(text)) !== null) {
    if (m.index > pos) {
      out.push([false, text.slice(pos, m.index).replace(/\\\$/g, "$")]);
    }
    out.push([true, m[1] !== void 0 ? m[1] : m[2]]);
    pos = m.index + m[0].length;
  }
  if (pos < text.length || pos === 0) {
    out.push([false, text.slice(pos).replace(/\\\$/g, "$")]);
  }
  return out;
}
var CODE_RE = new RegExp("(?<![\\\\`])`([^`]*[^`\\\\])`(?!`)", "g");
var MD_OPEN = `(?<![^\\s(\\[{"'\u201C\u2018])`;
var MD_CLOSE = `(?![^\\s.,;:!?)\\]}"'\u201D\u2019\u2026/\u2013\u2014-])`;
var STRONG_RE = new RegExp(
  MD_OPEN + "\\*\\*(?=\\S)(.+?)(?<=[^\\s\\\\])\\*\\*" + MD_CLOSE,
  "gs"
);
var EM_RE = new RegExp(
  MD_OPEN + "\\*(?=[^\\s*])(.+?)(?<=[^\\s\\\\*])\\*" + MD_CLOSE,
  "gs"
);
var MD_ATOM = 57344;
var MD_ATOM_SPLIT = /([-])/;
var MD_ATOM_ONLY = /^[-]$/;
var MD_ESCAPE_RE = /\\([*`])/g;
function markdownRuns(text, mathOn = true) {
  const tokens = [];
  let pos = 0;
  let m;
  CODE_RE.lastIndex = 0;
  while ((m = CODE_RE.exec(text)) !== null) {
    tokens.push(...mdMathTokens(text.slice(pos, m.index), mathOn));
    tokens.push(["code", null, m[1]]);
    pos = m.index + m[0].length;
  }
  tokens.push(...mdMathTokens(text.slice(pos), mathOn));
  const out = [];
  if (MD_ATOM_SPLIT.test(text)) {
    for (const t of tokens) {
      if (typeof t !== "string") out.push(t);
      else if (t !== "") out.push(["text", null, mdUnescape(t)]);
    }
    return out.length ? out : [["text", null, ""]];
  }
  const atoms = tokens.filter((t) => typeof t !== "string");
  let flat = "";
  let k = 0;
  for (const t of tokens) {
    flat += typeof t === "string" ? t : String.fromCharCode(MD_ATOM + k++);
  }
  for (const [style, chunk] of mdStyled(flat)) {
    for (const piece of chunk.split(MD_ATOM_SPLIT)) {
      if (!piece) continue;
      if (MD_ATOM_ONLY.test(piece)) {
        const [kind, , atomText] = atoms[piece.charCodeAt(0) - MD_ATOM];
        out.push([kind, style, atomText]);
      } else {
        out.push(["text", style, mdUnescape(piece)]);
      }
    }
  }
  return out.length ? out : [["text", null, ""]];
}
function mdMathTokens(text, mathOn) {
  if (!mathOn || !text.includes("$")) return [text];
  return mathSegments(text).map(([isMath, run]) => isMath ? ["math", null, run] : run);
}
function mdStyled(flat) {
  const out = [];
  for (const [strong, chunk] of mdSplit(STRONG_RE, flat)) {
    if (strong) {
      out.push(["strong", chunk]);
    } else {
      for (const [em, c] of mdSplit(EM_RE, chunk)) out.push([em ? "em" : null, c]);
    }
  }
  return out;
}
function mdSplit(re, text) {
  const out = [];
  let pos = 0;
  let m;
  re.lastIndex = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > pos) out.push([false, text.slice(pos, m.index)]);
    out.push([true, m[1]]);
    pos = m.index + m[0].length;
  }
  if (pos < text.length) out.push([false, text.slice(pos)]);
  return out;
}
function mdUnescape(text) {
  return text.replace(MD_ESCAPE_RE, "$1");
}
function renderTable(doc, opts = {}) {
  if (doc.ir_version !== IR_VERSION_SUPPORTED) {
    throw new Error(`gt-render supports ir_version ${IR_VERSION_SUPPORTED}, got ${doc.ir_version}`);
  }
  doc = Object.assign(
    {
      caption: null,
      label: null,
      hash: null,
      notes: [],
      foot: [],
      math: "auto"
    },
    doc
  );
  const d = opts.document || (typeof document !== "undefined" ? document : null);
  if (!d) throw new Error("no document available \u2014 pass opts.document");
  const maxRuleDepth = opts.maxRuleDepth === void 0 ? "auto" : opts.maxRuleDepth;
  const maxVruleDepth = opts.maxVruleDepth === void 0 ? 1 : opts.maxVruleDepth;
  const cols = doc.columns;
  const mathOn = doc.math !== "off";
  const el = d.createElement("div");
  el.className = "gt";
  if (doc.hash) el.setAttribute("data-gt-hash", doc.hash);
  if (doc.label) el.id = doc.label;
  const table = d.createElement("table");
  el.appendChild(table);
  if (doc.caption != null) {
    const cap = d.createElement("caption");
    cap.className = "gt-caption";
    fillCell(d, cap, cellOf(doc.caption), opts, mathOn);
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
        th.className = headClasses(
          doc,
          col,
          colspan,
          leaf,
          hc,
          maxVruleDepth
        ).join(" ");
        fillCell(d, th, hc, opts, mathOn);
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
  const depths = { maxRuleDepth, maxVruleDepth };
  renderSection(d, tbody, doc, doc.body, resolved, rawRes, opts, depths);
  table.appendChild(tbody);
  if (doc.foot.length) {
    const tfoot = d.createElement("tfoot");
    renderSection(d, tfoot, doc, doc.foot, [], [], opts, depths);
    table.appendChild(tfoot);
  }
  if (doc.notes.length) {
    const notes = d.createElement("div");
    notes.className = "gt-notes";
    for (const n of doc.notes) {
      const div = d.createElement("div");
      fillCell(d, div, { text: n }, opts, mathOn);
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
function renderSection(d, parent, doc, rows, resolved, rawRes, opts, depths) {
  const ncols = doc.columns.length;
  const mathOn = doc.math !== "off";
  const pending = new Array(ncols).fill(0);
  const carry = new Array(ncols).fill("");
  rows.forEach((row, r) => {
    const tr = d.createElement("tr");
    tr.setAttribute("data-r", String(r));
    const trCls = rowClasses(doc, row, r === 0, depths.maxRuleDepth).join(" ");
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
      td.className = bodyClasses(
        doc,
        col,
        colspan,
        cell,
        depths.maxVruleDepth
      ).join(" ");
      fillCell(d, td, cell, opts, mathOn);
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
function fillCell(d, node, cell, opts, mathOn) {
  if (cell.math) {
    node.classList.add("gt-math");
    renderMath(d, node, cell.text, opts);
  } else if (cell.html) {
    if (opts.allowHtml) node.innerHTML = cell.text;
    else node.textContent = cell.text;
  } else if (cell.markdown) {
    let group = null;
    for (const [kind, style, text] of markdownRuns(cell.text, mathOn)) {
      if (!style) {
        group = null;
      } else if (!group || group.tagName.toLowerCase() !== style) {
        group = node.appendChild(d.createElement(style));
      }
      const parent = group || node;
      if (kind === "math") {
        const span = d.createElement("span");
        span.className = "gt-math";
        renderMath(d, span, text, opts);
        parent.appendChild(span);
      } else if (kind === "code") {
        const code = d.createElement("code");
        code.textContent = text;
        parent.appendChild(code);
      } else if (text) {
        parent.appendChild(d.createTextNode(text));
      }
    }
  } else if (mathOn && cell.text.includes("$")) {
    for (const [isMath, run] of mathSegments(cell.text)) {
      if (isMath) {
        const span = d.createElement("span");
        span.className = "gt-math";
        renderMath(d, span, run, opts);
        node.appendChild(span);
      } else if (run) {
        node.appendChild(d.createTextNode(run));
      }
    }
  } else {
    node.textContent = cell.text;
  }
}
function renderMath(d, node, tex, opts) {
  if (opts.katex) {
    opts.katex.render(tex, node, { throwOnError: false });
  } else {
    node.textContent = `\\(${tex}\\)`;
  }
}
function columnClasses(col, maxVruleDepth) {
  const cls = [
    `gt-${col.align}`,
    col.role === "stub" ? "gt-stub" : "gt-data",
    col.wrap ? "gt-wrap" : "gt-nowrap"
  ];
  const slot = vruleSlot(col.break_depth, maxVruleDepth);
  if (slot !== null) cls.push(`gt-vbreak-${slot}`);
  return cls;
}
function headClasses(doc, col, colspan, leaf, hc, maxVruleDepth) {
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
  const vslot = col >= nStub ? vruleSlot(bd, maxVruleDepth) : null;
  if (vslot !== null) cls.push(`gt-vbreak-${vslot}`);
  for (const f of hc.flags || []) {
    if (CELL_FLAG_CLASS[f]) cls.push(CELL_FLAG_CLASS[f]);
  }
  return cls;
}
function bodyClasses(doc, col, colspan, cell, maxVruleDepth) {
  const cls = columnClasses(doc.columns[col], maxVruleDepth);
  const lastStub = doc.n_stub_levels > 0 && col + colspan === doc.n_stub_levels;
  if (lastStub) cls.push("gt-stub-end");
  for (const f of cell.flags || []) {
    if (CELL_FLAG_CLASS[f]) cls.push(CELL_FLAG_CLASS[f]);
  }
  return cls;
}
function rowClasses(doc, row, isFirst, maxRuleDepth) {
  const cls = [];
  const slot = isFirst ? null : ruleSlot(row.break_depth, doc.n_stub_levels, maxRuleDepth);
  if (slot !== null) cls.push(`gt-break-${slot}`);
  for (const f of row.flags || []) {
    if (ROW_FLAG_CLASS[f]) cls.push(ROW_FLAG_CLASS[f]);
  }
  return cls;
}
function csvEscape(s) {
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
var TEXT_IS_VALUE = /* @__PURE__ */ new Set(["string", "object"]);
function irToGridInput(doc) {
  if (doc.ir_version !== IR_VERSION_SUPPORTED) {
    throw new Error(`irToGridInput supports ir_version ${IR_VERSION_SUPPORTED}, got ${doc.ir_version}`);
  }
  const cols = doc.columns;
  for (const c of cols) {
    if ((c.role || "data") === "data" && !c.raw && !TEXT_IS_VALUE.has(c.dtype)) {
      throw new Error(
        `irToGridInput requires raw values on every non-string data column (missing on ${c.key} "${c.name.join(" / ")}", dtype ${c.dtype}) \u2014 build the document with include_raw='data', which covers numeric, date and bool columns`
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
    // csv-grid has no uppercase exponent, so `upper` (E, G) exports as
    // e and g; the cell text, which is normative, keeps its E
    case "sci":
      return dot + "e";
    case "gen":
      return dot + "g";
    // digits = significant figures
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
export {
  CELL_PAD,
  GT_RENDER_VERSION,
  IR_VERSION_SUPPORTED,
  MIN_COL,
  N_RULE_SLOTS,
  N_VRULE_SLOTS,
  gt_render_default as default,
  irToGridInput,
  markdownRuns,
  renderTable,
  ruleSlot,
  solveWidths,
  vruleSlot
};
