/* =====================================================================
   teatro.js — a tela do projetor: mapa público, jornal, relógio split-flap,
   quadro de situação, boletim do tempo, telegramas do árbitro e a animação
   da resolução do turno.
   Parâmetros úteis (modo mock, ?mock=1):  &status=lobby|finished|paused
   Teclas: M = muda o som · F = tela cheia · R = reprisa a última resolução
   ===================================================================== */
import { api, serverClock, MOCK } from "./api.js";
import { connect } from "./ws.js";
import { sfx } from "./sfx.js";
import { renderMap } from "./map.js";
import { emblemSVG, FACTION_DEFAULTS } from "./emblems.js";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pad2 = (n) => String(Math.max(0, Math.floor(n))).padStart(2, "0");
const fmtVP = (v) => (Math.round(v * 100) / 100).toLocaleString("pt-BR", { minimumFractionDigits: Number.isInteger(v) ? 0 : 1, maximumFractionDigits: 2 });
const query = new URLSearchParams(location.search);

let mapData = null;
let ctrl = null;
let clock = null;
let state = null;            // último estado público aplicado
let animating = false;       // resolução em curso
let alarmedAt = { 60: false, 10: false };
let lastTurnShown = null;

/* ======================================================================
   split-flap
   ====================================================================== */
function makeFlap() {
  const f = document.createElement("div");
  f.className = "flap";
  f.innerHTML = `<div class="f-top"><div class="t"> </div></div><div class="f-bot"><div class="t"> </div></div>
                 <div class="f-ftop"><div class="t"> </div></div><div class="f-fbot"><div class="t"> </div></div>`;
  f.dataset.v = " ";
  return f;
}
function buildFlaps(container, pattern) {
  container.replaceChildren();
  const flaps = [];
  for (const ch of pattern) {
    if (ch === "d") { const f = makeFlap(); container.appendChild(f); flaps.push(f); }
    else { const s = document.createElement("span"); s.className = "sep"; s.textContent = ch; container.appendChild(s); }
  }
  return flaps;
}
function setFlap(f, ch, instant = false) {
  const old = f.dataset.v;
  if (old === ch) return;
  const tops = f.querySelectorAll(".f-top .t, .f-ftop .t");
  const bots = f.querySelectorAll(".f-bot .t, .f-fbot .t");
  const set = (nodes, v) => nodes.forEach((n) => { n.textContent = v; });
  f.dataset.v = ch;
  if (instant || old === " " || reduceMotion()) {
    set(tops, ch); set(bots, ch); f.classList.remove("go"); return;
  }
  // embaixo fica o antigo até a placa nova cair; em cima já está o novo
  set(f.querySelectorAll(".f-top .t"), ch);
  set(f.querySelectorAll(".f-bot .t"), old);
  set(f.querySelectorAll(".f-ftop .t"), old);
  set(f.querySelectorAll(".f-fbot .t"), ch);
  f.classList.remove("go");
  void f.offsetWidth;
  f.classList.add("go");
  sfx.flap();
  clearTimeout(f._t);
  f._t = setTimeout(() => { set(f.querySelectorAll(".f-bot .t"), ch); set(f.querySelectorAll(".f-ftop .t"), ch); f.classList.remove("go"); }, 470);
}
const reduceMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const turnFlaps = buildFlaps($("fl-turn"), "dd/dd");
const timeFlaps = buildFlaps($("fl-time"), "dd:dd");
function showDigits(flaps, str, instant) { [...str.replace(/[^0-9\-]/g, "")].forEach((ch, i) => flaps[i] && setFlap(flaps[i], ch, instant)); }

/* ======================================================================
   relógio e fase
   ====================================================================== */
