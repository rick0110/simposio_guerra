/* =====================================================================
   qg.js — Quartel-General da nação: timbre (emblema, estoques, moral, relógio),
   pasta com as quatro seções, despachos que chegam pelo WebSocket (datilografados),
   arquivo de telegramas, boletim do turno e a gaveta da Mesa de Cálculo.
   Dados: GET /api/faction/state e /api/faction/dossier/{seção}; o relógio usa
   serverClock() + game.remaining_ms (em pausa e no lobby o tempo não anda).
   Modo simulado: qg.html?mock=1&me=GAU  (window.__mockWS(tipo, dados) injeta eventos)
   ===================================================================== */
import { api, serverClock, MOCK, withMock } from "./api.js";
import { connect } from "./ws.js";
import { sfx } from "./sfx.js";
import { emblemSVG, FACTION_DEFAULTS } from "./emblems.js";
import {
  h, fmt, clockText, svgEl, telegramEl, cipherText, SECTIONS, SEC_NAMES,
} from "./qg/common.js";
import { mountIntendencia } from "./qg/intendencia.js";
import { mountOperacoes } from "./qg/operacoes.js";
import { mountInteligencia } from "./qg/inteligencia.js";
import { mountGoverno } from "./qg/governo.js";

const $ = (id) => document.getElementById(id);
const PORTAL = MOCK ? withMock("index.html") : "/";
const REDUCED = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
const SEC_KEY = "em_qg_sec";
const BOL_KEY = "em_qg_bol";
const CIPHER_KINDS = new Set(["intercept", "flash"]);

const S = {
  fid: null,
  state: null,
  stateSeq: 0,
  stateApplied: 0,
  dossiers: {},
  map: null,
  clock: null,
  sec: "intendencia",
  arqFilter: "sec",
  lastStatus: null,
  lastTurn: null,
  alarmTurn: null,
  phaseText: null,
  sealFor: null,
};

let calc = null;          // Mesa de Cálculo (calc.js): a gaveta tem a própria alça
const inst = {};          // módulos das seções

/* ------------------------------------------------------------ utilidades */
const hora = () => new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function safe(fn, label = "") {
  try { return fn(); } catch (e) { console.error(label, e); return undefined; }
}

function factionName(id) {
  if (!id) return "milícia neutra";
  const list = (S.state && S.state.factions) || [];
  const f = list.find((x) => x.id === id) || FACTION_DEFAULTS[id];
  return f ? (f.short || f.name || id) : id;
}

function remainingMs() {
  const g = S.state && S.state.game;
  if (!g) return 0;
  if (g.status !== "running") return Math.max(0, Number(g.remaining_ms) || 0);
  const srvNow = S.clock ? S.clock.now() : Date.now();
  const elapsed = srvNow - (Number(g.now_ms) || srvNow);
  return Math.max(0, Number(g.remaining_ms) - elapsed);
}

function handleErr(e) {
  if (e && e.status === 401) { location.href = PORTAL; return; }
  console.warn(e);
  dispatch({ head: "Falha de comunicação", text: (e && e.message) || "Não foi possível atualizar os dados.", tone: "warn" });
}

/* ------------------------------------------------------------ Mesa de Cálculo */
function openCalc(tool, payload) {
  if (!calc) {
    dispatch({ head: "Mesa de Cálculo", text: "A Mesa de Cálculo não carregou nesta página. Recarregue a página.", tone: "warn" });
    return;
  }
  try {
    calc.open(tool, payload);
  } catch (e) {
    dispatch({ head: "Mesa de Cálculo", text: e.message || "Não foi possível abrir a ferramenta.", tone: "warn" });
  }
}

async function loadCalc() {
  try {
    const mod = await import("./calc.js");
    calc = mod.mountCalc($("calc-drawer"));
  } catch (e) {
    console.warn("Mesa de Cálculo indisponível:", e && e.message);
    calc = null;
  }
}

