/* =====================================================================
   arbitro.js — a Mesa do Árbitro (painel de controle da partida).
   ---------------------------------------------------------------------
   Login POST /api/admin/login · estado GET /api/admin/state (refeito a cada
   evento do canal admin, com debounce de 300 ms, e a cada 5 s) · relógio do
   turno = deadline_ms − serverClock.now() · teclas da partida · novo jogo com
   dupla confirmação · credenciais impressas · avisos · eventos · ajustes de
   emergência (nação e território) · ordens do turno · segredos (ocultos por
   padrão) · rollback · diário ao vivo (canal admin) e registros do estado.
   Mapa: renderMap em modo "faction" com todos os territórios em visibility
   "own", para o árbitro ver as tropas exatas de todas as nações.
   Modo mock (?mock=1): lê web/mock/admin_state.json e admin_events.json.
   ===================================================================== */
import { api, serverClock, MOCK } from "./api.js";
import { connect } from "./ws.js";
import { sfx } from "./sfx.js";
import { renderMap } from "./map.js";
import { emblemSVG, FACTION_DEFAULTS } from "./emblems.js";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const p2 = (n) => String(Math.max(0, Math.floor(n))).padStart(2, "0");
const fmtNum = (v, max = 1) => (v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toLocaleString("pt-BR", { maximumFractionDigits: max }));
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, Number(v) || 0));
const hms = (ms) => { const d = new Date(ms); return [d.getHours(), d.getMinutes(), d.getSeconds()].map(p2).join(":"); };
const clockText = (ms) => { const s = Math.ceil(ms / 1000); return `${p2(Math.floor(s / 60))}:${p2(s % 60)}`; };

const SECTIONS = [
  ["intendencia", "INT", "Intendência"],
  ["operacoes", "OPE", "Operações"],
  ["inteligencia", "SIG", "Inteligência"],
  ["governo", "GOV", "Governo"],
];
const STATES = ["limpo", "chuva", "tempestade"];
const REGIONS = [["norte", "Norte"], ["centro", "Centro"], ["sul", "Sul"]];
const TERRAIN = { planicie: "planície", floresta: "floresta", montanha: "montanha", pantano: "pântano", urbano: "urbano" };
const DIARY_MAX = 200;

/* ------------------------------------------------------------ estado */
let S = null;                 // última resposta de /api/admin/state
let TER = new Map();          // id -> território (de S)
let CREDS = {};               // nação -> senha (GET /api/admin/credentials)
let eventCatalog = [];        // GET /api/admin/events
let clock = null;             // serverClock()
let mapCtrl = null;
let mapData = null;
let authed = false;
let setupDone = false;
let showSecrets = false;
let selectedTerritory = "T01";
let refreshQueued = null;
let refreshing = false;
let refreshAgain = false;
let lastRefreshError = "";
const dirty = { nation: false, territory: false };
const diary = [];             // {t, tag, tone, text}

/* ------------------------------------------------------------ dados */
const fetchMock = async (file) => {
  const res = await fetch(new URL(file, document.baseURI), { cache: "no-store" });
  return res.json();
};

/** Lê rotas do árbitro. No modo mock, o estado vem do arquivo de exemplo. */
async function getAdmin(path) {
  if (!MOCK) return api.get(path);
  if (path === "/api/admin/state") {
    const s = await fetchMock("mock/admin_state.json");
    s.game.now_ms = Date.now();
    s.game.deadline_ms = Date.now() + s.game.remaining_ms;   // relógio vivo no mock
    return s;
  }
  if (path === "/api/admin/events") return fetchMock("mock/admin_events.json");
  if (path === "/api/admin/credentials") return (await fetchMock("mock/admin_state.json")).credentials;
  return api.get(path);
}

function sortedFactions() {
  return Object.values((S && S.factions) || {}).sort((a, b) => a.slot - b.slot);
}
const factionName = (fid) => (S && S.factions[fid] && S.factions[fid].name) || (FACTION_DEFAULTS[fid] || {}).name || fid || "neutro";
const factionShort = (fid) => (S && S.factions[fid] && S.factions[fid].short) || (FACTION_DEFAULTS[fid] || {}).short || fid || "neutro";

function factionList() {
  return sortedFactions().map((f) => {
    const d = FACTION_DEFAULTS[f.id] || {};
    return { id: f.id, name: f.name || d.name, short: f.short || d.short, color: d.color || "#8f866e" };
  });
}

async function loadState() {
  const s = await getAdmin("/api/admin/state");
  S = s;
  TER = new Map((s.territories || []).map((t) => [t.id, t]));
  return s;
}

async function loadCreds() {
  try { CREDS = (await getAdmin("/api/admin/credentials")) || {}; renderCreds(); } catch (err) { if (err.status === 401) lockOut(); }
}

function remainingMs() {
  const g = S.game;
  if (g.status === "running") return Math.max(0, g.deadline_ms - (clock ? clock.now() : Date.now()));
  return Math.max(0, g.remaining_ms || 0);
}

/* ------------------------------------------------------------ vistas */
function showView(name) {
  $("gate").hidden = name !== "gate";
  $("console").hidden = name !== "console";
  document.body.dataset.view = name;
}

function gateError(msg) {
  $("gate-error").textContent = msg || "";
  const stamp = document.querySelector(".gate__stamp");
  stamp.textContent = msg ? "negado" : "restrito";
  stamp.classList.remove("is-hit"); void stamp.offsetWidth; stamp.classList.add("is-hit");
}

function flash(text, kind = "") {
  const t = $("telex");
  t.classList.toggle("is-ok", kind === "ok");
  t.classList.toggle("is-err", kind === "err");
  $("telex-time").textContent = hms(Date.now());
  $("telex-text").textContent = text;
}