function phaseInfo(g) {
  if (!g || g.status === "lobby") return { text: "PREPARAÇÃO", lamp: "idle" };
  if (g.status === "finished") return { text: "FIM", lamp: "fim" };
  if (g.status === "paused") return { text: "PAUSA", lamp: "pausa" };
  if (g.phase === "resolucao" || g.phase === "resolução") return { text: "RESOLUÇÃO", lamp: "resolucao" };
  // prazo vencido (ou animação em curso): o servidor ainda resolve, mas o telão já não é "planejamento"
  if (animating || (clock && g.deadline_ms - clock.now() <= 0)) return { text: "RESOLUÇÃO", lamp: "resolucao" };
  return { text: "PLANEJAMENTO", lamp: "plan" };
}
function remainingMs(g) {
  if (!g) return null;
  if (g.status === "running" && g.phase !== "resolucao") return Math.max(0, g.deadline_ms - clock.now());
  if (g.status === "lobby" || g.status === "finished") return null;
  if (g.phase === "resolucao") return 0;
  return Math.max(0, g.remaining_ms ?? 0);
}
let firstClock = true;
function tickClock() {
  const g = state && state.game;
  const info = phaseInfo(g);
  const rem = remainingMs(g);
  const clockEl = $("clock");
  const alarm = g && g.status === "running" && rem != null && rem > 0 && rem <= 60000;
  clockEl.classList.toggle("is-alarm", !!alarm);
  clockEl.dataset.lamp = alarm ? "alarm" : info.lamp;
  clockEl.parentElement.dataset.lamp = clockEl.dataset.lamp;
  if ($("phase-text").textContent !== info.text) $("phase-text").textContent = info.text;
  const turn = g ? g.turn || 0 : 0, max = g ? g.max_turns || 0 : 0;
  showDigits(turnFlaps, pad2(turn) + pad2(max), firstClock);
  if (rem == null) showDigits(timeFlaps, "----", firstClock);
  else {
    const s = Math.ceil(rem / 1000);
    showDigits(timeFlaps, pad2(Math.min(99, Math.floor(s / 60))) + pad2(s % 60), firstClock);
  }
  firstClock = false;
  if (alarm) {
    const s = Math.ceil(rem / 1000);
    if (s <= 60 && !alarmedAt[60]) { alarmedAt[60] = true; sfx.alarm(); }
    if (s <= 10 && !alarmedAt[10]) { alarmedAt[10] = true; sfx.alarm(); }
  } else if (!rem || rem > 61000) { alarmedAt = { 60: false, 10: false }; }
}

/* ======================================================================
   jornal
   ====================================================================== */
const KICKERS = { battle: "Frente de batalha", capture: "Conquista", event: "Acontecimentos", politics: "Política", weather: "Tempo" };
const DEFAULT_NEWS = [{
  turn: 0, kind: "politics", headline: "O CONTINENTE EM ARMAS",
  body: "As nações mobilizam seus exércitos nas fronteiras de Lebesgue. Os Estados-Maiores aguardam a primeira ordem do Árbitro; os telégrafos estão em silêncio.",
}];
let newsPage = 0;
let fitCount = 2;
let newsSig = "";
let newsTimer = null;