/* ------------------------------------------------------------ contexto das seções */
const ctx = {
  api, sfx,
  get fid() { return S.fid; },
  state: () => S.state,
  dossier: (sec) => S.dossiers[sec] || null,
  map: () => S.map,
  name: (id) => factionName(id),
  calc: { open: (tool, payload) => openCalc(tool, payload) },
  reloadState: () => loadState(),
  reloadDossier: (sec) => loadDossier(sec),
  sessionLost: () => { location.href = PORTAL; },
};

/* ------------------------------------------------------------ carregamento */
async function loadState() {
  const seq = ++S.stateSeq;
  const s = await api.get("/api/faction/state");
  if (seq < S.stateApplied) return;       // resposta mais velha que a já aplicada
  S.stateApplied = seq;
  S.state = s;
  S.fid = s.faction.id;
  if (S.lastStatus === null) { S.lastStatus = s.game.status; S.lastTurn = s.game.turn; }
  refreshAll();
}

async function loadDossier(sec) {
  const d = await api.get(`/api/faction/dossier/${sec}`);
  S.dossiers[sec] = d;
  safe(() => inst[sec] && inst[sec].update(), sec);
}

async function loadAllDossiers() {
  await Promise.all(SECTIONS.map((sec) => loadDossier(sec).catch(handleErr)));
}

function refreshAll() {
  renderTimbre();
  tick();
  for (const sec of SECTIONS) safe(() => inst[sec] && inst[sec].update(), sec);
  if (!$("archive").classList.contains("hidden")) renderArchive();
  maybeBoletim();
}

/* ------------------------------------------------------------ timbre */
const THERM = { top: 12, bottom: 118 };

function buildThermo() {
  const ticks = [0, 25, 50, 75, 100].map((v) => {
    const y = THERM.bottom - (v * (THERM.bottom - THERM.top)) / 100;
    return `<line x1="30" x2="36" y1="${y}" y2="${y}"/><text x="38" y="${y + 3.5}">${v}</text>`;
  }).join("");
  const svg = svgEl(`<svg class="therm" viewBox="0 0 64 146" role="img" aria-label="Moral da nação">
      <rect class="therm__tube" x="16" y="${THERM.top - 4}" width="12" height="${THERM.bottom - THERM.top + 4}" rx="6"/>
      <g class="therm__ticks">${ticks}</g>
      <rect class="therm__fill" id="therm-fill" x="18.5" y="${THERM.bottom}" width="7" height="0"/>
      <circle class="therm__bulb" cx="22" cy="130" r="12"/>
    </svg>`);
  $("moral").replaceChildren(
    svg,
    h("div", { class: "moral__txt" },
      h("small", { class: "caps" }, "Moral"),
      h("b", { class: "mono", id: "moral-val" }, "—")));
}

function updateThermo(m) {
  const fill = $("therm-fill");
  if (!fill) return;
  const v = Math.max(0, Math.min(100, Number(m) || 0));
  const y = THERM.bottom - (v * (THERM.bottom - THERM.top)) / 100;
  fill.setAttribute("y", String(y));
  fill.setAttribute("height", String(THERM.bottom - y));
  $("moral-val").textContent = fmt(m, 1);
}