function setLink(status) {
  const map = {
    open: ["open", "ao vivo"],
    connecting: ["connecting", "conectando"],
    closed: ["closed", "sem canal, tentando de novo"],
    mock: ["mock", "modo de teste"],
  };
  const [st, label] = map[status] || ["closed", status];
  $("link-state").dataset.state = st;
  $("link-text").textContent = label;
}

/** Só troca o HTML se mudou (preserva foco, rolagem e o que está aberto). */
function setHTML(el, html, keepOpen = false) {
  if (el._html === html) return;
  const open = keepOpen ? new Set([...el.querySelectorAll("details[open][data-key]")].map((d) => d.dataset.key)) : null;
  el._html = html;
  el.innerHTML = html;
  if (open) el.querySelectorAll("details[data-key]").forEach((d) => { if (open.has(d.dataset.key)) d.open = true; });
}

function setOptions(sel, items) {
  const sig = JSON.stringify(items);
  if (sel._sig === sig) return;
  const prev = sel.value;
  sel._sig = sig;
  sel.innerHTML = items.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("");
  if (items.some(([v]) => v === prev)) sel.value = prev;
}

/* ------------------------------------------------------------ confirmação */
/** Caixa de confirmação (dialog). Com `word`, o botão só libera ao digitar a palavra. */
function ask({ title, body, ok = "CONFIRMAR", danger = false, word = null }) {
  const dlg = $("dlg-ask");
  const okBtn = $("ask-ok");
  const input = $("ask-word-input");
  $("ask-title").textContent = title;
  $("ask-body").textContent = body;
  okBtn.textContent = ok;
  const stamp = $("ask-stamp");
  stamp.textContent = danger ? "atenção" : "confirmar";
  stamp.classList.toggle("stamp--blue", !danger);
  $("ask-word-wrap").hidden = !word;
  $("ask-word").textContent = word || "";
  input.value = "";
  const check = () => { okBtn.disabled = !!word && input.value.trim().toUpperCase() !== word; };
  input.oninput = check;
  check();
  return new Promise((resolve) => {
    let result = false;
    const onOk = () => { result = true; dlg.close(); };
    const onCancel = () => dlg.close();
    const onKey = (e) => { if (e.key === "Enter" && word && !okBtn.disabled) { e.preventDefault(); onOk(); } };
    const onClose = () => {
      okBtn.removeEventListener("click", onOk);
      $("ask-cancel").removeEventListener("click", onCancel);
      input.removeEventListener("keydown", onKey);
      input.oninput = null;
      resolve(result);
    };
    okBtn.addEventListener("click", onOk);
    $("ask-cancel").addEventListener("click", onCancel);
    input.addEventListener("keydown", onKey);
    dlg.addEventListener("close", onClose, { once: true });
    dlg.showModal();
    (word ? input : $("ask-cancel")).focus();
  });
}

/* ------------------------------------------------------------ atualização */
function scheduleRefresh(delay = 300) {
  clearTimeout(refreshQueued);
  refreshQueued = setTimeout(refresh, delay);
}

async function refresh() {
  if (!authed) return;
  if (refreshing) { refreshAgain = true; return; }
  refreshing = true;
  try {
    await loadState();
    lastRefreshError = "";
    renderAll();
  } catch (err) {
    if (err.status === 401) lockOut();
    else if (err.message !== lastRefreshError) {
      lastRefreshError = err.message;
      flash(`Falha ao atualizar o estado: ${err.message}`, "err");
    }
  } finally {
    refreshing = false;
    if (refreshAgain) { refreshAgain = false; scheduleRefresh(0); }
  }
}

function lockOut() {
  authed = false;
  closeCreds();
  showView("gate");
  gateError("");
  $("gate-error").textContent = "A sessão do árbitro terminou. Digite a senha de novo.";
}

async function enter() {
  await loadState();          // 401 propaga para quem chamou
  authed = true;
  showView("console");
  if (!setupDone) await setup();
  renderAll();
  loadCreds();
}

async function setup() {
  clock = await serverClock();
  mapData = await api.get("/api/public/map");
  mapCtrl = renderMap($("map"), mapData, {
    mode: "faction", interactive: true, showIds: true, factions: factionList(),
  });
  mapCtrl.onTerritoryHover((id) => showCaption(id));
  mapCtrl.onTerritoryClick((id) => { if (id) pickTerritory(id); });
  eventCatalog = await getAdmin("/api/admin/events").catch(() => []);
  connect("admin", (msg) => { pushDiary(msg); scheduleRefresh(); }, (status, info) => {
    setLink(status);
    if (status === "open" && info && info.reconnected) scheduleRefresh(0);
  });
  setInterval(() => refresh(), 5000);
  setInterval(() => tickClock(), 250);
  setupDone = true;           // só depois de tudo montado: uma falha aqui é refeita no próximo login
}

/* ------------------------------------------------------------ render */
function renderAll() {
  if (!S) return;
  renderControls();
  tickClock();
  renderNations();
  renderMapState();
  renderSelectOptions();
  renderEvents();
  renderOrders();
  renderRecords();
  renderArauto();
  renderCreds();
  renderRollbackDefault();
  if (showSecrets) renderSecrets();
  renderDiary();
  if (!dirty.nation) fillNationForm();
  if (!dirty.territory) fillTerritoryForm();
}

function renderControls() {
  const g = S.game;
  const st = g.status;
  const canTime = st === "running" || st === "paused";
  $("btn-start").disabled = st !== "lobby";
  $("btn-pause").disabled = st !== "running";
  $("btn-resume").disabled = st !== "paused";
  $("btn-plus1").disabled = !canTime;
  $("btn-plus5").disabled = !canTime;
  $("btn-resolve").disabled = !canTime;
  $("turn-num").textContent = st === "lobby" ? `0 / ${g.max_turns}` : `${g.turn} / ${g.max_turns}`;
  $("phase-name").textContent = g.phase || "";
}

