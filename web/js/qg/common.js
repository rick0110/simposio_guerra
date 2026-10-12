/* =====================================================================
   qg/common.js — peças do Quartel-General compartilhadas pelas seções.
   ---------------------------------------------------------------------
   h(tag, attrs, ...filhos)          DOM montado sem innerHTML (texto sempre seguro)
   fmt(n, casas) / parseNum(v)       números em pt-BR (vírgula decimal)
   dossierPaper(d, {ctx, section})   folha datilografada do dossiê, com tabelas,
                                     CSV e botões "Abrir na Mesa de Cálculo"
   challengeBox({ctx, section})      questionário reservado (furos, carimbo, recompensa)
   orderSheet({ctx, section, ...})   folha de ordem em papel-carbono (carimbo EXPEDIDA)
   telegramEl({...})                 telegrama; cifra com espaços visíveis (·)
   ===================================================================== */

export const SECTIONS = ["intendencia", "operacoes", "inteligencia", "governo"];
export const SEC_NAMES = { intendencia: "Intendência", operacoes: "Operações", inteligencia: "Inteligência", governo: "Governo" };
export const SEC_CODE = { intendencia: "INT", operacoes: "OPE", inteligencia: "INL", governo: "GOV" };
export const RES = ["ALI", "ACO", "COM"];
export const RES_NAMES = { ALI: "Alimento", ACO: "Aço", COM: "Combustível" };
export const REGIONS = ["norte", "centro", "sul"];
export const REGION_NAMES = { norte: "Norte", centro: "Centro", sul: "Sul" };
export const WEATHER_NAMES = ["limpo", "chuva", "tempestade"];
export const WEATHER_ATK = [1.0, 0.85, 0.65];
export const TERRAIN_DEF = { planicie: 1.0, floresta: 1.25, montanha: 1.5, pantano: 1.2, urbano: 1.3 };
export const TERRAIN_NAMES = { planicie: "planície", floresta: "floresta", montanha: "montanha", pantano: "pântano", urbano: "urbano" };
export const CHALLENGE_ATTEMPTS = 3;
export const CIPHER_CRIB = "URGENTE ";

/* ------------------------------------------------------------ formatação */
const nfCache = new Map();
function nf(max, min) {
  const key = `${max}|${min}`;
  if (!nfCache.has(key)) nfCache.set(key, new Intl.NumberFormat("pt-BR", { minimumFractionDigits: min, maximumFractionDigits: max }));
  return nfCache.get(key);
}
/** fmt(21.5) -> "21,5"; fmt(3.14159, 2) -> "3,14"; null/NaN -> "—" */
export function fmt(n, max = 1, min = 0) {
  if (n === null || n === undefined || n === "") return "—";
  const v = Number(n);
  return Number.isFinite(v) ? nf(max, min).format(v) : "—";
}
/** "21,5" / "21.5" / 21.5 -> 21.5 ; inválido -> null */
export function parseNum(v) {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  const s = String(v ?? "").trim().replace(/\s/g, "").replace(",", ".");
  if (s === "" || s === "-" || s === ".") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}
export const pad2 = (n) => String(Math.max(0, Math.floor(n))).padStart(2, "0");
/** ms -> "11:42" (arredonda para cima: o último segundo ainda aparece) */
export function clockText(ms) {
  const t = Math.max(0, Math.ceil(ms / 1000));
  return `${pad2(Math.floor(t / 60))}:${pad2(t % 60)}`;
}
/** Cifra: espaço interno é um símbolo (36) — aqui aparece como ponto médio. */
export function cipherText(s) {
  return String(s ?? "").replace(/ /g, "·");
}
/** Índices 0–36 da cifra, em pares: "02 09  ·  13 20 …" */
export function codesText(codes) {
  const out = [];
  const arr = codes || [];
  for (let i = 0; i < arr.length; i += 2) out.push(arr.slice(i, i + 2).map((c) => String(c).padStart(2, "0")).join(" "));
  return out.join("  ·  ");
}

