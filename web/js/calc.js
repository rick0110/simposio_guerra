/* =====================================================================
   calc.js — Mesa de Cálculo (gaveta de ferramentas numéricas do ESTADO-MAIOR)
   ---------------------------------------------------------------------
   import { mountCalc } from "./calc.js";
   const calc = mountCalc(document.getElementById("calc-drawer"));
   calc.open("leontief", { Z, X });     // abre a gaveta na ferramenta e preenche os campos (não executa)
   calc.toggle(); calc.close(); calc.isOpen();

   Ferramentas: matrix | hill | leontief | markov | trilaterate | regression | lanchester
   Prefill:
     matrix      {A, B?, b?, op?}
     hill        {cipher, crib?|plainCrib?, cipherCrib?, key?}   (crib = trecho claro conhecido;
                 sem cipherCrib, usa os primeiros símbolos de cipher com o mesmo comprimento)
     leontief    {Z?, X?, A?, d?, x?, L?}
     markov      {sequence?, P?, state?, k?}
     trilaterate {stations: [[x,y]...], distances: [...]}
     regression  {rows: [{...}], target, features?} ou {csv, target, features?}
     lanchester  {A0, B0, alpha, beta, T?}
   Chamadas ao servidor: api.tool(name, body) -> POST /api/tools/{name} (sem login).
   ===================================================================== */

import { api } from "./api.js";

/* ------------------------------------------------------------ constantes */
const CSS_URL = new URL("../css/calc.css", import.meta.url).href;
const TOOLS = ["matrix", "hill", "leontief", "markov", "trilaterate", "regression", "lanchester"];
const TOOL_LABEL = {
  matrix: "Matrizes",
  hill: "Cifra de Hill",
  leontief: "Leontief",
  markov: "Markov (clima)",
  trilaterate: "Triangulação",
  regression: "Regressão",
  lanchester: "Lanchester",
};
const SECTORS = ["ALI", "ACO", "COM"];
const STATES = ["limpo", "chuva", "tempestade"];
const HILL_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ";
const GRID_COLS = "ABCDEFGHIJKLMNOPQRSTUVWX";
const GRID_ROWS = 16;
const CELL = 50;
const MAX_N = 12;
const TAPE_MAX = 40;
const HEIGHT_KEY = "estado-maior.calc.altura";

let uidSeq = 0;
let svgSeq = 0;
const uid = (p) => `${p}-${++uidSeq}`;

/* ------------------------------------------------------------ DOM */
/** h(tag, attrs?, ...filhos) — filhos podem ser nós, texto, null/false (ignorados) ou arrays. */
function h(tag, attrs, ...kids) {
  if (attrs && (typeof attrs !== "object" || attrs instanceof Node || Array.isArray(attrs))) {
    kids.unshift(attrs);
    attrs = null;
  }
  const el = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, "");
      else el.setAttribute(k, String(v));
    }
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === undefined || kid === null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const inputEl = (value, cls = "calc-input mono", extra = {}) => {
  const el = h("input", { class: cls, type: "text", autocomplete: "off", spellcheck: "false", ...extra });
  el.value = value ?? "";
  return el;
};

function field(label, control) {
  const id = uid("f");
  control.id = id;
  return h("div", { class: "calc-field" }, h("label", { class: "calc-field__lbl", for: id }, label), control);
}

/** Grupo de rádios; devolve {el, get(), set(v), onChange(fn)}. */
function radios(label, options, value) {
  const gname = uid("rg");
  const wrap = h("div", { class: "calc-radios", role: "radiogroup", "aria-label": label });
  const inputs = options.map(([v, text]) => {
    const inp = h("input", { type: "radio", name: gname, value: v });
    if (v === value) inp.checked = true;
    wrap.append(h("label", { class: "calc-radio" }, inp, text));
    return inp;
  });
  return {
    el: wrap,
    get: () => (inputs.find((i) => i.checked) || inputs[0]).value,
    set: (v) => inputs.forEach((i) => { i.checked = i.value === v; }),
    onChange: (fn) => inputs.forEach((i) => i.addEventListener("change", fn)),
  };
}

/** Enter executa; em textarea só Ctrl/⌘+Enter. Botões, selects e resumos seguem o comportamento nativo. */
function enterRuns(el, fn) {
  el.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || e.isComposing || e.shiftKey) return;
    const tag = e.target.tagName;
    if (tag === "BUTTON" || tag === "SUMMARY" || tag === "SELECT" || tag === "A") return;
    if (tag === "TEXTAREA" && !(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    fn();
  });
}

function ticket(msg) {
  return h("div", { class: "calc-ticket", role: "alert" },
    h("span", { class: "calc-ticket__tag stencil" }, "erro"),
    h("p", { class: "calc-ticket__txt" }, msg));
}

/** Botão de execução: desabilita enquanto roda e mostra erros como bilhete na própria ferramenta. */
function runBtn(label, fn, out) {
  let btn;
  const go = async () => {
    btn.disabled = true;
    try {
      await fn();
    } catch (err) {
      out.replaceChildren(ticket(msgOf(err)));
    } finally {
      btn.disabled = false;
    }
  };
  btn = h("button", { class: "btn btn--blue btn--solid calc-run", type: "button", onclick: go }, label);
  return { el: btn, go };
}

function sec(title, expl, go, ...kids) {
  const el = h("section", { class: "calc-sec" },
    h("h3", { class: "calc-sec__title stencil" }, title),
    expl ? h("p", { class: "calc-sec__expl typed" }, expl) : null,
    ...kids);
  if (go) enterRuns(el, go);
  return el;
}

function panelEl(tool, title, expl, ...kids) {
  return h("article", { class: "calc-panel", "data-tool": tool, hidden: true },
    h("header", { class: "calc-panel__head" },
      h("h2", { class: "calc-panel__title stencil" }, title),
      h("p", { class: "calc-panel__expl typed" }, expl)),
    ...kids);
}

/* ------------------------------------------------------------ números e texto */
const NF4 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 4, maximumFractionDigits: 4, useGrouping: false });

function f4(x) {
  if (typeof x !== "number" || !Number.isFinite(x)) return x === null || x === undefined ? "—" : String(x);
  if (x === 0) x = 0; // sem zero negativo
  return NF4.format(x);
}

/** Número para campo de texto (vírgula decimal, sem zeros inúteis). */
function fInput(x) {
  if (typeof x !== "number" || !Number.isFinite(x)) return "";
  return String(Number(x.toPrecision(12))).replace(".", ",");
}

/** Complexo [re, im] → "re + im·i". */
function cpx([re, im]) {
  return `${f4(re)} ${im < 0 ? "−" : "+"} ${f4(Math.abs(im))}i`;
}

const isPair = (z) => Array.isArray(z) && z.length === 2 && typeof z[0] === "number";
/** Complexo com parte imaginária nula aparece como real. */
const fmtCell = (x, complex) => {
  if (complex && isPair(x)) return x[1] === 0 ? f4(x[0]) : cpx(x);
  return f4(x);
};
const dot = (s) => String(s).replace(/ /g, "·");

/** Lê número no formato brasileiro ou no formato com ponto. NaN se inválido. */
function parseNum(raw) {
  let s = String(raw ?? "").trim().replace(/\s+/g, "");
  if (!s) return NaN;
  if (s.includes(",") && s.includes(".")) s = s.replace(/\./g, "").replace(",", ".");
  else if (s.includes(",")) s = s.replace(",", ".");
  return /^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(s) ? Number(s) : NaN;
}

/**
 * Quebra texto colado em linhas e células.
 * Separador: tab, depois ponto e vírgula, depois vírgula; sem nenhum, espaços.
 */
function splitTable(text) {
  const lines = String(text).replace(/\r/g, "").split("\n").filter((l) => l.trim() !== "");
  const sep = lines.some((l) => l.includes("\t")) ? "\t"
    : lines.some((l) => l.includes(";")) ? ";"
      : lines.some((l) => l.includes(",")) ? ","
        : null;
  return lines.map((l) => (sep ? l.split(sep).map((c) => c.trim()) : l.trim().split(/\s+/)));
}

const calcErr = (msg) => Object.assign(new Error(msg), { calc: true });

function msgOf(err) {
  if (err && (err.calc || err.status !== undefined)) return err.message;
  console.error(err);
  return "Não foi possível mostrar o resultado. Confira os dados e tente de novo.";
}

function numOf(raw, what) {
  const v = parseNum(raw);
  if (Number.isNaN(v)) throw calcErr(`${what}: informe um número (ex.: 0,25).`);
  return v;
}

function intOf(raw, what) {
  const v = parseNum(raw);
  if (!Number.isInteger(v)) throw calcErr(`${what}: informe um número inteiro.`);
  return v;
}

function labelsFor(n) {
  return n === 3 ? STATES : Array.from({ length: n }, (_, i) => `E${i + 1}`);
}

const blank = (r, c) => Array.from({ length: r }, () => Array(c).fill(""));

/* ------------------------------------------------------------ editor de matrizes */
/**
 * Grade editável. Opções: title, rows, cols, vector, fixed, rowLabel(i,n), colLabel(j,n), onResize(R,C).
 * Devolve {el, read, setNumbers, setSize, size, isBlank, clear}.
 */