/** Relógio, lâmpadas e texto de estado. Roda a cada 250 ms. */
function tickClock() {
  if (!S) return;
  const g = S.game;
  const ms = remainingMs();
  const resolving = g.status === "running" && ms <= 0;
  const run = g.status === "running" && !resolving;
  const clockEl = $("clock");
  clockEl.textContent = clockText(ms);
  clockEl.classList.toggle("is-dim", g.status === "lobby");
  clockEl.classList.toggle("is-red", resolving || g.status === "finished");
  $("lamp-run").classList.toggle("is-on", run);
  $("lamp-pause").classList.toggle("is-on", g.status === "paused");
  $("lamp-end").classList.toggle("is-on", resolving || g.status === "finished");
  $("lamp-end").classList.toggle("is-blink", resolving);

  const status = $("status-text");
  let text = "aguardando início", tone = "";
  if (g.status === "running" && resolving) { text = "resolvendo o turno"; tone = "red"; }
  else if (g.status === "running") text = "em curso";
  else if (g.status === "paused") { text = "pausada"; tone = "amber"; }
  else if (g.status === "finished") {
    text = "guerra encerrada";
    tone = "red";
  }
  status.textContent = text;
  if (tone) status.dataset.tone = tone; else delete status.dataset.tone;
}

function renderNations() {
  const html = sortedFactions().map((f) => {
    const st = f.stock || {};
    const moral = clamp(f.morale, 0, 100);
    const sects = SECTIONS.map(([k, code, label]) => {
      const sent = !!(f.orders_submitted && f.orders_submitted[k]);
      return `<span class="sect${sent ? " is-sent" : ""}" title="${esc(label)}: ${sent ? "ordem enviada neste turno" : "sem ordem neste turno"}">` +
        `<span class="tick" aria-hidden="true"></span>${code}<span class="sr-only">${sent ? " enviada" : " pendente"}</span></span>`;
    }).join("");
    return `<article class="nation${f.capitulated ? " is-capitulated" : ""}" data-faction="${esc(f.id)}">
      ${f.capitulated ? '<span class="stamp mini-stamp">capitulou</span>' : ""}
      <header class="nation__head">
        <span class="nation__emb" aria-hidden="true">${emblemSVG(f.id)}</span>
        <span class="nation__name">${esc(factionShort(f.id))}</span>
        <span class="nation__code">${esc(f.id)}</span>
      </header>
      <p class="nation__line"><b>ALI</b>${fmtNum(st.ALI)} <b>ACO</b>${fmtNum(st.ACO)} <b>COM</b>${fmtNum(st.COM)}</p>
      <p class="nation__line"><b>MOR</b>${fmtNum(moral, 0)}<span class="bar"><i style="width:${moral}%"></i></span> <b>TROP</b>${f.troops_total ?? "—"} <b>TER</b>${f.territories ?? "—"}</p>
      <p class="nation__line"><b>PV</b>${fmtNum(f.vp, 2)} <b>DESAF</b>${f.challenges_solved ?? 0}</p>
      <div class="nation__sects">${sects}</div>
    </article>`;
  }).join("");
  setHTML($("nations"), html);
}

function renderMapState() {
  if (!mapCtrl) return;
  mapCtrl.update({
    factions: factionList(),
    territories: S.territories.map((t) => ({ id: t.id, owner: t.owner, troops: t.troops, troops_range: null, visibility: "own" })),
  });
}

function renderSelectOptions() {
  const fids = sortedFactions().map((f) => f.id);
  setOptions($("aviso-to"), [["all", "Todas as nações"], ...fids.map((id) => [id, factionName(id)])]);
  setOptions($("adj-faction"), fids.map((id) => [id, factionName(id)]));
  setOptions($("adj-territory"), (S.territories || []).map((t) => [t.id, `${t.id} · ${t.name}`]));
  setOptions($("adj-owner"), [["", "neutro"], ...fids.map((id) => [id, factionName(id)])]);
  const maxT = Math.max(1, S.game.max_turns || 1);
  setOptions($("rb-turn"), Array.from({ length: maxT }, (_, i) => [String(i + 1), `turno ${i + 1}`]));
}

function renderRollbackDefault() {
  const sel = $("rb-turn");
  if (sel.dataset.touched) return;
  const t = Math.max(1, (S.game.turn || 1) - 1);
  sel.value = String(t);
}

function fillNationForm() {
  const f = S.factions[$("adj-faction").value];
  if (!f) return;
  const r = (v) => Math.round((Number(v) || 0) * 100) / 100;
  $("adj-ali").value = r(f.stock.ALI);
  $("adj-aco").value = r(f.stock.ACO);
  $("adj-com").value = r(f.stock.COM);
  $("adj-morale").value = r(f.morale);
}

function fillTerritoryForm() {
  const t = TER.get($("adj-territory").value);
  if (!t) return;
  $("adj-troops").value = t.troops;
  $("adj-owner").value = t.owner || "";
}

function renderEvents() {
  const done = {};
  for (const e of S.event_log || []) (done[e.id] ||= []).push(e.turn);
  const playable = S.game.status === "running" || S.game.status === "paused";
  $("eventos-hint").textContent = playable
    ? "Eventos valem a partir de agora, para as nações que estiverem no turno em curso."
    : "Eventos só podem ser disparados com a partida rodando ou pausada.";
  const html = eventCatalog.map((ev) => `
    <li>
      <div>
        <div class="ev-name">${esc(ev.name)}</div>
        <div class="ev-desc">${esc(ev.description)}</div>
        ${done[ev.id] ? `<div class="ev-done">disparado no turno ${done[ev.id].join(", ")}</div>` : ""}
      </div>
      <button class="btn btn--stamp btn--small" type="button" data-event="${esc(ev.id)}"${playable ? "" : " disabled"}>DISPARAR</button>
    </li>`).join("") || `<li><span class="typed faint">Catálogo de eventos indisponível.</span></li>`;
  setHTML($("event-list"), html);
}

