/* =====================================================================
   qg/operacoes.js — Operações: carta com névoa de guerra (map.js em modo
   "faction"), ordens de marcha por clique (origem → destino), estimativa de
   batalha (Lanchester via Mesa de Cálculo) e clima por região.
   Regras espelhadas do servidor (só para orientar; o servidor valida tudo):
   1 COM por batalhão em terra, 2 COM por rota marítima, pacto bloqueia ataque.
   ===================================================================== */
import {
  h, fmt, parseNum, svgEl, stampEl, kids, WEATHER_NAMES, WEATHER_ATK, TERRAIN_DEF, TERRAIN_NAMES,
  REGIONS, REGION_NAMES, dossierPaper, challengeBox, orderSheet,
} from "./common.js";
import { renderMap } from "../map.js";

const NS = "http://www.w3.org/2000/svg";
const T_BATTLE = 0.9;

const WX_ICON = [
  '<svg viewBox="0 0 24 24" class="wx-ico" aria-hidden="true"><circle cx="12" cy="12" r="4.6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 2.5v2.6M12 18.9v2.6M2.5 12h2.6M18.9 12h2.6M5.2 5.2l1.8 1.8M17 17l1.8 1.8M5.2 18.8 7 17M17 7l1.8-1.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  '<svg viewBox="0 0 24 24" class="wx-ico" aria-hidden="true"><path d="M7 15.5a4 4 0 0 1 .4-7.9 5.6 5.6 0 0 1 10.6 1.6A3.4 3.4 0 0 1 18 15.5z" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M8 18.5l-1 2.6M12 18.5l-1 2.6M16 18.5l-1 2.6" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>',
  '<svg viewBox="0 0 24 24" class="wx-ico" aria-hidden="true"><path d="M7 14.5a4 4 0 0 1 .4-7.9 5.6 5.6 0 0 1 10.6 1.6A3.4 3.4 0 0 1 18 14.5z" fill="currentColor" opacity=".85"/><path d="M12.8 13.5 10.6 18h3.1l-2 4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
];

/** "1–5" -> [1,5]; "21+" -> [21, 36] (teto presumido); outro -> null */
function rangeBounds(txt) {
  if (!txt) return null;
  const s = String(txt).replace("-", "–");
  const m = /^(\d+)\s*–\s*(\d+)$/.exec(s);
  if (m) return [Number(m[1]), Number(m[2])];
  const p = /^(\d+)\+$/.exec(s);
  if (p) return [Number(p[1]), Number(p[1]) + 15];
  return null;
}

/** Mesma lei quadrática do servidor (A' = −βB, B' = −αA), por passos pequenos. */
export function lanchesterLocal(A0, B0, alpha, beta, T = T_BATTLE) {
  let a = A0, b = B0, t = 0, winner = "none";
  const dt = 0.0005;
  while (t < T) {
    const na = a - beta * b * dt;
    const nb = b - alpha * a * dt;
    t += dt;
    if (nb <= 0) { winner = "attacker"; a = Math.max(0, na); b = 0; break; }
    if (na <= 0) { winner = "defender"; a = 0; b = Math.max(0, nb); break; }
    a = na; b = nb;
  }
  return { a_final: a, b_final: b, t_end: t, winner };
}