function matrixEditor(o = {}) {
  const vector = !!o.vector;
  const fixed = !!o.fixed;
  const title = o.title || "matriz";
  let R = o.rows ?? 2;
  let C = vector ? 1 : (o.cols ?? 2);
  let V = blank(R, C);

  const dim = h("span", { class: "calc-ed__dim mono" });
  const mx = h("div", { class: "mx calc-ed__mx" });
  const err = h("p", { class: "calc-ed__err", role: "alert", hidden: true });
  const sizeBtns = [];

  const dimTxt = (r, c) => (vector ? `${r} valor${r > 1 ? "es" : ""}` : `${r} × ${c}`);
  const showErr = (msg) => { err.textContent = msg; err.hidden = false; };
  const hideErr = () => { err.hidden = true; };

  function syncBtns() {
    for (const [b, kind] of sizeBtns) {
      b.disabled = (kind === "addR" && R >= MAX_N) || (kind === "subR" && R <= 1)
        || (kind === "addC" && C >= MAX_N) || (kind === "subC" && C <= 1);
    }
  }

  function cellName(i, j) {
    if (vector) return typeof o.rowLabel === "function" ? o.rowLabel(i, R) : String(i + 1);
    return `${i + 1},${j + 1}`;
  }

  function cell(i, j) {
    const inp = h("input", {
      class: "calc-cell mono", type: "text", inputmode: "decimal", autocomplete: "off", spellcheck: "false",
      "aria-label": `${title}, linha ${i + 1}, coluna ${j + 1}`,
    });
    inp.value = V[i][j];
    inp.addEventListener("input", () => { V[i][j] = inp.value; hideErr(); });
    inp.addEventListener("paste", (e) => {
      const t = e.clipboardData ? e.clipboardData.getData("text") : "";
      if (/[\n\t;]/.test(t)) { e.preventDefault(); applyText(t); }
    });
    return inp;
  }

  function render() {
    dim.textContent = dimTxt(R, C);
    syncBtns();
    const labeled = typeof o.rowLabel === "function";
    const kids = [];
    if (!vector && typeof o.colLabel === "function") {
      if (labeled) kids.push(h("span"));
      for (let j = 0; j < C; j++) kids.push(h("span", { class: "calc-ed__lbl" }, o.colLabel(j, C)));
    }
    for (let i = 0; i < R; i++) {
      if (labeled) kids.push(h("span", { class: "calc-ed__lbl" }, o.rowLabel(i, R)));
      for (let j = 0; j < C; j++) kids.push(cell(i, j));
    }
    const cols = `${labeled ? "max-content " : ""}repeat(${C}, minmax(0, 1fr))`;
    mx.replaceChildren(h("div", { class: "calc-ed__grid", style: `grid-template-columns:${cols}` }, kids));
  }

  function resize(nr, nc) {
    nr = Math.max(1, Math.min(MAX_N, nr));
    nc = vector ? 1 : Math.max(1, Math.min(MAX_N, nc));
    if (nr === R && nc === C) return;
    const NV = blank(nr, nc);
    for (let i = 0; i < Math.min(nr, R); i++) for (let j = 0; j < Math.min(nc, C); j++) NV[i][j] = V[i][j];
    V = NV; R = nr; C = nc;
    render();
    if (o.onResize) o.onResize(R, C);
  }

  function applyText(text) {
    const rows = splitTable(text)
      .map((r) => { const c = r.slice(); while (c.length && c[c.length - 1] === "") c.pop(); return c; })
      .filter((r) => r.length);
    if (!rows.length) return showErr("A colagem está vazia.");
    let cells;
    if (vector) {
      cells = rows.flat().map((s) => [s]);
    } else {
      const w = rows[0].length;
      if (rows.some((r) => r.length !== w)) return showErr("As linhas da colagem têm quantidades diferentes de colunas.");
      cells = rows;
    }
    const nr = cells.length;
    const nc = vector ? 1 : cells[0].length;
    if (nr > MAX_N || nc > MAX_N) return showErr(`Limite de ${MAX_N} linhas e colunas.`);
    if (fixed && (nr !== R || nc !== C)) return showErr(`${title} tem ${dimTxt(R, C)}; a colagem tem ${dimTxt(nr, nc)}.`);
    for (const row of cells) {
      for (const s of row) {
        if (Number.isNaN(parseNum(s))) return showErr(`Valor não numérico na colagem: "${s}".`);
      }
    }
    R = nr; C = nc; V = cells.map((r) => r.map((s) => s.trim()));
    hideErr();
    render();
    if (o.onResize) o.onResize(R, C);
    return undefined;
  }

  function read() {
    const out = V.map((row, i) => row.map((s, j) => {
      const v = parseNum(s);
      if (Number.isNaN(v)) {
        const where = `${title}, posição ${cellName(i, j)}`;
        throw calcErr(s.trim() ? `${where}: "${s.trim()}" não é número.` : `${where}: célula vazia.`);
      }
      return v;
    }));
    return vector ? out.map((r) => r[0]) : out;
  }

  function setNumbers(M) {
    if (!Array.isArray(M) || !M.length) throw calcErr(`${title}: dados ausentes.`);
    const nr = M.length;
    const nc = vector ? 1 : (Array.isArray(M[0]) ? M[0].length : 0);
    if (!vector && !nc) throw calcErr(`${title}: esperava uma matriz.`);
    if (fixed && (nr !== R || nc !== C)) throw calcErr(`${title}: esperava ${dimTxt(R, C)}, recebi ${dimTxt(nr, nc)}.`);
    R = nr; C = nc;
    V = blank(R, C);
    for (let i = 0; i < R; i++) for (let j = 0; j < C; j++) V[i][j] = fInput(vector ? M[i] : M[i][j]);
    hideErr();
    render();
    if (o.onResize) o.onResize(R, C);
  }

  function clear() {
    V = blank(R, C);
    hideErr();
    render();
  }

  const taPaste = h("textarea", {
    class: "calc-paste__ta mono", rows: 3, spellcheck: "false",
    "aria-label": `colar valores de ${title}`,
    placeholder: vector
      ? "Um valor por linha, ou uma linha com ponto e vírgula ou tab. Ctrl+Enter aplica."
      : "Cole do Excel ou CSV: uma linha por linha, colunas por tab, ponto e vírgula ou vírgula. Ctrl+Enter aplica.",
  });
  taPaste.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      e.stopPropagation();
      applyText(taPaste.value);
    }
  });
  const pasteBox = h("details", { class: "calc-paste" },
    h("summary", {}, "colar do Excel ou CSV"),
    taPaste,
    h("button", { class: "btn btn--small", type: "button", onclick: () => applyText(taPaste.value) }, "aplicar colagem"));

  let sizeRow = null;
  if (!fixed) {
    const add = (label, kind, fn) => {
      const b = h("button", { class: "btn btn--small", type: "button", onclick: fn }, label);
      sizeBtns.push([b, kind]);
      return b;
    };
    sizeRow = h("div", { class: "calc-ed__size" },
      add(vector ? "+ valor" : "+ linha", "addR", () => resize(R + 1, C)),
      add(vector ? "− valor" : "− linha", "subR", () => resize(R - 1, C)),
      vector ? null : add("+ coluna", "addC", () => resize(R, C + 1)),
      vector ? null : add("− coluna", "subC", () => resize(R, C - 1)));
  }

  const el = h("div", { class: `calc-ed${vector ? " calc-ed--vec" : ""}` },
    h("div", { class: "calc-ed__head" }, h("span", { class: "calc-ed__title stencil" }, title), dim),
    mx,
    sizeRow,
    pasteBox,
    err);

  render();

  return {
    el,
    read,
    setNumbers,
    setSize: (nr, nc) => resize(nr, nc ?? C),
    size: () => ({ rows: R, cols: C }),
    isBlank: () => V.every((row) => row.every((s) => s.trim() === "")),
    clear,
  };
}

/* ------------------------------------------------------------ apresentação de resultados */
function vecNode(v, { labels = null, complex = false } = {}) {
  const kids = [];
  v.forEach((x, i) => {
    if (labels) kids.push(h("span", { class: "calc-mx__lbl" }, labels[i] ?? ""));
    kids.push(h("span", { class: "mono calc-mx__c" }, fmtCell(x, complex)));
  });
  const cols = labels ? "max-content max-content" : "max-content";
  return h("div", { class: "mx calc-mx" }, h("div", { class: "calc-mx__g", style: `grid-template-columns:${cols}` }, kids));
}

function matNode(M, { complex = false, rowLabels = null, colLabels = null } = {}) {
  const C = M[0].length;
  const kids = [];
  if (colLabels) {
    if (rowLabels) kids.push(h("span"));
    colLabels.forEach((l) => kids.push(h("span", { class: "calc-mx__lbl" }, l)));
  }
  M.forEach((row, i) => {
    if (rowLabels) kids.push(h("span", { class: "calc-mx__lbl" }, rowLabels[i] ?? ""));
    row.forEach((x) => kids.push(h("span", { class: "mono calc-mx__c" }, fmtCell(x, complex))));
  });
  const cols = `${rowLabels ? "max-content " : ""}repeat(${C}, max-content)`;
  return h("div", { class: "mx calc-mx" }, h("div", { class: "calc-mx__g", style: `grid-template-columns:${cols}` }, kids));
}