function renderNews(force = false) {
  const g = state.game || {};
  const body = $("news-body");
  const turn = g.turn || 0;
  const day = 10 + turn;
  $("np-date").textContent = `LEBESGUE, ${day} DE JUNHO DE 1943`;
  $("np-no").textContent = `Nº ${Math.max(1, turn)}`;
  const finished = g.status === "finished";
  $("np-edition").textContent = finished ? "EDIÇÃO ESPECIAL · FIM DA GUERRA · PREÇO 20 RÉIS" : `EDIÇÃO EXTRA · TURNO ${turn} · PREÇO 20 RÉIS`;

  const ranking = sortedFactions();
  let items = (state.news && state.news.length ? state.news : DEFAULT_NEWS).slice();
  let lead;
  if (finished && ranking.length) {
    const w = ranking[0];
    lead = { kind: "politics", headline: "FIM DA GUERRA", body: `O Estado-Maior declarou encerrado o conflito no Continente de Lebesgue. ${w.name} termina na frente, com ${fmtVP(w.vp)} pontos de vitória e ${w.territories} territórios sob sua bandeira.`, podium: true };
  } else lead = items.shift();
  const MAXI = 8;
  const pagesGuess = Math.max(1, Math.ceil(items.length / Math.max(1, fitCount)));
  newsPage = newsPage % pagesGuess;
  const sig = JSON.stringify([lead, items, finished, newsPage, fitCount, ranking.map((f) => f.id + f.vp)]);
  if (sig === newsSig && !force) return;
  const sameLead = newsSig !== "" && JSON.stringify(JSON.parse(newsSig)[0]) === JSON.stringify(lead);
  newsSig = sig;
  const slice = items.slice(newsPage * fitCount, newsPage * fitCount + MAXI);

  let html = `<div class="lead"><div class="kicker">${esc(KICKERS[lead.kind] || "Notícias")}</div><h2 class="headline">${esc(lead.headline)}</h2>`;
  if (lead.podium) html += podiumHTML(ranking);
  html += `<p class="deck">${esc(lead.body)}</p></div>`;
  html += `<div class="cols ${sameLead ? "is-swap" : ""}" id="cols">` + slice.map((n) =>
    `<article><div class="kicker">${esc(KICKERS[n.kind] || "Notícias")}</div><h3 class="headline headline--small">${esc(n.headline)}</h3><p class="txt">${esc(n.body)}</p></article>`).join("") + `</div>`;
  body.innerHTML = html;

  // ajusta quantas notícias cabem na coluna (as que não cabem passam para a próxima "página")
  const cols = $("cols");
  const arts = [...cols.children];
  let fit = 0;
  const lim = cols.clientHeight + 1;
  arts.forEach((a, i) => { if (a.offsetTop + a.offsetHeight <= lim + (a.offsetTop === arts[0].offsetTop ? 40 : 0)) fit = i + 1; else a.remove(); });
  if (fit % 2 === 1 && fit > 1 && arts[fit - 1] && arts[fit - 1].offsetTop > arts[0].offsetTop) { /* linha incompleta: mantém */ }
  fit = Math.max(1, fit);
  if (fit !== fitCount && items.length > 0 && !force) { fitCount = fit; newsSig = ""; renderNews(true); return; }
  fitCount = fit;
  const pages = Math.max(1, Math.ceil(items.length / fitCount));
  clearInterval(newsTimer);
  if (pages > 1) newsTimer = setInterval(() => { if (!animating) { newsPage = (newsPage + 1) % pages; renderNews(true); } }, 13000);
}
function podiumHTML(r) {
  const step = (f, pos) => f ? `<div class="podium__step podium__step--${pos}" data-faction="${f.id}"><div class="emb">${emblemSVG(f.id)}</div><div class="pos">${pos}º LUGAR</div><div class="nm">${esc(f.short || f.name)}</div><div class="pv">${fmtVP(f.vp)} PV</div></div>` : `<div></div>`;
  return `<div class="podium">${step(r[1], 2)}${step(r[0], 1)}${step(r[2], 3)}</div>`;
}
function newEdition() {
  const n = $("news");
  n.classList.remove("is-new"); void n.offsetWidth; n.classList.add("is-new");
  sfx.page();
}

/* ======================================================================
   quadro de situação
   ====================================================================== */
function sortedFactions() {
  const f = (state.factions || []).slice();
  f.forEach((x) => { const d = FACTION_DEFAULTS[x.id] || {}; x.short = x.short || d.short; x.name = x.name || d.name; x.color = x.color || d.color; });
  return f.sort((a, b) => (b.vp - a.vp) || (b.territories - a.territories) || a.id.localeCompare(b.id));
}
const boardRows = new Map();
function renderBoard() {
  const list = $("board-list");
  const order = sortedFactions();
  const firstTops = new Map([...boardRows].map(([id, li]) => [id, li.getBoundingClientRect().top]));
  $("board").dataset.count = String(order.length);
  order.forEach((f, i) => {
    let li = boardRows.get(f.id);
    if (!li) {
      li = document.createElement("li");
      li.dataset.faction = f.id;
      li.style.setProperty("--c", f.color);
      li.innerHTML = `<span class="rank"></span><span class="emb">${emblemSVG(f.id)}</span><span class="nm"><span class="n"></span><small class="cap"></small></span><span class="nums"><span class="vp"></span><span class="tr"></span></span>`;
      boardRows.set(f.id, li);
    }
    li.style.setProperty("--c", f.color);
    li.classList.toggle("is-out", !!f.capitulated);
    li.querySelector(".rank").textContent = i + 1;
    li.querySelector(".n").textContent = f.short || f.name;
    li.querySelector(".cap").innerHTML = f.capitulated ? `${esc(f.name)} <span class="out-tag">CAPITULOU</span>` : esc(f.name);
    const vp = li.querySelector(".vp");
    const txt = fmtVP(f.vp);
    if (vp.textContent && vp.textContent !== txt) { vp.classList.remove("is-bump"); void vp.offsetWidth; vp.classList.add("is-bump"); }
    vp.textContent = txt;
    li.querySelector(".tr").innerHTML = `${f.territories}<small>terr.</small>`;
    list.appendChild(li); // reordena
  });
  for (const [id, li] of boardRows) if (!order.some((f) => f.id === id)) { li.remove(); boardRows.delete(id); }
  // FLIP: as linhas deslizam para a nova posição
  if (!reduceMotion()) {
    for (const [id, li] of boardRows) {
      const was = firstTops.get(id);
      if (was == null) continue;
      const dy = was - li.getBoundingClientRect().top;
      if (Math.abs(dy) < 2) continue;
      li.style.transition = "none"; li.style.transform = `translateY(${dy}px)`;
      requestAnimationFrame(() => requestAnimationFrame(() => { li.style.transition = ""; li.style.transform = ""; }));
    }
  }
}

