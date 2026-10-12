/* =====================================================================
   sfx.js — sons sintetizados (WebAudio), sem arquivos, discretos.
   ---------------------------------------------------------------------
   import { sfx } from "./sfx.js";
   sfx.key()          tecla de máquina de escrever
   sfx.stamp()        batida de carimbo de borracha
   sfx.morse("SOS")   bipes de telégrafo (máx. 20 caracteres)
   sfx.alarm()        três toques de campainha (último minuto)
   sfx.page()         folha de papel virando
   sfx.flap()         plaquinha de relógio split-flap
   sfx.thud()         estrondo surdo (batalha)
   sfx.setMuted(bool) / sfx.muted / sfx.unlocked
   O áudio só é criado depois do primeiro clique/tecla/toque do usuário
   (política dos navegadores). Antes disso, todas as chamadas são mudas e seguras.
   ===================================================================== */

const MORSE = {
  A: ".-", B: "-...", C: "-.-.", D: "-..", E: ".", F: "..-.", G: "--.", H: "....", I: "..", J: ".---",
  K: "-.-", L: ".-..", M: "--", N: "-.", O: "---", P: ".--.", Q: "--.-", R: ".-.", S: "...", T: "-",
  U: "..-", V: "...-", W: ".--", X: "-..-", Y: "-.--", Z: "--..",
  0: "-----", 1: ".----", 2: "..---", 3: "...--", 4: "....-", 5: ".....", 6: "-....", 7: "--...", 8: "---..", 9: "----.",
};

let ctx = null;
let master = null;
let noiseBuf = null;
let muted = false;
let unlocked = false;
try { muted = localStorage.getItem("em_muted") === "1"; } catch { /* sem storage */ }

function ensure() {
  if (!unlocked || muted) return null;
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    try {
      ctx = new AC();
      master = ctx.createGain();
      master.gain.value = 0.55;
      const comp = ctx.createDynamicsCompressor();
      master.connect(comp);
      comp.connect(ctx.destination);
      // ruído branco de 1 s, reaproveitado por todos os sons
      noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
      const d = noiseBuf.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    } catch { ctx = null; return null; }
  }
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  return ctx;
}

function noise(t, dur, { type = "bandpass", freq = 2000, q = 1, gain = 0.3, attack = 0.002, freqEnd = null } = {}) {
  const src = ctx.createBufferSource();
  src.buffer = noiseBuf;
  src.loop = true;
  const f = ctx.createBiquadFilter();
  f.type = type;
  f.frequency.setValueAtTime(freq, t);
  if (freqEnd) f.frequency.exponentialRampToValueAtTime(freqEnd, t + dur);
  f.Q.value = q;
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.linearRampToValueAtTime(gain, t + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  src.connect(f); f.connect(g); g.connect(master);
  src.start(t, Math.random() * 0.5); src.stop(t + dur + 0.02);
}

function tone(t, dur, { freq = 440, freqEnd = null, type = "sine", gain = 0.2, attack = 0.004 } = {}) {
  const o = ctx.createOscillator();
  o.type = type;
  o.frequency.setValueAtTime(freq, t);
  if (freqEnd) o.frequency.exponentialRampToValueAtTime(freqEnd, t + dur);
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.linearRampToValueAtTime(gain, t + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g); g.connect(master);
  o.start(t); o.stop(t + dur + 0.02);
}

export const sfx = {
  get muted() { return muted; },
  get unlocked() { return unlocked; },

  setMuted(v) {
    muted = !!v;
    try { localStorage.setItem("em_muted", muted ? "1" : "0"); } catch { /* sem storage */ }
    if (ctx && master) master.gain.value = muted ? 0 : 0.55;
  },

  /** Tecla de máquina de escrever: clique seco + batida grave curta. */
  key() {
    if (!ensure()) return;
    const t = ctx.currentTime;
    noise(t, 0.035, { freq: 3200 + Math.random() * 900, q: 1.4, gain: 0.35 });
    tone(t, 0.05, { freq: 170 + Math.random() * 30, freqEnd: 90, type: "triangle", gain: 0.22 });
  },

  /** Carimbo de borracha: baque surdo + estalo de papel. */
  stamp() {
    if (!ensure()) return;
    const t = ctx.currentTime;
    tone(t, 0.18, { freq: 120, freqEnd: 42, type: "sine", gain: 0.7, attack: 0.002 });
    noise(t, 0.09, { type: "lowpass", freq: 1400, gain: 0.55 });
    noise(t + 0.01, 0.03, { type: "highpass", freq: 3000, gain: 0.12 });
  },

  /** Telégrafo: sequência de bipes de 650 Hz. */
  morse(text = "STOP") {
    if (!ensure()) return;
    const unit = 0.07;
    let t = ctx.currentTime + 0.02;
    const s = String(text).toUpperCase().slice(0, 20);
    for (const ch of s) {
      if (ch === " ") { t += unit * 4; continue; }
      const code = MORSE[ch];
      if (!code) continue;
      for (const sym of code) {
        const len = sym === "." ? unit : unit * 3;
        tone(t, len, { freq: 650, type: "square", gain: 0.05, attack: 0.006 });
        t += len + unit;
      }
      t += unit * 2;
    }
  },

  /** Campainha: três pancadas de dois tons. */
  alarm() {
    if (!ensure()) return;
    const t = ctx.currentTime;
    for (let i = 0; i < 3; i++) {
      tone(t + i * 0.28, 0.2, { freq: 880, type: "triangle", gain: 0.16 });
      tone(t + i * 0.28 + 0.01, 0.2, { freq: 1318, type: "sine", gain: 0.07 });
    }
  },

  /** Folha virando: varredura de ruído filtrado. */
  page() {
    if (!ensure()) return;
    const t = ctx.currentTime;
    noise(t, 0.32, { freq: 900, freqEnd: 4200, q: 0.7, gain: 0.22, attack: 0.08 });
    noise(t + 0.22, 0.08, { type: "highpass", freq: 5000, gain: 0.08 });
  },

  /** Plaquinha de split-flap. */
  flap() {
    if (!ensure()) return;
    const t = ctx.currentTime;
    noise(t, 0.02, { freq: 2600 + Math.random() * 600, q: 2, gain: 0.16 });
    noise(t + 0.07, 0.02, { freq: 1800, q: 2, gain: 0.12 });
  },

  /** Estrondo distante (batalha). */
  thud() {
    if (!ensure()) return;
    const t = ctx.currentTime;
    tone(t, 0.5, { freq: 78, freqEnd: 30, type: "sine", gain: 0.6, attack: 0.004 });
    noise(t, 0.35, { type: "lowpass", freq: 600, freqEnd: 120, gain: 0.5 });
  },
};

function unlock() {
  if (unlocked) return;
  unlocked = true;
  ensure();
  for (const ev of ["pointerdown", "keydown", "touchstart"]) window.removeEventListener(ev, unlock, true);
}
for (const ev of ["pointerdown", "keydown", "touchstart"]) window.addEventListener(ev, unlock, true);

export default sfx;