function block(label, node, lines, copy, use = null) {
  return {
    label, lines, copy, use,
    node: h("div", { class: "calc-res" }, h("h4", { class: "calc-res__lbl stencil" }, label), node),
  };
}

/** kind: "num" | "vec" | "mat". Gera o bloco de exibição, as linhas da fita e o texto copiável (TSV). */
function valueBlock(label, v, kind, opts = {}) {
  const { complex = false, labels = null, rowLabels = null, colLabels = null, use = null } = opts;
  if (kind === "num") {
    const t = f4(v);
    return block(label, h("span", { class: "mono calc-num" }, t), [`${label} = ${t}`], t, use);
  }
  if (kind === "vec") {
    const items = v.map((x) => fmtCell(x, complex));
    const lines = labels ? items.map((t, i) => `${labels[i]} = ${t}`) : [`${label} = (${items.join("; ")})`];
    return block(label, vecNode(v, { labels, complex }), lines, items.join("\n"), use);
  }
  const txt = v.map((row) => row.map((x) => fmtCell(x, complex)));
  const pad = " ".repeat(label.length + 3);
  const lines = txt.map((r, i) => (i === 0 ? `${label} = ` : pad) + "[ " + r.join("  ") + " ]");
  return block(label, matNode(v, { complex, rowLabels, colLabels }), lines, txt.map((r) => r.join("\t")).join("\n"), use);
}

/** Mostra os blocos no painel e imprime uma linha na fita para cada bloco. */
function finish(out, ctx, tool, blocks, extra = []) {
  out.replaceChildren(...blocks.map((b) => b.node), ...extra);
  for (const b of blocks) {
    ctx.tape({ tool, title: `${TOOL_LABEL[tool]} · ${b.label}`, lines: b.lines, copy: b.copy, use: b.use });
  }
}

function telegramBox(head, text) {
  const s = String(text);
  return h("div", { class: "telegram calc-tg" },
    h("div", { class: "telegram__head" }, h("span", {}, head), h("span", { class: "mono" }, `${[...s].length} símbolos`)),
    h("p", { class: "calc-tg__txt" }, h("span", { class: "telegram__strip" }, dot(s))));
}

function barsBlock(label, probs, names, use = null) {
  const rows = probs.map((p, i) => h("div", { class: "calc-bars__row" },
    h("span", { class: "calc-bars__lbl" }, names[i]),
    h("span", { class: "calc-bars__track" },
      h("span", { class: "calc-bars__fill", style: `width:${(Math.max(0, p) * 100).toFixed(2)}%` })),
    h("span", { class: "mono calc-bars__v" }, f4(p))));
  const lines = probs.map((p, i) => `${names[i]} = ${f4(p)}`);
  return block(label, h("div", { class: "calc-bars" }, rows), lines, lines.join("\n"), use);
}

/* ------------------------------------------------------------ SVG (só números e rótulos constantes) */
function niceStep(max, parts) {
  const raw = max / parts;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const f = raw / mag;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * mag;
}

function mapSVG(stations, dists, ex, ey) {
  const cols = GRID_COLS.length;
  const W = cols * CELL, H = GRID_ROWS * CELL, pad = 34;
  const id = `calc-map-${++svgSeq}`;
  let s = `<svg class="calc-map" viewBox="${-pad} ${-pad} ${W + 2 * pad} ${H + 2 * pad}" role="img" aria-label="Quadrícula A a X e 1 a 16 com estações e posição estimada">`;
  s += `<defs><clipPath id="${id}-c"><rect x="0" y="0" width="${W}" height="${H}"/></clipPath>`;
  s += `<pattern id="${id}-h" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="7" class="calc-map__hatch"/></pattern></defs>`;
  s += `<rect x="0" y="0" width="${W}" height="${H}" class="calc-map__bg"/>`;
  const c = Math.floor(ex / CELL), r = Math.floor(ey / CELL);
  if (c >= 0 && c < cols && r >= 0 && r < GRID_ROWS) {
    s += `<rect x="${c * CELL}" y="${r * CELL}" width="${CELL}" height="${CELL}" fill="url(#${id}-h)" class="calc-map__cell"/>`;
  }
  for (let i = 0; i <= cols; i++) s += `<line x1="${i * CELL}" y1="0" x2="${i * CELL}" y2="${H}" class="calc-map__grid"/>`;
  for (let j = 0; j <= GRID_ROWS; j++) s += `<line x1="0" y1="${j * CELL}" x2="${W}" y2="${j * CELL}" class="calc-map__grid"/>`;
  for (let i = 0; i < cols; i++) s += `<text x="${i * CELL + CELL / 2}" y="-12" text-anchor="middle" class="calc-map__lbl">${GRID_COLS[i]}</text>`;
  for (let j = 0; j < GRID_ROWS; j++) s += `<text x="-12" y="${j * CELL + CELL / 2}" text-anchor="end" dominant-baseline="middle" class="calc-map__lbl">${j + 1}</text>`;
  s += `<g clip-path="url(#${id}-c)">`;
  stations.forEach(([x, y], i) => { s += `<circle cx="${x}" cy="${y}" r="${dists[i]}" class="calc-map__ring"/>`; });
  s += "</g>";
  stations.forEach(([x, y], i) => {
    s += `<circle cx="${x}" cy="${y}" r="6" class="calc-map__st"/><text x="${x + 10}" y="${y - 8}" class="calc-map__stl">E${i + 1}</text>`;
  });
  if (ex >= 0 && ex <= W && ey >= 0 && ey <= H) {
    s += `<path d="M${ex - 12},${ey} L${ex + 12},${ey} M${ex},${ey - 12} L${ex},${ey + 12}" class="calc-map__est"/>`;
    s += `<circle cx="${ex}" cy="${ey}" r="9" class="calc-map__est-r"/>`;
  } else {
    s += `<text x="8" y="${-pad + 14}" class="calc-map__stl">posição estimada fora do mapa</text>`;
  }
  return s + "</svg>";
}

function markovSVG(P, names) {
  const n = P.length;
  const W = 540, HH = 320, cx = 270, cy = 165, RR = n <= 3 ? 112 : 128, NR = 30;
  const id = `calc-arr-${++svgSeq}`;
  const pts = P.map((_, i) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
    return [cx + RR * Math.cos(a), cy + RR * Math.sin(a)];
  });
  let edges = "", texts = "", nodes = "";
  pts.forEach(([x, y], i) => {
    nodes += `<circle cx="${x}" cy="${y}" r="${NR}" class="calc-dg__node"/>`;
    const ux = x - cx, uy = y - cy, L = Math.hypot(ux, uy) || 1;
    const lx = x + (ux / L) * (NR + 20), ly = y + (uy / L) * (NR + 20) + 4;
    const anchor = ux > 20 ? "start" : ux < -20 ? "end" : "middle";
    texts += `<text x="${lx}" y="${ly}" text-anchor="${anchor}" class="calc-dg__name">${names[i]}</text>`;
  });
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const p = P[i][j];
      if (!(p > 1e-9)) continue;
      const sw = (0.8 + 7 * p).toFixed(2);
      if (i === j) {
        const [x, y] = pts[i];
        const ux = x - cx, uy = y - cy, L = Math.hypot(ux, uy) || 1;
        const ox = x + (ux / L) * (NR + 14), oy = y + (uy / L) * (NR + 14);
        edges += `<circle cx="${ox}" cy="${oy}" r="13" class="calc-dg__loop" style="stroke-width:${sw}"/>`;
        texts += `<text x="${ox + (ux / L) * 26}" y="${oy + (uy / L) * 26 + 4}" text-anchor="middle" class="calc-dg__p">${f4(p)}</text>`;
        continue;
      }
      const [x1, y1] = pts[i], [x2, y2] = pts[j];
      const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy);
      const ux = dx / L, uy = dy / L, nx = -uy, ny = ux;
      const sx = x1 + ux * NR, sy = y1 + uy * NR;
      const ex = x2 - ux * (NR + 7), ey = y2 - uy * (NR + 7);
      const bend = 22;
      const mx = (sx + ex) / 2 + nx * bend, my = (sy + ey) / 2 + ny * bend;
      edges += `<path d="M${sx},${sy} Q${mx},${my} ${ex},${ey}" style="stroke-width:${sw}" class="calc-dg__arrow" marker-end="url(#${id})"/>`;
      const tx = 0.25 * sx + 0.5 * mx + 0.25 * ex, ty = 0.25 * sy + 0.5 * my + 0.25 * ey;
      texts += `<text x="${tx + nx * 11}" y="${ty + ny * 11 + 4}" text-anchor="middle" class="calc-dg__p">${f4(p)}</text>`;
    }
  }
  const defs = `<defs><marker id="${id}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto"><path d="M0,0 L10,5 L0,10 z" class="calc-dg__head"/></marker></defs>`;
  return `<svg class="calc-dg__svg" viewBox="0 0 ${W} ${HH}" role="img" aria-label="Diagrama de estados da cadeia de Markov">${defs}${edges}${nodes}${texts}</svg>`;
}