function renderTimbre() {
  const st = S.state;
  if (!st) return;
  const f = st.faction;
  const g = st.game;
  if (S.sealFor !== f.id) {
    S.sealFor = f.id;
    $("seal").replaceChildren(svgEl(emblemSVG(f.id, { size: 78 })));
  }
  $("seal").style.color = f.color;
  document.documentElement.style.setProperty("--nation", f.color);
  document.title = `${f.short || f.name} · Quartel-General`;
  $("t-name").textContent = `${f.name} — Quartel-General`;
  $("t-cap").textContent = `Capital: ${f.capital_name} (${f.capital})${f.capitulated ? " · capitulou" : ""}`;
  $("t-turn").textContent = `Turno ${g.turn} de ${g.max_turns}`;
  $("ledger").replaceChildren(...[
    ["ALI", "Alimento", fmt(f.stock.ALI)],
    ["ACO", "Aço", fmt(f.stock.ACO)],
    ["COM", "Combustível", fmt(f.stock.COM)],
    ["TROPAS", "batalhões", fmt(f.troops_total, 0)],
    ["PV", "pontos de vitória", fmt(f.vp, 2)],
    ["TERR.", "territórios", fmt(f.territories, 0)],
  ].map(([code, name, val]) => h("div", { class: "tag", title: name },
    h("small", { class: "caps" }, code),
    h("b", { class: "mono" }, val))));
  if (!$("moral-val")) buildThermo();
  updateThermo(f.morale);
}

/** Fase exibida no carimbo: depende do estado e do relógio. */
function phaseInfo(rem) {
  const g = S.state.game;
  if (S.state.faction.capitulated) return ["CAPITULOU", "red"];
  switch (g.status) {
    case "lobby": return ["AGUARDANDO INÍCIO", "ink"];
    case "paused": return ["PAUSADO", "blue"];
    case "finished": return ["FIM", "ink"];
    default: return rem <= 0 ? ["RESOLVENDO", "olive"] : ["PLANEJAMENTO", "olive"];
  }
}

function tick() {
  const st = S.state;
  if (!st) return;
  const g = st.game;
  const rem = remainingMs();
  const clockEl = $("clock");
  clockEl.textContent = clockText(rem);
  const alarm = g.status === "running" && rem > 0 && rem <= 60000;
  clockEl.classList.toggle("is-alarm", alarm);
  $("turnbox").classList.toggle("is-alarm", alarm);
  if (alarm && S.alarmTurn !== g.turn) { S.alarmTurn = g.turn; sfx.alarm(); }
  const [label, tone] = phaseInfo(rem);
  if (S.phaseText !== label) {
    S.phaseText = label;
    const ph = $("phase");
    ph.textContent = label;
    ph.className = `stamp stamp--${tone}`;
  }
}

/* ------------------------------------------------------------ pasta: seções */
function initialSection() {
  const fromHash = location.hash.slice(1);
  if (SECTIONS.includes(fromHash)) return fromHash;
  try {
    const v = localStorage.getItem(SEC_KEY);
    if (SECTIONS.includes(v)) return v;
  } catch { /* sem armazenamento */ }
  return "intendencia";
}

function showSection(sec, { save = true } = {}) {
  if (!SECTIONS.includes(sec)) sec = "intendencia";
  S.sec = sec;
  for (const s of SECTIONS) {
    const tab = $(`tab-${s}`);
    const panel = $(`sec-${s}`);
    const on = s === sec;
    tab.classList.toggle("is-active", on);
    tab.setAttribute("aria-selected", on ? "true" : "false");
    tab.tabIndex = on ? 0 : -1;
    panel.hidden = !on;
  }
  if (save) {
    try { localStorage.setItem(SEC_KEY, sec); } catch { /* sem armazenamento */ }
    if (location.hash !== `#${sec}`) history.replaceState(null, "", `#${sec}`);
  }
  if (!$("archive").classList.contains("hidden")) renderArchive();
}

function mountSections() {
  const mounts = { intendencia: mountIntendencia, operacoes: mountOperacoes, inteligencia: mountInteligencia, governo: mountGoverno };
  for (const sec of SECTIONS) inst[sec] = mounts[sec]($(`sec-${sec}`), ctx);
}

/* ------------------------------------------------------------ despachos */
/**
 * Despacho: um telegrama que se datilografa no canto. Cifra com espaços visíveis.
 * Até três na pilha; clique dispensa. Sem animação se o sistema pedir movimento reduzido.
 */
