/* =====================================================================
   ws.js — WebSocket com reconexão exponencial (1 s -> 15 s)
   ---------------------------------------------------------------------
   import { connect } from "./ws.js";
   const conn = connect("public", (msg) => {...}, (status, info) => {...});
     canal: "public" | "faction" | "admin"
     msg:   {type, data}            (phase | state | dossier | telegram | broadcast | news | resolution | message)
     status: "connecting" | "open" | "closed" | "mock"
             info.reconnected === true na reabertura -> refaça os GETs
   conn.close()   encerra de vez
   conn.status    estado atual
   Modo mock (?mock=1): não conecta. status vira "mock" e window.__mockWS(type, data)
   injeta mensagens à mão (para testar animações sem servidor).
   ===================================================================== */
import { MOCK } from "./api.js";

export function connect(channel, onMessage, onStatus = () => {}) {
  const conn = { status: "connecting", close() {}, send() {} };

  if (MOCK) {
    conn.status = "mock";
    window.__mockWS = (type, data) => onMessage({ type, data });
    queueMicrotask(() => onStatus("mock", {}));
    return conn;
  }

  let socket = null;
  let delay = 1000;
  let timer = null;
  let closed = false;
  let everOpened = false;

  const setStatus = (s, info = {}) => { conn.status = s; try { onStatus(s, info); } catch (e) { console.error(e); } };

  function open() {
    if (closed) return;
    setStatus("connecting");
    const proto = location.protocol === "https:" ? "wss" : "ws";
    try {
      socket = new WebSocket(`${proto}://${location.host}/ws?ch=${encodeURIComponent(channel)}`);
    } catch {
      schedule();
      return;
    }
    socket.onopen = () => {
      const reconnected = everOpened;
      everOpened = true;
      delay = 1000;
      setStatus("open", { reconnected });
    };
    socket.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      try { onMessage(msg); } catch (e) { console.error(e); }
    };
    socket.onclose = () => {
      socket = null;
      if (closed) return;
      setStatus("closed");
      schedule();
    };
    socket.onerror = () => { try { socket && socket.close(); } catch { /* nada */ } };
  }

  function schedule() {
    if (closed) return;
    clearTimeout(timer);
    timer = setTimeout(open, delay);
    delay = Math.min(15000, Math.round(delay * 1.7));
  }

  conn.close = () => { closed = true; clearTimeout(timer); try { socket && socket.close(); } catch { /* nada */ } };
  conn.send = (obj) => { if (socket && socket.readyState === 1) socket.send(typeof obj === "string" ? obj : JSON.stringify(obj)); };
  open();
  return conn;
}

export default connect;
