/* =====================================================================
   qg/intendencia.js — Intendência: dossiê (transações Z, produção X),
   questionário (Leontief) e ordem de produção + recrutamento com prévia.
   A prévia é ESTIMATIVA local: (I−A)x com A = Z·diag(X)⁻¹ calculada aqui;
   a resolução usa a matriz oculta do turno e pode diferir um pouco.
   ===================================================================== */
import { h, fmt, parseNum, RES, RES_NAMES, dossierPaper, challengeBox, orderSheet, stampEl } from "./common.js";

const LABOR_DEFAULT = { ALI: 1.0, ACO: 1.5, COM: 1.2 };
const RECRUIT_DEFAULT = { ALI: 2, ACO: 2, COM: 1 };

/** A = Z·diag(X)⁻¹ a partir do dataset "transacoes" (linhas Z + linha X). */
export function matrixAFromDossier(d) {
  const ds = d && (d.datasets || []).find((x) => x.id === "transacoes");
  if (!ds) return null;
  const X = ds.rows.find((r) => r[0] === "X");
  const Z = ds.rows.filter((r) => r !== X);
  if (!X || Z.length !== 3) return null;
  const Xv = X.slice(1, 4).map(Number);
  if (Xv.some((v) => !(v > 0))) return null;
  return Z.map((r) => r.slice(1, 4).map((v, j) => Number(v) / Xv[j]));
}

/** y = (I − A)x */
function netOf(A, x) {
  return x.map((xi, i) => xi - A[i].reduce((acc, a, j) => acc + a * x[j], 0));
}

