/* =====================================================================
   qg/inteligencia.js — Inteligência: dossiê (leituras das estações, criptogramas),
   telegramas interceptados como tiras de telegrama, decifragem inline
   (chave pelo cabeçalho "URGENTE " ou chave colada) e ordem de bombardeio.
   A decifragem usa as ferramentas do servidor (hill_recover / hill_decrypt):
   é ajuda permitida; a lógica da análise continua com os alunos.
   ===================================================================== */
import {
  h, fmt, parseNum, stampEl, telegramEl, codesText, CIPHER_CRIB,
  dossierPaper, challengeBox, orderSheet,
} from "./common.js";

const KEY_STORE = "em_qg_keys";
const BOMB_COM = 4;

function readKeys() {
  try { return JSON.parse(localStorage.getItem(KEY_STORE) || "{}") || {}; } catch { return {}; }
}
function writeKey(ns, key) {
  try {
    const all = readKeys();
    all[ns] = key;
    localStorage.setItem(KEY_STORE, JSON.stringify(all));
  } catch { /* sem armazenamento: a chave fica só nesta tela */ }
}

/** Decifragem de um telegrama: chave 2×2 (colada ou obtida pelo cabeçalho). */
function decipherPanel(it, ns, crib, ctx) {
  const saved = readKeys()[ns] || null;
  const flatSaved = saved ? [saved[0][0], saved[0][1], saved[1][0], saved[1][1]] : [];
  const cells = [0, 1, 2, 3].map((i) => h("input", {
    class: "input key-cell", type: "text", inputmode: "numeric", maxlength: "3", autocomplete: "off",
    "aria-label": `Chave, posição ${i + 1} de 4`, value: flatSaved.length ? String(flatSaved[i]) : "",
  }));
  const status = h("p", { class: "hint decipher__status", "aria-live": "polite" },
    saved ? "Chave guardada neste PC para esta nação (troca a cada 2 turnos: confira o cabeçalho)." : "Cole a chave K = [[a, b], [c, d]] (inteiros mod 37) ou obtenha-a pelo cabeçalho.");
  const out = h("div", { class: "decoded", "aria-live": "polite" });

  const readKey = () => {
    const v = cells.map((c) => parseNum(c.value));
    if (v.some((x) => x === null || !Number.isInteger(x))) return null;
    return [[v[0], v[1]], [v[2], v[3]]];
  };
  const setKey = (K) => {
    const f = [K[0][0], K[0][1], K[1][0], K[1][1]];
    cells.forEach((c, i) => { c.value = String(f[i]); });
  };

  const recover = async () => {
    status.textContent = "Obtendo a chave pelo cabeçalho…";
    try {
      const r = await ctx.api.tool("hill_recover", { plain: crib, cipher: it.cipher.slice(0, crib.length), n: 2 });
      const K = r && r.key;
      if (Array.isArray(K) && K.length === 2) {
        setKey(K);
        writeKey(ns, K);
        status.textContent = `Chave obtida pelo cabeçalho «${crib}». Agora decifre o telegrama inteiro.`;
      } else {
        status.textContent = "A Mesa de Cálculo não devolveu a chave (modo simulado ou cabeçalho inválido).";
      }
    } catch (e) {
      status.textContent = e.message || "Falha ao obter a chave.";
    }
  };

  const decrypt = async () => {
    const K = readKey();
    if (!K) { status.textContent = "A chave tem quatro inteiros (ex.: 3, 3, 2, 5). Confira os campos."; return; }
    status.textContent = "Decifrando…";
    try {
      const r = await ctx.api.tool("hill_decrypt", { cipher: it.cipher, key: K });
      if (r && typeof r.plain === "string") {
        out.replaceChildren(h("p", { class: "typed decoded__text" }, r.plain));
        const ok = r.plain.startsWith(crib);
        status.textContent = ok
          ? `Cabeçalho «${crib}» confere: a chave está certa para este telegrama.`
          : `O cabeçalho não confere com «${crib}»: a chave está errada.`;
        if (ok) writeKey(ns, K);
      } else {
        status.textContent = "A Mesa de Cálculo não devolveu o texto (modo simulado?).";
      }
    } catch (e) {
      status.textContent = e.message || "Falha ao decifrar.";
    }
  };

  return h("details", { class: "decipher" },
    h("summary", null, "Decifrar com a chave"),
    h("div", { class: "key-row" },
      h("span", { class: "caps faint" }, "chave K"),
      h("span", { class: "key-grid" }, cells)),
    h("div", { class: "row" },
      h("button", { class: "btn btn--small", type: "button", onclick: recover }, `Obter chave pelo cabeçalho «${crib.trim()}»`),
      h("button", { class: "btn btn--small btn--blue", type: "button", onclick: decrypt }, "Decifrar")),
    status,
    out);
}

function interceptEl(it, ns, crib, ctx) {
  const codes = h("details", { class: "codes" },
    h("summary", null, "Índices da cifra (0–36, em pares)"),
    h("p", { class: "mono codes__txt" }, codesText(it.codes)));
  return telegramEl({
    head: `Interceptação — ${String(it.from_name || "").toUpperCase()}`,
    meta: `Turno ${it.turn} · ${it.kind === "flash" ? "relâmpago" : "briefing"}`,
    body: it.cipher, cipher: true, cls: "telegram--intercept",
    extra: [codes, decipherPanel(it, `${ns}${it.from}`, crib, ctx)],
  });
}