function renderOrders() {
  const html = sortedFactions().map((f) => {
    const secs = SECTIONS.map(([k, , label]) => {
      const payload = (f.orders || {})[k];
      if (payload == null) return `<details><summary class="is-empty">${esc(label)} <span class="when">sem ordem</span></summary></details>`;
      const at = (f.orders_at || {})[k];
      return `<details data-key="${esc(f.id)}:${k}"><summary>${esc(label)} <span class="when">enviada ${at ? hms(at) : ""}</span></summary>` +
        `<pre>${esc(JSON.stringify(payload, null, 2))}</pre></details>`;
    }).join("");
    return `<article class="paper order-sheet">
      <header class="order-sheet__head"><span class="nation__emb" data-faction="${esc(f.id)}" aria-hidden="true">${emblemSVG(f.id)}</span>
        <h3 class="stencil">${esc(factionShort(f.id))}</h3><span class="typed faint">turno ${S.game.turn}</span></header>
      ${secs}
    </article>`;
  }).join("");
  setHTML($("orders"), html, true);
}

function describeKey(fid, cid, k, gridLabel) {
  switch (k.kind) {
    case "leontief": return `x* = (${k.x.map((v) => fmtNum(v, 2)).join("; ")}) · d = (${k.d.map((v) => fmtNum(v, 1)).join("; ")})`;
    case "markov": return `P(tempestade) = ${fmtNum(k.p, 3)} · região ${k.region} · estado atual ${STATES[k.state] ?? k.state}`;
    case "depot": return `alvo ${k.target} em ${k.territory} (${gridLabel(k.true)}) · estimativa ${(k.est || []).map((v) => fmtNum(v, 0)).join(", ")}`;
    case "ols": return `β₂ (propaganda) = ${fmtNum(k.beta, 3)}`;
    default: return JSON.stringify(k);
  }
}

function renderSecrets() {
  const gridLabel = (p) => (mapCtrl && p ? mapCtrl.gridLabel(p[0], p[1]) : "—");
  const fids = sortedFactions();

  // telegramas: cifrado e em claro
  const tele = [];
  for (const f of fids) {
    for (const tg of f.telegrams || []) {
      const plain = (f.telegrams_plain || {})[tg.id];
      if (plain == null) continue;
      tele.push({ turn: tg.turn, at: tg.at_ms, to: f.id, from: tg.from, kind: tg.kind, body: tg.body, plain });
    }
  }
  tele.sort((a, b) => (b.turn - a.turn) || (b.at - a.at));
  const KIND = { intercept: "interceptado", flash: "relâmpago", report: "relatório", broadcast: "aviso", diplomacy: "diplomacia" };
  const teleRows = tele.slice(0, 60).map((r) =>
    `<tr><td>${r.turn}</td><td>${esc(r.to)}</td><td>${esc(r.from || "—")}</td><td>${esc(KIND[r.kind] || r.kind)}</td>` +
    `<td class="mono-cell">${esc(r.body)}</td><td class="txt">${esc(r.plain)}</td></tr>`).join("") ||
    `<tr><td colspan="6" class="txt">Nenhum telegrama com texto claro ainda.</td></tr>`;

  // gabaritos
  const keyRows = [];
  for (const f of fids) {
    const keys = (S.challenge_keys || {})[f.id] || {};
    const cst = (S.challenge_state || {})[f.id] || {};
    for (const [cid, k] of Object.entries(keys)) {
      const st = cst[cid] || {};
      keyRows.push(`<tr><td>${esc(f.id)}</td><td class="mono-cell">${esc(cid)}</td>` +
        `<td class="txt">${esc(describeKey(f.id, cid, k, gridLabel))}</td>` +
        `<td>${st.solved ? "resolvido" : `${st.attempts_left ?? "?"} tent.`}</td></tr>`);
    }
  }

  // depósitos e clima
  const depotRows = fids.map((f) => {
    const d = (S.depots || {})[f.id];
    if (!d) return "";
    const t = TER.get(d.territory);
    return `<tr><td>${esc(f.id)}</td><td class="txt">${esc(d.territory)} · ${esc(t ? t.name : "")}</td>` +
      `<td class="mono-cell">${gridLabel(d.point)} (${fmtNum(d.point[0], 0)}, ${fmtNum(d.point[1], 0)})</td></tr>`;
  }).join("");
  const weather = (S.last_resolution || {}).weather || {};
  const climateRows = REGIONS.map(([id, name]) => {
    const c = (S.climate || {})[id];
    return `<tr><td>${esc(name)}</td><td>${esc(STATES[weather[id]] ?? "—")}</td><td>${esc(c ? STATES[c.next] : "—")}</td></tr>`;
  }).join("");

  // cifra, matriz técnica e coeficientes do moral
  const mat = (M, dec) => (M || []).map((row) => row.map((v) => fmtNum(v, dec)).join(" ")).join(" / ");
  const hillRows = fids.map((f) => {
    const K = f.cipher_key;
    return `<tr><td>${esc(f.id)}</td><td class="mono-cell">${K ? `[${mat(K, 0)}]` : "—"}</td>` +
      `<td>${f.cipher_gen ?? "—"}</td><td class="mono-cell">${esc(mat(f.A_turn, 3))}</td>` +
      `<td class="mono-cell">${(f.betas || []).map((b) => fmtNum(b, 2)).join(" ")}</td></tr>`;
  }).join("");

  const html = `
    <div class="wide">
      <h3 class="stencil">Telegramas: cifrado e texto claro</h3>
      <table class="ledger"><thead><tr><th>turno</th><th>recebido por</th><th>origem</th><th>tipo</th><th>cifrado</th><th>em claro</th></tr></thead>
      <tbody>${teleRows}</tbody></table>
    </div>
    <div>
      <h3 class="stencil">Gabaritos dos desafios</h3>
      <table class="ledger"><thead><tr><th>nação</th><th>desafio</th><th>gabarito</th><th>estado</th></tr></thead>
      <tbody>${keyRows.join("") || `<tr><td colspan="4" class="txt">Sem desafios neste turno.</td></tr>`}</tbody></table>
    </div>
    <div>
      <h3 class="stencil">Depósitos de suprimento</h3>
      <table class="ledger"><thead><tr><th>nação</th><th>território</th><th>quadrícula</th></tr></thead>
      <tbody>${depotRows || `<tr><td colspan="3" class="txt">—</td></tr>`}</tbody></table>
      <h3 class="stencil" style="margin-top:14px">Clima</h3>
      <table class="ledger"><thead><tr><th>região</th><th>vigente</th><th>pré-sorteado</th></tr></thead>
      <tbody>${climateRows}</tbody></table>
    </div>
    <div class="wide">
      <h3 class="stencil">Chaves de Hill, matriz técnica A e coeficientes do moral</h3>
      <table class="ledger"><thead><tr><th>nação</th><th>chave K</th><th>geração</th><th>A do turno (3×3)</th><th>β (moral)</th></tr></thead>
      <tbody>${hillRows}</tbody></table>
    </div>`;
  setHTML($("secrets"), html);
}