function lanchesterSVG(traj, A0, B0, tEnd) {
  const W = 640, HH = 300, L = 58, R = 16, T0 = 14, BM = 40;
  const pw = W - L - R, ph = HH - T0 - BM;
  const tmax = tEnd > 0 ? tEnd : 1;
  const ymax = Math.max(A0, B0, 1e-9) * 1.08;
  const X = (t) => L + (t / tmax) * pw;
  const Y = (v) => T0 + ph - (v / ymax) * ph;
  const ys = niceStep(ymax, 5), xs = niceStep(tmax, 5);
  let g = "";
  for (let v = 0; v <= ymax + 1e-9; v += ys) {
    const dec = ys < 1 ? 2 : 0;
    g += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" class="calc-plot__grid"/>`;
    g += `<text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end" class="calc-plot__tick">${v.toFixed(dec).replace(".", ",")}</text>`;
  }
  for (let t = 0; t <= tmax + 1e-9; t += xs) {
    g += `<line x1="${X(t)}" x2="${X(t)}" y1="${T0}" y2="${T0 + ph}" class="calc-plot__grid"/>`;
    g += `<text x="${X(t)}" y="${T0 + ph + 16}" text-anchor="middle" class="calc-plot__tick">${t.toFixed(2).replace(".", ",")}</text>`;
  }
  const pa = traj.map(([t, a]) => `${X(t).toFixed(1)},${Y(a).toFixed(1)}`).join(" ");
  const pb = traj.map(([t, , b]) => `${X(t).toFixed(1)},${Y(b).toFixed(1)}`).join(" ");
  const endLine = tEnd > 0
    ? `<line x1="${X(tEnd)}" x2="${X(tEnd)}" y1="${T0}" y2="${T0 + ph}" class="calc-plot__end"/><text x="${X(tEnd) - 4}" y="${T0 + 12}" text-anchor="end" class="calc-plot__tick">t = ${tEnd.toFixed(4).replace(".", ",")}</text>`
    : "";
  return `<svg class="calc-plot__svg" viewBox="0 0 ${W} ${HH}" role="img" aria-label="Trajetórias de A e B no tempo">`
    + g + endLine
    + `<line x1="${L}" x2="${L}" y1="${T0}" y2="${T0 + ph}" class="calc-plot__axis"/>`
    + `<line x1="${L}" x2="${W - R}" y1="${T0 + ph}" y2="${T0 + ph}" class="calc-plot__axis"/>`
    + `<polyline points="${pa}" class="calc-plot__a"/>`
    + `<polyline points="${pb}" class="calc-plot__b"/>`
    + `<text x="${L + 10}" y="${T0 + 16}" class="calc-plot__leg calc-plot__a-t">A(t) atacante</text>`
    + `<text x="${L + 150}" y="${T0 + 16}" class="calc-plot__leg calc-plot__b-t">B(t) defensor</text>`
    + `<text x="${W - R}" y="${T0 + ph + 32}" text-anchor="end" class="calc-plot__tick">tempo</text>`
    + "</svg>";
}

/* ------------------------------------------------------------ parsers de dados colados */
function parseSeq(text) {
  return String(text).split(/[\s,;]+/).filter(Boolean).map((t) => (/^\d+$/.test(t) ? Number(t) : t));
}

/** Leituras de triangulação: 3 colunas (x, y, distância) ou 4 (Estação, x, y, distância). Cabeçalho ignorado. */
function parseReadings(text) {
  const rows = splitTable(text).filter((r) => r.some((c) => c !== ""));
  const out = [];
  rows.forEach((r, idx) => {
    let cells = r.slice();
    while (cells.length && cells[cells.length - 1] === "") cells.pop();
    if (cells.length === 4) cells = cells.slice(1);
    if (cells.length !== 3) throw calcErr(`Linha ${idx + 1}: são esperadas 3 colunas (x, y, distância) ou 4 (estação, x, y, distância).`);
    if (cells.some((c) => Number.isNaN(parseNum(c)))) {
      if (idx === 0) return; // cabeçalho
      throw calcErr(`Linha ${idx + 1}: há valor não numérico.`);
    }
    out.push({ x: cells[0], y: cells[1], d: cells[2] });
  });
  if (out.length < 3) throw calcErr("São necessárias pelo menos 3 leituras (estações).");
  return out;
}

/** CSV de regressão → {cols, rows, ignored}. Mantém só colunas numéricas. */
function dataFromCSV(text) {
  const rows = splitTable(text).filter((r) => r.some((c) => c !== ""));
  if (rows.length < 2) throw calcErr("Cole o cabeçalho na primeira linha e ao menos uma observação.");
  const header = rows[0].map((c, j) => c || `col${j + 1}`);
  if (new Set(header).size !== header.length) throw calcErr("Cabeçalho com nomes repetidos.");
  if (rows.slice(1).some((r) => r.length !== header.length)) throw calcErr("Há linhas com quantidade de colunas diferente do cabeçalho.");
  const body = rows.slice(1);
  const numericIdx = header.map((_, j) => j).filter((j) => body.every((r) => !Number.isNaN(parseNum(r[j]))));
  const cols = numericIdx.map((j) => header[j]);
  const ignored = header.filter((_, j) => !numericIdx.includes(j));
  if (!cols.length) throw calcErr("Nenhuma coluna numérica encontrada.");
  return { cols, ignored, rows: body.map((r) => Object.fromEntries(numericIdx.map((j) => [header[j], parseNum(r[j])]))) };
}

/** rows (objetos) → {cols, rows, ignored}. */
function dataFromRows(raw) {
  if (!Array.isArray(raw) || !raw.length || !raw.every((r) => r && typeof r === "object")) {
    throw calcErr("Os dados devem ser uma lista de objetos (uma linha por observação).");
  }
  const keys = [...new Set(raw.flatMap((r) => Object.keys(r)))];
  const cols = keys.filter((k) => raw.every((r) => !Number.isNaN(parseNum(r[k]))));
  const ignored = keys.filter((k) => !cols.includes(k));
  return { cols, ignored, rows: raw.map((r) => Object.fromEntries(cols.map((k) => [k, parseNum(r[k])]))) };
}

/* ============================================================ painéis */

/* ---------- 01 Matrizes ---------- */
function matrixPanel(ctx) {
  const OPS = [
    ["det", "Determinante", "det(A) mede o fator de escala da transformação; zero indica matriz singular, que não tem inversa."],
    ["inv", "Inversa", "A⁻¹ tal que A·A⁻¹ = I. Serve para isolar x em A·x = b."],
    ["solve", "Resolver A·x = b", "x = A⁻¹·b, por eliminação gaussiana. A precisa ser quadrada e invertível."],
    ["lstsq", "Mínimos quadrados", "x que minimiza ‖A·x − b‖², pelas equações normais Aᵀ·A·x = Aᵀ·b. A tem m ≥ n linhas."],
    ["eig", "Autovalores e autovetores", "A·v = λ·v. Os autovetores são as colunas de V. Valores complexos aparecem como re + im·i."],
    ["pow", "Potência A^k", "A^k = A·A·…·A (k fatores). Para P^k em cadeias de Markov, use a ferramenta 04."],
    ["mul", "Produto A·B", "Cada entrada de A·B soma os produtos da linha de A pela coluna de B. Colunas de A = linhas de B."],
    ["transpose", "Transposta", "Aᵀ troca linhas por colunas: (Aᵀ)ᵢⱼ = Aⱼᵢ."],
    ["stationary", "Vetor estacionário", "π com π·P = π e Σπ = 1, para P com linhas somando 1. A matriz A é lida como P."],
  ];
  const KIND = { det: "num", inv: "mat", pow: "mat", mul: "mat", transpose: "mat", solve: "vec", lstsq: "vec", stationary: "vec", eig: "eig" };
  const sel = h("select", { class: "calc-select mono", "aria-label": "operação" },
    OPS.map(([k, lbl]) => h("option", { value: k }, lbl)));
  const expl = h("p", { class: "calc-expl typed", "aria-live": "polite" });
  const out = h("div", { class: "calc-out", "aria-live": "polite" });

  const B = matrixEditor({ title: "B", rows: 2, cols: 2 });
  const b = matrixEditor({ title: "b (vetor)", rows: 2, vector: true });
  const A = matrixEditor({
    title: "A", rows: 2, cols: 2,
    onResize: (r) => { b.setSize(r); B.setSize(A.size().cols, B.size().cols); },
  });
  A.setNumbers([[2, 1], [1, 3]]);
  B.setNumbers([[1, 0], [0, 1]]);
  b.setNumbers([1, 2]);
  const kIn = inputEl("2", "calc-input mono", { inputmode: "numeric", "aria-label": "expoente k" });
  const kField = field("expoente k", kIn);

  function sync() {
    const op = sel.value;
    expl.textContent = OPS.find((o) => o[0] === op)[2];
    B.el.hidden = op !== "mul";
    b.el.hidden = !(op === "solve" || op === "lstsq");
    kField.hidden = op !== "pow";
  }
  sel.addEventListener("change", sync);

  async function run() {
    const op = sel.value;
    const body = { op, A: A.read() };
    if (op === "mul") body.B = B.read();
    if (op === "solve" || op === "lstsq") body.b = b.read();
    if (op === "pow") body.k = intOf(kIn.value, "expoente k");
    const res = await ctx.call("matrix", body);
    const label = OPS.find((o) => o[0] === op)[1];
    const kind = KIND[op];
    let blocks;
    if (kind === "num") blocks = [valueBlock("det(A)", res.result, "num")];
    else if (kind === "eig") {
      blocks = [
        valueBlock("autovalores λ", res.result, "vec", { complex: true }),
        valueBlock("autovetores (colunas de V)", res.vectors, "mat", { complex: true }),
      ];
    } else if (op === "lstsq") {
      blocks = [
        valueBlock("x", res.result, "vec"),
        valueBlock("resíduo ‖A·x − b‖²", res.residuo_quadratico, "num"),
      ];
    } else if (kind === "vec") {
      blocks = [valueBlock(op === "stationary" ? "π" : "x", res.result, "vec")];
    } else {
      blocks = [valueBlock("resultado", res.result, "mat", { use: { tool: "matrix", prefill: { A: res.result } } })];
    }
    finish(out, ctx, "matrix", blocks);
  }

  const run1 = runBtn("Calcular", run, out);
  sync();
  return {
    el: panelEl("matrix", "Matrizes",
      "Operações de álgebra linear sobre A (e B, b, k quando necessários). Números com vírgula decimal; colagens do Excel são aceitas.",
      sec("Operação", null, run1.go,
        field("operação", sel),
        expl),
      sec("Dados", null, run1.go,
        h("div", { class: "calc-cols" }, A.el, h("div", { class: "calc-stack" }, B.el, b.el, kField)),
        h("div", { class: "calc-actions" }, run1.el)),
      sec("Resultado", null, null, out)),
    prefill(p) {
      if (p.op && OPS.some((o) => o[0] === p.op)) sel.value = p.op;
      if (p.A) A.setNumbers(p.A);
      if (p.B) B.setNumbers(p.B);
      if (p.b) b.setNumbers(p.b);
      if (p.k !== undefined) kIn.value = String(p.k);
      sync();
    },
  };
}