function dispatch({ head, text = "", cipher = false, tone = "" }) {
  const stack = $("dispatches");
  if (!stack) return;
  const body = h("span", { class: "telegram__strip" }, "");
  const el = h("article", { class: `telegram dispatch${tone ? ` dispatch--${tone}` : ""}`, role: "status" },
    h("div", { class: "telegram__head" }, h("span", null, head), h("span", null, hora())),
    h("div", { class: cipher ? "telegram__body cipher" : "telegram__body" }, body));
  el.title = "Clique para dispensar";
  el.addEventListener("click", () => el.remove());
  while (stack.children.length >= 3) stack.firstElementChild.remove();
  stack.append(el);

  const full = cipher ? cipherText(text) : String(text ?? "");
  const removeLater = () => setTimeout(() => el.remove(), Math.min(20000, 7000 + full.length * 50));
  if (REDUCED || !full) { body.textContent = full; removeLater(); return; }

  el.classList.add("is-typing");
  const step = Math.max(10, Math.min(28, 1800 / Math.max(1, full.length)));
  let i = 0;
  const timer = setInterval(() => {
    if (!el.isConnected) { clearInterval(timer); return; }
    i += 1;
    body.textContent = full.slice(0, i);
    if (i % 3 === 1 && stack.querySelectorAll(".is-typing").length === 1 && !sfx.muted) sfx.key();
    if (i >= full.length) {
      clearInterval(timer);
      el.classList.remove("is-typing");
      removeLater();
    }
  }, step);
}

function onPhase(g) {
  const prev = S.lastStatus;
  const prevTurn = S.lastTurn;
  S.lastStatus = g.status;
  S.lastTurn = g.turn;
  if (prev === null) return;
  if (g.status === "running" && prev === "lobby") {
    dispatch({ head: "Guerra iniciada", text: `O árbitro abriu as hostilidades. Turno ${g.turn} em andamento.` });
  } else if (g.status === "running" && prev === "paused") {
    dispatch({ head: "Partida retomada", text: `O árbitro retomou o relógio no turno ${g.turn}.` });
  } else if (g.status === "paused" && prev !== "paused") {
    dispatch({ head: "Partida pausada", text: "O árbitro pausou o relógio. As ordens já enviadas continuam valendo." });
  } else if (g.status === "finished" && prev !== "finished") {
    dispatch({ head: "Fim de jogo", text: "A guerra terminou. O quadro final está no Teatro de Operações." });
  } else if (g.status === "running" && prevTurn !== null && g.turn !== prevTurn) {
    dispatch({ head: `Turno ${g.turn}`, text: `Novo turno. Prazo de ${Math.round(Number(g.turn_ms) / 60000)} min para as ordens.` });
  }
}

function onResolution(r) {
  const battles = r.battles || [];
  const caps = battles.filter((b) => b.result === "captured").length;
  if (battles.length) sfx.thud();
  dispatch({
    head: `Resolução do turno ${r.turn}`,
    text: `${battles.length} batalha(s), ${caps} território(s) tomado(s), ${(r.moves || []).length} movimento(s). O boletim está na mesa.`,
  });
}

function onMessage(msg) {
  const type = msg && msg.type;
  const data = (msg && msg.data) || {};
  switch (type) {
    case "state": loadState().catch(handleErr); break;
    case "phase": onPhase(data); loadState().catch(handleErr); break;
    case "resolution": onResolution(data); loadState().catch(handleErr); break;
    case "telegram":
      dispatch({ head: data.title || "Telegrama", text: data.body || "", cipher: CIPHER_KINDS.has(data.kind) });
      loadState().catch(handleErr);
      if (CIPHER_KINDS.has(data.kind)) loadDossier("inteligencia").catch(handleErr);
      break;
    case "dossier":
      dispatch({ head: "Dossiê novo", text: `Dossiês do turno ${data.turn} prontos nas quatro seções.` });
      loadAllDossiers();
      loadState().catch(handleErr);
      break;
    case "broadcast":
      dispatch({ head: data.title || "Aviso do árbitro", text: data.text || "" });
      break;
    case "message":
      dispatch({ head: `Telegrama diplomático de ${factionName(data.from)}`, text: data.text || "" });
      loadState().catch(handleErr);
      break;
    default: break;
  }
}

