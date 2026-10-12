/* =====================================================================
   map.js — a CARTA do Continente de Lebesgue (renderizador SVG compartilhado)
   Usado pelo Teatro (projetor) e pelo Quartel-General de cada nação.
   Requer web/css/map.css (e base.css/fonts.css na página).
   ---------------------------------------------------------------------
   import { renderMap, updateMap } from "./map.js";

   const ctrl = renderMap(svgEl, mapData, options);
     svgEl    <svg> vazio (o renderizador define viewBox e conteúdo)
     mapData  resposta de GET /api/public/map  (CONTRATO §2)
     options  {
       mode:        "public" | "faction"    (padrão "public")
                    public  -> só os donos (cores); sem contadores
                    faction -> fichas de tropa: exatas (visibility own/revealed),
                               faixa "6–10" (adjacent), névoa de hachura a lápis (hidden)
       interactive: true|false  (padrão true) — territórios clicáveis/focáveis
       showIds:     mostra "T07" sob o nome (padrão: mode === "faction")
       factions:    [{id,color,short,name}] — cores/nomes (senão vêm de update() ou do padrão)
       myFaction:   "GAU" — destaca o contorno da própria nação (modo faction)
     }

   Controlador devolvido:
     ctrl.update(stateLike)     stateLike = resposta de /api/public/state OU /api/faction/state:
                                { territories:[{id, owner, troops, troops_range, visibility}],
                                  factions?:[...] | faction?:{...} }.
                                Durante uma animação, a atualização fica pendente e é aplicada ao fim.
     ctrl.setSelection(ids)     realça territórios (marca-texto amarelo + contorno a tinta)
     ctrl.setOrders(moves)      desenha ordens planejadas [{from,to,troops}] (setas azuis a lápis)
     ctrl.animateResolution(report, opts) -> Promise
                                report = last_resolution: {turn, battles:[{from,to,attacker,defender,
                                att_before,def_before,att_after,def_after,result}], moves:[{from,to,faction,troops}]}
                                opts: {revert:false,   // true: antes de animar, devolve aos donos antigos
                                                       // os territórios "captured" (usado em replay)
                                       speed:1,        // multiplicador de velocidade
                                       onStep(info)}   // {kind:"battle"|"moves"|"done", index,total,battle,
                                                       //  fromName,toName,attackerName,defenderName,captured}
     ctrl.skipAnimation()       encerra a animação em curso
     ctrl.onTerritoryClick(cb)  cb(id, MouseEvent|KeyboardEvent)
     ctrl.onTerritoryHover(cb)  cb(id|null, MouseEvent)
     ctrl.setOwner(id, fid)     troca o dono (com transição de cor)
     ctrl.getOwner(id)  ctrl.centroid(id)  ctrl.territory(id)  ctrl.gridLabel(x,y)
     ctrl.isAnimating
     ctrl.destroy()
   updateMap(state) atualiza o último mapa criado (atalho do CONTRATO §6).
   Convenções: viewBox "-52 -52 1304 1010"; coordenadas do mapa 0..1200 × 0..800.
   ===================================================================== */

const NS = "http://www.w3.org/2000/svg";
export const VIEWBOX = { x: -52, y: -52, w: 1304, h: 1010 };

const DEFAULT_FACTIONS = {
  GAU: { id: "GAU", color: "#2b4a74", short: "Gáussia", name: "República de Gáussia" },
  EUL: { id: "EUL", color: "#8c2f23", short: "Eulerândia", name: "Império de Eulerândia" },
  HIL: { id: "HIL", color: "#4d5b24", short: "Hilbertânia", name: "Federação de Hilbertânia" },
  NOE: { id: "NOE", color: "#a87a1c", short: "Noethéria", name: "Reino de Noethéria" },
  CAU: { id: "CAU", color: "#5b3a6b", short: "Cauchýria", name: "Principado de Cauchýria" },
  RIE: { id: "RIE", color: "#3b5b5a", short: "Riemânnia", name: "Confederação de Riemânnia" },
};
const NEUTRAL_COLOR = "#8f866e";
const NEUTRAL_BY_TERRAIN = {
  planicie: "#c9b878", floresta: "#8fa06a", montanha: "#a99a7e", pantano: "#92ab94", urbano: "#bba98a",
};

/* paleta da carta */
const C = {
  paper: "#e9dfc5", land: "#f1e8d0", sea: "#b4c6c8", seaLight: "#d6e1dd", seaLine: "#58798a",
  ink: "#2a241a", inkSoft: "#4b402c", river: "#3f7089", relief: "#6a4e33", grid: "rgba(70,52,34,.2)",
  grease: "#b3261e", pencil: "#3c3a36", blue: "#24406b", red: "#a3271c", tree: "#4a6a40",
};

let lastCtrl = null;
export function updateMap(state) { if (lastCtrl) lastCtrl.update(state); }

/* ----------------------------------------------------------- utilitários */
function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  if (attrs) for (const k in attrs) { const v = attrs[k]; if (v !== undefined && v !== null) e.setAttribute(k, v); }
  if (parent) parent.appendChild(e);
  return e;
}
const f1 = (n) => (Math.round(n * 10) / 10).toString();

