/* =====================================================================
   login.js — o Portão: escolha da nação, senha, carimbo de acesso/negado.
   ===================================================================== */
import { api, MOCK, withMock } from "./api.js";
import { sfx } from "./sfx.js";
import { emblemSVG, FACTION_DEFAULTS } from "./emblems.js";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const QG = MOCK ? "qg.html" : "/qg";
const MARK_PATHS = [
  "M8 30 C6 8 60 -2 150 4 S296 8 292 34 C290 58 200 66 120 62 S10 58 8 30 Z",
  "M10 36 C4 12 70 0 160 6 S300 14 290 38 C282 62 190 64 110 60 S18 62 10 36 Z",
];

let factions = [];
let busy = false;

function currentFid() {
  const r = document.querySelector('input[name="faction"]:checked');
  return r ? r.value : null;
}

function renderNations(list) {
  const grid = $("nations-grid");
  grid.innerHTML = list.map((f, i) => `
    <label class="nation" data-faction="${esc(f.id)}" style="--c:${esc(f.color)}">
      <input type="radio" name="faction" value="${esc(f.id)}" ${f.capitulated ? "" : ""}>
      <span class="nation__body">
        <span class="nation__emb" style="color:${esc(f.color)}">${emblemSVG(f.id)}</span>
        <span class="nation__nm">${esc(f.short || f.name)}<small>${esc(f.name)}</small></span>
      </span>
      <svg class="nation__mark" viewBox="0 0 300 68" preserveAspectRatio="none" aria-hidden="true"><path pathLength="1" d="${MARK_PATHS[i % 2]}"/></svg>
    </label>`).join("");
  grid.addEventListener("change", () => {
    const f = factions.find((x) => x.id === currentFid());
    const art = $("seal-art");
    art.classList.remove("is-set"); void art.offsetWidth;
    if (f) { art.innerHTML = emblemSVG(f.id); art.style.color = f.color; art.classList.add("is-set"); sfx.stamp(); }
    $("error").textContent = "";
    $("password").focus({ preventScroll: true });
  });
}

async function loadFactions() {
  try {
    const st = await api.get("/api/public/state");
    if (st && Array.isArray(st.factions) && st.factions.length) {
      return st.factions.map((f) => ({ ...FACTION_DEFAULTS[f.id], ...f }));
    }
  } catch { /* servidor sem jogo: usa o padrão */ }
  return Object.values(FACTION_DEFAULTS);
}

function showVerdict(kind) {
  const v = $("verdict");
  const s = $("verdict-stamp");
  s.className = "stamp stamp--double " + (kind === "ok" ? "stamp--olive" : "");
  s.textContent = kind === "ok" ? "ACESSO AUTORIZADO" : "NEGADO";
  s.style.setProperty("--rot", kind === "ok" ? "-5deg" : "-9deg");
  v.classList.remove("hidden");
  void s.offsetWidth;
  s.classList.add("is-hit");
  setTimeout(() => sfx.stamp(), 140);
}

async function submit(ev) {
  ev.preventDefault();
  if (busy) return;
  const fid = currentFid();
  const pw = $("password").value;
  const err = $("error");
  const card = $("card");
  $("verdict").classList.add("hidden");
  card.classList.remove("is-denied");
  if (!fid) { err.textContent = "Assinale a nação com o carimbo antes de apresentar as credenciais."; denyShake(); return; }
  if (!pw) { err.textContent = "Datilografe a senha da nação."; $("password").focus(); return; }
  busy = true; card.classList.add("is-busy");
  err.textContent = "";
  try {
    await api.post("/api/login", { faction_id: fid, password: pw });
    showVerdict("ok");
    sfx.morse("OK");
    setTimeout(() => { location.href = QG; }, MOCK ? 4000 : 1250);
  } catch (e) {
    err.textContent = e.message || "Credenciais recusadas.";
    showVerdict("denied");
    denyShake();
    busy = false; card.classList.remove("is-busy");
    $("password").select();
  }
}
function denyShake() {
  const card = $("card");
  card.classList.remove("is-denied"); void card.offsetWidth; card.classList.add("is-denied");
}

async function checkSession() {
  try {
    const me = await api.get("/api/me");
    if (me && me.faction_id) {
      const f = factions.find((x) => x.id === me.faction_id) || { id: me.faction_id, ...FACTION_DEFAULTS[me.faction_id] };
      $("resume-emblem").innerHTML = emblemSVG(f.id);
      $("resume-emblem").style.setProperty("--c", f.color || "#555");
      $("resume-name").textContent = f.short || f.name || f.id;
      $("resume-go").textContent = `Continuar como ${f.short || f.name || f.id}`;
      $("resume").classList.remove("hidden");
      $("resume-go").onclick = () => { sfx.stamp(); location.href = QG; };
      $("resume-out").onclick = async () => {
        try { await api.post("/api/logout", {}); } catch { /* ignora */ }
        $("resume").classList.add("hidden");
      };
    }
  } catch { /* sem sessão */ }
}

async function boot() {
  $("serial").firstChild.textContent = "Nº " + String(143 + Math.floor((Date.now() / 60000) % 800)).padStart(4, "0");
  $("link-teatro").href = MOCK ? "teatro.html?mock=1" : "/teatro";
  $("link-arbitro").href = MOCK ? "arbitro.html?mock=1" : "/arbitro";
  factions = await loadFactions();
  renderNations(factions);
  $("form").addEventListener("submit", submit);
  $("password").addEventListener("keydown", (e) => { if (e.key.length === 1 || e.key === "Backspace") sfx.key(); });
  $("peek").addEventListener("click", () => {
    const p = $("password");
    const show = p.type === "password";
    p.type = show ? "text" : "password";
    $("peek").setAttribute("aria-pressed", String(show));
    $("peek").textContent = show ? "ocultar" : "mostrar";
  });
  await checkSession();
}
boot();