export function mountInteligencia(root, ctx) {
  root.classList.add("sec", "sec--inteligencia");
  const dossierSlot = h("div", { class: "slot slot--dossier" });
  const interList = h("div", { class: "intercepts" });
  const interSheet = h("section", { class: "paper intercept-sheet" },
    h("header", { class: "intercept-sheet__head" },
      h("h3", { class: "stencil" }, "Telegramas interceptados"),
      stampEl("Interceptado", "blue")),
    h("p", { class: "typed faint" }, "Cifra de Hill 2×2 sobre 37 símbolos (A–Z, 0–9 e espaço). O espaço interno aparece como ·. Todo telegrama começa por «URGENTE »."),
    interList);
  const chal = challengeBox({ ctx, section: "inteligencia" });

  /* ------------------------------------------------------------ ordem: bombardeio */
  let choice = "nao";
  let curDep = null;
  const depTxt = h("p", { class: "typed depot__txt" });
  const radioBomb = h("input", { type: "radio", name: "bomb-choice", value: "bomb", id: "bomb-yes" });
  const radioNo = h("input", { type: "radio", name: "bomb-choice", value: "nao", id: "bomb-no", checked: true });
  const confirmBox = h("input", { type: "checkbox", id: "bomb-ok" });
  const confirmRow = h("label", { class: "check confirm-row", for: "bomb-ok", hidden: true }, confirmBox, " Confirmo o bombardeio deste depósito (custa 4 COM).");
  const comNote = h("p", { class: "hint" });
  const bombLabel = h("label", { class: "choice", for: "bomb-yes" }, radioBomb,
    h("span", null, h("b", null, "Bombardear o depósito"), h("small", null, "perde 25% do maior estoque do dono; matriz A piora")));
  const noLabel = h("label", { class: "choice", for: "bomb-no" }, radioNo,
    h("span", null, h("b", null, "Não bombardear"), h("small", null, "nenhuma ação de bombardeio neste turno")));
  for (const r of [radioBomb, radioNo]) r.addEventListener("change", () => { choice = radioBomb.checked ? "bomb" : "nao"; syncBomb(); });
  confirmBox.addEventListener("change", () => syncBomb());

  function syncBomb() {
    const on = choice === "bomb" && !!curDep;
    confirmRow.hidden = !on;
    bombLabel.classList.toggle("is-on", on);
    noLabel.classList.toggle("is-on", !on);
  }

  const orderBody = h("div", { class: "order-body depot" },
    depTxt,
    h("div", { class: "choices" }, bombLabel, noLabel),
    confirmRow,
    comNote);

  const sheet = orderSheet({
    ctx, section: "inteligencia", body: orderBody,
    getPayload: () => {
      if (choice === "bomb" && curDep) {
        if (!confirmBox.checked) {
          sheet.msg(["Marque a confirmação antes de carimbar o bombardeio."], "errors", "Falta confirmar");
          return null;
        }
        return { bombard: curDep.territory };
      }
      return { bombard: null };
    },
  });

  root.replaceChildren(
    h("div", { class: "area-dossier" }, dossierSlot, interSheet),
    h("div", { class: "area-side" }, chal.el, sheet.el));

  let interKey = null;
  let dossierShown = null;

  function renderDepot(st) {
    const dep = st.faction.bonuses && st.faction.bonuses.depot_located;
    curDep = dep || null;
    const com = Number(st.faction.stock.COM) || 0;
    if (dep) {
      const owner = dep.owner ? ctx.name(dep.owner) : "milícia neutra";
      depTxt.textContent = `Depósito localizado em ${dep.name} (${dep.territory}), de ${owner}. O bombardeio está liberado só neste turno.`;
      radioBomb.disabled = false;
    } else {
      depTxt.textContent = "Nenhum depósito localizado neste turno. Triangule a posição do depósito inimigo (questionário ao lado): ao acertar, o território é revelado e a ordem é liberada. Sem isso, a ordem é não bombardear.";
      radioBomb.disabled = true;
      if (choice === "bomb") { choice = "nao"; radioNo.checked = true; }
    }
    comNote.textContent = com < BOMB_COM
      ? `Combustível insuficiente: ${fmt(com)} COM em estoque, o bombardeio custa ${BOMB_COM}.`
      : `Combustível em estoque: ${fmt(com)} COM (bombardeio custa ${BOMB_COM}).`;
    syncBomb();
  }

  function renderIntercepts(its, crib, ns) {
    const list = [...its].reverse();
    interList.replaceChildren(...(list.length
      ? list.map((it) => interceptEl(it, ns, crib, ctx))
      : [h("p", { class: "typed faint" }, "Nenhum telegrama interceptado ainda. Os da metade do turno chegam como relâmpago.")]));
  }

  function update() {
    const d = ctx.dossier("inteligencia");
    const st = ctx.state();
    if (d !== dossierShown) {
      dossierShown = d;
      dossierSlot.replaceChildren(dossierPaper(d, { ctx, section: "inteligencia" }));
    }
    const crib = (d && d.extras && d.extras.crib) || CIPHER_CRIB;
    const its = (d && d.extras && d.extras.intercepts) || [];
    const ns = st ? `${st.faction.id}:` : "";
    const key = its.map((x) => `${x.id}:${x.cipher.length}`).join("|") + `#${st ? st.faction.id : ""}`;
    if (key !== interKey) {
      interKey = key;
      renderIntercepts(its, crib, ns);
    }
    chal.update(d ? d.challenges : []);
    if (st) {
      sheet.setTurn(st.game.turn);
      const o = st.orders && st.orders.inteligencia;
      sheet.setLast(o ? [o.bombard ? `Bombardeio em ${o.bombard}` : "Sem bombardeio"] : null);
      renderDepot(st);
    }
  }

  return { update };
}