function onStatus(s, info) {
  const conn = $("conn");
  conn.dataset.s = s;
  conn.textContent = s === "open" ? "Linha aberta" : s === "mock" ? "Simulado" : s === "connecting" ? "Conectando…" : "Linha caída";
  if (s === "open" && info && info.reconnected) {
    loadState().catch(handleErr);
    loadAllDossiers();
  }
}

/* ------------------------------------------------------------ arquivo de telegramas */
function filterBtn(key, label) {
  const on = S.arqFilter === key;
  return h("button", {
    class: `btn btn--small${on ? " is-on" : ""}`, type: "button", "aria-pressed": on ? "true" : "false",
    onclick: () => { S.arqFilter = key; renderArchive(); },
  }, label);
}

function renderArchive() {
  const st = S.state;
  const box = $("archive");
  if (!st) return;
  const list = [...(st.telegrams || [])].sort((a, b) => (b.at_ms || 0) - (a.at_ms || 0) || (b.turn || 0) - (a.turn || 0));
  const filt = S.arqFilter === "sec" ? list.filter((t) => t.section === S.sec || t.section == null) : list;
  box.replaceChildren(
    h("header", { class: "archive__head" },
      h("h2", { class: "stencil" }, "Arquivo de telegramas"),
      h("button", { class: "btn btn--small", type: "button", onclick: closeArchive, "aria-label": "Fechar o arquivo" }, "Fechar")),
    h("div", { class: "archive__filter" },
      filterBtn("sec", `Esta seção (${SEC_NAMES[S.sec]})`),
      filterBtn("all", "Todas as seções")),
    h("div", { class: "archive__list" }, filt.length
      ? filt.map((tg) => telegramEl({
          head: tg.title || "Telegrama",
          meta: `Turno ${tg.turn}${tg.from ? ` · ${factionName(tg.from)}` : ""}`,
          body: tg.body || "",
          cipher: CIPHER_KINDS.has(tg.kind),
          cls: `telegram--${tg.kind || "geral"}`,
        }))
      : h("p", { class: "typed faint" }, "Nenhum telegrama nesta visão.")));
}

function openArchive() {
  renderArchive();
  $("archive").classList.remove("hidden");
  $("b-arquivo").setAttribute("aria-expanded", "true");
}

function closeArchive() {
  $("archive").classList.add("hidden");
  $("b-arquivo").setAttribute("aria-expanded", "false");
}

/* ------------------------------------------------------------ boletim do turno */
function readSeen() {
  try { return Number(localStorage.getItem(`${BOL_KEY}_${S.fid}`)) || 0; } catch { return 0; }
}
function writeSeen(t) {
  try { localStorage.setItem(`${BOL_KEY}_${S.fid}`, String(t)); } catch { /* sem armazenamento */ }
}

function renderBoletim() {
  const st = S.state;
  const r = st && st.last_report;
  const box = $("boletim");
  if (!r || !r.turn) {
    box.replaceChildren(
      h("h2", { class: "stencil", id: "boletim-title" }, "Boletim do turno"),
      h("p", { class: "typed" }, "Ainda não há boletim: ele sai quando o primeiro turno for resolvido."),
      h("div", { class: "row" }, h("button", { class: "btn btn--small", type: "button", onclick: closeBoletim }, "Fechar")));
    return;
  }
  box.replaceChildren(
    h("span", { class: "stamp stamp--ink boletim__stamp" }, "Confidencial"),
    h("header", { class: "boletim__head" },
      h("h2", { class: "stencil", id: "boletim-title" }, `Boletim do turno ${r.turn}`),
      h("p", { class: "typed faint" }, st.faction.name)),
    h("ul", { class: "typed boletim__lines" }, (r.lines || []).map((l) => h("li", null, l))),
    h("div", { class: "row" },
      h("button", { class: "btn btn--small btn--blue", type: "button", onclick: closeBoletim }, "Fechar boletim")));
}

