/* =====================================================================
   qg/governo.js — Governo: dossiê (pesquisa de opinião, quadro das nações),
   questionário (regressão: efeito da propaganda), ordem de política
   (ração, propaganda, jornada, transferências, pactos) e telegrafia
   diplomática (telegramas entre Governos).
   ===================================================================== */
import {
  h, fmt, parseNum, svgEl, RES, RES_NAMES, stampEl, telegramEl, listBox,
  dossierPaper, challengeBox, orderSheet,
} from "./common.js";
import { emblemSVG } from "../emblems.js";

const RACAO = [
  { v: "0", t: "Normal", d: "consumo civil de 6 ALI por turno" },
  { v: "1", t: "Reduzida", d: "consumo civil de 4 ALI por turno" },
  { v: "2", t: "Severa", d: "consumo civil de 2 ALI por turno" },
];
const HORAS = [
  { v: "8", t: "8 horas", d: "mão de obra ×1,0" },
  { v: "10", t: "10 horas", d: "mão de obra ×1,2" },
  { v: "12", t: "12 horas", d: "mão de obra ×1,4" },
];
const MAX_TRANSFERS = 4;
const MAX_MSG = 600;

export function mountGoverno(root, ctx) {
  root.classList.add("sec", "sec--governo");
  const dossierSlot = h("div", { class: "slot slot--dossier" });
  const chal = challengeBox({ ctx, section: "governo" });

  let touched = false;
  let lastOrderKey = "";
  let fid = null;
  let factionKey = "";
  let busyMsg = false;

  /* ------------------------------------------------------------ política */
  const radioGroup = (name, opts, label) => opts.map((o) => {
    const id = `gov-${name}-${o.v}`;
    return h("label", { class: "choice", for: id },
      h("input", { type: "radio", name: `gov-${name}`, value: o.v, id }),
      h("span", null, h("b", null, o.t), h("small", null, o.d)));
  });
  const racaoLabels = radioGroup("racao", RACAO);
  const horasLabels = radioGroup("horas", HORAS);
  const propRange = h("input", { type: "range", min: "0", max: "5", step: "1", value: "0", id: "gov-prop", "aria-label": "Propaganda (0 a 5)" });
  const propNum = h("output", { class: "mono prop__out", for: "gov-prop" }, "0");
  const propHint = h("p", { class: "hint" });
  propRange.addEventListener("input", () => { touched = true; syncProp(); });

  function syncProp() {
    propNum.textContent = propRange.value;
    const st = ctx.state();
    const acoStock = st ? Number(st.faction.stock.ACO) || 0 : 0;
    const p = Number(propRange.value);
    propHint.textContent = `Propaganda custa 1 ACO por ponto (${p} ponto(s) = ${p} ACO). Estoque de Aço: ${fmt(acoStock)}.`;
  }

  /* transferências: linhas dinâmicas */
  const transferRows = h("div", { class: "transfers" });
  const transferHint = h("p", { class: "hint" }, "Transferências saem do seu estoque na resolução e vão para outro Governo. Até 4 linhas.");
  const addRowBtn = h("button", { class: "btn btn--small", type: "button", onclick: () => { addTransferRow(); touched = true; } }, "+ linha de transferência");

  function otherFactions() {
    const st = ctx.state();
    return st ? (st.factions || []).filter((f) => f.id !== st.faction.id && !f.capitulated) : [];
  }

  function fillSelect(sel, keep) {
    const opts = otherFactions();
    sel.replaceChildren(...opts.map((f) => h("option", { value: f.id }, f.short || f.name)));
    if (keep && opts.some((f) => f.id === keep)) sel.value = keep;
  }

  function addTransferRow(init = {}) {
    if (transferRows.children.length >= MAX_TRANSFERS) return;
    const sel = h("select", { class: "input input--sel", "aria-label": "Nação destinatária" });
    fillSelect(sel, init.to);
    const amt = {};
    const cells = RES.map((s) => {
      const inp = h("input", { type: "number", min: "0", step: "0.5", inputmode: "decimal", class: "input input--num input--sm", placeholder: s, "aria-label": `${RES_NAMES[s]} a transferir` });
      if (init[s] !== undefined) inp.value = String(init[s]);
      amt[s] = inp;
      return inp;
    });
    const row = h("div", { class: "transfer-row" },
      h("label", { class: "caps faint" }, "Para"), sel,
      h("div", { class: "transfer-row__amt" }, cells),
      h("button", { class: "btn btn--small", type: "button", "aria-label": "Remover linha", onclick: () => { row.remove(); touched = true; } }, "×"));
    row.__read = () => ({ to: sel.value, ...Object.fromEntries(RES.map((s) => [s, parseNum(amt[s].value)])) });
    transferRows.append(row);
  }

  /* pactos: uma linha por nação */
  const pactList = h("div", { class: "pacts" });
  const pactRefs = new Map();   // id -> {propose, denounce, status, label}

  function buildPacts(st) {
    const others = (st.factions || []).filter((f) => f.id !== st.faction.id);
    pactList.replaceChildren();
    pactRefs.clear();
    for (const f of others) {
      const propose = h("input", { type: "checkbox", id: `pact-p-${f.id}` });
      const denounce = h("input", { type: "checkbox", id: `pact-d-${f.id}` });
      const status = h("p", { class: "pact__status typed" });
      const pLab = h("label", { class: "check", for: `pact-p-${f.id}` }, propose, h("span", { class: "pact__plab" }, "propor pacto"));
      const dLab = h("label", { class: "check", for: `pact-d-${f.id}` }, denounce, h("span", null, "denunciar (−5 de moral)"));
      pactRefs.set(f.id, { propose, denounce, status, pLab, dLab, f });
      pactList.append(h("div", { class: "pact", "data-faction": f.id },
        h("span", { class: "pact__emb", style: { color: f.color } }, svgEl(emblemSVG(f.id, { size: 30 }))),
        h("div", { class: "pact__body" }, h("b", null, f.name), status, h("div", { class: "pact__opts" }, pLab, dLab))));
    }
  }

  function syncPacts(st) {
    for (const [id, ref] of pactRefs) {
      const act = (st.faction.pacts || []).find((p) => p.with === id);
      const proposed = (st.faction.pact_proposals_received || []).includes(id);
      const dead = !!ref.f.capitulated;
      if (act) ref.status.textContent = `Pacto ativo até o turno ${act.until_turn}: ataques entre as duas nações bloqueados.`;
      else if (proposed) ref.status.textContent = `${ref.f.short} propôs pacto. Aceite propondo de volta.`;
      else ref.status.textContent = dead ? "Nação capitulada." : "Sem pacto.";
      ref.pLab.querySelector(".pact__plab").textContent = act ? "já há pacto" : proposed ? "aceitar (propor de volta)" : "propor pacto";
      ref.propose.disabled = !!act || dead;
      ref.denounce.disabled = !act;
      if (!act) ref.denounce.checked = false;
      if (act) ref.propose.checked = false;
      ref.dLab.classList.toggle("is-off", !act);
    }
  }

  /* ------------------------------------------------------------ ordem */
  const orderBody = h("div", { class: "order-body gov" },
    h("div", { class: "gov-block" },
      h("p", { class: "caps faint" }, "Ração"),
      h("div", { class: "choices", role: "radiogroup", "aria-label": "Ração" }, racaoLabels)),
    h("div", { class: "gov-block" },
      h("p", { class: "caps faint" }, "Propaganda (0 a 5)"),
      h("div", { class: "prop" }, propRange, propNum),
      propHint),
    h("div", { class: "gov-block" },
      h("p", { class: "caps faint" }, "Jornada de trabalho"),
      h("div", { class: "choices", role: "radiogroup", "aria-label": "Jornada" }, horasLabels)),
    h("div", { class: "gov-block" },
      h("p", { class: "caps faint" }, "Transferências de recursos"),
      transferRows, addRowBtn, transferHint),
    h("div", { class: "gov-block" },
      h("p", { class: "caps faint" }, "Pactos de não agressão"),
      pactList));

  const sheet = orderSheet({
    ctx, section: "governo", body: orderBody,
    getPayload: () => {
      const racao = Number(orderBody.querySelector('input[name="gov-racao"]:checked')?.value ?? 0);
      const horas = Number(orderBody.querySelector('input[name="gov-horas"]:checked')?.value ?? 8);
      const propaganda = Number(propRange.value) || 0;
      const transfers = [];
      const errors = [];
      for (const row of transferRows.children) {
        const r = row.__read();
        const vals = RES.map((s) => r[s]);
        if (vals.some((v) => v !== null && v < 0)) { errors.push("Transferências não podem ser negativas."); continue; }
        const amounts = Object.fromEntries(RES.map((s, i) => [s, vals[i] ?? 0]));
        if (RES.every((s) => amounts[s] === 0)) continue;
        transfers.push({ to: r.to, ...amounts });
      }
      if (errors.length) { sheet.msg(errors, "errors", "Ordem recusada"); return null; }
      const pact_propose = [];
      const pact_denounce = [];
      for (const [id, ref] of pactRefs) {
        if (ref.propose.checked && !ref.propose.disabled) pact_propose.push(id);
        if (ref.denounce.checked && !ref.denounce.disabled) pact_denounce.push(id);
      }
      return { racao, propaganda, horas, transfers, pact_propose, pact_denounce };
    },
  });

  /* ------------------------------------------------------------ telegrafia */
  const tapeList = h("div", { class: "tape-list", "aria-live": "polite" });
  const toSel = h("select", { class: "input input--sel", id: "msg-to", "aria-label": "Destinatário do telegrama" });
  const txt = h("textarea", { id: "msg-text", class: "input msg-text", rows: "3", maxlength: String(MAX_MSG), placeholder: "Texto do telegrama diplomático (até 600 caracteres)" });
  const counter = h("span", { class: "hint mono" }, `0/${MAX_MSG}`);
  const msgNote = h("div", { class: "msg-note", "aria-live": "polite" });
  const msgBtn = h("button", { class: "btn btn--blue btn--small", type: "submit" }, "Transmitir telegrama");
  txt.addEventListener("input", () => { counter.textContent = `${txt.value.length}/${MAX_MSG}`; });

  async function sendMsg() {
    if (busyMsg) return;
    const to = toSel.value;
    const text = txt.value.trim();
    if (!to) { msgNote.replaceChildren(listBox(["Escolha a nação destinatária."], "errors", "Telegrama recusado")); return; }
    if (!text) { msgNote.replaceChildren(listBox(["O telegrama está vazio."], "errors", "Telegrama recusado")); return; }
    busyMsg = true; msgBtn.disabled = true;
    try {
      await ctx.api.post("/api/faction/message", { to_faction: to, text });
      txt.value = ""; counter.textContent = `0/${MAX_MSG}`;
      msgNote.replaceChildren(h("p", { class: "typed chal__ok" }, "Telegrama transmitido."));
      if (ctx.sfx) ctx.sfx.morse("OK");
      await ctx.reloadState();
    } catch (e) {
      if (e && e.status === 401) { ctx.sessionLost(); return; }
      msgNote.replaceChildren(listBox([e.message || "Falha ao transmitir."], "errors", "Telegrama recusado"));
    } finally {
      busyMsg = false; msgBtn.disabled = false;
    }
  }

  const tapeSheet = h("section", { class: "paper tape-sheet" },
    h("header", { class: "tape-sheet__head" },
      h("h3", { class: "stencil" }, "Telegrafia diplomática"),
      stampEl("Diplomacia", "olive")),
    h("p", { class: "typed faint" }, "Telegramas entre Governos. Só circulam com a guerra em andamento."),
    tapeList,
    h("form", { class: "msg-form", onsubmit: (e) => { e.preventDefault(); sendMsg(); } },
      h("div", { class: "field" }, h("label", { for: "msg-to" }, "Para"), toSel),
      h("div", { class: "field" }, h("label", { for: "msg-text" }, "Telegrama"), txt),
      h("div", { class: "row" }, msgBtn, counter),
      msgNote));

  root.replaceChildren(
    h("div", { class: "area-dossier" }, dossierSlot),
    h("div", { class: "area-chal" }, chal.el),
    h("div", { class: "area-side" }, sheet.el),
    h("div", { class: "area-tele" }, tapeSheet));

  /* ------------------------------------------------------------ estado */
  function prefill(o) {
    const key = JSON.stringify(o || null);
    if (key === lastOrderKey) return;
    lastOrderKey = key;
    if (touched || !o) return;
    const r = orderBody.querySelector(`input[name="gov-racao"][value="${o.racao}"]`);
    if (r) r.checked = true;
    const hz = orderBody.querySelector(`input[name="gov-horas"][value="${o.horas}"]`);
    if (hz) hz.checked = true;
    propRange.value = String(o.propaganda || 0);
    syncProp();
    transferRows.replaceChildren();
    for (const t of o.transfers || []) addTransferRow(t);
    for (const [id, ref] of pactRefs) {
      ref.propose.checked = (o.pact_propose || []).includes(id);
      ref.denounce.checked = (o.pact_denounce || []).includes(id);
    }
  }

  function renderMessages(st) {
    const msgs = (st.messages || []).slice(-30).reverse();
    const name = (id) => (ctx.name(id));
    tapeList.replaceChildren(...(msgs.length
      ? msgs.map((m) => telegramEl({
          head: m.from === st.faction.id ? `Enviado a ${name(m.to)}` : `Recebido de ${name(m.from)}`,
          meta: `Turno ${m.turn}`,
          body: m.text,
          cls: "telegram--diplo",
        }))
      : [h("p", { class: "typed faint" }, "Nenhum telegrama diplomático ainda.")]));
  }

  function renderToSel(st) {
    const cur = toSel.value;
    const opts = (st.factions || []).filter((f) => f.id !== st.faction.id && !f.capitulated);
    toSel.replaceChildren(...opts.map((f) => h("option", { value: f.id }, f.name)));
    if (opts.some((f) => f.id === cur)) toSel.value = cur;
  }

  function update() {
    const d = ctx.dossier("governo");
    const st = ctx.state();
    dossierSlot.replaceChildren(dossierPaper(d, { ctx, section: "governo" }));
    chal.update(d ? d.challenges : []);
    if (!st) return;
    fid = st.faction.id;
    const fk = (st.factions || []).map((f) => f.id).join(",") + "#" + fid;
    if (fk !== factionKey) {
      factionKey = fk;
      buildPacts(st);
      renderToSel(st);
    }
    syncPacts(st);
    syncProp();
    sheet.setTurn(st.game.turn);
    const o = st.orders && st.orders.governo;
    sheet.setLast(o ? [
      `Ração ${o.racao} · propaganda ${o.propaganda} · jornada ${o.horas} h`,
      o.transfers && o.transfers.length ? `Transferências: ${o.transfers.map((t) => `${t.to} (${RES.map((s) => `${s} ${fmt(t[s])}`).join(", ")})`).join("; ")}` : "Sem transferências",
      `Pactos: propor ${(o.pact_propose || []).join(", ") || "nenhum"} · denunciar ${(o.pact_denounce || []).join(", ") || "nenhum"}`,
    ] : null);
    prefill(o);
    renderMessages(st);
  }

  // qualquer toque do aluno marca o formulário como "editado" (não sobrescrevemos com a última ordem)
  orderBody.addEventListener("input", () => { touched = true; });
  orderBody.addEventListener("change", () => { touched = true; });

  return { update };
}