/* ---------- 02 Cifra de Hill ---------- */
function hillPanel(ctx) {
  const ruler = h("div", { class: "calc-ruler", role: "img", "aria-label": "Alfabeto: A a Z são 0 a 25, dígitos 0 a 9 são 26 a 35, espaço é 36" },
    [...HILL_ALPHA].map((ch, i) => h("span", { class: "calc-ruler__c" },
      h("b", { "aria-hidden": "true" }, ch === " " ? "·" : ch),
      h("i", { "aria-hidden": "true" }, String(i)))));

  const keyEd = matrixEditor({ title: "chave K (2 × 2)", rows: 2, cols: 2, fixed: true });

  // passo 1: recuperar K
  const plainCrib = inputEl("URGENTE ", "calc-input mono", { "aria-label": "trecho claro conhecido (crib)" });
  const cipherCrib = inputEl("", "calc-input mono", { "aria-label": "trecho cifrado correspondente", placeholder: "ex.: CJNUVMN8" });
  const out1 = h("div", { class: "calc-out", "aria-live": "polite" });
  const invOut = h("div", { class: "calc-out", "aria-live": "polite" });
  const run1 = runBtn("Recuperar K", async () => {
    const res = await ctx.call("hill_recover", { plain: plainCrib.value, cipher: cipherCrib.value, n: 2 });
    keyEd.setNumbers(res.key);
    const kb = valueBlock("chave K", res.key, "mat");
    finish(out1, ctx, "hill", [kb], [h("span", { class: "stamp stamp--blue" }, "conferido")]);
    invOut.replaceChildren();
  }, out1);
  const runInv = runBtn("K⁻¹ mod 37", async () => {
    const res = await ctx.call("modinv", { K: keyEd.read() });
    finish(invOut, ctx, "hill", [valueBlock("K⁻¹ (mod 37)", res.result, "mat")]);
  }, invOut);

  // passo 2: decifrar
  const cipherTA = h("textarea", { class: "calc-ta mono", rows: 3, spellcheck: "false", "aria-label": "criptograma", placeholder: "criptograma interceptado; espaços são símbolos do alfabeto" });
  const out2 = h("div", { class: "calc-out", "aria-live": "polite" });
  const run2 = runBtn("Decifrar", async () => {
    const res = await ctx.call("hill_decrypt", { cipher: cipherTA.value, key: keyEd.read() });
    out2.replaceChildren(telegramBox("texto claro", res.plain));
    ctx.tape({ tool: "hill", title: "Cifra de Hill · texto claro", lines: [dot(res.plain)], copy: res.plain, use: null });
  }, out2);

  // passo 3: cifrar
  const plainTA = h("textarea", { class: "calc-ta mono", rows: 2, spellcheck: "false", "aria-label": "mensagem a cifrar", placeholder: "mensagem própria, em letras, números e espaços" });
  const out3 = h("div", { class: "calc-out", "aria-live": "polite" });
  const run3 = runBtn("Cifrar", async () => {
    const res = await ctx.call("hill_encrypt", { plain: plainTA.value, key: keyEd.read() });
    out3.replaceChildren(telegramBox("criptograma", res.cipher));
    ctx.tape({ tool: "hill", title: "Cifra de Hill · criptograma", lines: [dot(res.cipher)], copy: res.cipher, use: null });
  }, out3);

  return {
    el: panelEl("hill", "Cifra de Hill sobre ℤ₃₇",
      "Alfabeto de 37 símbolos, com A–Z = 0–25, 0–9 = 26–35 e espaço = 36. Com um trecho claro conhecido e o cifrado correspondente, K = C·P⁻¹ (mod 37).",
      sec("Alfabeto", "Régua de conversão. Aritmética sempre módulo 37 (primo, então toda matriz com determinante não nulo em ℤ₃₇ é invertível).", null, ruler),
      sec("1 · Recuperar a chave K", "Informe o trecho claro conhecido (com o espaço final, se houver) e o trecho cifrado de mesmo comprimento.", run1.go,
        h("div", { class: "calc-cols" }, field("trecho claro conhecido", plainCrib), field("trecho cifrado correspondente", cipherCrib)),
        h("div", { class: "calc-actions" }, run1.el),
        out1, invOut,
        h("div", { class: "calc-actions" }, runInv.el)),
      sec("Chave K", "Preenchida pelo passo 1 ou digitada. Usada nos passos 2 e 3.", null, keyEd.el),
      sec("2 · Decifrar", "Criptograma e chave K: p = K⁻¹·c (mod 37), em blocos de 2 símbolos.", run2.go,
        field("criptograma", cipherTA),
        h("div", { class: "calc-actions" }, run2.el), out2),
      sec("3 · Cifrar", "Mensagem própria e chave K: c = K·p (mod 37). Útil para conferir a chave.", run3.go,
        field("mensagem", plainTA),
        h("div", { class: "calc-actions" }, run3.el), out3)),
    prefill(p) {
      if (p.key) keyEd.setNumbers(p.key);
      const plain = p.plainCrib ?? p.crib;
      if (plain != null) plainCrib.value = String(plain);
      if (p.cipherCrib != null) cipherCrib.value = String(p.cipherCrib);
      else if (p.cipher != null && plain != null) cipherCrib.value = String(p.cipher).slice(0, String(plain).length);
      if (p.cipher != null) cipherTA.value = String(p.cipher);
    },
  };
}

/* ---------- 03 Leontief ---------- */
function leontiefPanel(ctx) {
  const rl = (i) => SECTORS[i];
  const cl = (j) => SECTORS[j];
  const Z = matrixEditor({ title: "Z (transações)", rows: 3, cols: 3, fixed: true, rowLabel: rl, colLabel: cl });
  const X = matrixEditor({ title: "X (produção total)", rows: 3, vector: true, fixed: true, rowLabel: rl });
  const A = matrixEditor({ title: "A (técnica)", rows: 3, cols: 3, fixed: true, rowLabel: rl, colLabel: cl });
  const d = matrixEditor({ title: "d (demanda final)", rows: 3, vector: true, fixed: true, rowLabel: rl });
  const x = matrixEditor({ title: "x (produção bruta)", rows: 3, vector: true, fixed: true, rowLabel: rl });
  const L = matrixEditor({ title: "L (mão de obra por unidade)", rows: 3, vector: true, fixed: true, rowLabel: rl });
  const src = radios("fonte da matriz técnica A", [["zx", "calcular A = Z·diag(X)⁻¹"], ["a", "usar A informada"]], "zx");
  const zxBox = h("div", { class: "calc-cols" }, Z.el, X.el);
  const aBox = h("div", {}, A.el);
  const out = h("div", { class: "calc-out", "aria-live": "polite" });

  function sync() {
    const zx = src.get() === "zx";
    zxBox.hidden = !zx;
    aBox.hidden = zx;
  }
  src.onChange(sync);

  async function run() {
    const body = {};
    if (src.get() === "zx") { body.Z = Z.read(); body.X = X.read(); } else body.A = A.read();
    const hasD = !d.isBlank(), hasX = !x.isBlank(), hasL = !L.isBlank();
    if (!hasD && !hasX) throw calcErr("Informe a demanda d (para x necessário) ou a produção x (para produção líquida e mão de obra).");
    if (hasD) body.d = d.read();
    if (hasX) body.x = x.read();
    // a mão de obra só existe com x; sem x, os demais cálculos seguem e o aviso aparece abaixo
    if (hasL && hasX) body.L = L.read();
    const res = await ctx.call("leontief", body);
    const blocks = [];
    if (res.A) blocks.push(valueBlock("A = Z·diag(X)⁻¹", res.A, "mat", { rowLabels: SECTORS, colLabels: SECTORS, use: { tool: "leontief", prefill: { A: res.A } } }));
    if (res.x_required) blocks.push(valueBlock("x necessário, (I − A)·x = d", res.x_required, "vec", { labels: SECTORS, use: { tool: "leontief", prefill: { x: res.x_required } } }));
    if (res.net) blocks.push(valueBlock("produção líquida (I − A)·x", res.net, "vec", { labels: SECTORS }));
    if (res.labor !== undefined) blocks.push(valueBlock("mão de obra L·x", res.labor, "num"));
    const notes = hasL && !hasX ? [h("p", { class: "calc-note typed" }, "A mão de obra L·x não foi calculada: informe a produção x.")] : [];
    finish(out, ctx, "leontief", blocks, notes);
  }
  const run1 = runBtn("Calcular", run, out);
  sync();

  return {
    el: panelEl("leontief", "Modelo de Leontief",
      "Produção de três setores: x = A·x + d, ou (I − A)·x = d. A técnica é A = Z·diag(X)⁻¹, em que Z são as transações e X a produção total. Preencha só o que quiser calcular.",
      sec("Matriz técnica", null, run1.go, src.el, zxBox, aBox),
      sec("Demanda e produção", "d: demanda final, para obter x necessário. x: produção bruta, para obter a produção líquida (I − A)·x e a mão de obra L·x.", run1.go,
        h("div", { class: "calc-cols" }, d.el, x.el, L.el),
        h("div", { class: "calc-actions" }, run1.el)),
      sec("Resultado", null, null, out)),
    prefill(p) {
      if (p.Z) Z.setNumbers(p.Z);
      if (p.X) X.setNumbers(p.X);
      if (p.A) A.setNumbers(p.A);
      if (p.d) d.setNumbers(p.d);
      if (p.x) x.setNumbers(p.x);
      if (p.L) L.setNumbers(p.L);
      src.set(p.A && !p.Z ? "a" : "zx");
      sync();
    },
  };
}