/* ======================================================================
   clima (ícones em traço de tinta)
   ====================================================================== */
const CLOUD = "M17 33H46a8.5 8.5 0 0 0 .5-17 12 12 0 0 0-23-2.5A10 10 0 0 0 17 33Z";
const ICONS = {
  0: `<g fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="32" cy="26" r="9.5"/><path d="M32 8v6M32 38v6M14 26h6M44 26h6M19.3 13.3l4.2 4.2M40.5 34.5l4.2 4.2M44.7 13.3l-4.2 4.2M23.5 34.5l-4.2 4.2"/><path d="M27.5 24.5q2-2.5 5-1.5" stroke-width="1.5" opacity=".6"/></g>`,
  1: `<g fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="${CLOUD}" transform="translate(0 -4)"/><path d="M21 34l-3 8M31 34l-3 8M41 34l-3 8M26 43l-2.6 6M36 43l-2.6 6" stroke-width="2.2"/></g>`,
  2: `<g fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="${CLOUD}" transform="translate(0 -6)"/><path d="M34 29l-8 10h7l-5 10" stroke-width="3"/><path d="M17 33l-3 7M47 33l-3 7M22 43l-2.4 5.5" stroke-width="2.1"/></g>`,
};
const WNAMES = ["limpo", "chuva", "tempestade"];
let weatherSig = "";
function renderWeather() {
  const w = state.weather || {};
  const regions = (mapData && mapData.climate_regions) || [{ id: "norte", name: "Norte" }, { id: "centro", name: "Centro" }, { id: "sul", name: "Sul" }];
  const sig = JSON.stringify(w);
  if (sig === weatherSig) return;
  weatherSig = sig;
  $("weather-cells").innerHTML = regions.map((r) => {
    const v = Number.isInteger(w[r.id]) ? w[r.id] : 0;
    return `<div class="wcell" data-w="${v}"><svg viewBox="0 0 64 52" aria-hidden="true">${ICONS[v]}</svg><div><b>${esc(r.name)}</b><span>${WNAMES[v]}</span></div></div>`;
  }).join("");
}

/* ======================================================================
   estados da tela: lobby / correndo / fim
   ====================================================================== */
function applyOverlay() {
  const g = state.game || {};
  const ov = $("overlay");
  document.body.dataset.status = g.status || "lobby";
  const stamp = $("overlay-stamp");
  if (g.status === "lobby") {
    $("overlay-line1").textContent = "AGUARDANDO";
    $("overlay-line2").textContent = "ORDENS DO ÁRBITRO";
    $("overlay-note").textContent = "O Teatro de Operações será aberto quando o Árbitro iniciar a guerra.";
    stamp.classList.remove("overlay__stamp--ink");
    showOverlay(ov, stamp);
  } else if (g.status === "finished") {
    $("overlay-line1").textContent = "FIM DA";
    $("overlay-line2").textContent = "GUERRA";
    const w = sortedFactions()[0];
    $("overlay-note").textContent = w ? `Vitória de ${w.short || w.name}. O Estado-Maior agradece aos comandantes.` : "O Estado-Maior agradece aos comandantes.";
    stamp.classList.add("overlay__stamp--ink");
    showOverlay(ov, stamp);
  } else if (!ov.classList.contains("hidden")) {
    ov.classList.add("hidden");
  }
}
let overlayKind = "";
function showOverlay(ov, stamp) {
  const kind = state.game.status;
  if (overlayKind === kind && !ov.classList.contains("hidden")) return;
  overlayKind = kind;
  ov.classList.remove("hidden");
  stamp.classList.remove("is-hit"); void stamp.offsetWidth; stamp.classList.add("is-hit");
  setTimeout(() => sfx.stamp(), 120);
}

