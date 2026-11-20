/* =====================================================================
   cinema.js — vídeos de instrução dentro do QG.
   O catálogo fica em /videos/index.json (servido pelo próprio servidor do jogo,
   sem depender de internet):
     { "secoes":   { "<seção>": { "arquivo", "titulo", "duracao" } },
       "briefing": { "<n.º de nações>": { "<id da nação>": { "arquivo", "titulo", "duracao" } } },
       "geral":    { "arquivo", "titulo", "duracao" } }      (opcional: fallback do briefing)
   Um vídeo que não está no catálogo simplesmente não ganha botão.
   ===================================================================== */
import { h } from "./common.js";

const $ = (id) => document.getElementById(id);
let catalogo = null;
let aberto = false;

export async function loadCatalog() {
  try {
    const r = await fetch("/videos/index.json", { cache: "no-cache" });
    catalogo = r.ok ? await r.json() : {};
  } catch {
    catalogo = {};
  }
  return catalogo;
}

/** Vídeo de instrução da seção, ou null. */
export function sectionVideo(sec) {
  return (catalogo && catalogo.secoes && catalogo.secoes[sec]) || null;
}

/** Briefing da nação para uma partida com n nações; senão o vídeo geral; senão null. */
export function briefingVideo(fid, n) {
  const b = catalogo && catalogo.briefing && catalogo.briefing[String(n)];
  return (b && b[fid]) || (catalogo && catalogo.geral) || null;
}

/** Abre o "cinema": uma tela de projeção por cima do QG. */
export function openFilm(v, { kicker = "Instrução em vídeo" } = {}) {
  if (!v) return;
  const box = $("cine");
  const video = h("video", {
    class: "cine__video", controls: "", playsinline: "", preload: "metadata",
    src: `/videos/${v.arquivo}`,
  });
  box.replaceChildren(
    h("header", { class: "cine__head" },
      h("div", null,
        h("p", { class: "caps cine__kicker" }, kicker),
        h("h2", { class: "stencil", id: "cine-title" }, v.titulo || "Instrução")),
      h("button", { class: "btn btn--small cine__close", type: "button", onclick: closeFilm }, "Fechar")),
    video,
    h("p", { class: "typed cine__note" },
      v.duracao ? `Duração: ${v.duracao}. ` : "",
      "Pause quando quiser e repita o passo na Mesa de Cálculo. O relógio da guerra continua correndo."));
  box.classList.remove("hidden");
  $("cine-veil").classList.remove("hidden");
  aberto = true;
  video.play?.().catch(() => { /* o navegador pode exigir um clique */ });
  box.querySelector(".cine__close").focus();
}

export function closeFilm() {
  if (!aberto) return;
  const box = $("cine");
  const v = box.querySelector("video");
  if (v) { v.pause(); v.removeAttribute("src"); v.load(); }
  box.classList.add("hidden");
  box.replaceChildren();
  $("cine-veil").classList.add("hidden");
  aberto = false;
}

export const filmOpen = () => aberto;