/* ---------- 04 Markov ---------- */
function markovPanel(ctx) {
  const seqTA = h("textarea", { class: "calc-ta mono", rows: 3, spellcheck: "false", "aria-label": "sequência observada do clima", placeholder: "limpo, chuva, tempestade, chuva … (ou 0, 1, 2)" });
  const src = radios("fonte de P", [["seq", "estimar P pela sequência"], ["P", "usar a matriz P abaixo"]], "seq");
  const out = h("div", { class: "calc-out", "aria-live": "polite" });
  const stateSel = h("select", { class: "calc-select mono", "aria-label": "estado atual" });
  const kIn = inputEl("1", "calc-input mono", { inputmode: "numeric", "aria-label": "passos k" });

  function refreshStates() {
    const n = P.size().rows;
    const cur = Math.min(Number(stateSel.value) || 0, n - 1);
    stateSel.replaceChildren(...labelsFor(n).map((l, i) => h("option", { value: String(i) }, l)));
    stateSel.value = String(cur);
  }

  const P = matrixEditor({
    title: "P (linhas: de · colunas: para)", rows: 3, cols: 3,
    rowLabel: (i, n) => labelsFor(n)[i],
    colLabel: (j, n) => labelsFor(n)[j],
    onResize: () => refreshStates(),
  });
  P.setNumbers([[0.7, 0.2, 0.1], [0.3, 0.5, 0.2], [0.2, 0.3, 0.5]]);
  refreshStates();
  const pBox = h("div", {}, P.el);

  function sync() { pBox.hidden = src.get() !== "P"; }
  src.onChange(sync);

  async function run() {
    const body = {};
    if (src.get() === "seq") body.sequence = parseSeq(seqTA.value);
    else body.P = P.read();
    body.state = Number(stateSel.value);
    body.k = intOf(kIn.value, "passos k");
    const res = await ctx.call("markov", body);
    const Pm = res.P_estimated || body.P;
    const names = Pm ? labelsFor(Pm.length) : STATES;
    const blocks = [];
    if (res.P_estimated) {
      P.setNumbers(res.P_estimated);
      blocks.push(valueBlock("P estimada", res.P_estimated, "mat", { rowLabels: names, colLabels: names, use: { tool: "markov", prefill: { P: res.P_estimated } } }));
    }
    if (res.forecast) {
      blocks.push(barsBlock(`previsão: a partir de ${names[body.state] ?? body.state}, após ${body.k} passo(s)`, res.forecast, names));
    }
    if (res.stationary) blocks.push(valueBlock("estacionário π", res.stationary, "vec", { labels: names }));
    else if (res.stationary === null) blocks.push(block("estacionário", h("p", { class: "calc-note typed" }, "A cadeia não tem distribuição estacionária única."), ["estacionário: não há distribuição única"], "não há distribuição única"));
    const extra = [];
    if (Pm) {
      const dg = h("figure", { class: "calc-dg" }, h("figcaption", { class: "calc-dg__cap typed" }, "diagrama de estados: espessura proporcional à probabilidade"));
      const svgBox = h("div", { class: "calc-dg__box" });
      svgBox.innerHTML = markovSVG(Pm, names);
      dg.append(svgBox);
      extra.push(dg);
    }
    finish(out, ctx, "markov", blocks, extra);
  }
  const run1 = runBtn("Calcular", run, out);
  sync();

  return {
    el: panelEl("markov", "Cadeias de Markov (clima)",
      "Clima como cadeia de Markov: a probabilidade do próximo estado depende só do atual. P estimada = contagem das transições ÷ total de cada linha.",
      sec("Sequência observada", "Diário meteorológico em ordem, separado por vírgula, espaço ou quebra de linha. Aceita nomes ou 0, 1, 2.", run1.go,
        field("sequência", seqTA)),
      sec("Matriz de transição", null, run1.go, src.el, pBox),
      sec("Previsão", "Distribuição após k passos, a partir do estado atual: linha de P^k.", run1.go,
        h("div", { class: "calc-cols" }, field("estado atual", stateSel), field("passos k", kIn)),
        h("div", { class: "calc-actions" }, run1.el)),
      sec("Resultado", null, null, out)),
    prefill(p) {
      if (p.sequence) seqTA.value = p.sequence.join(", ");
      if (p.P) P.setNumbers(p.P);
      if (p.state !== undefined) {
        const idx = typeof p.state === "number" ? p.state : labelsFor(P.size().rows).indexOf(String(p.state).toLowerCase());
        if (idx >= 0) stateSel.value = String(idx);
      }
      if (p.k !== undefined) kIn.value = String(p.k);
      src.set(p.sequence ? "seq" : (p.P ? "P" : src.get()));
      sync();
    },
  };
}

/* ---------- 05 Triangulação ---------- */
function trilaterPanel(ctx) {
  let rows = [{ x: "", y: "", d: "" }, { x: "", y: "", d: "" }, { x: "", y: "", d: "" }, { x: "", y: "", d: "" }];
  const tbody = h("tbody");
  const addBtn = h("button", { class: "btn btn--small", type: "button", onclick: () => { rows.push({ x: "", y: "", d: "" }); draw(); } }, "+ estação");
  const delBtn = h("button", { class: "btn btn--small", type: "button", onclick: () => { rows.pop(); draw(); } }, "− estação");
  const readings = h("textarea", { class: "calc-ta mono", rows: 4, spellcheck: "false", "aria-label": "leituras coladas", placeholder: "Estação, x, y, distância (uma por linha). Também aceita só x, y, distância." });
  const out = h("div", { class: "calc-out", "aria-live": "polite" });

  function draw() {
    tbody.replaceChildren(...rows.map((r, i) => {
      const cellIn = (key, label) => {
        const inp = h("input", { class: "calc-cell mono", type: "text", inputmode: "decimal", autocomplete: "off", spellcheck: "false", "aria-label": `E${i + 1}, ${label}` });
        inp.value = r[key];
        inp.addEventListener("input", () => { r[key] = inp.value; });
        return h("td", {}, inp);
      };
      return h("tr", {}, h("th", { scope: "row", class: "mono" }, `E${i + 1}`), cellIn("x", "x"), cellIn("y", "y"), cellIn("d", "distância"));
    }));
    delBtn.disabled = rows.length <= 3;
  }

  const applyReadings = h("button", { class: "btn btn--small", type: "button", onclick: () => {
    try {
      rows = parseReadings(readings.value).map((r) => ({ ...r }));
      draw();
      out.replaceChildren();
    } catch (err) {
      out.replaceChildren(ticket(msgOf(err)));
    }
  } }, "aplicar leituras");

  const mapWrap = h("div", { class: "calc-map-wrap" });

  async function run() {
    const stations = rows.map((r, i) => [numOf(r.x, `x da estação E${i + 1}`), numOf(r.y, `y da estação E${i + 1}`)]);
    const distances = rows.map((r, i) => numOf(r.d, `distância da estação E${i + 1}`));
    const res = await ctx.call("trilaterate", { stations, distances });
    const cellLbl = res.grid;
    mapWrap.innerHTML = mapSVG(stations, distances, res.x, res.y);
    const gridBlock = block("quadrícula", h("span", { class: "stamp stamp--blue" }, cellLbl), [`quadrícula = ${cellLbl}`], cellLbl);
    finish(out, ctx, "trilaterate", [valueBlock("posição (x; y)", [res.x, res.y], "vec", { labels: ["x", "y"] }), gridBlock], [mapWrap]);
  }
  const run1 = runBtn("Triangular", run, out);
  draw();

  return {
    el: panelEl("trilaterate", "Triangulação por estações",
      "Cada estação mede a distância até o depósito: (x − xᵢ)² + (y − yᵢ)² = rᵢ². Subtraindo a primeira equação das outras, obtém-se um sistema linear resolvido por mínimos quadrados.",
      sec("Leituras das estações", "Coordenadas em unidades do mapa (ex.: 1200 × 800) e distâncias com ruído. Mínimo de 3 estações.", run1.go,
        h("div", { class: "calc-tbl-wrap" },
          h("table", { class: "ledger calc-st" },
            h("thead", {}, h("tr", {}, h("th", {}, "estação"), h("th", {}, "x"), h("th", {}, "y"), h("th", {}, "distância"))),
            tbody)),
        h("div", { class: "calc-actions" }, addBtn, delBtn),
        h("details", { class: "calc-paste" }, h("summary", {}, "colar leituras do Excel ou CSV"), readings, applyReadings)),
      sec("Posição", null, run1.go,
        h("div", { class: "calc-actions" }, run1.el)),
      sec("Resultado", null, null, out)),
    prefill(p) {
      if (!Array.isArray(p.stations) || !Array.isArray(p.distances)) throw calcErr("Prefill de triangulação: informe stations e distances.");
      rows = p.stations.map((s, i) => ({ x: fInput(s[0]), y: fInput(s[1]), d: fInput(p.distances[i]) }));
      draw();
    },
  };
}