/* ------------------------------------------------------------ DOM seguro */
/** h("div", {class: "x", onclick: fn}, filhos...) — strings viram texto; arrays são achatados. */
export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const k of Object.keys(attrs)) {
      const v = attrs[k];
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "style") Object.assign(el.style, v);
      else if (k === "value") el.value = v;
      else if (k === "checked") el.checked = !!v;
      else if (k === "disabled") el.disabled = !!v;
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : String(v));
    }
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

/** Lista de filhos segura para replaceChildren(...kids(...)): achata arrays e descarta null/false. */
export function kids(...xs) {
  return xs.flat(Infinity)
    .filter((x) => x !== null && x !== undefined && x !== false)
    .map((x) => (x instanceof Node ? x : document.createTextNode(String(x))));
}

/** Converte um trecho SVG estático (string fixa do próprio código) em elemento. */
export function svgEl(markup) {
  const t = document.createElement("template");
  t.innerHTML = markup.trim();
  return t.content.firstElementChild;
}

/** Carimbo de borracha. tone: "" (vermelho) | "blue" | "olive" | "ink". */
export function stampEl(text, tone = "", hit = false) {
  return h("span", { class: `stamp${tone ? ` stamp--${tone}` : ""}${hit ? " is-hit" : ""}` }, text);
}

/** Caixa de mensagens do servidor (erros bloqueiam; avisos só informam). */
export function listBox(items, kind, heading) {
  return h("div", { class: `msgbox msgbox--${kind}`, role: kind === "errors" ? "alert" : "status" },
    heading ? h("b", { class: "caps" }, heading) : null,
    h("ul", null, (items || []).map((t) => h("li", null, String(t)))));
}

/* ------------------------------------------------------------ telegramas */
export function telegramEl({ head, meta = "", body = "", cipher = false, cls = "", extra = null }) {
  return h("article", { class: `telegram ${cls}`.trim() },
    h("div", { class: "telegram__head" }, h("span", null, head), meta ? h("span", null, meta) : null),
    h("div", { class: cipher ? "telegram__body cipher" : "telegram__body" },
      h("span", { class: "telegram__strip" }, cipher ? cipherText(body) : String(body ?? ""))),
    extra);
}

/* ------------------------------------------------------------ dossiê */
/** Mesa de Cálculo: qual ferramenta abre cada conjunto de dados (dados já convertidos). */
function calcSpec(section, ds, d) {
  const rows = ds.rows || [];
  const cols = ds.columns || [];
  if (section === "intendencia" && ds.id === "transacoes") {
    const X = rows.find((r) => r[0] === "X");
    const Zrows = rows.filter((r) => r !== X);
    return {
      label: "Abrir na Mesa de Cálculo", tool: "leontief",
      payload: () => ({ Z: Zrows.map((r) => r.slice(1, 4).map(Number)), X: X ? X.slice(1, 4).map(Number) : [] }),
    };
  }
  if (section === "operacoes" && ds.id === "diario_clima") {
    return {
      label: "Abrir na Mesa (Markov)", tool: "markov", regions: true,
      payload: (reg) => {
        const idx = cols.indexOf(REGION_NAMES[reg] || "Centro");
        return { sequence: rows.map((r) => r[idx]) };
      },
    };
  }
  if (section === "inteligencia" && ds.id === "leituras") {
    return {
      label: "Abrir na Mesa (triangulação)", tool: "trilaterate",
      payload: () => ({ stations: rows.map((r) => [Number(r[1]), Number(r[2])]), distances: rows.map((r) => Number(r[3])) }),
    };
  }
  if (section === "governo" && ds.id === "pesquisa") {
    return {
      label: "Abrir na Mesa (regressão)", tool: "regression",
      payload: () => ({ rows: rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]]))), target: "delta_moral" }),
    };
  }
  return null;
}

/** Ação por linha (um criptograma abre na Mesa como cifra de Hill). */
function rowCalc(section, ds, d) {
  if (section === "inteligencia" && ds.id === "criptogramas") {
    const crib = (d.extras && d.extras.crib) || CIPHER_CRIB;
    return (row) => ({ label: "Abrir na Mesa", tool: "hill", payload: { cipher: String(row[3] ?? ""), crib, plainCrib: crib } });
  }
  return null;
}