function renderCreds() {
  const rows = sortedFactions().map((f) =>
    `<tr><td>${esc(factionName(f.id))} <span class="faint">(${esc(f.id)})</span></td><td>${esc(CREDS[f.id] ?? "—")}</td></tr>`).join("");
  setHTML($("creds-body"), rows || `<tr><td colspan="2">Sem nações nesta partida.</td></tr>`);
  $("cred-origin").textContent = location.origin;
}

function renderArauto() {
  const html = (S.news || []).slice(0, 3).map((n) =>
    `<article class="arauto__item"><span class="rec__turn">turno ${n.turn}</span>` +
    `<h4 class="news">${esc(n.headline)}</h4><p class="news">${esc(n.body)}</p></article>`).join("") ||
    `<p class="diary-empty">Nenhuma manchete ainda. O Arauto sai ao fim de cada turno.</p>`;
  setHTML($("arauto"), html);
}

function renderRecords() {
  const news = (S.news || []).slice(0, 20).map((n) =>
    `<article class="rec"><span class="rec__turn">turno ${n.turn} · ${esc(n.kind || "")}</span><h4>${esc(n.headline)}</h4><p>${esc(n.body)}</p></article>`).join("") ||
    `<p class="diary-empty">Sem manchetes ainda.</p>`;
  const log = (S.event_log || []).map((e) => `<li>turno ${e.turn}: ${esc(e.name)}</li>`).join("") ||
    `<li class="faint">Nenhum evento disparado.</li>`;
  const fids = sortedFactions();
  const hist = (S.history || []).map((h) =>
    `<tr><td>${h.turn}</td><td>${h.battles ?? 0}</td><td>${h.captures ?? 0}</td>` +
    fids.map((f) => `<td>${fmtNum(h.troops?.[f.id], 0)}/${fmtNum(h.morale?.[f.id], 0)}</td>`).join("") + `</tr>`).join("") ||
    `<tr><td colspan="${3 + fids.length}">Sem histórico ainda.</td></tr>`;
  const html = `
    <h3 class="diary-sub">Manchetes d’O Arauto</h3>${news}
    <h3 class="diary-sub">Eventos disparados</h3><ul class="typed" style="margin:0;padding-left:18px">${log}</ul>
    <h3 class="diary-sub">Histórico por turno (tropas/moral)</h3>
    <table class="ledger"><thead><tr><th>turno</th><th>batalhas</th><th>conquistas</th>${fids.map((f) => `<th>${esc(f.id)}</th>`).join("")}</tr></thead>
    <tbody>${hist}</tbody></table>`;
  setHTML($("diary-records"), html);
}

/* ------------------------------------------------------------ diário */
function describe(msg) {
  const type = msg.type || "?";
  const x = msg.data || {};
  switch (type) {
    case "phase": return { tag: "fase", text: `${x.phase || x.status}: turno ${x.turn ?? "—"} de ${x.max_turns ?? "—"}` };
    case "state": return { tag: "estado", text: x.faction ? `ajuste de emergência em ${x.faction}: ${(x.edited || []).join(", ")}` : "estado atualizado" };
    case "dossier": return { tag: "dossiês", text: `dossiês do turno ${x.turn ?? "?"} entregues às seções` };
    case "telegram": return { tag: "telegrama", text: `${x.title || "telegrama"}${x.section ? ` (${x.section})` : ""}` };
    case "broadcast": return { tag: "aviso", tone: "red", text: x.text || "" };
    case "news": return { tag: "manchete", text: x.headline || "" };
    case "resolution": return { tag: "resolução", tone: "red", text: `turno ${x.turn} resolvido: ${(x.battles || []).length} batalha(s), ${(x.moves || []).length} movimento(s)` };
    case "message": return { tag: "diplomacia", text: `${x.from || "?"} → ${x.to || "?"}: ${x.text || ""}` };
    default: return { tag: type, text: JSON.stringify(x).slice(0, 200) };
  }
}

function pushDiary(msg) {
  diary.unshift({ t: Date.now(), ...describe(msg) });
  if (diary.length > DIARY_MAX) diary.length = DIARY_MAX;
  renderDiary();
}