/* ---------- 06 Regressão ---------- */
function regressionPanel(ctx) {
  let data = null;
  let target = null;
  const feats = new Set();
  const csvTA = h("textarea", { class: "calc-ta mono", rows: 4, spellcheck: "false", "aria-label": "dados em CSV", placeholder: "cabeçalho na 1ª linha; separador ; , ou tab\nex.: racao;propaganda;delta_moral\n0;2;1,5" });
  const info = h("p", { class: "calc-expl typed", "aria-live": "polite" }, "Nenhum dado carregado.");
  const preview = h("div", { class: "calc-tbl-wrap" });
  const targetBox = h("div", { class: "calc-radios calc-vars", role: "radiogroup", "aria-label": "variável alvo" });
  const featBox = h("div", { class: "calc-radios calc-vars", role: "group", "aria-label": "variáveis explicativas" });
  const out = h("div", { class: "calc-out", "aria-live": "polite" });

  function renderPreview() {
    if (!data) { preview.replaceChildren(); return; }
    const shown = data.rows.slice(0, 6);
    preview.replaceChildren(h("table", { class: "ledger" },
      h("thead", {}, h("tr", {}, data.cols.map((c) => h("th", {}, c)))),
      h("tbody", {}, shown.map((r) => h("tr", {}, data.cols.map((c) => h("td", { class: "mono" }, f4(r[c]))))))));
  }

  function renderVars() {
    if (!data) { targetBox.replaceChildren(); featBox.replaceChildren(); return; }
    if (!data.cols.includes(target)) target = data.cols[data.cols.length - 1];
    feats.delete(target);
    const gname = uid("alvo");
    targetBox.replaceChildren(...data.cols.map((c) => {
      const inp = h("input", { type: "radio", name: gname, value: c });
      inp.checked = c === target;
      inp.addEventListener("change", () => {
        if (target) feats.add(target);
        target = c;
        feats.delete(c);
        renderVars();
      });
      return h("label", { class: "calc-radio" }, inp, c);
    }));
    featBox.replaceChildren(...data.cols.filter((c) => c !== target).map((c) => {
      const inp = h("input", { type: "checkbox", value: c });
      inp.checked = feats.has(c);
      inp.addEventListener("change", () => { if (inp.checked) feats.add(c); else feats.delete(c); });
      return h("label", { class: "calc-radio" }, inp, c);
    }));
  }

  function setData(d, tgt) {
    data = d;
    target = tgt && d.cols.includes(tgt) ? tgt : d.cols[d.cols.length - 1];
    feats.clear();
    d.cols.filter((c) => c !== target).forEach((c) => feats.add(c));
    info.textContent = `${d.rows.length} observações; variáveis numéricas: ${d.cols.join(", ")}.`
      + (d.ignored.length ? ` Ignoradas (não numéricas): ${d.ignored.join(", ")}.` : "");
    renderPreview();
    renderVars();
  }

  const loadBtn = h("button", { class: "btn btn--small", type: "button", onclick: () => {
    try { setData(dataFromCSV(csvTA.value)); out.replaceChildren(); } catch (err) { out.replaceChildren(ticket(msgOf(err))); }
  } }, "ler dados");

  async function run() {
    if (!data) throw calcErr("Cole os dados em CSV e clique em ler dados antes de estimar.");
    const fl = data.cols.filter((c) => c !== target && feats.has(c));
    if (!fl.length) throw calcErr("Marque ao menos uma variável explicativa.");
    const rows = data.rows.map((r) => Object.fromEntries([...fl, target].map((k) => [k, r[k]])));
    const res = await ctx.call("regression", { rows, target, features: fl });
    const coefs = Object.entries(res.coefficients);
    const tbl = h("table", { class: "ledger" },
      h("thead", {}, h("tr", {}, h("th", {}, "variável"), h("th", {}, "β"))),
      h("tbody", {}, coefs.map(([k, v]) => h("tr", {}, h("td", {}, k), h("td", { class: "mono" }, f4(v))))));
    const coefBlock = block("coeficientes", tbl, coefs.map(([k, v]) => `${k} = ${f4(v)}`), coefs.map(([k, v]) => `${k}\t${f4(v)}`).join("\n"));
    const notes = fl.map((f) => {
      const beta = res.coefficients[f];
      return h("p", { class: "calc-note typed" }, `Cada unidade a mais de ${f} muda ${target} em ${f4(beta)}, mantidas as demais variáveis.`);
    });
    const r2Block = valueBlock("R²", res.r2, "num");
    finish(out, ctx, "regression", [coefBlock, r2Block], notes);
  }
  const run1 = runBtn("Estimar", run, out);

  return {
    el: panelEl("regression", "Regressão linear múltipla",
      "Mínimos quadrados: y ≈ β₀ + β₁·x₁ + … . Cada β mostra o efeito de uma variável sobre o alvo, mantidas as outras constantes.",
      sec("Dados", "Cole o CSV com cabeçalho na primeira linha. Só as colunas numéricas são usadas.", null,
        field("dados (CSV)", csvTA),
        h("div", { class: "calc-actions" }, loadBtn),
        info, preview),
      sec("Variáveis", null, run1.go,
        h("div", { class: "calc-cols" },
          h("div", {}, h("span", { class: "calc-field__lbl" }, "alvo (y)"), targetBox),
          h("div", {}, h("span", { class: "calc-field__lbl" }, "explicativas (x)"), featBox)),
        h("div", { class: "calc-actions" }, run1.el)),
      sec("Resultado", null, null, out)),
    prefill(p) {
      let d;
      if (Array.isArray(p.rows)) d = dataFromRows(p.rows);
      else if (p.csv != null) d = dataFromCSV(String(p.csv));
      else return;
      csvTA.value = p.csv != null ? String(p.csv) : csvTA.value;
      setData(d, p.target);
      if (Array.isArray(p.features)) {
        feats.clear();
        p.features.filter((f) => f !== target && d.cols.includes(f)).forEach((f) => feats.add(f));
        renderVars();
      }
    },
  };
}

/* ---------- 07 Lanchester ---------- */
function lanchesterPanel(ctx) {
  const LABELS = {
    A0: "A₀ (forças do atacante)",
    B0: "B₀ (forças do defensor)",
    alpha: "α (eficácia do atacante)",
    beta: "β (eficácia do defensor)",
    T: "T (duração do combate)",
  };
  const DEF = { A0: "100", B0: "80", alpha: "0,6", beta: "0,5", T: "0,9" };
  const inputs = Object.fromEntries(Object.keys(LABELS).map((k) => [k, inputEl(DEF[k], "calc-input mono", { inputmode: "decimal", "aria-label": LABELS[k] })]));
  const out = h("div", { class: "calc-out", "aria-live": "polite" });

  async function run() {
    const v = Object.fromEntries(Object.keys(LABELS).map((k) => [k, numOf(inputs[k].value, LABELS[k])]));
    const res = await ctx.call("lanchester", v);
    const w = res.winner;
    const verdict = w === "attacker" ? "Atacante (A) vence: B zera antes de T"
      : w === "defender" ? "Defensor (B) segura: A zera antes de T"
        : "Sem vencedor até T: as duas forças sobrevivem";
    const stampCls = w === "attacker" ? "stamp stamp--blue" : w === "defender" ? "stamp stamp--red" : "stamp stamp--ink";
    const verdictEl = h("div", { class: "calc-verdict" }, h("span", { class: stampCls }, verdict));
    const chart = h("div", { class: "calc-plot" });
    chart.innerHTML = lanchesterSVG(res.trajectory, v.A0, v.B0, res.t_end);
    const blocks = [
      valueBlock("A no fim do combate", res.a_final, "num"),
      valueBlock("B no fim do combate", res.b_final, "num"),
      valueBlock("instante de término (t)", res.t_end, "num"),
    ];
    finish(out, ctx, "lanchester", blocks, [verdictEl, chart]);
  }
  const run1 = runBtn("Simular", run, out);

  return {
    el: panelEl("lanchester", "Lei quadrática de Lanchester",
      "A′ = −β·B e B′ = −α·A durante T. Para no instante em que um lado zera. α é a eficácia do atacante A; β, a do defensor B.",
      sec("Parâmetros", null, run1.go,
        h("div", { class: "calc-cols calc-cols--5" }, ...Object.keys(LABELS).map((k) => field(LABELS[k], inputs[k]))),
        h("div", { class: "calc-actions" }, run1.el)),
      sec("Resultado", null, null, out)),
    prefill(p) {
      for (const k of Object.keys(LABELS)) {
        if (p[k] !== undefined && p[k] !== null) inputs[k].value = fInput(Number(p[k]));
      }
    },
  };
}

