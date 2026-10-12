/* =====================================================================
   emblems.js — emblemas das nações desenhados em SVG (as fontes embutidas
   são subconjuntos latin e não têm ∇ ⊥ ℛ ε ζ).
   ---------------------------------------------------------------------
   import { emblemSVG, FACTION_DEFAULTS } from "./emblems.js";
   emblemSVG("GAU")            -> string <svg> (cor = currentColor; use style="color:#2b4a74")
   emblemSVG("GAU", {ring:false, size:40})
   FACTION_DEFAULTS            -> {GAU:{name, short, color, capital}, ...}
   ===================================================================== */

export const FACTION_DEFAULTS = {
  GAU: { id: "GAU", name: "República de Gáussia", short: "Gáussia", color: "#2b4a74", capital: "Eliminópolis" },
  EUL: { id: "EUL", name: "Império de Eulerândia", short: "Eulerândia", color: "#8c2f23", capital: "Totiente" },
  HIL: { id: "HIL", name: "Federação de Hilbertânia", short: "Hilbertânia", color: "#4d5b24", capital: "Ortonormal" },
  NOE: { id: "NOE", name: "Reino de Noethéria", short: "Noethéria", color: "#a87a1c", capital: "Anelópolis" },
  CAU: { id: "CAU", name: "Principado de Cauchýria", short: "Cauchýria", color: "#5b3a6b", capital: "Convergência" },
  RIE: { id: "RIE", name: "Confederação de Riemânnia", short: "Riemânnia", color: "#3b5b5a", capital: "Zeta" },
};

// Glifos desenhados em traço (viewBox -50..50), centro em 0,0.
const GLYPHS = {
  // nabla: triângulo invertido, traço duplo
  GAU: `<path d="M-21 -17 H21 L0 21 Z" fill="none" stroke="currentColor" stroke-width="5.2" stroke-linejoin="miter"/>
        <path d="M-12.5 -11.5 H12.5 L0 11 Z" fill="currentColor" opacity=".22"/>`,
  // e (número de Euler) em serifada itálica desenhada
  EUL: `<path d="M-15 3 H15 C15 -9 8 -16 0 -16 C-9 -16 -17 -8 -17 2 C-17 12 -9 18 0 18 C7 18 12 14 15 10" fill="none" stroke="currentColor" stroke-width="5.4" stroke-linecap="round" stroke-linejoin="round"/>`,
  // perpendicular
  HIL: `<path d="M0 -20 V14 M-21 17 H21" fill="none" stroke="currentColor" stroke-width="5.6" stroke-linecap="butt"/>
        <path d="M0 -20 V14" stroke="currentColor" stroke-width="5.6" fill="none"/>
        <path d="M-9 17 V8 H9 V17" fill="none" stroke="currentColor" stroke-width="2.6" opacity=".0"/>`,
  // R caligráfico (anel)
  NOE: `<path d="M-12 20 V-18 H3 C14 -18 17 -11 17 -6 C17 1 12 4 3 4 H-12 M2 4 L16 20" fill="none" stroke="currentColor" stroke-width="5.4" stroke-linejoin="round" stroke-linecap="round"/>
        <path d="M-18 20 H-6" stroke="currentColor" stroke-width="3.6" fill="none"/>
        <path d="M-18 -18 H-8" stroke="currentColor" stroke-width="3.6" fill="none"/>`,
  // epsilon
  CAU: `<path d="M15 -12 C9 -18 -2 -18 -8 -12 C-14 -6 -8 -1 0 0 C-9 1 -15 6 -9 13 C-3 19 8 18 15 12" fill="none" stroke="currentColor" stroke-width="5.4" stroke-linecap="round" stroke-linejoin="round"/>`,
  // zeta
  RIE: `<path d="M-14 -17 H14 C5 -14 -7 -9 -7 -2 C-7 4 0 5 4 6 C10 8 12 13 8 17 C4 21 -3 20 -5 15" fill="none" stroke="currentColor" stroke-width="5.2" stroke-linecap="round" stroke-linejoin="round"/>`,
};

const NEUTRAL = `<circle r="5" fill="currentColor"/>`;

/** Emblema: duplo círculo + glifo, na cor `currentColor`. */
export function emblemSVG(fid, { size = null, ring = true, label = "" } = {}) {
  const glyph = GLYPHS[fid] || NEUTRAL;
  const dim = size ? ` width="${size}" height="${size}"` : "";
  const aria = label ? ` role="img" aria-label="${label}"` : ` aria-hidden="true"`;
  const rings = ring
    ? `<circle r="46" fill="none" stroke="currentColor" stroke-width="5"/>
       <circle r="37.5" fill="none" stroke="currentColor" stroke-width="2"/>`
    : "";
  return `<svg class="emblem-svg" viewBox="-50 -50 100 100"${dim}${aria} xmlns="http://www.w3.org/2000/svg">${rings}${glyph}</svg>`;
}

export default emblemSVG;