/* ======================================================================
   aplicar estado (sempre que chega um GET novo)
   ====================================================================== */
function applyState(s) {
  const prevTurn = state && state.game ? state.game.turn : null;
  state = s;
  if (MOCK && query.get("status")) s.game.status = query.get("status");
  if (MOCK && query.get("six") && s.factions.length < 6) {
    s.factions.push({ id: "HIL", name: "Federação de Hilbertânia", short: "Hilbertânia", color: "#4d5b24", vp: 5.5, territories: 4 }, { id: "RIE", name: "Confederação de Riemânnia", short: "Riemânnia", color: "#3b5b5a", vp: 4, territories: 3, capitulated: true });
  }
  if (MOCK && query.get("remaining") && s.game.status === "running") s.game.deadline_ms = Date.now() + Number(query.get("remaining")) * 1000;
  if (MOCK && query.get("status") === "paused") { s.game.status = "paused"; s.game.remaining_ms = s.game.remaining_ms || 300000; }
  if (ctrl) ctrl.update(s);
  renderBoard();
  renderWeather();
  renderNews();
  applyOverlay();
  tickClock();
  if (prevTurn != null && s.game && s.game.turn !== prevTurn) { newEdition(); alarmedAt = { 60: false, 10: false }; }
}

let pendingRefresh = false;
async function refresh() {
  if (animating) { pendingRefresh = true; return; }
  try {
    const s = await api.get("/api/public/state");
    if (animating) { pendingRefresh = true; return; }
    applyState(s);
  } catch (e) { console.warn("Falha ao obter o estado:", e.message); }
}

/* ======================================================================
   resolução: escurece a lateral, anima o mapa, atualiza o jornal
   ====================================================================== */
const queue = [];
let running = false;
function enqueue(job) { queue.push(job); if (!running) drain(); }
async function drain() {
  running = true;
  while (queue.length) { try { await queue.shift()(); } catch (e) { console.error(e); } }
  running = false;
}

function slipShow(info) {
  const slip = $("slip");
  if (info.kind === "done") { slip.classList.add("hidden"); return; }
  if (info.kind !== "battle" && info.kind !== "moves") return;
  const wasHidden = slip.classList.contains("hidden");
  slip.classList.remove("hidden");
  if (wasHidden) { slip.style.animation = "none"; void slip.offsetWidth; slip.style.animation = ""; }
  if (info.kind === "battle") {
    const b = info.battle;
    $("slip-kicker").textContent = `COMUNICADO DE CAMPANHA · BATALHA ${info.index + 1} DE ${info.total}`;
    $("slip-line").textContent = `${info.attackerName} ataca ${info.toName}`;
    $("slip-sub").innerHTML = `${b.att_before} contra ${b.def_before} · <b>${info.captured ? "TERRITÓRIO TOMADO" : b.result === "stalemate" ? "IMPASSE: O ATACANTE RECUA" : "ATAQUE REPELIDO"}</b>`;
  } else {
    $("slip-kicker").textContent = "COMUNICADO DE CAMPANHA · MOVIMENTAÇÕES";
    $("slip-line").textContent = "Tropas em marcha";
    $("slip-sub").textContent = `${info.total} deslocamento${info.total === 1 ? "" : "s"} registrado${info.total === 1 ? "" : "s"} pelo Estado-Maior`;
  }
}

async function runResolution(report, opts = {}) {
  if (!ctrl) return;
  animating = true;
  $("curtain").classList.add("is-on");
  sfx.page();
  const hasBattles = report && report.battles && report.battles.length;
  try {
    await ctrl.animateResolution(report || {}, {
      revert: !!opts.revert,
      onStep: (info) => {
        slipShow(info);
        if (info.kind === "impact") sfx.thud();
        if (info.kind === "captured") setTimeout(() => sfx.stamp(), 60);
        if (info.kind === "battle") sfx.morse("..");
      },
    });
  } finally {
    animating = false;
    $("slip").classList.add("hidden");
    $("curtain").classList.remove("is-on");
    pendingRefresh = false;
    await refresh();
    if (hasBattles || (report && report.moves && report.moves.length)) newEdition();
  }
}