function renderDiary() {
  const box = $("diary-live");
  const html = diary.length
    ? diary.map((e) => `<div class="diary-line"><span class="diary-line__time">${hms(e.t)}</span>` +
      `<span class="diary-line__tag${e.tone ? ` is-${e.tone}` : ""}">${esc(e.tag)}</span>` +
      `<span class="diary-line__text">${esc(e.text)}</span></div>`).join("")
    : `<p class="diary-empty">Nada ainda. Os eventos da partida aparecem aqui ao chegar.</p>`;
  setHTML(box, html);
}

/* ------------------------------------------------------------ mapa */
function showCaption(id) {
  const cap = $("map-caption");
  const tid = id || selectedTerritory;
  const t = tid && TER.get(tid);
  if (!t || !S) {
    cap.textContent = "Passe o cursor sobre um território. Clique para selecioná-lo no ajuste de emergência.";
    return;
  }
  const dono = t.owner ? factionShort(t.owner) : "neutro";
  const capOf = sortedFactions().find((f) => f.capital === t.id);
  cap.innerHTML = `<strong>${esc(t.id)}</strong> ${esc(t.name)} · ${esc(TERRAIN[t.terrain] || t.terrain)} · dono: ${esc(dono)} · ` +
    `${t.troops} batalhão(ões)${capOf ? ` · capital de ${esc(factionShort(capOf.id))}` : ""}`;
}

function pickTerritory(id) {
  selectedTerritory = id;
  if (mapCtrl) mapCtrl.setSelection([id]);
  $("adj-territory").value = id;
  dirty.territory = false;
  fillTerritoryForm();
  showCaption(id);
  flash(`Território ${id} selecionado para o ajuste de emergência.`);
}

/* ------------------------------------------------------------ ações */
/** Envia uma ação do árbitro. Erros do servidor vão para a fita (telex). */
async function act(path, body, okText, opts = {}) {
  if (opts.ask && !(await ask(opts.ask))) return null;
  try {
    const res = await api.post(path, body);
    flash(okText, "ok");
    if (opts.stamp) sfx.stamp(); else sfx.key();
    scheduleRefresh(150);
    return res;
  } catch (err) {
    if (err.status === 401) lockOut();
    else flash(err.message || "Falha na ação.", "err");
    return null;
  }
}

function openNewGame() {
  const g = S ? S.game : { n_factions: 4, max_turns: 8, turn_ms: 720000 };
  $("ng-n").value = String(g.n_factions || 4);
  $("ng-min").value = String(Math.round(((g.turn_ms || 720000) / 60000) * 100) / 100);
  $("ng-turns").value = String(g.max_turns || 8);
  $("ng-seed").value = "";
  $("ng-error").textContent = "";
  $("dlg-new").showModal();
}

async function submitNewGame() {
  const n = Number($("ng-n").value);
  const minutos = Number(String($("ng-min").value).replace(",", "."));
  const turnos = Number($("ng-turns").value);
  const seedRaw = $("ng-seed").value.trim();
  let err = null;
  if (!(n >= 2 && n <= 6)) err = "Informe de 2 a 6 nações.";
  else if (!(minutos > 0 && minutos <= 120)) err = "Os minutos por turno devem estar entre 0,5 e 120.";
  else if (!(Number.isInteger(turnos) && turnos >= 1 && turnos <= 30)) err = "O número de turnos deve ser um inteiro de 1 a 30.";
  else if (seedRaw && !/^-?\d+$/.test(seedRaw)) err = "A semente deve ser um número inteiro, ou fica vazia para sortear.";
  $("ng-error").textContent = err || "";
  if (err) return;

  const cur = S.game;
  const first = await ask({
    title: "Criar nova partida?",
    body: `Isto apaga a partida atual (turno ${cur.turn} de ${cur.max_turns}, ${cur.n_factions} nações).\n` +
      `A nova partida começa em espera: ${n} nações, ${turnos} turno(s) de ${minutos} min.`,
    ok: "SIM, APAGAR A PARTIDA", danger: true,
  });
  if (!first) return;
  const second = await ask({
    title: "Confirmação final",
    body: "Esta ação não pode ser desfeita. Digite APAGAR para criar a nova partida.",
    ok: "CRIAR PARTIDA", danger: true, word: "APAGAR",
  });
  if (!second) return;
  try {
    await api.post("/api/admin/new_game", {
      n_factions: n, turn_minutes: minutos, max_turns: turnos, seed: seedRaw ? Number(seedRaw) : null,
    });
    $("dlg-new").close();
    sfx.stamp();
    flash(`Nova partida criada: ${n} nações, ${turnos} turno(s) de ${minutos} min. Aguardando o início.`, "ok");
    await loadState();          // primeiro o estado (nações novas), depois as senhas novas
    await loadCreds();
    renderAll();
    scheduleRefresh(0);
  } catch (err2) {
    if (err2.status === 401) lockOut();
    else $("ng-error").textContent = err2.message;
  }
}

async function openCreds() {
  if (!S) return;
  await loadCreds();
  const origin = location.origin;
  $("cred-grid").innerHTML = sortedFactions().map((f) => {
    const d = FACTION_DEFAULTS[f.id] || {};
    const capital = d.capital || (TER.get(f.capital) || {}).name || "";
    return `<article class="cred-card" data-faction="${esc(f.id)}">
      <header class="cred-card__head">
        <span class="cred-card__emblem" aria-hidden="true">${emblemSVG(f.id)}</span>
        <div>
          <h2 class="cred-card__nation">${esc(factionName(f.id))}</h2>
          <p class="cred-card__capital">Capital: ${esc(capital)}</p>
        </div>
      </header>
      <div>
        <p class="cred-card__label">senha da sala</p>
        <p class="cred-card__pass">${esc(CREDS[f.id] ?? "—")}</p>
      </div>
      <div>
        <p class="cred-card__label">endereço</p>
        <p class="cred-card__addr">${esc(origin)}</p>
      </div>
      <ol class="cred-card__steps">
        <li>Abra o endereço acima no navegador.</li>
        <li>Escolha a sua nação na lista.</li>
        <li>Digite a senha desta folha.</li>
      </ol>
      <p class="cred-card__room">Sala: <span></span></p>
      <p class="cred-card__foot">Guarde esta folha. A senha identifica a sua sala.</p>
    </article>`;
  }).join("") || `<p class="typed">Não há nações nesta partida.</p>`;
  $("cred-sheet").hidden = false;
  $("cred-print").focus();
}