export function mountOperacoes(root, ctx) {
  root.classList.add("sec", "sec--operacoes");

  let fid = null;
  let ctrl = null;
  let terr = {};            // id -> território do mapa público (vizinhos, terreno, clima)
  let owners = {}, troops = {}, vis = {}, ranges = {};
  let draft = [];           // ordens de marcha em edição: {from, to, troops}
  let pick = null;          // origem escolhida
  let pickValid = [];       // destinos válidos da origem
  let touched = false;
  let lastOrderKey = "";
  let battleSeq = 0;
  let lastBattle = null;

  /* ---------------------------------------------------------- mapa */
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "carta-host");
  const pop = h("div", { class: "pop paper hidden", role: "dialog", "aria-label": "Ordem de marcha" });
  const mapHint = h("p", { class: "map-hint typed", "aria-live": "polite" },
    "Clique num território seu para começar uma ordem de marcha.");
  const mapWrap = h("div", { class: "mapwrap" }, svg, pop);
  const weatherBox = h("div", { class: "wx-box" });
  const mapSheet = h("section", { class: "paper mapsheet" },
    h("header", { class: "mapsheet__head" },
      h("span", { class: "caps" }, "Carta do continente"),
      h("span", { class: "typed faint" }, "névoa de guerra: tropas exatas só nos seus territórios")),
    mapWrap,
    mapHint,
    h("p", { class: "map-legend" }, "Origem sua → destino destacado. Tracejado: rota marítima (2 COM por batalhão, cancelada na tempestade)."),
    weatherBox);

  /* ---------------------------------------------------------- ordens */
  const draftList = h("ul", { class: "moves" });
  const costLine = h("p", { class: "prev__line" });
  const orderBody = h("div", { class: "order-body" }, draftList, costLine);
  const sheet = orderSheet({
    ctx, section: "operacoes", body: orderBody,
    getPayload: () => ({ moves: draft.map((m) => ({ from: m.from, to: m.to, troops: m.troops })) }),
  });

  /* ---------------------------------------------------------- batalha */
  const sel = h("select", { class: "input input--sel", id: "bat-sel", "aria-label": "Ataque a estimar", onchange: () => estimate() });
  const moraleIn = h("input", {
    id: "bat-mor", type: "number", min: "0", max: "100", step: "1", inputmode: "numeric",
    class: "input input--num", value: "70", oninput: () => estimate(),
  });
  const batOut = h("div", { class: "battle__out", "aria-live": "polite" });
  const modSlot = h("div", { class: "mods" });
  const openLan = h("button", {
    class: "btn btn--small btn--blue", type: "button",
    onclick: () => {
      if (!lastBattle) return;
      ctx.calc.open("lanchester", { A0: lastBattle.A0, B0: lastBattle.B0, alpha: lastBattle.alpha, beta: lastBattle.beta, T: T_BATTLE });
    },
  }, "Abrir Lanchester na Mesa");
  const battle = h("section", { class: "paper battle" },
    h("header", { class: "battle__head" }, h("h3", { class: "stencil" }, "Estimativa de batalha"), stampEl("Estimativa", "ink")),
    h("p", { class: "typed faint" }, "Para cada ataque da ordem: pior e melhor caso dentro da faixa conhecida do defensor, com terreno e clima de origem."),
    h("div", { class: "field" }, h("label", { for: "bat-sel" }, "Ataque"), sel),
    h("div", { class: "field" }, h("label", { for: "bat-mor" }, "Moral presumida do defensor (0–100)"), moraleIn),
    batOut,
    h("p", { class: "hint" }, "Moral do defensor é oculta: 70 é a moral inicial; milícias neutras têm 60."),
    modSlot,
    h("div", { class: "row" }, openLan));

  /* ---------------------------------------------------------- dossiê */
  const dossierSlot = h("div", { class: "slot slot--dossier" });
  const chal = challengeBox({ ctx, section: "operacoes" });

  root.replaceChildren(
    h("div", { class: "area-map" }, mapSheet),
    h("div", { class: "area-side" }, sheet.el),
    h("div", { class: "area-battle" }, battle),
    h("div", { class: "area-dossier" }, dossierSlot),
    h("div", { class: "area-chal" }, chal.el));

  /* ================================================================ regras */
  const ownerName = (o) => (o ? ctx.name(o) : "neutro");
  const tname = (t) => (terr[t] ? terr[t].name : t);
  const isSea = (m) => !(terr[m.from] && (terr[m.from].neighbors || []).includes(m.to));
  const moveCost = (list) => list.reduce((acc, m) => acc + m.troops * (isSea(m) ? 2 : 1), 0);
  const committed = (t) => draft.filter((m) => m.from === t).reduce((acc, m) => acc + m.troops, 0);
  const available = (t) => Math.max(0, (troops[t] ?? 0) - committed(t));
  const pactBlocked = (o) => {
    if (!o || o === fid) return false;
    const st = ctx.state();
    return !!(st && (st.faction.pacts || []).some((p) => p.with === o));
  };
  const kindLabel = (to) => {
    if (owners[to] === fid) return "reforço";
    if (owners[to]) return `ataque a ${ownerName(owners[to])}`;
    return "ocupação de neutro";
  };
  function describe(tid) {
    const t = terr[tid];
    if (!t) return "";
    const v = vis[tid];
    let info = "tropas desconhecidas";
    if (v === "own" || v === "revealed") info = `${troops[tid]} batalhão(ões)`;
    else if (v === "adjacent" && ranges[tid]) info = `tropas: ${ranges[tid]}`;
    return `${tname(tid)} (${tid}) · ${ownerName(owners[tid])} · ${info}`;
  }

  function indexState(st) {
    owners = {}; troops = {}; vis = {}; ranges = {};
    for (const t of st.territories || []) {
      owners[t.id] = t.owner;
      troops[t.id] = t.troops;
      vis[t.id] = t.visibility;
      ranges[t.id] = t.troops_range;
    }
  }

  function ensureMap() {
    const st = ctx.state();
    const md = ctx.map();
    if (ctrl || !st || !md) return;
    for (const t of md.territories) terr[t.id] = t;
    ctrl = renderMap(svg, md, { mode: "faction", interactive: true, myFaction: fid, factions: st.factions || [] });
    ctrl.onTerritoryClick(onClick);
  }

  /* ================================================================ interação */
  function setHint(text) { mapHint.textContent = text; }

  function startPick(tid) {
    pick = tid;
    const t = terr[tid];
    const cand = [...new Set([...(t.neighbors || []), ...(t.sea_neighbors || [])])];
    pickValid = cand.filter((b) => !pactBlocked(owners[b]));
    if (ctrl) ctrl.setSelection([tid, ...pickValid]);
    pop.classList.add("hidden");
    setHint(`Origem ${tid} (${t.name}): ${available(tid)} batalhão(ões) disponível(is). Clique num território destacado para dar a ordem (Esc cancela).`);
  }

  function cancelPick() {
    pick = null;
    pickValid = [];
    if (ctrl) ctrl.setSelection([]);
    pop.classList.add("hidden");
    setHint("Clique num território seu para começar uma ordem de marcha.");
  }

  function onClick(tid, ev) {
    if (!ctrl || !fid) return;
    if (pick) {
      if (tid === pick) { cancelPick(); return; }
      if (pickValid.includes(tid)) { openPop(tid, ev); return; }
      if (owners[tid] === fid) { startPick(tid); return; }
      setHint(`${tname(tid)} não é vizinho de ${pick} por terra nem por mar, ou há pacto com a nação dona. Escolha um destacado, ou cancele (Esc).`);
      return;
    }
    if (owners[tid] === fid) {
      if (available(tid) <= 0) { setHint(`${tname(tid)} não tem batalhões livres para marchar (já comprometidos ou sem tropas).`); return; }
      startPick(tid);
      return;
    }
    setHint(describe(tid));
  }

  function openPop(to, ev) {
    const from = pick;
    const max = available(from);
    if (max <= 0) { cancelPick(); return; }
    const range = h("input", { type: "range", min: "1", max: String(max), step: "1", value: String(Math.min(max, 1)), "aria-label": "Quantos batalhões" });
    const num = h("input", { type: "number", min: "1", max: String(max), step: "1", inputmode: "numeric", class: "input input--num", value: String(Math.min(max, 1)), "aria-label": "Batalhões" });
    const cost = h("p", { class: "typed pop__cost" });
    const sea = isSea({ from, to });
    const readN = () => Math.min(max, Math.max(1, Math.floor(parseNum(num.value) || 1)));
    const updCost = () => {
      const n = readN();
      cost.textContent = `${n} batalhão(ões) · custo ${n * (sea ? 2 : 1)} COM (${sea ? "rota marítima" : "terrestre"})`;
    };
    range.addEventListener("input", () => { num.value = range.value; updCost(); });
    num.addEventListener("input", () => { range.value = String(readN()); updCost(); });
    const ok = h("button", { class: "btn btn--small btn--blue", type: "button", onclick: () => {
      const n = readN();
      addMove({ from, to, troops: n });
      cancelPick();
    } }, "Lançar ordem");
    const cancel = h("button", { class: "btn btn--small", type: "button", onclick: () => cancelPick() }, "Cancelar");
    pop.replaceChildren(
      h("p", { class: "caps" }, "Ordem de marcha"),
      h("p", { class: "typed pop__route" }, `${from} → ${to} · ${tname(to)}`),
      h("p", { class: "typed faint" }, kindLabel(to)),
      h("div", { class: "pop__row" }, range, num),
      cost,
      h("div", { class: "row" }, ok, cancel));
    updCost();
    pop.classList.remove("hidden");
    const wrap = mapWrap.getBoundingClientRect();
    const hasPoint = ev && typeof ev.clientX === "number" && ev.clientX > 0;
    const x = hasPoint ? ev.clientX - wrap.left + 14 : 16;
    const y = hasPoint ? ev.clientY - wrap.top + 14 : 16;
    pop.style.left = `${Math.max(8, Math.min(x, wrap.width - 290))}px`;
    pop.style.top = `${Math.max(8, Math.min(y, wrap.height - 200))}px`;
    num.focus();
  }

  function addMove(m) {
    const ex = draft.find((x) => x.from === m.from && x.to === m.to);
    if (ex) ex.troops += m.troops; else draft.push(m);
    touched = true;
    renderDraft();
    estimate();
  }

  function renderDraft() {
    draftList.replaceChildren(...(draft.length
      ? draft.map((m, i) => h("li", { class: "move" },
          h("span", { class: "mono move__route" }, `${m.from} → ${m.to}`),
          h("span", { class: "move__what" }, `${m.troops} bat. · ${kindLabel(m.to)} · ${isSea(m) ? 2 : 1} COM/bat.`),
          h("button", {
            class: "btn btn--small", type: "button", "aria-label": `Remover ordem ${m.from} para ${m.to}`,
            onclick: () => { draft.splice(i, 1); touched = true; renderDraft(); estimate(); },
          }, "Remover")))
      : [h("li", { class: "typed faint move--empty" }, "Nenhuma ordem de marcha. Clique numa origem sua no mapa.")]));
    const c = moveCost(draft);
    const com = Number(ctx.state() ? ctx.state().faction.stock.COM : 0) || 0;
    const over = c > com + 1e-9;
    costLine.replaceChildren(...kids(
      h("span", null, "Combustível previsto: "), h("b", { class: "mono" }, fmt(c, 0)),
      h("span", null, " COM de "), h("b", { class: "mono" }, fmt(com)), h("span", null, " em estoque"),
      over ? h("span", { class: "warn-tag" }, "excede o estoque: os movimentos serão reduzidos") : null));
    if (ctrl) ctrl.setOrders(draft);
  }

  /* ================================================================ batalha */
  async function runLanchester(A0, B0, alpha, beta) {
    try {
      const r = await ctx.api.tool("lanchester", { A0, B0, alpha, beta, T: T_BATTLE });
      if (r && typeof r.winner === "string") return r;
    } catch (e) { /* sem servidor: cálculo local abaixo */ }
    return lanchesterLocal(A0, B0, alpha, beta, T_BATTLE);
  }

  async function estimate() {
    const st = ctx.state();
    if (!st || !ctrl) return;
    const attacks = draft.filter((m) => owners[m.to] !== fid);
    const prev = sel.value;
    sel.replaceChildren(...attacks.map((m, i) => h("option", { value: String(i) },
      `${m.from} → ${m.to} · ${m.troops} bat. contra ${tname(m.to)}`)));
    if (!attacks.length) {
      sel.value = "";
      batOut.replaceChildren(h("p", { class: "typed faint" }, "Nenhum ataque na ordem. A estimativa aparece quando houver um movimento contra território inimigo ou neutro."));
      lastBattle = null;
      return;
    }
    sel.value = prev && Number(prev) < attacks.length ? prev : "0";
    const m = attacks[Number(sel.value) || 0];
    const seq = ++battleSeq;
    const target = m.to, origin = m.from;
    const dm = Math.max(0, Math.min(100, parseNum(moraleIn.value) ?? (owners[target] ? 70 : 60)));
    const wIdx = Number((st.weather || {})[terr[origin].climate]) || 0;
    const alpha = (0.5 + Number(st.faction.morale) / 100) * WEATHER_ATK[wIdx];
    const beta = (0.5 + dm / 100) * (TERRAIN_DEF[terr[target].terrain] || 1);
    let lo, hi, note;
    const v = vis[target];
    if (v === "own" || v === "revealed") { lo = hi = Number(troops[target]); note = "tropas exatas"; }
    else {
      const rb = rangeBounds(ranges[target]);
      if (rb) { [lo, hi] = rb; note = `faixa ${ranges[target]}`; }
      else { lo = 1; hi = 20; note = "sem informação: faixa presumida 1–20"; }
    }
    batOut.replaceChildren(h("p", { class: "typed faint" }, "calculando…"));
    const cases = [{ name: "Pior caso", B0: hi }, { name: "Melhor caso", B0: lo }];
    const results = [];
    for (const c of cases) results.push(await runLanchester(m.troops, c.B0, alpha, beta));
    if (seq !== battleSeq) return;   // resposta velha: outro ataque foi escolhido
    lastBattle = { A0: m.troops, B0: hi, alpha, beta };
    batOut.replaceChildren(...kids(
      h("p", { class: "typed" },
        `${origin} → ${target} · ${tname(target)} (${TERRAIN_NAMES[terr[target].terrain] || terr[target].terrain}) · `,
        `${WEATHER_NAMES[wIdx]} na origem · defensor: ${note}`),
      cases.map((c, i) => outcomeRow(c, m.troops, results[i]))));
  }

  function outcomeRow(c, A0, r) {
    let tone = "draw", text;
    if (r.winner === "attacker") { tone = "won"; text = `território tomado; sobram ${fmt(r.a_final)} batalhão(ões)`; }
    else if (r.winner === "defender") { tone = "lost"; text = `ataque repelido; defesa com ${fmt(r.b_final)}`; }
    else text = `impasse ao fim de T = 0,9: ${fmt(r.a_final)} × ${fmt(r.b_final)}`;
    return h("div", { class: `bcase bcase--${tone}` },
      h("b", { class: "caps" }, `${c.name} · defensor ${c.B0}`),
      h("span", null, `${A0} atacantes contra ${c.B0} defensores → ${text}`));
  }

  /* ================================================================ clima */
  function renderWeather(st) {
    const wx = st.weather || {};
    const fc = st.weather_forecast;
    weatherBox.replaceChildren(
      h("p", { class: "caps faint" }, "Clima atual por região"),
      h("ul", { class: "wx" }, REGIONS.map((r) => {
        const idx = Number(wx[r]) || 0;
        return h("li", { class: `wx__row wx--${idx}` },
          svgEl(WX_ICON[idx]),
          h("span", { class: "wx__reg" }, REGION_NAMES[r]),
          h("b", { class: "wx__state" }, WEATHER_NAMES[idx]),
          fc
            ? h("span", { class: "wx__fc" }, `previsão: ${WEATHER_NAMES[Number(fc[r])]}`)
            : h("span", { class: "wx__fc faint" }, "previsão oculta"));
      })));
  }

  /* ================================================================ estado */
  function prefill(order) {
    const key = JSON.stringify(order || null);
    if (key === lastOrderKey) return;
    lastOrderKey = key;
    if (touched || !order || !Array.isArray(order.moves)) return;
    draft = order.moves.map((m) => ({ from: m.from, to: m.to, troops: m.troops }));
  }

  function renderModifiers(d) {
    const ds = d && (d.datasets || []).find((x) => x.id === "modificadores");
    if (!ds) { modSlot.replaceChildren(); return; }
    modSlot.replaceChildren(
      h("p", { class: "caps faint" }, "Tabela de modificadores (dossiê)"),
      h("div", { class: "ledger-wrap" }, h("table", { class: "ledger ledger--mods" },
        h("tbody", null, ds.rows.map((r) => h("tr", null,
          h("td", { class: "txt" }, String(r[0])),
          h("td", null, typeof r[1] === "number" ? fmt(r[1], 3) : String(r[1]))))))));
  }

  let curTurn = null;
  let dossierShown = null;
  function update() {
    const st = ctx.state();
    const d = ctx.dossier("operacoes");
    if (d !== dossierShown) {
      dossierShown = d;
      dossierSlot.replaceChildren(dossierPaper(d, { ctx, section: "operacoes" }));
      renderModifiers(d);
    }
    chal.update(d ? d.challenges : []);
    if (!st) return;
    fid = st.faction.id;
    if (d && d.turn !== curTurn) { curTurn = d.turn; }
    ensureMap();
    indexState(st);
    if (ctrl) ctrl.update(st);
    const before = draft.length;
    draft = draft.filter((m) => owners[m.from] === fid);
    if (draft.length !== before) setHint("Uma ordem foi retirada: o território de origem já não é seu.");
    renderWeather(st);
    sheet.setTurn(st.game.turn);
    const o = st.orders && st.orders.operacoes;
    sheet.setLast(o && Array.isArray(o.moves)
      ? (o.moves.length ? o.moves.map((m) => `${m.from} → ${m.to}: ${m.troops} batalhão(ões)`) : ["Sem movimentos: a nação ficou parada."])
      : null);
    prefill(o);
    renderDraft();
    estimate();
  }

  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && pick) cancelPick(); });

  return { update, cancelPick };
}