/* ======================================================================
   telegrama do árbitro
   ====================================================================== */
const drops = [];
let dropBusy = false;
function enqueueDrop(data) { drops.push(data); if (!dropBusy) showNextDrop(); }
async function showNextDrop() {
  dropBusy = true;
  while (drops.length) {
    const d = drops.shift();
    const text = String(d.text || d.message || d.body || "").toUpperCase();
    const host = $("drop");
    const to = d.to && d.to !== "all" ? `PARA ${d.to}` : "A TODAS AS NAÇÕES";
    const tg = document.createElement("div");
    tg.className = "telegram is-typing";
    tg.innerHTML = `<div class="telegram__head"><span>Telegrama oficial · Árbitro</span><span>${esc(to)}</span></div><div><span class="telegram__strip"></span></div><div class="telegram__foot">STOP</div>`;
    host.replaceChildren(tg);
    sfx.morse("STOP");
    const strip = tg.querySelector(".telegram__strip");
    await sleep(900);
    for (let i = 0; i < text.length; i++) {
      strip.textContent = text.slice(0, i + 1);
      if (i % 2 === 0 && text[i] !== " ") sfx.key();
      await sleep(26);
    }
    tg.classList.remove("is-typing");
    await sleep(Math.min(16000, 5000 + text.length * 70));
    tg.classList.add("is-leaving");
    await sleep(650);
    host.replaceChildren();
  }
  dropBusy = false;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ======================================================================
   mensagens do servidor
   ====================================================================== */
function onMessage(msg) {
  const { type, data } = msg;
  switch (type) {
    case "resolution": enqueue(() => runResolution((data && data.report) || data)); break;
    case "broadcast": enqueueDrop(data || {}); break;
    case "phase": case "state": case "news": refresh(); break;
    default: break;
  }
}
function onStatus(s, info) {
  const tag = $("conn-tag");
  tag.dataset.s = s;
  tag.textContent = s === "open" ? "LINHA ABERTA" : s === "mock" ? "SIMULADO" : s === "connecting" ? "CONECTANDO…" : "LINHA CAÍDA";
  if (s === "open" && info && info.reconnected) refresh();
}

/* ======================================================================
   partida
   ====================================================================== */
async function boot() {
  const soundTag = $("sound-tag");
  const syncSoundTag = () => {
    soundTag.textContent = sfx.muted ? "SOM: DESLIGADO (M)" : sfx.unlocked ? "SOM: LIGADO (M)" : "SOM: TOQUE PARA ATIVAR";
  };
  soundTag.addEventListener("click", () => { if (sfx.unlocked) sfx.setMuted(!sfx.muted); syncSoundTag(); });
  window.addEventListener("pointerdown", () => setTimeout(syncSoundTag, 50), true);
  window.addEventListener("keydown", (e) => {
    if (e.key === "m" || e.key === "M") { sfx.setMuted(!sfx.muted); syncSoundTag(); }
    else if (e.key === "f" || e.key === "F") { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen?.(); }
    else if ((e.key === "r" || e.key === "R") && state && state.last_resolution) window.__replay();
  });
  syncSoundTag();

  clock = await serverClock();
  try {
    mapData = await api.get("/api/public/map");
  } catch (e) {
    $("overlay").classList.remove("hidden");
    $("overlay-line1").textContent = "SEM";
    $("overlay-line2").textContent = "COMUNICAÇÃO";
    $("overlay-note").textContent = e.message;
    return;
  }
  ctrl = renderMap($("map"), mapData, { mode: "public", interactive: false });
  window.__ctrl = ctrl;
  await refresh();
  connect("public", onMessage, onStatus);
  setInterval(tickClock, 250);
  document.body.classList.add("ready");
  // esconde as etiquetas depois de um tempo para limpar a projeção (voltam ao passar o mouse)
  if (!MOCK) setTimeout(() => $("conn-tag").parentElement.classList.add("is-quiet"), 20000);
  if (query.get("demo") === "1") setTimeout(() => window.__replay(), 2500);
}

/** Reprisa a última resolução (revertendo as capturas para animá-las). */
window.__replay = () => { if (state && state.last_resolution) enqueue(() => runResolution(state.last_resolution, { revert: true })); };
window.__state = () => state;
window.__broadcast = (text) => enqueueDrop({ text });

boot();