function closeCreds() {
  $("cred-sheet").hidden = true;
}

/* ------------------------------------------------------------ formulários */
async function submitNation(e) {
  e.preventDefault();
  const fid = $("adj-faction").value;
  const f = S.factions[fid];
  if (!f) return adjErr("Escolha uma nação.");
  const num = (id) => { const v = Number($(id).value); return $(id).value.trim() === "" || !Number.isFinite(v) ? null : v; };
  const changes = [];
  const stock = {};
  for (const [k, id] of [["ALI", "adj-ali"], ["ACO", "adj-aco"], ["COM", "adj-com"]]) {
    const v = num(id);
    if (v === null || v < 0) return adjErr(`Recurso ${k}: informe um número não negativo.`);
    if (Math.abs(v - f.stock[k]) > 0.006) { stock[k] = v; changes.push(`${k}: ${fmtNum(f.stock[k])} → ${fmtNum(v)}`); }
  }
  const morale = num("adj-morale");
  if (morale === null || morale < 0 || morale > 100) return adjErr("Moral: informe um valor de 0 a 100.");
  const patch = {};
  if (Object.keys(stock).length) patch.stock = stock;
  if (Math.abs(morale - f.morale) > 0.006) { patch.morale = morale; changes.push(`moral: ${fmtNum(f.morale)} → ${fmtNum(morale)}`); }
  if (!changes.length) return adjErr("Nenhum valor foi alterado.");
  adjErr("");
  const ok = await ask({
    title: `Ajustar ${factionName(fid)}?`,
    body: `${changes.join("\n")}\nO ajuste é imediato e fica registrado no diário.`,
    ok: "APLICAR", danger: true,
  });
  if (!ok) return;
  try {
    await api.post("/api/admin/edit_faction", { faction_id: fid, patch });
    dirty.nation = false;
    flash(`Ajuste aplicado a ${factionName(fid)}: ${changes.length} campo(s).`, "ok");
    sfx.stamp();
    scheduleRefresh(0);
  } catch (err) {
    if (err.status === 401) lockOut(); else adjErr(err.message);
  }
}

async function submitTerritory(e) {
  e.preventDefault();
  const tid = $("adj-territory").value;
  const t = TER.get(tid);
  if (!t) return adjErr("Escolha um território.");
  const n = Number($("adj-troops").value);
  if (!Number.isInteger(n) || n < 0) return adjErr("Batalhões: informe um inteiro não negativo.");
  const newOwner = $("adj-owner").value || null;
  const changes = [];
  const patch = {};
  if (n !== t.troops) { patch.troops = { [tid]: n }; changes.push(`batalhões: ${t.troops} → ${n}`); }
  const curOwner = t.owner || null;
  if (newOwner !== curOwner) {
    patch.owner = { [tid]: newOwner };
    changes.push(`dono: ${curOwner ? factionShort(curOwner) : "neutro"} → ${newOwner ? factionShort(newOwner) : "neutro"}`);
  }
  if (!changes.length) return adjErr("Nenhum valor foi alterado.");
  adjErr("");
  const ok = await ask({
    title: `Ajustar ${tid} · ${t.name}?`,
    body: `${changes.join("\n")}\nO ajuste é imediato e fica registrado no diário.`,
    ok: "APLICAR", danger: true,
  });
  if (!ok) return;
  // o servidor exige uma nação de referência: usa o dono atual (ou a primeira nação)
  const refFaction = curOwner || newOwner || sortedFactions()[0].id;
  try {
    await api.post("/api/admin/edit_faction", { faction_id: refFaction, patch });
    dirty.territory = false;
    flash(`Ajuste aplicado a ${tid}: ${changes.length} campo(s).`, "ok");
    sfx.stamp();
    scheduleRefresh(0);
  } catch (err) {
    if (err.status === 401) lockOut(); else adjErr(err.message);
  }
}

function adjErr(msg) { $("adj-error").textContent = msg || ""; }

async function submitRollback(e) {
  e.preventDefault();
  const turn = Number($("rb-turn").value);
  $("rb-error").textContent = "";
  const ok = await ask({
    title: `Voltar ao fim do turno ${turn}?`,
    body: "O estado atual é substituído pelo estado salvo ao fim desse turno. Ordens, resoluções e avisos posteriores deixam de existir nesta partida.",
    ok: "VOLTAR", danger: true,
  });
  if (!ok) return;
  try {
    await api.post("/api/admin/rollback", { turn });
    flash(`Partida voltou ao fim do turno ${turn}.`, "ok");
    sfx.stamp();
    scheduleRefresh(0);
  } catch (err) {
    if (err.status === 401) return lockOut();
    $("rb-error").textContent = `Não foi possível voltar: ${err.message}`;
    flash(err.message, "err");
  }
}

async function fireEvent(id) {
  const ev = eventCatalog.find((x) => x.id === id);
  if (!ev) return;
  await act("/api/admin/event", { event_id: id }, `Evento disparado: ${ev.name}.`, {
    stamp: true,
    ask: { title: `Disparar “${ev.name}”?`, body: `${ev.description}\nO efeito vale a partir de agora.`, ok: "DISPARAR", danger: true },
  });
}