function cellEl(v, ds, ci) {
  if (ds.id === "criptogramas" && ci === 3) return h("td", { class: "txt cipher-cell" }, cipherText(v));
  if (typeof v === "number") return h("td", null, fmt(v, 2));
  return h("td", { class: "txt" }, v === null || v === undefined ? "" : String(v));
}

function datasetBlock(ds, d, section, ctx) {
  const cols = ds.columns || [];
  const rowAct = rowCalc(section, ds, d);
  const headRow = h("tr", null, cols.map((c) => h("th", null, c || "")), rowAct ? h("th", null, "") : null);
  const bodyRows = (ds.rows || []).map((row) => h("tr", null,
    row.map((v, ci) => cellEl(v, ds, ci)),
    rowAct ? h("td", { class: "ledger-act" }, h("button", {
      class: "btn btn--small", type: "button",
      onclick: () => { const s = rowAct(row); ctx.calc.open(s.tool, s.payload); },
    }, "Abrir na Mesa")) : null));
  const table = h("div", { class: "ledger-wrap" },
    h("table", { class: "ledger" }, h("thead", null, headRow), h("tbody", null, bodyRows)));

  const actions = h("div", { class: "ds__actions" },
    ds.csv_url ? h("a", { class: "btn btn--small", href: ds.csv_url, download: "" }, "Baixar CSV") : null);
  const sp = calcSpec(section, ds, d);
  let sel = null;
  if (sp && sp.regions) {
    sel = h("select", { class: "input input--sel", "aria-label": "Região do diário meteorológico" },
      REGIONS.map((r) => h("option", { value: r }, REGION_NAMES[r])));
    sel.value = (d.extras && d.extras.challenge_region) || "centro";
    actions.append(sel);
  }
  if (sp) {
    actions.append(h("button", {
      class: "btn btn--small btn--blue", type: "button",
      onclick: () => ctx.calc.open(sp.tool, sp.payload(sel ? sel.value : null)),
    }, sp.label));
  }
  return h("section", { class: "ds" },
    h("h3", { class: "ds__title typed" }, ds.title),
    ds.description ? h("p", { class: "ds__desc" }, ds.description) : null,
    table,
    actions);
}

/** Folha do dossiê (datilografada, presa à pasta). */
export function dossierPaper(d, { ctx, section }) {
  if (!d) {
    return h("article", { class: "paper dossier dossier--empty" },
      h("p", { class: "typed faint" }, "O dossiê deste turno ainda não chegou. Aguarde o briefing do árbitro."));
  }
  const brief = String(d.briefing || "").split(/\n\s*\n/).filter(Boolean);
  return h("article", { class: "paper dossier" },
    h("span", { class: "stamp stamp--ink dossier__stamp" }, "Confidencial"),
    h("header", { class: "dossier__head" },
      h("h2", { class: "stencil dossier__title" }, d.title),
      h("p", { class: "typed faint" }, `Turno ${d.turn} · dados gerados para esta nação`)),
    h("div", { class: "typed dossier__brief" }, brief.map((p) => h("p", null, p))),
    (d.datasets || []).map((ds) => datasetBlock(ds, d, section, ctx)));
}

/* ------------------------------------------------------------ questionário */
/**
 * Questionário reservado. update(lista) recebe dossier.challenges.
 * A resposta é enviada a POST /api/faction/challenge/{id}; o carimbo CORRETO/INCORRETO
 * só aparece quando o servidor gasta uma tentativa (erro de formato não gasta).
 */