export function mountIntendencia(root, ctx) {
  root.classList.add("sec", "sec--intendencia");
  const dossierSlot = h("div", { class: "slot slot--dossier" });
  const chal = challengeBox({ ctx, section: "intendencia" });

  const inputs = {};
  let touched = false;
  let lastOrderKey = "";
  let curTurn = null;
  let A = null;                       // matriz A estimada (botão "usar A da tabela")
  const aBtn = h("button", { class: "btn btn--small", type: "button" }, "Usar A da tabela");
  const aNote = h("p", { class: "hint" }, "Calcula A = Z·diag(X)⁻¹ com a tabela de transações. Sem ela, a prévia mostra só a mão de obra e a capacidade.");
  const aSlot = h("div", { class: "a-slot" });
  const prevSlot = h("div", { class: "preview" });

  const prodFields = RES.map((s) => {
    const id = `int-x-${s}`;
    const inp = h("input", {
      id, type: "number", min: "0", step: "0.5", inputmode: "decimal", class: "input input--num",
      oninput: () => { touched = true; preview(); },
    });
    inputs[s] = inp;
    return h("div", { class: "prod" },
      h("label", { for: id }, `${RES_NAMES[s]} (${s})`),
      inp,
      h("small", { class: "hint", "data-cap": s }, ""));
  });
  const recInp = h("input", {
    id: "int-rec", type: "number", min: "0", step: "1", inputmode: "numeric", class: "input input--num",
    oninput: () => { touched = true; preview(); },
  });
  inputs.recruit = recInp;

  aBtn.addEventListener("click", () => {
    const d = ctx.dossier("intendencia");
    A = matrixAFromDossier(d);
    if (!A) aNote.textContent = "Não foi possível calcular A: a tabela de transações está incompleta.";
    preview();
  });

  const orderBody = h("div", { class: "order-body" },
    h("div", { class: "prod-grid" }, prodFields),
    h("div", { class: "field recruit" },
      h("label", { for: "int-rec" }, "Recrutar batalhões (custo por batalhão: ALI 2, ACO 2, COM 1)"),
      recInp),
    h("div", { class: "row a-row" }, aBtn),
    aNote, aSlot,
    prevSlot);

  const sheet = orderSheet({
    ctx, section: "intendencia", body: orderBody,
    getPayload: () => {
      const production = {};
      for (const s of RES) {
        const v = parseNum(inputs[s].value);
        production[s] = v === null ? 0 : Math.max(0, Math.round(v * 100) / 100);
      }
      const rv = parseNum(recInp.value);
      const recruit = rv === null ? 0 : Math.max(0, Math.floor(rv));
      return { production, recruit };
    },
  });

  function readX() {
    return RES.map((s) => { const v = parseNum(inputs[s].value); return v === null ? 0 : Math.max(0, v); });
  }

  /** Prévia ao vivo: mão de obra, capacidade, produção líquida e estoque projetado. */
  function preview() {
    const st = ctx.state();
    const d = ctx.dossier("intendencia");
    if (!st) return;
    const f = st.faction;
    const L = (d && d.extras && d.extras.labor) || f.labor || LABOR_DEFAULT;
    const cap = f.capacity || {};
    const rc = (d && d.extras && d.extras.recruit_cost) || RECRUIT_DEFAULT;
    const upkeep = (d && d.extras && d.extras.upkeep_forecast && d.extras.upkeep_forecast.total) || 0;
    const W = Number(f.workforce) || 0;
    const x = readX();
    const recruit = Math.max(0, Math.floor(parseNum(recInp.value) || 0));
    const used = RES.reduce((acc, s, i) => acc + Number(L[s]) * x[i], 0);

    RES.forEach((s, i) => {
      const hint = root.querySelector(`[data-cap="${s}"]`);
      if (!hint) return;
      const over = x[i] > Number(cap[s] || 0) + 1e-9;
      hint.textContent = `capacidade ${fmt(cap[s])}${over ? " · acima da capacidade (será cortado)" : ""}`;
      hint.classList.toggle("is-warn", over);
    });

    const pct = W > 0 ? Math.min(100, (used / W) * 100) : 0;
    const laborOver = used > W + 1e-9;
    const gauge = h("div", { class: "gauge", role: "img", "aria-label": `Mão de obra usada ${fmt(used)} de ${fmt(W)}` },
      h("div", { class: `gauge__fill${laborOver ? " is-over" : ""}`, style: { width: `${pct}%` } }));
    const laborLine = h("p", { class: "prev__line" },
      h("span", null, "Mão de obra usada "),
      h("b", { class: "mono" }, fmt(used)),
      h("span", null, " de "),
      h("b", { class: "mono" }, fmt(W)),
      h("span", null, " disponíveis"),
      laborOver ? h("span", { class: "warn-tag" }, "insuficiente: a produção será reduzida") : null);

    const children = [h("p", { class: "caps faint" }, "Prévia da ordem (estimativa)"), gauge, laborLine];

    if (A) {
      const net = netOf(A, x);
      const recCost = RES.map((s) => (rc[s] || 0) * recruit);
      const stock = RES.map((s) => Number(f.stock[s]) || 0);
      const proj = RES.map((s, i) => stock[i] + net[i] - recCost[i] - (s === "ALI" ? upkeep : 0));
      const row = (label, vals, cls = "") => h("tr", { class: cls },
        h("th", { class: "txt" }, label),
        vals.map((v) => h("td", { class: v < 0 ? "is-neg" : "" }, fmt(v, 1))));
      children.push(h("div", { class: "ledger-wrap" },
        h("table", { class: "ledger ledger--proj" },
          h("thead", null, h("tr", null,
            h("th", { class: "txt" }, "Setor"),
            RES.map((s) => h("th", null, s)))),
          h("tbody", null,
            row("Estoque atual", stock),
            row("+ produção líquida (I−A)x", net),
            row("− recrutamento", recCost.map((v) => -v)),
            row("− manutenção ALI (tropas + civil)", RES.map((s) => (s === "ALI" ? -upkeep : 0))),
            row("= estoque projetado", proj, "is-total")))));
      children.push(h("p", { class: "hint" },
        "Estimativa: a produção líquida usa A do turno anterior. A resolução aplica a matriz do turno, a jornada, a moral e a mão de obra efetiva."));
      if (proj.some((v) => v < 0)) children.push(h("p", { class: "warnings" }, "Projeção negativa: a nação entra em falta de alimento se a ordem for esta."));
    }
    prevSlot.replaceChildren(...children);
  }

  function renderA() {
    if (!A) { aSlot.replaceChildren(); return; }
    aSlot.replaceChildren(h("div", { class: "ledger-wrap" },
      h("p", { class: "caps faint" }, "Matriz técnica A estimada"),
      h("table", { class: "ledger" },
        h("thead", null, h("tr", null, h("th", { class: "txt" }, "de \\ para"), RES.map((s) => h("th", null, s)))),
        h("tbody", null, A.map((r, i) => h("tr", null, h("th", { class: "txt" }, RES[i]), r.map((v) => h("td", null, fmt(v, 3)))))))));
  }

  function prefill(order) {
    const key = JSON.stringify(order || null);
    if (key === lastOrderKey) return;
    lastOrderKey = key;
    if (touched || !order) return;
    const p = order.production || {};
    for (const s of RES) inputs[s].value = p[s] !== undefined ? String(p[s]).replace(".", ",") : "";
    recInp.value = order.recruit !== undefined ? String(order.recruit) : "";
  }

  function update() {
    const d = ctx.dossier("intendencia");
    const st = ctx.state();
    dossierSlot.replaceChildren(dossierPaper(d, { ctx, section: "intendencia" }));
    chal.update(d ? d.challenges : []);
    if (d && d.turn !== curTurn) { curTurn = d.turn; A = null; aNote.textContent = "Calcula A = Z·diag(X)⁻¹ com a tabela de transações. Sem ela, a prévia mostra só a mão de obra e a capacidade."; }
    if (st) {
      const o = st.orders && st.orders.intendencia;
      sheet.setTurn(st.game.turn);
      sheet.setLast(o ? [
        `Produção bruta: Alimento ${fmt(o.production.ALI)} · Aço ${fmt(o.production.ACO)} · Combustível ${fmt(o.production.COM)}`,
        `Recrutas: ${o.recruit} batalhão(ões)`,
      ] : null);
      prefill(o);
    }
    renderA();
    preview();
  }

  root.replaceChildren(dossierSlot, h("div", { class: "side" }, chal.el, sheet.el));
  return { update };
}