/* ------------------------------------------------------------ ligações */
function wire() {
  // login
  $("gate-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("gate-submit");
    btn.disabled = true;
    try {
      await api.post("/api/admin/login", { password: $("gate-pass").value });
      $("gate-pass").value = "";
      gateError("");
      sfx.stamp();
      await enter();
    } catch (err) {
      gateError(err.message || "Não foi possível entrar.");
      $("gate-pass").select();
    } finally {
      btn.disabled = false;
    }
  });

  // teclas da partida
  $("btn-start").addEventListener("click", () => act("/api/admin/start", {}, "Guerra iniciada: o turno 1 está em curso.", { stamp: true }));
  $("btn-pause").addEventListener("click", () => act("/api/admin/pause", {}, "Partida pausada. O relógio parou."));
  $("btn-resume").addEventListener("click", () => act("/api/admin/resume", {}, "Partida retomada."));
  $("btn-plus1").addEventListener("click", () => act("/api/admin/extend", { minutes: 1 }, "Prazo estendido em 1 minuto."));
  $("btn-plus5").addEventListener("click", () => act("/api/admin/extend", { minutes: 5 }, "Prazo estendido em 5 minutos."));
  $("btn-resolve").addEventListener("click", () => act("/api/admin/resolve_now", {}, "Turno resolvido. Veja o diário e as manchetes.", {
    stamp: true,
    ask: {
      title: "Resolver o turno agora?",
      body: "As ordens recebidas até agora são congeladas e o turno é resolvido já.\nSeções que não enviaram ordens ficam sem ação neste turno.",
      ok: "RESOLVER", danger: true,
    },
  }));
  $("btn-new").addEventListener("click", openNewGame);
  $("btn-cred-top").addEventListener("click", openCreds);
  $("btn-cred").addEventListener("click", openCreds);
  $("ng-cancel").addEventListener("click", () => $("dlg-new").close());
  $("ng-submit").addEventListener("click", submitNewGame);
  $("form-new").addEventListener("submit", (e) => e.preventDefault());

  // impressão de credenciais
  $("cred-print").addEventListener("click", () => window.print());
  $("cred-close").addEventListener("click", closeCreds);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("cred-sheet").hidden) closeCreds(); });

  // abas da gaveta e do diário
  document.querySelectorAll(".folder__tab[data-tab]").forEach((tab) => tab.addEventListener("click", () => {
    document.querySelectorAll(".folder__tab[data-tab]").forEach((t) => {
      const on = t === tab;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", String(on));
      document.querySelector(`[data-panel="${t.dataset.tab}"]`).hidden = !on;
    });
  }));
  document.querySelectorAll("[data-dtab]").forEach((tab) => tab.addEventListener("click", () => {
    document.querySelectorAll("[data-dtab]").forEach((t) => {
      const on = t === tab;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", String(on));
    });
    $("diary-live").hidden = tab.dataset.dtab !== "live";
    $("diary-records").hidden = tab.dataset.dtab !== "records";
  }));

  // avisos
  $("form-aviso").addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = $("aviso-text").value.trim();
    const to = $("aviso-to").value;
    if (!text) { flash("O aviso está vazio.", "err"); return; }
    try {
      await api.post("/api/admin/broadcast", { text, to });
      $("aviso-text").value = "";
      flash(to === "all" ? "Aviso enviado a todas as nações." : `Aviso enviado a ${factionName(to)}.`, "ok");
      sfx.key();
      scheduleRefresh(150);
    } catch (err) {
      if (err.status === 401) lockOut(); else flash(err.message, "err");
    }
  });

  // eventos (delegação)
  $("event-list").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-event]");
    if (btn && !btn.disabled) fireEvent(btn.dataset.event);
  });

  // ajuste de emergência
  $("form-nation").addEventListener("submit", submitNation);
  $("form-territory").addEventListener("submit", submitTerritory);
  $("adj-faction").addEventListener("change", () => { dirty.nation = false; adjErr(""); fillNationForm(); });
  $("adj-territory").addEventListener("change", () => { selectedTerritory = $("adj-territory").value; if (mapCtrl) mapCtrl.setSelection([selectedTerritory]); dirty.territory = false; adjErr(""); fillTerritoryForm(); showCaption(selectedTerritory); });
  $("form-nation").addEventListener("input", () => { dirty.nation = true; });
  $("form-territory").addEventListener("input", () => { dirty.territory = true; });

  // segredos
  $("btn-secrets").addEventListener("click", () => {
    showSecrets = !showSecrets;
    const btn = $("btn-secrets");
    btn.textContent = showSecrets ? "OCULTAR SEGREDOS" : "MOSTRAR SEGREDOS";
    btn.setAttribute("aria-pressed", String(showSecrets));
    $("secrets").hidden = !showSecrets;
    $("secrets-hint").textContent = showSecrets
      ? "Visíveis agora. Não projete nem espelhe esta aba."
      : "Oculto. Telegramas em claro, gabaritos, depósitos e clima pré-sorteado. Não projete esta aba.";
    if (showSecrets) renderSecrets(); else { $("secrets")._html = null; $("secrets").innerHTML = ""; }
  });

  // rollback
  $("rb-turn").addEventListener("change", (e) => { e.target.dataset.touched = "1"; });
  $("form-rollback").addEventListener("submit", submitRollback);
}

/* ------------------------------------------------------------ início */
wire();
(async function boot() {
  showView("gate");
  try {
    await enter();              // já há sessão de árbitro (cookie)? entra direto
  } catch (err) {
    // 401: sem sessão, a porta de senha já está aberta. Outro erro: servidor fora do ar.
    if (err.status !== 401) $("gate-error").textContent = `${err.message} Tente de novo em instantes.`;
  }
})();