export function challengeBox({ ctx, section, title = "Questionário reservado" }) {
  let cur = null;
  let busy = false;
  let lastStamp = null;   // mantém o carimbo do último envio enquanto o desafio for o mesmo
  const inputId = `chal-in-${section}`;
  const input = h("input", { id: inputId, type: "text", autocomplete: "off", spellcheck: "false", class: "input chal__input" });
  const btn = h("button", { class: "btn btn--stamp btn--small chal__send", type: "submit" }, "Enviar resposta");
  const holes = h("div", { class: "furos", role: "img", "aria-label": "" });
  const holesTxt = h("span", { class: "typed faint" }, "");
  const prompt = h("p", { class: "typed chal__prompt" });
  const fmtLine = h("p", { class: "chal__format" });
  const resultSlot = h("div", { class: "chal__result", "aria-live": "polite" });
  const rewardLine = h("p", { class: "chal__reward" });
  const form = h("form", { class: "chal__form", onsubmit: (e) => { e.preventDefault(); send(); } },
    h("div", { class: "field chal__field" }, h("label", { for: inputId }, "Sua resposta"), input),
    h("div", { class: "row" }, btn, holesTxt));
  const empty = h("p", { class: "typed faint chal__empty" }, "Nenhum questionário reservado neste turno.");
  const body = h("div", { class: "chal__body" }, prompt, fmtLine, h("div", { class: "row chal__holes" }, holes), form, resultSlot, rewardLine);
  const el = h("section", { class: "paper challenge" },
    h("header", { class: "chal__head" }, h("h3", { class: "stencil" }, title), stampEl("Reservado", "ink")),
    body, empty);

  function renderHoles(left, solved) {
    const used = solved ? CHALLENGE_ATTEMPTS - left : CHALLENGE_ATTEMPTS - left;
    holes.replaceChildren(...Array.from({ length: CHALLENGE_ATTEMPTS }, (_, i) =>
      h("i", { class: `furo${i < used ? " is-used" : ""}` })));
    holes.setAttribute("aria-label", `${left} tentativa(s) restante(s) de ${CHALLENGE_ATTEMPTS}`);
    holesTxt.textContent = solved ? "Resolvido neste turno" : `Tentativas restantes: ${left} de ${CHALLENGE_ATTEMPTS}`;
  }

  function update(list) {
    const c = (list && list[0]) || null;
    if (!c) { empty.hidden = false; body.hidden = true; cur = null; return; }
    empty.hidden = true; body.hidden = false;
    if (!cur || cur.id !== c.id) { input.value = ""; lastStamp = null; resultSlot.replaceChildren(); rewardLine.textContent = ""; }
    cur = c;
    prompt.textContent = c.prompt;
    fmtLine.textContent = `Formato da resposta: ${c.answer_format}`;
    renderHoles(c.attempts_left, c.solved);
    const closed = c.solved || c.attempts_left <= 0;
    input.disabled = closed || busy;
    btn.disabled = closed || busy;
    if (!lastStamp) {
      if (c.solved) { resultSlot.replaceChildren(stampEl("Correto", "olive")); rewardLine.textContent = c.reward_text ? `Recompensa: ${c.reward_text}` : ""; }
      else if (c.attempts_left <= 0) resultSlot.replaceChildren(stampEl("Sem tentativas", "ink"));
    }
  }

  function showResult(r, prevLeft) {
    resultSlot.replaceChildren();
    rewardLine.textContent = "";
    if (r && r.correct) {
      lastStamp = stampEl("Correto", "olive", true);
      resultSlot.append(lastStamp);
      if (ctx.sfx) ctx.sfx.stamp();
      if (r.reward && r.reward.text) rewardLine.textContent = `Recompensa: ${r.reward.text}`;
    } else if (r && typeof r.attempts_left === "number" && typeof prevLeft === "number" && r.attempts_left < prevLeft) {
      lastStamp = stampEl("Incorreto", "", true);
      resultSlot.append(lastStamp);
      if (ctx.sfx) ctx.sfx.stamp();
    }
    if (r && r.message) resultSlot.append(h("p", { class: r.correct ? "typed chal__ok" : "typed chal__msg" }, r.message));
    if (r && r.correct === undefined) resultSlot.append(h("p", { class: "typed faint" }, "Resposta enviada."));
  }

  async function send() {
    if (!cur || busy) return;
    const answer = input.value.trim();
    if (!answer) { resultSlot.replaceChildren(h("p", { class: "typed chal__msg" }, "Escreva a resposta antes de enviar.")); return; }
    busy = true; btn.textContent = "Enviando…"; input.disabled = true; btn.disabled = true;
    const prevLeft = cur.attempts_left;
    const id = cur.id;
    try {
      const r = await ctx.api.post(`/api/faction/challenge/${encodeURIComponent(id)}`, { answer });
      showResult(r, prevLeft);
      await ctx.reloadState();
      await ctx.reloadDossier(section);
    } catch (e) {
      if (e && e.status === 401) { ctx.sessionLost(); return; }
      resultSlot.replaceChildren(h("p", { class: "typed chal__msg" }, e.message || "Não foi possível enviar a resposta."));
    } finally {
      busy = false; btn.textContent = "Enviar resposta";
      if (cur) { input.disabled = cur.solved || cur.attempts_left <= 0; btn.disabled = input.disabled; }
    }
  }

  return { el, update };
}