function openBoletim() {
  renderBoletim();
  $("boletim").classList.remove("hidden");
  $("veil").classList.remove("hidden");
  $("boletim").focus?.();
}

function closeBoletim() {
  $("boletim").classList.add("hidden");
  $("veil").classList.add("hidden");
}

/** Abre o boletim sozinho quando há um relatório de turno que este PC ainda não viu. */
function maybeBoletim() {
  const st = S.state;
  const r = st && st.last_report;
  if (!r || !r.turn) return;
  if (r.turn > readSeen()) {
    writeSeen(r.turn);
    openBoletim();
  }
}

/* ------------------------------------------------------------ casca */
function syncSound() {
  $("b-som").textContent = sfx.muted ? "Som: desligado" : "Som: ligado";
  $("b-som").setAttribute("aria-pressed", sfx.muted ? "true" : "false");
}

function wireChrome() {
  for (const sec of SECTIONS) $(`tab-${sec}`).addEventListener("click", () => showSection(sec));
  $("tabs").addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const i = SECTIONS.indexOf(S.sec);
    const j = (i + (e.key === "ArrowRight" ? 1 : SECTIONS.length - 1)) % SECTIONS.length;
    showSection(SECTIONS[j]);
    $(`tab-${SECTIONS[j]}`).focus();
    e.preventDefault();
  });
  window.addEventListener("hashchange", () => {
    const v = location.hash.slice(1);
    if (SECTIONS.includes(v) && v !== S.sec) showSection(v, { save: false });
  });

  $("b-boletim").addEventListener("click", openBoletim);
  $("b-arquivo").addEventListener("click", () => ($("archive").classList.contains("hidden") ? openArchive() : closeArchive()));
  $("b-som").addEventListener("click", () => { sfx.setMuted(!sfx.muted); syncSound(); });
  $("b-sair").addEventListener("click", async () => {
    try { await api.post("/api/logout", {}); } catch { /* sai mesmo assim */ }
    location.href = PORTAL;
  });
  $("veil").addEventListener("click", closeBoletim);

  window.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "");
    if (e.key === "Escape") { closeBoletim(); closeArchive(); }
    if (!typing && (e.key === "m" || e.key === "M")) { sfx.setMuted(!sfx.muted); syncSound(); }
  });
  syncSound();
}

function showFailure(e) {
  $("loading-stamp").textContent = "Sem comunicação";
  $("loading-stamp").className = "stamp stamp--double";
  $("loading-note").textContent = (e && e.message) || "Não foi possível abrir o Quartel-General.";
  const back = h("a", { class: "btn btn--small", href: PORTAL }, "Voltar ao portão");
  $("loading-note").after(back);
}

async function boot() {
  wireChrome();
  try { S.clock = await serverClock(); } catch { S.clock = null; }
  loadCalc();
  try {
    S.map = await api.get("/api/public/map");
  } catch (e) {
    if (e && e.status === 401) { location.replace(PORTAL); return; }
    showFailure(e);
    return;
  }
  mountSections();
  try {
    await loadState();
  } catch (e) {
    if (e && e.status === 401) { location.replace(PORTAL); return; }
    showFailure(e);
    return;
  }
  await loadAllDossiers();
  showSection(initialSection(), { save: false });
  connect("faction", onMessage, onStatus);
  setInterval(tick, 250);
  // rede de segurança: se algum evento se perder, o estado é relido a cada minuto
  setInterval(() => loadState().catch(() => {}), 60000);
  document.body.dataset.status = "ready";
  $("loading").hidden = true;
}

window.__qg = { state: () => S.state, dossiers: () => S.dossiers, dispatch };
boot();