/* ============================================================ montagem */
function ensureCss() {
  const has = [...document.querySelectorAll('link[rel="stylesheet"]')]
    .some((l) => (l.getAttribute("href") || "").split("?")[0].endsWith("calc.css"));
  if (!has) document.head.append(h("link", { rel: "stylesheet", href: CSS_URL }));
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = h("textarea", { style: "position:fixed;opacity:0" }, text);
    document.body.append(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}

function flash(btn, text) {
  const old = btn.textContent;
  btn.textContent = text;
  setTimeout(() => { btn.textContent = old; }, 1400);
}

/**
 * Monta a gaveta da Mesa de Cálculo dentro de containerEl (fixo no rodapé).
 * Devolve {open(tool, prefill?), toggle(), close(), isOpen()}.
 */
export function mountCalc(containerEl) {
  if (!containerEl) throw new Error("mountCalc: contêiner ausente");
  if (containerEl.__calc) return containerEl.__calc;
  ensureCss();
  containerEl.classList.add("calc-drawer");
  containerEl.replaceChildren();
  containerEl.setAttribute("role", "region");
  containerEl.setAttribute("aria-label", "Mesa de cálculo");

  const bodyId = uid("calc-body");
  let current = "matrix";
  let isOpen = false;
  const tapeItems = [];

  /* alça */
  const toggleBtn = h("button", { class: "btn btn--brass calc-handle__btn", type: "button", "aria-expanded": "false", "aria-controls": bodyId }, "MESA DE CÁLCULO");
  const grip = h("div", {
    class: "calc-grip", role: "separator", tabindex: "0", "aria-orientation": "horizontal",
    "aria-label": "Altura da mesa de cálculo: arraste, ou use as setas para cima e para baixo", title: "Arraste para ajustar a altura",
  }, h("i"), h("i"), h("i"));
  const statusEl = h("span", { class: "calc-handle__status mono", "aria-live": "polite" }, "fita vazia");
  const handle = h("div", { class: "calc-handle" }, toggleBtn, grip, statusEl);

  /* índice (gavetinhas) */
  const indexBtns = {};
  const nav = h("nav", { class: "calc-index", "aria-label": "Ferramentas" }, TOOLS.map((t, i) => {
    const b = h("button", { class: "calc-index__tab", type: "button", "data-tool": t, onclick: () => select(t) },
      h("span", { class: "calc-index__n mono" }, String(i + 1).padStart(2, "0")),
      h("span", { class: "calc-index__name" }, TOOL_LABEL[t]));
    indexBtns[t] = b;
    return b;
  }));

  /* painéis */
  const ctx = {
    call: (tool, body) => api.tool(tool, body),
    tape: (item) => addTape(item),
    open: (tool, prefill) => open(tool, prefill),
  };
  const panels = {
    matrix: matrixPanel(ctx),
    hill: hillPanel(ctx),
    leontief: leontiefPanel(ctx),
    markov: markovPanel(ctx),
    trilaterate: trilaterPanel(ctx),
    regression: regressionPanel(ctx),
    lanchester: lanchesterPanel(ctx),
  };
  const bench = h("main", { class: "calc-bench" }, TOOLS.map((t) => panels[t].el));

  /* fita de resultados */
  const tapeList = h("ol", { class: "calc-tape__list", "aria-live": "polite" });
  const tapeEmpty = h("p", { class: "calc-tape__empty typed" }, "A fita está vazia. Cada resultado imprime uma linha aqui.");
  const tape = h("aside", { class: "calc-tape", "aria-label": "Fita de resultados" },
    h("h3", { class: "calc-tape__head stencil" }, "Fita de resultados"),
    tapeEmpty,
    tapeList);

  const body = h("div", { class: "calc-body", id: bodyId }, nav, bench, tape);
  containerEl.append(handle, body);

  function itemNode(item) {
    const copyB = h("button", { class: "btn btn--small", type: "button", onclick: async () => {
      const ok = await copyText(item.copy ?? item.lines.join("\n"));
      flash(copyB, ok ? "copiado" : "não copiou");
    } }, "copiar");
    const useB = item.use
      ? h("button", { class: "btn btn--small", type: "button", onclick: () => open(item.use.tool, item.use.prefill) }, "usar como entrada")
      : null;
    return h("li", { class: "calc-tape__item" },
      h("div", { class: "calc-tape__title stencil" }, item.title),
      h("pre", { class: "calc-tape__lines mono" }, item.lines.join("\n")),
      h("div", { class: "calc-tape__acts" }, copyB, useB));
  }

  function addTape(item) {
    tapeItems.push(item);
    tapeList.append(itemNode(item));
    if (tapeItems.length > TAPE_MAX) {
      tapeItems.shift();
      tapeList.firstElementChild?.remove();
    }
    tapeEmpty.hidden = true;
    const n = tapeItems.length;
    statusEl.textContent = `${n} ${n === 1 ? "linha" : "linhas"} na fita`;
    tape.scrollTop = tape.scrollHeight;
  }

  function select(tool) {
    if (!TOOLS.includes(tool)) return;
    current = tool;
    for (const t of TOOLS) {
      panels[t].el.hidden = t !== tool;
      indexBtns[t].setAttribute("aria-current", t === tool ? "true" : "false");
    }
  }

  function open(tool, prefill) {
    if (TOOLS.includes(tool)) select(tool);
    if (prefill && typeof prefill === "object") {
      try {
        panels[current].prefill(prefill);
      } catch (err) {
        console.error(err);
        const msg = msgOf(err);
        const target = panels[current].el.querySelector(".calc-out");
        if (target) target.replaceChildren(ticket(msg));
      }
    }
    isOpen = true;
    containerEl.classList.add("is-open");
    toggleBtn.setAttribute("aria-expanded", "true");
    body.removeAttribute("inert");
  }

  function close() {
    if (!isOpen) return;
    isOpen = false;
    containerEl.classList.remove("is-open");
    toggleBtn.setAttribute("aria-expanded", "false");
    body.setAttribute("inert", "");
    if (body.contains(document.activeElement)) toggleBtn.focus({ preventScroll: true });
  }

  function toggle() {
    if (isOpen) close();
    else open();
  }

  /* altura: arraste ou setas na alça */
  const HKEY = HEIGHT_KEY;
  function setHeight(px) {
    const max = Math.max(220, window.innerHeight - 48);
    const H = Math.round(Math.max(220, Math.min(max, px)));
    containerEl.style.setProperty("--calc-h", `${H}px`);
    grip.setAttribute("aria-valuenow", String(H));
    return H;
  }
  function saveHeight() {
    try { localStorage.setItem(HKEY, String(Math.round(containerEl.getBoundingClientRect().height))); } catch { /* sem armazenamento */ }
  }
  try {
    const saved = Number(localStorage.getItem(HKEY));
    if (saved > 0) setHeight(saved);
    else setHeight(window.innerHeight * 0.55);
  } catch {
    setHeight(window.innerHeight * 0.55);
  }
  grip.setAttribute("aria-valuemin", "220");

  let dragging = false;
  grip.addEventListener("pointerdown", (e) => {
    dragging = true;
    grip.setPointerCapture(e.pointerId);
    e.preventDefault();
  });
  grip.addEventListener("pointermove", (e) => {
    if (dragging) setHeight(window.innerHeight - e.clientY);
  });
  const endDrag = () => { if (dragging) { dragging = false; saveHeight(); } };
  grip.addEventListener("pointerup", endDrag);
  grip.addEventListener("pointercancel", endDrag);
  grip.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
    e.preventDefault();
    const cur = containerEl.getBoundingClientRect().height;
    setHeight(cur + (e.key === "ArrowUp" ? 40 : -40));
    saveHeight();
  });

  toggleBtn.addEventListener("click", toggle);
  containerEl.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen) {
      e.stopPropagation();
      close();
    }
  });
  nav.addEventListener("keydown", (e) => {
    const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const j = (TOOLS.indexOf(current) + step + TOOLS.length) % TOOLS.length;
    select(TOOLS[j]);
    indexBtns[TOOLS[j]].focus();
  });

  select(current);
  body.setAttribute("inert", "");

  const calc = {
    open,
    toggle,
    close,
    isOpen: () => isOpen,
  };
  containerEl.__calc = calc;
  return calc;
}