function hexRgb(h) {
  const m = /^#?([0-9a-f]{6})$/i.exec(h);
  if (!m) return [143, 134, 110];
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function mix(a, b, t) {
  const A = hexRgb(a), B = hexRgb(b);
  const c = A.map((v, i) => Math.round(v + (B[i] - v) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function hashStr(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

function pip(pt, poly) {
  let inside = false;
  const [x, y] = pt;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function bbox(poly) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (const [x, y] of poly) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  return { x0, y0, x1, y1 };
}
function polyD(poly, close = true) {
  let d = "";
  for (let i = 0; i < poly.length; i++) d += (i ? "L" : "M") + f1(poly[i][0]) + " " + f1(poly[i][1]);
  return d + (close ? "Z" : "");
}
/** Suaviza uma polilinha com curvas quadráticas pelos pontos médios. */
function smoothD(pts, closed = false) {
  if (pts.length < 3) return polyD(pts, false);
  let d = `M${f1(pts[0][0])} ${f1(pts[0][1])}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const mx = (pts[i][0] + pts[i + 1][0]) / 2, my = (pts[i][1] + pts[i + 1][1]) / 2;
    d += `Q${f1(pts[i][0])} ${f1(pts[i][1])} ${f1(mx)} ${f1(my)}`;
  }
  const l = pts[pts.length - 1];
  d += `L${f1(l[0])} ${f1(l[1])}`;
  return closed ? d + "Z" : d;
}

/** Encadeia segmentos [[a,b],...] em polilinhas contínuas (para o tracejado não reiniciar a cada trecho). */
function chainSegments(segs) {
  const key = (p) => p[0] + "," + p[1];
  const adj = new Map();
  segs.forEach((s, i) => {
    for (const p of s) { const k = key(p); if (!adj.has(k)) adj.set(k, []); adj.get(k).push(i); }
  });
  const used = new Array(segs.length).fill(false);
  const chains = [];
  const walk = (start, from) => {
    const out = [];
    let cur = from;
    for (;;) {
      const cand = (adj.get(key(cur)) || []).find((i) => !used[i]);
      if (cand === undefined) break;
      used[cand] = true;
      const s = segs[cand];
      const next = key(s[0]) === key(cur) ? s[1] : s[0];
      out.push(next);
      cur = next;
    }
    return out;
  };
  for (let i = 0; i < segs.length; i++) {
    if (used[i]) continue;
    used[i] = true;
    const [a, b] = segs[i];
    const fwd = walk(i, b);
    const back = walk(i, a);
    chains.push([...back.reverse(), a, b, ...fwd]);
  }
  return chains;
}

function wrapName(name, max = 11) {
  const words = name.split(" ");
  const lines = [];
  let cur = "";
  for (const w of words) {
    if (!cur) cur = w;
    else if ((cur + " " + w).length <= max) cur += " " + w;
    else { lines.push(cur); cur = w; }
  }
  if (cur) lines.push(cur);
  return lines;
}

const reduceMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ========================================================================
   renderMap
   ======================================================================== */
export function renderMap(svg, map, options = {}) {
  const mode = options.mode || "public";
  const interactive = options.interactive !== false;
  const showIds = options.showIds !== undefined ? options.showIds : mode === "faction";
  const W = map.width || 1200, H = map.height || 800;
  const cell = (map.grid && map.grid.cell) || 50;
  const cols = (map.grid && map.grid.cols) || "ABCDEFGHIJKLMNOPQRSTUVWX";
  const rows = (map.grid && map.grid.rows) || 16;

  svg.setAttribute("viewBox", `${VIEWBOX.x} ${VIEWBOX.y} ${VIEWBOX.w} ${VIEWBOX.h}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.classList.add("carta");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Carta do Continente de Lebesgue");
  svg.replaceChildren();

  /* dados ---------------------------------------------------------------- */
  const T = {};
  for (const t of map.territories) T[t.id] = t;
  const factions = {};
  for (const k in DEFAULT_FACTIONS) factions[k] = { ...DEFAULT_FACTIONS[k] };
  for (const f of options.factions || []) factions[f.id] = { ...(factions[f.id] || {}), ...f };
  const owner = {}; // id -> fid | null
  const vis = {};   // id -> own|adjacent|revealed|hidden|public
  const troops = {};
  const ranges = {};
  for (const t of map.territories) { owner[t.id] = null; vis[t.id] = "public"; }
  const colorOf = (fid) => (fid && factions[fid] ? factions[fid].color : NEUTRAL_COLOR);
  const nameOf = (fid) => (fid && factions[fid] ? factions[fid].short || factions[fid].name || fid : "Neutros");
  const seaPath = {};
  for (const r of map.sea_routes || []) { seaPath[r.a + ">" + r.b] = r.path; seaPath[r.b + ">" + r.a] = r.path.slice().reverse(); }

  /* defs ----------------------------------------------------------------- */
  const defs = el("defs", null, svg);
  const noiseURI = "data:image/svg+xml;utf8," + encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='3' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 .2  0 0 0 0 .13  0 0 0 0 .05  0 0 0 .6 0'/></filter><rect width='100%' height='100%' filter='url(#n)'/></svg>");
  const fiberURI = "data:image/svg+xml;utf8," + encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' width='360' height='360'><filter id='f'><feTurbulence type='fractalNoise' baseFrequency='.012 .11' numOctaves='2' seed='11'/><feColorMatrix values='0 0 0 0 .4  0 0 0 0 .3  0 0 0 0 .16  0 0 0 .3 0'/></filter><rect width='100%' height='100%' filter='url(#f)'/></svg>");
  const uid = Math.random().toString(36).slice(2, 7);
  const id = (s) => `${s}-${uid}`;

  const pNoise = el("pattern", { id: id("noise"), width: 240, height: 240, patternUnits: "userSpaceOnUse" }, defs);
  el("image", { href: noiseURI, width: 240, height: 240 }, pNoise);
  const pFiber = el("pattern", { id: id("fiber"), width: 360, height: 360, patternUnits: "userSpaceOnUse" }, defs);
  el("image", { href: fiberURI, width: 360, height: 360 }, pFiber);

  // aquarela: bordas irregulares + grão de papel aparecendo através do pigmento
  const fWash = el("filter", { id: id("wash"), x: "-6%", y: "-6%", width: "112%", height: "112%", "color-interpolation-filters": "sRGB" }, defs);
  el("feTurbulence", { type: "fractalNoise", baseFrequency: ".035", numOctaves: 2, seed: 4, result: "n" }, fWash);
  el("feDisplacementMap", { in: "SourceGraphic", in2: "n", scale: 6, xChannelSelector: "R", yChannelSelector: "G", result: "d" }, fWash);
  el("feTurbulence", { type: "fractalNoise", baseFrequency: ".7", numOctaves: 2, seed: 9, result: "g" }, fWash);
  el("feColorMatrix", { in: "g", type: "matrix", values: "0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -.7 1.2", result: "ga" }, fWash);
  el("feComposite", { in: "d", in2: "ga", operator: "in" }, fWash);

  // lápis-cera: leve tremor + grão de cera
  const fCray = el("filter", { id: id("crayon"), x: "-15%", y: "-35%", width: "130%", height: "170%", "color-interpolation-filters": "sRGB" }, defs);
  el("feTurbulence", { type: "fractalNoise", baseFrequency: ".05", numOctaves: 2, seed: 2, result: "n" }, fCray);
  el("feDisplacementMap", { in: "SourceGraphic", in2: "n", scale: 3.2, xChannelSelector: "R", yChannelSelector: "G", result: "d" }, fCray);
  el("feTurbulence", { type: "fractalNoise", baseFrequency: "1.1", numOctaves: 2, seed: 5, result: "g" }, fCray);
  el("feColorMatrix", { in: "g", type: "matrix", values: "0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.8 1.75", result: "ga" }, fCray);
  el("feComposite", { in: "d", in2: "ga", operator: "in" }, fCray);

  // borracha do carimbo
  const fStamp = el("filter", { id: id("stamp"), x: "-5%", y: "-10%", width: "110%", height: "120%", "color-interpolation-filters": "sRGB" }, defs);
  el("feTurbulence", { type: "fractalNoise", baseFrequency: ".9", numOctaves: 2, seed: 12, result: "g" }, fStamp);
  el("feColorMatrix", { in: "g", type: "matrix", values: "0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.1 2.0", result: "ga" }, fStamp);
  el("feComposite", { in: "SourceGraphic", in2: "ga", operator: "in" }, fStamp);

  // névoa: hachura densa a lápis em duas direções
  const pFog = el("pattern", { id: id("fog"), width: 4.4, height: 4.4, patternUnits: "userSpaceOnUse", patternTransform: "rotate(38)" }, defs);
  el("line", { x1: 0, y1: 0, x2: 0, y2: 4.4, stroke: "#3a342a", "stroke-width": 1.15, "stroke-opacity": 0.8 }, pFog);
  const pFog2 = el("pattern", { id: id("fog2"), width: 9, height: 9, patternUnits: "userSpaceOnUse", patternTransform: "rotate(-52)" }, defs);
  el("line", { x1: 0, y1: 0, x2: 0, y2: 9, stroke: "#3a342a", "stroke-width": 0.8, "stroke-opacity": 0.55 }, pFog2);

  const clipMap = el("clipPath", { id: id("clipmap") }, defs);
  el("rect", { x: 0, y: 0, width: W, height: H }, clipMap);

  /* camadas -------------------------------------------------------------- */
  const gSea = el("g", { class: "l-sea" }, svg);
  const gLand = el("g", { class: "l-land" }, svg);
  const gWash = el("g", { class: "l-wash" }, svg);
  const gFog = el("g", { class: "l-fog" }, svg);
  const gSym = el("g", { class: "l-symbols" }, svg);
  const gRiver = el("g", { class: "l-rivers" }, svg);
  const gBord = el("g", { class: "l-borders" }, svg);
  const gGrid = el("g", { class: "l-grid" }, svg);
  const gRoute = el("g", { class: "l-routes" }, svg);
  const gLabel = el("g", { class: "l-labels" }, svg);
  const gSel = el("g", { class: "l-selection" }, svg);
  const gTok = el("g", { class: "l-tokens" }, svg);
  const gOrd = el("g", { class: "l-orders" }, svg);
  const gFx = el("g", { class: "l-fx" }, svg);
  const gFrame = el("g", { class: "l-frame" }, svg);
  const gAge = el("g", { class: "l-age", "pointer-events": "none" }, svg);
  const gHit = el("g", { class: "l-hit" }, svg);

  /* ---- papel (margem) --------------------------------------------------- */
  el("rect", { x: VIEWBOX.x, y: VIEWBOX.y, width: VIEWBOX.w, height: VIEWBOX.h, fill: C.paper }, gSea);

  /* ---- mar + water-lining ----------------------------------------------- */
  const gMar = el("g", { "clip-path": `url(#${id("clipmap")})` }, gSea);
  el("rect", { x: 0, y: 0, width: W, height: H, fill: C.sea }, gMar);
  const landD = (map.land || []).map((r) => polyD(r, true)).join("");
  const LEVELS = 7;
  for (let i = LEVELS - 1; i >= 0; i--) {
    const dist = 6 + i * 6.2 + i * i * 0.5;       // distâncias crescentes à costa
    const lw = 1.25 - i * 0.1;                      // linha mais fina ao afastar-se
    const op = 0.92 - i * 0.1;                      // e mais clara
    const t = i / (LEVELS - 1);
    const band = mix(C.seaLight, C.sea, Math.pow(t, 0.75));
    const outer = i === LEVELS - 1 ? C.sea : mix(C.seaLight, C.sea, Math.pow((i + 1) / (LEVELS - 1), 0.75));
    el("path", { d: landD, fill: "none", stroke: mix(outer, C.seaLine, op), "stroke-width": f1(dist * 2 + lw), "stroke-linejoin": "round" }, gMar);
    el("path", { d: landD, fill: "none", stroke: band, "stroke-width": f1(dist * 2 - lw), "stroke-linejoin": "round" }, gMar);
  }

  /* ---- terra ------------------------------------------------------------ */
  el("path", { d: landD, fill: C.land }, gLand);

  /* ---- aquarela por território + hit areas ------------------------------ */
  const washEl = {}, hitEl = {};
  for (const t of map.territories) {
    const g = el("g", { filter: `url(#${id("wash")})`, "data-id": t.id, class: "wash" }, gWash);
    const d = polyD(t.polygon);
    const fill = el("path", { d, class: "wash-fill", "fill-opacity": 0.5 }, g);
    const edge = el("path", { d, class: "wash-edge", fill: "none", "stroke-width": 6, "stroke-opacity": 0.22, "stroke-linejoin": "round" }, g);
    washEl[t.id] = { fill, edge };
    const hit = el("path", { d, class: "hit", "data-id": t.id }, gHit);
    if (interactive) {
      hit.setAttribute("tabindex", "0");
      hit.setAttribute("role", "button");
      hit.setAttribute("aria-label", `${t.name} (${t.id})`);
    }
    hitEl[t.id] = hit;
  }

  /* ---- névoa (modo faction) --------------------------------------------- */
  const fogEl = {};
  if (mode === "faction") {
    for (const t of map.territories) {
      const gF = el("g", { class: "fog", "data-id": t.id, opacity: 0 }, gFog);
      const d = polyD(t.polygon);
      el("path", { d, fill: `url(#${id("fog")})` }, gF);
      el("path", { d, fill: `url(#${id("fog2")})` }, gF);
      fogEl[t.id] = gF;
    }
  }

  /* ---- símbolos de terreno ---------------------------------------------- */
  const labelInfo = {};
  for (const t of map.territories) {
    const lines = wrapName(t.name);
    if (showIds) lines.push(t.id);
    const lp = t.label_pos || t.centroid;
    const lh = 15.5;
    const nL = lines.length;
    const top = lp[1] - (nL * lh) / 2;
    labelInfo[t.id] = { lines, lp, lh, top, bottom: top + nL * lh + 2 };
  }
  const treeD = [], reedD = [];
  for (const t of map.territories) {
    if (t.terrain !== "floresta" && t.terrain !== "pantano") continue;
    const rnd = mulberry32(hashStr(t.id));
    const bb = bbox(t.polygon);
    const area = (bb.x1 - bb.x0) * (bb.y1 - bb.y0) * 0.6;
    const want = Math.min(26, Math.round(area / (t.terrain === "floresta" ? 1100 : 1600)));
    const li = labelInfo[t.id];
    let tries = 0, got = 0;
    const spots = [];
    while (got < want && tries++ < 400) {
      const x = bb.x0 + rnd() * (bb.x1 - bb.x0), y = bb.y0 + rnd() * (bb.y1 - bb.y0);
      if (!pip([x, y], t.polygon) || !pip([x + 7, y + 7], t.polygon) || !pip([x - 7, y + 7], t.polygon) || !pip([x + 7, y - 9], t.polygon) || !pip([x - 7, y - 9], t.polygon)) continue;
      if (Math.abs(x - li.lp[0]) < 62 && y > li.top - 22 && y < li.bottom + 34) continue;
      if (spots.some(([sx, sy]) => (sx - x) ** 2 + (sy - y) ** 2 < 24 * 24)) continue;
      spots.push([x, y]); got++;
      if (t.terrain === "floresta") {
        treeD.push(`M${f1(x - 3.6)} ${f1(y)}a3.6 3.6 0 1 0 7.2 0a3.6 3.6 0 1 0 -7.2 0M${f1(x)} ${f1(y + 3.6)}v3.4`);
      } else {
        reedD.push(`M${f1(x - 6)} ${f1(y)}h12M${f1(x - 3)} ${f1(y)}v-4M${f1(x)} ${f1(y)}v-6M${f1(x + 3)} ${f1(y)}v-4M${f1(x - 9)} ${f1(y + 3.5)}h5M${f1(x + 4)} ${f1(y + 3.5)}h5`);
      }
    }
  }
  el("path", { d: treeD.join(""), class: "sym-tree", fill: "none" }, gSym);
  el("path", { d: reedD.join(""), class: "sym-reed", fill: "none" }, gSym);
  // relevo: hachuras e curvas de nível
  const reliefHatch = [], reliefContour = [];
  for (const r of map.relief || []) {
    if (r.length > 6) reliefContour.push(smoothD(r, false));
    else reliefHatch.push(polyD(r, false));
  }
  el("path", { d: reliefContour.join(""), class: "sym-contour", fill: "none" }, gSym);
  el("path", { d: reliefHatch.join(""), class: "sym-relief", fill: "none" }, gSym);

  /* ---- rios -------------------------------------------------------------- */
  for (const r of map.rivers || []) {
    el("path", { d: smoothD(r), class: "river-bank", fill: "none" }, gRiver);
    el("path", { d: smoothD(r), class: "river", fill: "none" }, gRiver);
  }

  /* ---- fronteiras --------------------------------------------------------- */
  const pairs = new Map();
  const seen = new Map();
  for (const t of map.territories) {
    const p = t.polygon;
    for (let i = 0; i < p.length; i++) {
      const a = p[i], b = p[(i + 1) % p.length];
      const ka = a[0] + "," + a[1], kb = b[0] + "," + b[1];
      const ek = ka < kb ? ka + "|" + kb : kb + "|" + ka;
      if (seen.has(ek)) {
        const other = seen.get(ek);
        const pk = other < t.id ? other + "|" + t.id : t.id + "|" + other;
        if (!pairs.has(pk)) pairs.set(pk, { a: other < t.id ? other : t.id, b: other < t.id ? t.id : other, segs: [] });
        pairs.get(pk).segs.push([a, b]);
      } else seen.set(ek, t.id);
    }
  }
  const borderPairs = [...pairs.values()].map((pr) => ({ a: pr.a, b: pr.b, d: chainSegments(pr.segs).map((c) => polyD(c, false)).join("") }));
  const bSame = el("path", { class: "border border--prov", fill: "none" }, gBord);
  const bDiff = el("path", { class: "border border--nation", fill: "none" }, gBord);
  const coastLine = el("path", { d: landD, class: "coast", fill: "none" }, gBord);
  void coastLine;
  let myOutline = null;
  if (options.myFaction) myOutline = el("path", { class: "border border--mine", fill: "none" }, gBord);

  /* ---- quadrícula --------------------------------------------------------- */
  {
    let d = "";
    for (let x = cell; x < W; x += cell) d += `M${x} 0V${H}`;
    for (let y = cell; y < H; y += cell) d += `M0 ${y}H${W}`;
    el("path", { d, class: "grid-line", fill: "none" }, gGrid);
  }

  /* ---- rotas marítimas ---------------------------------------------------- */
  for (const r of map.sea_routes || []) {
    el("path", { d: smoothD(r.path), class: "sea-route", fill: "none" }, gRoute);
    for (const p of [r.path[0], r.path[r.path.length - 1]]) {
      const g = el("g", { transform: `translate(${f1(p[0])} ${f1(p[1])})`, class: "anchor" }, gRoute);
      el("circle", { r: 10, class: "anchor-bg" }, g);
      el("path", { d: "M0 -6.2v11.6M-3.6 -3.4h7.2M-5.6 2.2a5.6 5.6 0 0 0 11.2 0M-5.6 2.2l-1.4 -1.8M5.6 2.2l1.4 -1.8", class: "anchor-ink", fill: "none" }, g);
      el("circle", { cy: -7.4, r: 1.7, class: "anchor-ink", fill: "none" }, g);
    }
  }

  /* ---- rótulos ------------------------------------------------------------- */
  const tbox = {};
  for (const t of map.territories) tbox[t.id] = bbox(t.polygon);
  const onLand = (x, y) => {
    for (const t of map.territories) {
      const b = tbox[t.id];
      if (x < b.x0 - 6 || x > b.x1 + 6 || y < b.y0 - 6 || y > b.y1 + 6) continue;
      if (pip([x, y], t.polygon)) return true;
    }
    return false;
  };
  // um rótulo de mar nunca deve pisar em terra: procura a posição livre mais próxima
  const seaFits = (cx, cy, half, ang, wd) => {
    const a = (ang * Math.PI) / 180, ca = Math.cos(a), sa = Math.sin(a);
    for (let d = -half; d <= half; d += 10) {
      const x = cx + ca * d, y = cy + sa * d;
      if (x < 10 || x > W - 10 || y < 14 || y > H - 8) return false;
      for (const off of [-wd, wd]) if (onLand(x - sa * off, y + ca * off)) return false;
    }
    return true;
  };
  const SEA_TRIES = [[1, 1], [0.78, 1], [0.6, 0.95], [0.45, 0.88], [0.3, 0.8]]; // [espaçamento, tamanho]
  for (const l of map.labels || []) {
    const ang = l.angle || 0;
    let best = null;
    for (const [k, fs] of SEA_TRIES) {
      const half = (l.text.length * (19 * fs * 0.66 + 19 * fs * 0.26 * k)) / 2;
      const cands = [[0, 0]];
      for (let r = 10; r <= 110; r += 10) for (let q = 0; q < 16; q++) cands.push([Math.cos((q * Math.PI) / 8) * r, Math.sin((q * Math.PI) / 8) * r]);
      const hit = cands.find(([dx, dy]) => seaFits(l.pos[0] + dx, l.pos[1] + dy, half, ang, 8 * fs));
      if (hit) { best = { dx: hit[0], dy: hit[1], k, fs }; break; }
    }
    const x = l.pos[0] + (best ? best.dx : 0), y = l.pos[1] + (best ? best.dy : 0);
    const t = el("text", { x, y, class: "t-sea", "text-anchor": "middle", transform: ang ? `rotate(${ang} ${x} ${y})` : null }, gLabel);
    if (best && best.k < 1) { t.style.letterSpacing = `${(0.26 * best.k).toFixed(2)}em`; t.style.fontSize = `${(19 * best.fs).toFixed(1)}px`; }
    t.textContent = l.text;
  }
  const markerPos = {}, tokenPos = {};
  const capMarks = [];
  for (const t of map.territories) {
    const li = labelInfo[t.id];
    const tx = el("text", { x: li.lp[0], class: "t-name", "text-anchor": "middle", "data-id": t.id }, gLabel);
    li.lines.forEach((line, i) => {
      const isId = showIds && i === li.lines.length - 1;
      const ts = el("tspan", { x: li.lp[0], y: li.top + li.lh * i + 11.5, class: isId ? "t-id" : null }, tx);
      ts.textContent = line;
    });
    // posição dos símbolos: capital acima do nome; ficha de tropa abaixo
    const inside = (p, hw, hh) => pip(p, t.polygon) && pip([p[0] + hw, p[1] + hh], t.polygon) && pip([p[0] - hw, p[1] + hh], t.polygon) && pip([p[0] + hw, p[1] - hh], t.polygon) && pip([p[0] - hw, p[1] - hh], t.polygon);
    const candsTok = [[li.lp[0], li.bottom + 14], [li.lp[0], li.top - 14], [t.centroid[0], t.centroid[1]]];
    tokenPos[t.id] = candsTok.find((p) => inside(p, 26, 13)) || candsTok.find((p) => inside(p, 10, 6)) || candsTok[0];
    const candsCap = [[li.lp[0], li.top - 13], [li.lp[0], li.bottom + 14]];
    markerPos[t.id] = candsCap.find((p) => inside(p, 10, 10)) || candsCap[0];
    if (t.capital) capMarks.push(t);
  }
  const capEl = {};
  for (const t of capMarks) {
    const p = markerPos[t.id];
    const g = el("g", { transform: `translate(${f1(p[0])} ${f1(p[1])})`, class: "capital" }, gLabel);
    el("circle", { r: 11.5, class: "cap-bg" }, g);
    el("circle", { r: 11.5, class: "cap-ring", fill: "none" }, g);
    const pts = [];
    for (let i = 0; i < 10; i++) { const r = i % 2 ? 4.4 : 9.4, a = -Math.PI / 2 + (i * Math.PI) / 5; pts.push(f1(Math.cos(a) * r) + "," + f1(Math.sin(a) * r)); }
    el("polygon", { points: pts.join(" "), class: "cap-star" }, g);
    capEl[t.id] = g;
  }

  /* ---- moldura, régua, cartucho ---------------------------------------------- */
  drawFrame(gFrame, { W, H, cell, cols, rows });

  /* ---- envelhecimento do papel (por cima de tudo, sem interferir nos cliques) ---- */
  el("rect", { x: VIEWBOX.x, y: VIEWBOX.y, width: VIEWBOX.w, height: VIEWBOX.h, fill: `url(#${id("fiber")})`, opacity: 0.55 }, gAge);
  el("rect", { x: VIEWBOX.x, y: VIEWBOX.y, width: VIEWBOX.w, height: VIEWBOX.h, fill: `url(#${id("noise")})`, opacity: 0.22 }, gAge);
  // vincos de dobra
  el("path", { d: `M${W / 2} ${VIEWBOX.y}V${VIEWBOX.y + VIEWBOX.h}M${VIEWBOX.x} ${H / 2 + 40}H${VIEWBOX.x + VIEWBOX.w}`, class: "fold", fill: "none" }, gAge);
  el("path", { d: `M${W / 2 + 1.6} ${VIEWBOX.y}V${VIEWBOX.y + VIEWBOX.h}M${VIEWBOX.x} ${H / 2 + 41.6}H${VIEWBOX.x + VIEWBOX.w}`, class: "fold fold--hi", fill: "none" }, gAge);
  // manchas de umidade e cantos gastos
  const gStain = el("radialGradient", { id: id("stain"), cx: "50%", cy: "50%", r: "50%" }, defs);
  el("stop", { offset: "0", "stop-color": "#8a6a2c", "stop-opacity": 0.2 }, gStain);
  el("stop", { offset: "0.55", "stop-color": "#8a6a2c", "stop-opacity": 0.07 }, gStain);
  el("stop", { offset: "1", "stop-color": "#8a6a2c", "stop-opacity": 0 }, gStain);
  for (const [cx, cy, r] of [[-30, 20, 260], [1240, 930, 300], [1190, -20, 190], [20, 930, 220]]) {
    el("circle", { cx, cy, r, fill: `url(#${id("stain")})` }, gAge);
  }
  // anel de café discreto
  el("circle", { cx: 1010, cy: 905, r: 36, fill: "none", stroke: "#7a5226", "stroke-width": 3, opacity: 0.1 }, gAge);

  /* ------------------------------------------------------------------------
     estado dinâmico
     ------------------------------------------------------------------------ */
  let animating = false;
  let pending = null;
  let selection = [];
  let clickCb = null, hoverCb = null;

  function terrColor(tid) {
    const o = owner[tid];
    if (o) return colorOf(o);
    return NEUTRAL_BY_TERRAIN[T[tid].terrain] || NEUTRAL_COLOR;
  }

  function refreshBorders() {
    let same = "", diff = "";
    for (const p of borderPairs) {
      if ((owner[p.a] || null) === (owner[p.b] || null)) same += p.d;
      else diff += p.d;
    }
    bSame.setAttribute("d", same);
    bDiff.setAttribute("d", diff);
    if (myOutline) {
      // contorno extra, em cor da nação, nas fronteiras entre "meu" e "não meu"
      let mine = "";
      for (const p of borderPairs) {
        const am = owner[p.a] === options.myFaction, bm = owner[p.b] === options.myFaction;
        if (am !== bm) mine += p.d;
      }
      myOutline.setAttribute("d", mine);
      myOutline.setAttribute("stroke", colorOf(options.myFaction));
    }
  }

  function paintTerritory(tid) {
    const w = washEl[tid];
    const col = terrColor(tid);
    const isNeutral = !owner[tid];
    w.fill.style.fill = col;
    w.edge.style.stroke = col;
    w.fill.setAttribute("fill-opacity", isNeutral ? 0.45 : 0.62);
    w.edge.setAttribute("stroke-opacity", isNeutral ? 0.16 : 0.26);
    hitEl[tid].setAttribute("data-owner", owner[tid] || "");
    if (capEl[tid]) capEl[tid].querySelector(".cap-ring").style.stroke = owner[tid] ? colorOf(owner[tid]) : C.inkSoft;
  }

  function buildToken(tid) {
    const v = vis[tid];
    if (mode !== "faction") return null;
    const pos = tokenPos[tid];
    const o = owner[tid];
    const col = colorOf(o);
    let label = null;
    if (v === "own" || v === "revealed") label = troops[tid] != null ? String(troops[tid]) : null;
    else if (v === "adjacent") label = ranges[tid] || null;
    if (label == null) return null;
    const exact = v === "own" || v === "revealed";
    const w = Math.max(40, 31 + label.length * 9.2);
    const h = 27;
    const g = el("g", { class: `token token--${v}`, transform: `translate(${f1(pos[0])} ${f1(pos[1])})`, "data-id": tid });
    el("rect", { x: -w / 2 + 2.5, y: -h / 2 + 3, width: w, height: h, class: "tok-shadow" }, g);
    const body = el("rect", { x: -w / 2, y: -h / 2, width: w, height: h, class: "tok-body" }, g);
    if (exact) { body.style.fill = col; body.style.stroke = mix(col, "#000000", 0.35); }
    else { body.style.stroke = col; }
    // símbolo OTAN de infantaria
    const sx = -w / 2 + 6;
    const sym = el("g", { class: "tok-sym" }, g);
    el("rect", { x: sx, y: -5, width: 14, height: 10, fill: "none" }, sym);
    el("path", { d: `M${sx} -5L${sx + 14} 5M${sx + 14} -5L${sx} 5` }, sym);
    if (exact) sym.style.stroke = "#f1e8d0"; else sym.style.stroke = col;
    const tx = el("text", { x: sx + 14 + (w - 26) / 2 - 3, y: 5.5, "text-anchor": "middle", class: "tok-num" }, g);
    tx.textContent = label;
    if (exact) tx.style.fill = "#f6efd9"; else tx.style.fill = mix(col, "#000000", 0.25);
    if (v === "revealed") el("circle", { cx: w / 2 - 3, cy: -h / 2 + 3, r: 3.6, class: "tok-pin" }, g);
    return g;
  }

  function refreshTokens() {
    gTok.replaceChildren();
    if (mode !== "faction") return;
    for (const t of map.territories) {
      const g = buildToken(t.id);
      if (g) gTok.appendChild(g);
      if (fogEl[t.id]) fogEl[t.id].setAttribute("opacity", vis[t.id] === "hidden" ? 0.95 : 0);
    }
  }

  function refreshAll() {
    for (const t of map.territories) paintTerritory(t.id);
    refreshBorders();
    refreshTokens();
  }

  function applyState(state) {
    if (!state) return;
    if (Array.isArray(state.factions)) for (const f of state.factions) factions[f.id] = { ...(factions[f.id] || {}), ...f };
    if (state.faction && state.faction.id) factions[state.faction.id] = { ...(factions[state.faction.id] || {}), ...state.faction };
    for (const t of state.territories || []) {
      if (!(t.id in owner)) continue;
      owner[t.id] = t.owner || null;
      vis[t.id] = t.visibility || (mode === "faction" ? "hidden" : "public");
      troops[t.id] = t.troops != null ? t.troops : null;
      ranges[t.id] = t.troops_range || null;
    }
    refreshAll();
    setSelection(selection);
  }

  /* ---- seleção ------------------------------------------------------------- */
  function setSelection(ids) {
    selection = (ids || []).filter((x) => T[x]);
    gSel.replaceChildren();
    for (const tid of selection) {
      const d = polyD(T[tid].polygon);
      el("path", { d, class: "sel-wash" }, gSel);
      el("path", { d, class: "sel-line" }, gSel);
    }
  }

  /* ---- setas ------------------------------------------------------------------ */
  function centroid(tid) { return T[tid].centroid; }

  /** pontos da haste: reta curva (ou a rota marítima) de A a B, com tremor de mão. */
  function shaftPoints(from, to, rnd, wobble, tail = 26) {
    const A = centroid(from), B = centroid(to);
    let ctrl;
    const sea = seaPath[from + ">" + to];
    let pts;
    if (sea) {
      const raw = [A, ...sea, B];
      pts = [];
      for (let i = 0; i < raw.length - 1; i++) {
        for (let k = 0; k < 4; k++) {
          const u = k / 4;
          pts.push([raw[i][0] + (raw[i + 1][0] - raw[i][0]) * u, raw[i][1] + (raw[i + 1][1] - raw[i][1]) * u]);
        }
      }
      pts.push(B);
    } else {
      const dx = B[0] - A[0], dy = B[1] - A[1];
      const len = Math.hypot(dx, dy) || 1;
      const side = (hashStr(from + to) % 2) ? 1 : -1;
      ctrl = [(A[0] + B[0]) / 2 - (dy / len) * len * 0.1 * side, (A[1] + B[1]) / 2 + (dx / len) * len * 0.1 * side];
      pts = [];
      const n = Math.max(10, Math.round(len / 9));
      for (let i = 0; i <= n; i++) {
        const u = i / n;
        pts.push([
          (1 - u) * (1 - u) * A[0] + 2 * (1 - u) * u * ctrl[0] + u * u * B[0],
          (1 - u) * (1 - u) * A[1] + 2 * (1 - u) * u * ctrl[1] + u * u * B[1],
        ]);
      }
    }
    // recorta as pontas (não cobrir os rótulos/centros) e acrescenta tremor
    const trim = (arr, d, fromStart) => {
      const a = fromStart ? arr.slice() : arr.slice().reverse();
      let acc = 0, i = 0;
      while (i < a.length - 1 && acc < d) { acc += Math.hypot(a[i + 1][0] - a[i][0], a[i + 1][1] - a[i][1]); i++; }
      const out = a.slice(i);
      return fromStart ? out : out.reverse();
    };
    const total = pts.reduce((acc, p, i) => acc + (i ? Math.hypot(p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]) : 0), 0);
    const k = Math.min(1, (total * 0.62) / (tail + 20));
    pts = trim(trim(pts, 20 * k, true), tail * k, false);
    return pts.map((p, i) => {
      const k = i / Math.max(1, pts.length - 1);
      const w = wobble * Math.sin(k * 9 + rnd() * 1.4) + (rnd() - 0.5) * wobble * 0.8;
      const prev = pts[Math.max(0, i - 1)], next = pts[Math.min(pts.length - 1, i + 1)];
      const tx = next[0] - prev[0], ty = next[1] - prev[1], tl = Math.hypot(tx, ty) || 1;
      return [p[0] - (ty / tl) * w, p[1] + (tx / tl) * w];
    });
  }

  function arrowGeometry(from, to, wobble, seedKey, tail = 26) {
    const rnd = mulberry32(hashStr(seedKey));
    const pts = shaftPoints(from, to, rnd, wobble, tail);
    const n = pts.length;
    const e = pts[n - 1];
    const q = pts[Math.max(0, n - 4)];
    const ang = Math.atan2(e[1] - q[1], e[0] - q[0]);
    const hl = 30;
    const h1 = [e[0] - Math.cos(ang - 0.5) * hl, e[1] - Math.sin(ang - 0.5) * hl];
    const h2 = [e[0] - Math.cos(ang + 0.5) * hl, e[1] - Math.sin(ang + 0.5) * hl];
    return {
      shaft: polyD(pts, false),
      shaft2: polyD(pts.map((p) => [p[0] + (rnd() - 0.5) * 2.4, p[1] + (rnd() - 0.5) * 2.4]), false),
      head: `M${f1(h1[0])} ${f1(h1[1])}L${f1(e[0])} ${f1(e[1])}L${f1(h2[0])} ${f1(h2[1])}`,
      headFill: `M${f1(h1[0])} ${f1(h1[1])}L${f1(e[0])} ${f1(e[1])}L${f1(h2[0])} ${f1(h2[1])}L${f1((h1[0] + h2[0]) / 2 + (e[0] - (h1[0] + h2[0]) / 2) * 0.25)} ${f1((h1[1] + h2[1]) / 2 + (e[1] - (h1[1] + h2[1]) / 2) * 0.25)}Z`,
      start: pts[0], end: e, mid: pts[Math.floor(n / 2)],
    };
  }

  /* ---- ordens planejadas (setas azuis a lápis) ------------------------------------ */
  function setOrders(moves) {
    gOrd.replaceChildren();
    (moves || []).forEach((m, i) => {
      if (!T[m.from] || !T[m.to]) return;
      const g = arrowGeometry(m.from, m.to, 1.1, "ord" + m.from + m.to + i, 20);
      const grp = el("g", { class: "order" }, gOrd);
      el("path", { d: g.shaft, class: "order-shaft" }, grp);
      el("path", { d: g.headFill, class: "order-head" }, grp);
      const tag = el("g", { transform: `translate(${f1(g.start[0])} ${f1(g.start[1])})`, class: "order-tag" }, grp);
      el("circle", { r: 14 }, tag);
      const tx = el("text", { y: 5.5, "text-anchor": "middle" }, tag);
      tx.textContent = m.troops != null ? m.troops : "";
    });
  }

  /* ------------------------------------------------------------------------
     animação da resolução
     ------------------------------------------------------------------------ */
  let timeScale = 1;
  let skipping = false;
  const live = new Set();       // animações WAAPI em curso (para cancelar)
  const timers = new Set();
  let skipResolve = null;

  function wait(ms) {
    return new Promise((res) => {
      if (skipping) return res();
      const id = setTimeout(() => { timers.delete(id); res(); }, ms * timeScale);
      timers.add(id);
      const prev = skipResolve;
      skipResolve = () => { clearTimeout(id); res(); if (prev) prev(); };
    });
  }
  function anim(node, kf, opts) {
    if (skipping || !node.animate) return Promise.resolve();
    const a = node.animate(kf, { fill: "both", ...opts, duration: Math.max(1, (opts.duration || 300) * timeScale) });
    live.add(a);
    return a.finished.catch(() => {}).finally(() => live.delete(a));
  }
  const center = (node) => { node.style.transformBox = "fill-box"; node.style.transformOrigin = "center"; };

  function burstShape(rnd, R) {
    const pts = [];
    const n = 15;
    for (let i = 0; i < n * 2; i++) {
      const a = (i * Math.PI) / n + (rnd() - 0.5) * 0.12;
      const r = i % 2 ? R * (0.42 + rnd() * 0.12) : R * (0.8 + rnd() * 0.42);
      pts.push(f1(Math.cos(a) * r) + "," + f1(Math.sin(a) * r));
    }
    return pts.join(" ");
  }

  function textHalo(parent, x, y, str, cls, rot = 0) {
    const t = el("text", { x, y, class: cls, "text-anchor": "middle", transform: rot ? `rotate(${rot} ${x} ${y})` : null }, parent);
    t.textContent = str;
    return t;
  }

  function stampNode(tid, label, sub, color, scale = 1) {
    const [cx, cy] = centroid(tid);
    const outer = el("g", { transform: `translate(${f1(cx)} ${f1(cy - 4)}) rotate(${-9 + (hashStr(tid) % 7) - 3})`, class: "res-stamp" });
    const inner = el("g", { filter: `url(#${id("stamp")})` }, outer);
    center(inner);
    const w = (label.length * 24 + 38) * scale, h = (sub ? 78 : 56) * scale;
    el("rect", { x: -w / 2 - 5, y: -h / 2 - 5, width: w + 10, height: h + 10, class: "stamp-box stamp-box--bg" }, inner);
    const box = el("rect", { x: -w / 2, y: -h / 2, width: w, height: h, class: "stamp-box" }, inner);
    el("rect", { x: -w / 2 - 6, y: -h / 2 - 6, width: w + 12, height: h + 12, class: "stamp-box stamp-box--thin" }, inner);
    inner.style.color = color;
    const t1 = el("text", { x: 0, y: sub ? -2 : 13 * scale, "text-anchor": "middle", class: "stamp-text", "font-size": 42 * scale }, inner);
    t1.textContent = label;
    if (sub) { const t2 = el("text", { x: 0, y: 28 * scale, "text-anchor": "middle", class: "stamp-sub", "font-size": 17 * scale }, inner); t2.textContent = sub; }
    void box;
    return { outer, inner };
  }

  async function playBattle(b, fx, stamps, idx, total, onStep) {
    const rnd = mulberry32(hashStr(b.from + b.to + idx));
    const captured = b.result === "captured";
    const attId = b.attacker, defId = b.defender;
    const attLoss = Math.max(0, (b.att_before || 0) - (b.att_after || 0));
    const defLoss = Math.max(0, (b.def_before || 0) - (b.def_after || 0));
    const geo = arrowGeometry(b.from, b.to, 2.4, "bat" + b.from + b.to + idx, 40);
    if (onStep) onStep({
      kind: "battle", index: idx, total, battle: b, captured,
      fromName: T[b.from].name, toName: T[b.to].name,
      attackerName: nameOf(attId), defenderName: nameOf(defId),
      attLoss, defLoss,
    });

    // 1) seta de lápis-cera
    const grp = el("g", { filter: `url(#${id("crayon")})`, class: "arrow-grp" }, fx);
    const s1 = el("path", { d: geo.shaft, class: "arrow-shaft", pathLength: 1 }, grp);
    const s2 = el("path", { d: geo.shaft2, class: "arrow-shaft arrow-shaft--2", pathLength: 1 }, grp);
    const hd = el("path", { d: geo.headFill, class: "arrow-head", opacity: 0 }, grp);
    for (const p of [s1, s2]) { p.style.strokeDasharray = "1 2"; p.style.strokeDashoffset = "1.02"; }
    // número de atacantes na origem
    const tagA = el("g", { transform: `translate(${f1(geo.start[0])} ${f1(geo.start[1])})`, opacity: 0 }, fx);
    const tagAi = el("g", {}, tagA); center(tagAi);
    el("rect", { x: -22, y: -15, width: 44, height: 28, class: "arrow-tag", style: `stroke:${colorOf(attId)}` }, tagAi);
    const ta = el("text", { y: 7, "text-anchor": "middle", class: "arrow-tag-num" }, tagAi);
    ta.textContent = b.att_before != null ? b.att_before : "";
    anim(tagA, [{ opacity: 0 }, { opacity: 1 }], { duration: 160 });
    await Promise.all([
      anim(s1, [{ strokeDashoffset: 1.02 }, { strokeDashoffset: 0 }], { duration: 520, easing: "cubic-bezier(.35,.1,.3,1)" }),
      anim(s2, [{ strokeDashoffset: 1.02 }, { strokeDashoffset: 0 }], { duration: 600, easing: "cubic-bezier(.35,.1,.3,1)", delay: 50 }),
    ]);
    await anim(hd, [{ opacity: 0 }, { opacity: 1 }], { duration: 90 });

    // 2) explosão de tinta no alvo
    const [tx, ty] = centroid(b.to);
    const burst = el("g", { transform: `translate(${f1(tx)} ${f1(ty)})`, class: "burst" }, fx);
    const bi = el("g", {}, burst); center(bi);
    el("polygon", { points: burstShape(rnd, 42), class: "burst-outer" }, bi);
    el("polygon", { points: burstShape(rnd, 26), class: "burst-inner" }, bi);
    for (let i = 0; i < 7; i++) {
      const a = rnd() * Math.PI * 2, r = 50 + rnd() * 20;
      el("circle", { cx: f1(Math.cos(a) * r), cy: f1(Math.sin(a) * r), r: f1(1.8 + rnd() * 3.2), class: "burst-dot" }, bi);
    }
    if (onStep) onStep({ kind: "impact", index: idx, total, battle: b, captured });
    const popB = anim(bi, [{ transform: "scale(.15) rotate(-12deg)", opacity: 0 }, { transform: "scale(1.18) rotate(3deg)", opacity: 1, offset: 0.55 }, { transform: "scale(1) rotate(0)", opacity: 0.94 }], { duration: 320, easing: "cubic-bezier(.2,.9,.3,1)" });
    // tremor do alvo
    const shake = anim(gFx, [{ transform: "translate(0,0)" }, { transform: "translate(2.5px,-1.5px)" }, { transform: "translate(-2px,1.5px)" }, { transform: "translate(1.2px,1px)" }, { transform: "translate(0,0)" }], { duration: 240 });
    await Promise.all([popB, shake]);

    // 3) baixas
    const nums = [];
    const pushNum = (x, y, v, cls) => {
      if (!(v > 0)) return;
      const g = el("g", { transform: `translate(${f1(x)} ${f1(y)})`, class: "loss" }, fx);
      const gi = el("g", { opacity: 0 }, g); center(gi);
      textHalo(gi, 0, 0, "−" + v, cls);
      nums.push(anim(gi, [{ opacity: 0, transform: "translateY(14px) scale(.7)" }, { opacity: 1, transform: "translateY(-3px) scale(1.12)", offset: 0.7 }, { opacity: 1, transform: "translateY(0) scale(1)" }], { duration: 320, easing: "ease-out" }));
    };
    pushNum(tx, ty - 56, defLoss, "loss-num");
    pushNum(geo.start[0] - 58 * Math.sign(geo.end[0] - geo.start[0] || 1), geo.start[1] + 8, attLoss, "loss-num loss-num--att");
    await Promise.all(nums);

    // 4) carimbo + troca de dono
    let st;
    if (captured) {
      setOwner(b.to, attId);
      if (onStep) onStep({ kind: "captured", index: idx, total, battle: b });
      st = stampNode(b.to, "TOMADO", nameOf(attId).toUpperCase(), colorOf(attId));
      stamps.appendChild(st.outer);
      await anim(st.inner, [
        { transform: "scale(2.6) rotate(-10deg)", opacity: 0 },
        { transform: "scale(.93)", opacity: 0.95, offset: 0.62 },
        { transform: "scale(1.03) translate(2px,0)", opacity: 0.92, offset: 0.8 },
        { transform: "scale(1)", opacity: 0.9 },
      ], { duration: 340, easing: "cubic-bezier(.3,.2,.2,1)" });
    } else {
      st = stampNode(b.to, "REPELIDO", nameOf(defId).toUpperCase(), colorOf(defId), 0.78);
      stamps.appendChild(st.outer);
      await anim(st.inner, [
        { transform: "scale(2.2) rotate(8deg)", opacity: 0 },
        { transform: "scale(1)", opacity: 0.9 },
      ], { duration: 300, easing: "cubic-bezier(.3,.2,.2,1)" });
    }
    await wait(520);

    // limpa a batalha (a cor do território já virou)
    const gone = [grp, tagA, burst, ...fx.querySelectorAll(".loss"), st.outer];
    await Promise.all(gone.map((n) => anim(n, [{ opacity: 1 }, { opacity: 0 }], { duration: 260 })));
    for (const n of gone) n.remove();
  }

  async function playMoves(moves, fx, onStep) {
    const list = (moves || []).filter((m) => T[m.from] && T[m.to]);
    if (!list.length) return;
    if (onStep) onStep({ kind: "moves", index: 0, total: list.length, moves: list });
    const nodes = [];
    const jobs = list.map((m, i) => {
      const g = arrowGeometry(m.from, m.to, 1.2, "mv" + m.from + m.to + i, 18);
      const grp = el("g", { class: "move-grp", filter: `url(#${id("crayon")})` }, fx);
      const sh = el("path", { d: g.shaft, class: "move-shaft", pathLength: 1 }, grp);
      const hd = el("path", { d: g.headFill, class: "move-head", opacity: 0 }, grp);
      sh.style.strokeDasharray = "1 2"; sh.style.strokeDashoffset = "1.02";
      const tag = el("g", { transform: `translate(${f1(g.start[0])} ${f1(g.start[1])})`, opacity: 0 }, fx);
      el("circle", { r: 14, class: "move-tag", style: `stroke:${colorOf(m.faction)}` }, tag);
      const tx = el("text", { y: 5.5, "text-anchor": "middle", class: "move-tag-num" }, tag);
      tx.textContent = m.troops != null ? m.troops : "";
      nodes.push(grp, tag);
      return (async () => {
        await wait(i * 170);
        anim(tag, [{ opacity: 0 }, { opacity: 1 }], { duration: 160 });
        await anim(sh, [{ strokeDashoffset: 1.02 }, { strokeDashoffset: 0 }], { duration: 420, easing: "ease-out" });
        await anim(hd, [{ opacity: 0 }, { opacity: 1 }], { duration: 90 });
      })();
    });
    await Promise.all(jobs);
    await wait(1800);
    await Promise.all(nodes.map((n) => anim(n, [{ opacity: 1 }, { opacity: 0 }], { duration: 400 })));
    for (const n of nodes) n.remove();
  }

  function cancelAll() {
    skipping = true;
    for (const t of timers) clearTimeout(t);
    timers.clear();
    for (const a of live) { try { a.finish(); } catch { /* nada */ } }
    live.clear();
    if (skipResolve) { const r = skipResolve; skipResolve = null; r(); }
  }

  async function animateResolution(report, opts = {}) {
    if (animating) return;
    const battles = (report && report.battles) || [];
    const moves = (report && report.moves) || [];
    animating = true;
    skipping = false;
    skipResolve = null;
    timeScale = (opts.speed ? 1 / opts.speed : 1) * (reduceMotion() ? 0.25 : 1);
    if (opts.revert) {
      for (const b of battles) if (b.result === "captured" && T[b.to]) setOwner(b.to, b.defender || null, true);
    }
    const stamps = el("g", { class: "res-stamps" }, gFx);
    const fx = el("g", { class: "res-fx" }, gFx);
    try {
      await wait(250);
      for (let i = 0; i < battles.length; i++) {
        if (skipping) break;
        const b = battles[i];
        if (!T[b.from] || !T[b.to]) continue;
        await playBattle(b, fx, stamps, i, battles.length, opts.onStep);
      }
      if (!skipping) await playMoves(moves, fx, opts.onStep);
      if (!skipping) await wait(300);
    } finally {
      // garante dono final correto mesmo se pulou a animação
      for (const b of battles) if (b.result === "captured" && T[b.to]) setOwner(b.to, b.attacker, true);
      stamps.remove();
      fx.remove();
      gFx.replaceChildren();
      animating = false;
      skipping = false;
      if (opts.onStep) opts.onStep({ kind: "done" });
      if (pending) { const p = pending; pending = null; applyState(p); }
    }
  }

  /* ---- troca de dono ----------------------------------------------------------------- */
  function setOwner(tid, fid, instant = false) {
    if (!T[tid]) return;
    owner[tid] = fid || null;
    if (instant) {
      washEl[tid].fill.style.transition = "none";
      washEl[tid].edge.style.transition = "none";
    }
    paintTerritory(tid);
    refreshBorders();
    if (instant) requestAnimationFrame(() => { washEl[tid].fill.style.transition = ""; washEl[tid].edge.style.transition = ""; });
  }

  /* ---- interação ---------------------------------------------------------------------- */
  const hoverLine = el("path", { class: "hover-line", fill: "none", opacity: 0 }, gSel);
  void hoverLine;
  const onMove = (ev) => {
    const tid = ev.target && ev.target.getAttribute && ev.target.getAttribute("data-id");
    if (ev.target.classList && ev.target.classList.contains("hit")) {
      hoverLine.setAttribute("d", polyD(T[tid].polygon));
      hoverLine.setAttribute("opacity", 1);
      if (hoverCb) hoverCb(tid, ev);
    }
  };
  const onLeave = (ev) => { hoverLine.setAttribute("opacity", 0); if (hoverCb) hoverCb(null, ev); };
  const onClick = (ev) => {
    const tid = ev.target && ev.target.getAttribute && ev.target.getAttribute("data-id");
    if (tid && ev.target.classList.contains("hit") && clickCb) clickCb(tid, ev);
  };
  const onKey = (ev) => {
    if ((ev.key === "Enter" || ev.key === " ") && ev.target.classList && ev.target.classList.contains("hit")) {
      ev.preventDefault();
      if (clickCb) clickCb(ev.target.getAttribute("data-id"), ev);
    }
  };
  if (interactive) {
    gHit.addEventListener("pointermove", onMove);
    gHit.addEventListener("pointerleave", onLeave);
    gHit.addEventListener("click", onClick);
    gHit.addEventListener("keydown", onKey);
    gHit.classList.add("is-interactive");
  }

  const ctrl = {
    update(state) {
      if (animating) { pending = state; return; }
      applyState(state);
    },
    setSelection,
    setOrders,
    animateResolution,
    skipAnimation() { if (animating) cancelAll(); },
    onTerritoryClick(cb) { clickCb = cb; },
    onTerritoryHover(cb) { hoverCb = cb; },
    setOwner,
    getOwner: (tid) => owner[tid] || null,
    centroid,
    territory: (tid) => T[tid],
    gridLabel: (x, y) => `${cols[Math.max(0, Math.min(cols.length - 1, Math.floor(x / cell)))]}${Math.max(1, Math.min(rows, Math.floor(y / cell) + 1))}`,
    get isAnimating() { return animating; },
    factions,
    destroy() { cancelAll(); svg.replaceChildren(); if (lastCtrl === ctrl) lastCtrl = null; },
  };
  refreshAll();
  lastCtrl = ctrl;
  return ctrl;
}

/* ========================================================================
   moldura da carta: régua A–X / 1–16, título, legenda, escala, rosa dos ventos
   ======================================================================== */
function drawFrame(g, { W, H, cell, cols, rows }) {
  const band = 8;
  // régua em blocos alternados (como nas cartas militares)
  let dark = "";
  for (let i = 0; i < cols.length; i++) if (i % 2 === 0) dark += `M${i * cell} ${-band}h${cell}v${band}h${-cell}ZM${i * cell} ${H}h${cell}v${band}h${-cell}Z`;
  for (let j = 0; j < rows; j++) if (j % 2 === 0) dark += `M${-band} ${j * cell}h${band}v${cell}h${-band}ZM${W} ${j * cell}h${band}v${cell}h${-band}Z`;
  el("path", { d: dark, class: "ruler-dark" }, g);
  el("rect", { x: -band, y: -band, width: W + band * 2, height: H + band * 2, class: "ruler-frame", fill: "none" }, g);
  el("rect", { x: 0, y: 0, width: W, height: H, class: "neatline", fill: "none" }, g);
  for (let i = 0; i < cols.length; i++) {
    for (const y of [-17, H + 29]) {
      const t = el("text", { x: i * cell + cell / 2, y, class: "ruler-text", "text-anchor": "middle" }, g);
      t.textContent = cols[i];
    }
  }
  for (let j = 0; j < rows; j++) {
    for (const x of [-26, W + 26]) {
      const t = el("text", { x, y: j * cell + cell / 2 + 6, class: "ruler-text", "text-anchor": "middle" }, g);
      t.textContent = j + 1;
    }
  }
  // moldura externa dupla
  const ox = VIEWBOX.x + 6, oy = VIEWBOX.y + 6, ow = VIEWBOX.w - 12, oh = VIEWBOX.h - 12;
  el("rect", { x: ox, y: oy, width: ow, height: oh, class: "outer-frame", fill: "none" }, g);
  el("rect", { x: ox + 5, y: oy + 5, width: ow - 10, height: oh - 10, class: "outer-frame outer-frame--thin", fill: "none" }, g);

  /* cartucho inferior */
  const y0 = H + 54;
  const title = el("text", { x: 0, y: y0 + 24, class: "cart-title" }, g);
  title.textContent = "CARTA DO CONTINENTE DE LEBESGUE";
  const sub = el("text", { x: 0, y: y0 + 49, class: "cart-sub" }, g);
  sub.textContent = "SERVIÇO GEOGRÁFICO  ·  1943";
  const sub2 = el("text", { x: 0, y: y0 + 68, class: "cart-note" }, g);
  sub2.textContent = "Levantamento a lápis e nanquim. Quadrícula de 25 km.";
  el("path", { d: `M0 ${y0 + 30}H450`, class: "cart-rule" }, g);
  el("path", { d: `M0 ${y0 + 33}H450`, class: "cart-rule cart-rule--thin" }, g);
  // carimbo RESERVADO
  const st = el("g", { transform: `translate(386 ${y0 + 62}) rotate(-6)`, class: "cart-stamp" }, g);
  el("rect", { x: -58, y: -19, width: 116, height: 34, fill: "none", class: "cart-stamp-box" }, st);
  const stt = el("text", { y: 7, "text-anchor": "middle", class: "cart-stamp-text" }, st);
  stt.textContent = "RESERVADO";

  // legenda (sinais convencionais)
  const lx = 505;
  const lg = el("g", { transform: `translate(${lx} ${y0 + 8})`, class: "legend" }, g);
  const lt = el("text", { x: 0, y: 8, class: "leg-head" }, lg);
  lt.textContent = "SINAIS CONVENCIONAIS";
  const items = [
    [0, 0, "cap", "Capital"],
    [0, 1, "nation", "Fronteira entre nações"],
    [0, 2, "prov", "Divisa de província"],
    [1, 0, "river", "Rio"],
    [1, 1, "sea", "Rota marítima"],
    [1, 2, "hill", "Relevo"],
  ];
  for (const [c, r, kind, text] of items) {
    const x = c * 175, y = 28 + r * 21;
    const s = el("g", { transform: `translate(${x} ${y})` }, lg);
    if (kind === "cap") {
      el("circle", { cx: 12, cy: -4, r: 8, class: "cap-bg" }, s);
      el("circle", { cx: 12, cy: -4, r: 8, class: "cap-ring", fill: "none", style: "stroke:#2a241a" }, s);
      const pts = [];
      for (let i = 0; i < 10; i++) { const rr = i % 2 ? 3.1 : 6.6, a = -Math.PI / 2 + (i * Math.PI) / 5; pts.push(f1(12 + Math.cos(a) * rr) + "," + f1(-4 + Math.sin(a) * rr)); }
      el("polygon", { points: pts.join(" "), class: "cap-star" }, s);
    } else if (kind === "nation") el("path", { d: "M0 -4h26", class: "border border--nation" }, s);
    else if (kind === "prov") el("path", { d: "M0 -4h26", class: "border border--prov" }, s);
    else if (kind === "river") el("path", { d: "M0 -4q6 -5 13 0t13 0", class: "river", fill: "none" }, s);
    else if (kind === "sea") el("path", { d: "M0 -4h26", class: "sea-route" }, s);
    else el("path", { d: "M2 0l5 -9l5 9M12 0l5 -9l5 9", class: "sym-relief", fill: "none" }, s);
    const tt = el("text", { x: 36, y: 0, class: "leg-text" }, s);
    tt.textContent = text;
  }

  // escala gráfica: 1 unidade = 0,5 km
  const sx = 880, sy = y0 + 46;
  const sc = el("g", { transform: `translate(${sx} ${sy})`, class: "scale" }, g);
  const seg = 50;
  for (let i = 0; i < 4; i++) el("rect", { x: i * seg, y: 0, width: seg, height: 7, class: i % 2 ? "scale-w" : "scale-b" }, sc);
  [0, 25, 50, 75, 100].forEach((km, i) => {
    const t = el("text", { x: i * seg, y: 24, class: "scale-text", "text-anchor": "middle" }, sc);
    t.textContent = km;
  });
  const sk = el("text", { x: 4 * seg + 14, y: 8, class: "scale-text scale-text--unit" }, sc);
  sk.textContent = "KM";
  const sh = el("text", { x: 0, y: -12, class: "leg-head" }, sc);
  sh.textContent = "ESCALA GRÁFICA";

  // rosa dos ventos
  const rx = 1170, ry = y0 + 52;
  const rose = el("g", { transform: `translate(${rx} ${ry})`, class: "rose" }, g);
  el("circle", { r: 42, class: "rose-ring", fill: "none" }, rose);
  el("circle", { r: 38, class: "rose-ring rose-ring--thin", fill: "none" }, rose);
  let ticks = "";
  for (let i = 0; i < 32; i++) { const a = (i * Math.PI) / 16, r1 = i % 4 === 0 ? 33 : 38, r2 = 40; ticks += `M${f1(Math.cos(a) * r1)} ${f1(Math.sin(a) * r1)}L${f1(Math.cos(a) * r2)} ${f1(Math.sin(a) * r2)}`; }
  el("path", { d: ticks, class: "rose-tick", fill: "none" }, rose);
  const pt = (ang, r) => `${f1(Math.sin(ang) * r)},${f1(-Math.cos(ang) * r)}`;
  for (let k = 0; k < 8; k++) {
    const ang = (k * Math.PI) / 4;
    const long = k % 2 === 0;
    const R = long ? 40 : 25, wv = long ? 7 : 5;
    el("polygon", { points: `0,0 ${pt(ang - 0.28, wv)} ${pt(ang, R)}`, class: "rose-dark" }, rose);
    el("polygon", { points: `0,0 ${pt(ang + 0.28, wv)} ${pt(ang, R)}`, class: "rose-light" }, rose);
  }
  const N = el("text", { y: -47, "text-anchor": "middle", class: "rose-n" }, rose);
  N.textContent = "N";
}