/* ------------------------------------------------------------ ordem */
/**
 * Folha de ordem em papel-carbono.
 * getPayload() -> objeto (ordem) | null (quando a seção já mostrou o motivo).
 * send() chama POST /api/faction/orders/{section}; mostra erros (bloqueiam),
 * avisos, o carimbo EXPEDIDA com a hora e recarrega o estado.
 */
export function orderSheet({ ctx, section, body, getPayload, title = "Ordem de operação" }) {
  let busy = false;
  const noEl = h("span", { class: "mono" }, "");
  const lastEl = h("div", { class: "order__last" });
  const msgEl = h("div", { class: "order__msgs", "aria-live": "polite" });
  const stampSlot = h("div", { class: "order__stamp", "aria-live": "polite" });
  const btn = h("button", { class: "btn btn--blue order__send", type: "button" }, "Assinar e carimbar");
  const el = h("article", { class: "paper paper--carbon order", "data-section": section },
    h("header", { class: "order__head" },
      h("p", { class: "caps" }, `${title} Nº `, noEl),
      h("p", { class: "typed faint" }, "Confira os números, assine e carimbe. Vale a última ordem enviada até o prazo.")),
    body,
    lastEl, msgEl,
    h("footer", { class: "order__foot" }, btn),
    stampSlot);

  async function send(payload) {
    if (busy) return false;
    busy = true;
    const prev = btn.textContent;
    btn.disabled = true; btn.textContent = "Carimbando…";
    msgEl.replaceChildren(); stampSlot.replaceChildren();
    try {
      const res = await ctx.api.post(`/api/faction/orders/${section}`, payload);
      const errors = (res && res.errors) || [];
      const warnings = (res && res.warnings) || [];
      if ((res && res.ok === false) || errors.length) {
        msgEl.append(listBox(errors.length ? errors : ["A ordem não foi aceita."], "errors", "Ordem recusada"));
        if (warnings.length) msgEl.append(listBox(warnings, "warnings", "Avisos"));
        return false;
      }
      if (warnings.length) msgEl.append(listBox(warnings, "warnings", "Avisos do Estado-Maior"));
      const hora = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      stampSlot.append(h("div", { class: "expedida" }, stampEl("Expedida", "blue", true), h("p", { class: "typed" }, `às ${hora}`)));
      if (ctx.sfx) ctx.sfx.stamp();
      await ctx.reloadState();
      return true;
    } catch (e) {
      if (e && e.status === 401) { ctx.sessionLost(); return false; }
      msgEl.append(listBox([e.message || "Falha ao enviar a ordem."], "errors", "Ordem recusada"));
      return false;
    } finally {
      busy = false; btn.disabled = false; btn.textContent = prev;
    }
  }

  btn.addEventListener("click", () => {
    const p = getPayload ? getPayload() : null;
    if (p) send(p);
  });

  return {
    el,
    setTurn(t) { noEl.textContent = `${t}/${SEC_CODE[section]}`; },
    /** lines: array de textos da última ordem expedida (vinda de faction_state.orders). */
    setLast(lines) {
      lastEl.replaceChildren(
        h("p", { class: "caps faint" }, "Última ordem expedida"),
        lines && lines.length
          ? h("ul", { class: "typed order__lines" }, lines.map((l) => h("li", null, l)))
          : h("p", { class: "typed faint" }, "Nenhuma ordem expedida ainda."));
    },
    msg(items, kind, heading) { msgEl.replaceChildren(listBox(items, kind, heading)); },
    clearMsg() { msgEl.replaceChildren(); },
    send,
    get busy() { return busy; },
  };
}
