/* =====================================================================
   api.js — acesso HTTP ao servidor do ESTADO-MAIOR
   ---------------------------------------------------------------------
   import { api, serverClock, MOCK } from "./api.js";

   api.get("/api/public/state")            -> Promise<json>
   api.post("/api/login", {faction_id, password})
   api.tool("matrix", {op:"det", A:[[1,2],[3,4]]})   -> POST /api/tools/matrix
   Erros: lançam Error cuja .message é a `detail` do servidor (português) e
   que carrega .status (HTTP) e .body.

   Modo mock: abra a página com ?mock=1 (ou ?mock=1 em qualquer tela).
   GETs são servidos de web/mock/*.json:
     /api/public/map            -> mock/map.json
     /api/public/state          -> mock/public_state.json   (relógio é "vivo": o prazo é recalculado)
     /api/faction/state         -> mock/faction_state.json
     /api/faction/dossier/X     -> mock/dossier_X.json
     /api/me                    -> {faction_id:null, admin:false}
     /api/server_time           -> hora local
   POSTs em mock retornam {ok:true}.

   serverClock(): Promise<{now(), offset, sync()}> — relógio sincronizado com
   /api/server_time (compensa metade do RTT, refaz a cada 60 s).
   clock.now() devolve ms epoch "do servidor". Útil: restante = deadline_ms - clock.now().
   ===================================================================== */

export const MOCK = new URLSearchParams(location.search).get("mock") === "1";

/** Preserva ?mock=1 ao navegar entre páginas. */
export function withMock(url) {
  if (!MOCK) return url;
  return url + (url.includes("?") ? "&" : "?") + "mock=1";
}

const MOCK_MAP = [
  [/^\/api\/public\/map(\?.*)?$/, "mock/map.json"],
  [/^\/api\/public\/state(\?.*)?$/, "mock/public_state.json"],
  [/^\/api\/faction\/state(\?.*)?$/, "mock/faction_state.json"],
  [/^\/api\/faction\/dossier\/([a-z]+)(\?.*)?$/, (m) => `mock/dossier_${m[1]}.json`],
];

function mockUrl(path) {
  for (const [re, target] of MOCK_MAP) {
    const m = re.exec(path);
    if (m) return new URL(typeof target === "function" ? target(m) : target, document.baseURI).href;
  }
  return null;
}

function makeError(message, status, body) {
  const err = new Error(message);
  err.status = status;
  err.body = body;
  return err;
}

async function readJSON(res) {
  const text = await res.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = null; }
  if (!res.ok) {
    let detail = body && body.detail;
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg || String(d)).join("; ");
    throw makeError(detail || `Erro ${res.status} do servidor.`, res.status, body);
  }
  return body;
}

async function mockGet(path) {
  if (/^\/api\/me/.test(path)) return { faction_id: null, admin: false };
  if (/^\/api\/server_time/.test(path)) return { now_ms: Date.now() };
  const url = mockUrl(path);
  if (!url) throw makeError(`Mock indisponível para ${path}`, 404);
  const res = await fetch(url, { cache: "no-store" });
  const body = await readJSON(res);
  // relógio vivo no mock: o prazo corre a partir de agora
  if (body && body.game && typeof body.game.remaining_ms === "number" && body.game.status === "running") {
    const now = Date.now();
    body.game.now_ms = now;
    body.game.deadline_ms = now + body.game.remaining_ms;
  }
  return body;
}

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    throw makeError("Sem conexão com o servidor. Verifique a rede e tente de novo.", 0);
  }
  return readJSON(res);
}

export const api = {
  get(path) {
    return MOCK ? mockGet(path) : request("GET", path);
  },
  post(path, body = {}) {
    if (MOCK) return Promise.resolve({ ok: true });
    return request("POST", path, body);
  },
  tool(name, body = {}) {
    if (MOCK) return Promise.resolve({ ok: true });
    return request("POST", `/api/tools/${encodeURIComponent(name)}`, body);
  },
};

/* ------------------------------------------------------------- relógio */
let _clock = null;

export async function serverClock() {
  if (_clock) return _clock;
  const clock = {
    offset: 0,
    rtt: 0,
    now() { return Date.now() + this.offset; },
    async sync() {
      if (MOCK) { this.offset = 0; return this; }
      try {
        const t0 = Date.now();
        const { now_ms } = await request("GET", "/api/server_time");
        const t1 = Date.now();
        this.rtt = t1 - t0;
        this.offset = now_ms + this.rtt / 2 - t1;
      } catch { /* mantém o offset anterior */ }
      return this;
    },
  };
  _clock = clock;
  await clock.sync();
  setInterval(() => clock.sync(), 60000);
  return clock;
}

export default api;
