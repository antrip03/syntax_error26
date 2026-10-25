// Ambient sound and small-talk sounds, all synthesised with the Web Audio API (no audio files).
// One "bed" per area (village by day / by night, and each interior), crossfaded as you move.
// Townsfolk get a short grunt or "hm" when you chat; animals cluck, meow or quack.
// The AudioContext starts on the first key press or click (browser autoplay rules).

import { on } from "./store.js";

const KEY = "vaudville-sound";
let enabled = (() => { try { return localStorage.getItem(KEY) !== "off"; } catch { return true; } })();
let ctx = null, master = null, duckGain = null, noiseBuf = null;
let want = "village", bed = null, night = false, ducked = false;

export const soundOn = () => enabled;
export function setSound(v) {
  enabled = v;
  try { localStorage.setItem(KEY, v ? "on" : "off"); } catch { /* private mode */ }
  if (!ctx) return;
  master.gain.setTargetAtTime(v ? 0.42 : 0, ctx.currentTime, 0.2);
  if (v && !bed) startBed(want);
}

function init() {
  if (ctx) { if (ctx.state === "suspended") ctx.resume(); return; }
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return;
  ctx = new AC();
  master = ctx.createGain(); master.gain.value = enabled ? 0.42 : 0;
  duckGain = ctx.createGain(); duckGain.gain.value = 1;
  duckGain.connect(master); master.connect(ctx.destination);
  noiseBuf = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
  const d = noiseBuf.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  startBed(want);
}
for (const ev of ["pointerdown", "keydown"]) window.addEventListener(ev, init, { passive: true });
export const unlockAudio = () => init(); // for handlers that stop the key event before it reaches window

// ---------- building blocks ----------

const rnd = (a, b) => a + Math.random() * (b - a);

function noise(out, { type = "lowpass", freq = 800, q = 0.7, gain = 0.05 } = {}) {
  const src = ctx.createBufferSource(); src.buffer = noiseBuf; src.loop = true;
  src.loopStart = Math.random(); // decorrelate layers
  const f = ctx.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q;
  const g = ctx.createGain(); g.gain.value = gain;
  src.connect(f).connect(g).connect(out); src.start();
  return { src, f, g, stop: () => src.stop() };
}

function lfo(param, rate, depth, base) {
  const o = ctx.createOscillator(); o.frequency.value = rate;
  const g = ctx.createGain(); g.gain.value = depth;
  param.value = base;
  o.connect(g).connect(param); o.start();
  return { stop: () => o.stop() };
}

// A short enveloped tone. env: [attack, decay]
function blip(out, { freq, to = null, type = "sine", gain = 0.05, attack = 0.005, dur = 0.12, filter = null, q = 1, at = 0 }) {
  const t = ctx.currentTime + at;
  const o = ctx.createOscillator(); o.type = type; o.frequency.setValueAtTime(freq, t);
  if (to) o.frequency.exponentialRampToValueAtTime(to, t + dur);
  const g = ctx.createGain(); g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(gain, t + attack); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  let node = o;
  if (filter) { const f = ctx.createBiquadFilter(); f.type = "bandpass"; f.frequency.value = filter; f.Q.value = q; node = o.connect(f); }
  node.connect(g).connect(out);
  o.start(t); o.stop(t + dur + 0.05);
}

function burst(out, { freq = 3000, type = "highpass", gain = 0.06, dur = 0.03, q = 0.8, at = 0 }) {
  const t = ctx.currentTime + at;
  const src = ctx.createBufferSource(); src.buffer = noiseBuf;
  const f = ctx.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q;
  const g = ctx.createGain(); g.gain.setValueAtTime(gain, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  src.connect(f).connect(g).connect(out);
  src.start(t, Math.random() * 1.5, dur + 0.05);
}

// Metallic strike: a few inharmonic partials (anvils, pans, bells, glasses).
function metal(out, base, { gain = 0.05, dur = 0.6, ratios = [1, 2.76, 5.4, 8.9] } = {}) {
  ratios.forEach((r, i) => blip(out, { freq: base * r, gain: gain / (i + 1), dur: dur / (1 + i * 0.4), attack: 0.002 }));
}

// Repeats fn at random intervals until stopped.
function every(min, max, fn) {
  let alive = true, id;
  const loop = () => { if (!alive) return; fn(); id = setTimeout(loop, rnd(min, max)); };
  id = setTimeout(loop, rnd(min * 0.3, max * 0.6));
  return { stop: () => { alive = false; clearTimeout(id); } };
}

function crackle(out, gain = 0.05) {
  return every(180, 900, () => burst(out, { freq: rnd(350, 900), type: "bandpass", q: 1.2, gain: gain * rnd(0.3, 0.8), dur: rnd(0.02, 0.05) }));
}

function murmur(out, level = 1, [min, max] = [900, 2600]) {
  // a crowd far off: quiet mumbled syllables from random voices, muffled
  const lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 1400; lp.connect(out);
  const g = ctx.createGain(); g.gain.value = 0.35 * level; g.connect(lp);
  const e = every(min, max, () => voiceSyllables(g, ["m", "f", "m_old", "f"][Math.floor(Math.random() * 4)], Math.floor(rnd(1, 4)), 0.5));
  return { stop: () => { e.stop(); lp.disconnect(); } };
}

// ---------- beds ----------

const BEDS = {
  village(out) {
    const parts = [];
    parts.push(murmur(out, 0.5, [2500, 6000]));
    parts.push(every(4000, 11000, () => { if (!night) birdSong(out); }));
    parts.push(every(600, 1400, () => {
      if (!night) return;
      for (let i = 0; i < 2; i++) blip(out, { freq: 3600, gain: 0.006, dur: 0.05, attack: 0.01, at: i * 0.09 });
    }));
    return parts;
  },
  chapel(out) {
    const parts = [];
    const chords = [[146.8, 185, 220, 293.7], [130.8, 164.8, 196, 261.6], [110, 146.8, 174.6, 220]];
    const voices = [];
    const lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 1100; lp.connect(out);
    const pad = ctx.createGain(); pad.gain.value = 0; pad.connect(lp);
    pad.gain.linearRampToValueAtTime(0.03, ctx.currentTime + 3);
    for (let i = 0; i < 4; i++) for (const det of [-4, 4]) {
      const o = ctx.createOscillator(); o.type = "triangle"; o.detune.value = det; o.frequency.value = chords[0][i];
      o.connect(pad); o.start(); voices.push({ o, i });
    }
    // hummed choir: sawtooth through an "ah" formant, with vibrato
    const choir = ctx.createGain(); choir.gain.value = 0.008; choir.connect(out);
    const form = ctx.createBiquadFilter(); form.type = "bandpass"; form.frequency.value = 760; form.Q.value = 4; form.connect(choir);
    const sing = [0, 2].map((i) => { const o = ctx.createOscillator(); o.type = "sawtooth"; o.frequency.value = chords[0][i] * 2; o.connect(form); o.start(); return { o, i }; });
    const vib = ctx.createOscillator(); vib.frequency.value = 5; const vg = ctx.createGain(); vg.gain.value = 6;
    vib.connect(vg); sing.forEach((s) => vg.connect(s.o.detune)); vib.start();
    let k = 0;
    parts.push(every(9000, 13000, () => {
      k = (k + 1) % chords.length;
      const t = ctx.currentTime;
      voices.forEach(({ o, i }) => o.frequency.setTargetAtTime(chords[k][i], t, 0.8));
      sing.forEach(({ o, i }) => o.frequency.setTargetAtTime(chords[k][i] * 2, t, 0.8));
    }));
    parts.push(every(26000, 42000, () => metal(out, 262, { gain: 0.022, dur: 4, ratios: [1, 2.0, 2.4, 3.0] })));
    parts.push({ stop: () => { voices.forEach(({ o }) => o.stop()); sing.forEach(({ o }) => o.stop()); vib.stop(); } });
    return parts;
  },
  bakery(out) {
    return [crackle(out, 0.04), murmur(out, 0.8),
      every(6000, 14000, () => metal(out, rnd(420, 620), { gain: 0.018, dur: 0.3, ratios: [1, 2.76, 5.4] }))];
  },
  inn(out) {
    return [crackle(out, 0.05), murmur(out, 1.2, [500, 1500]),
      every(6000, 15000, () => { const f = rnd(1800, 2400); blip(out, { freq: f, gain: 0.012, dur: 0.2 }); blip(out, { freq: f * 1.5, gain: 0.007, dur: 0.15, at: 0.05 }); })];
  },
  guildhall(out) {
    let tock = false;
    return [
      every(1000, 1001, () => { tock = !tock; burst(out, { freq: tock ? 700 : 950, type: "bandpass", q: 5, gain: 0.04, dur: 0.025 }); })];
  },
  smithy(out) {
    const roar = noise(out, { freq: 140, gain: 0 });
    return [roar, lfo(roar.g.gain, 0.35, 0.008, 0.018), crackle(out, 0.045),
      every(2600, 4800, () => metal(out, rnd(520, 640), { gain: 0.04, dur: 0.8, ratios: [1, 2.76, 5.4] }))];
  },
  mill(out) {
    const rumble = noise(out, { freq: 90, gain: 0 });
    return [rumble, lfo(rumble.g.gain, 0.5, 0.012, 0.025),
      every(300, 900, () => blip(out, { freq: rnd(500, 900), to: rnd(900, 1400), gain: 0.008, dur: 0.06, attack: 0.01 })), // water drips
      every(5000, 10000, () => blip(out, { freq: rnd(110, 160), to: rnd(90, 200), type: "sawtooth", gain: 0.02, dur: rnd(0.4, 0.8), attack: 0.1, filter: 600, q: 3 }))];
  },
  river(out) { // the herb cottage: a bubbling cauldron
    return [crackle(out, 0.03),
      every(120, 520, () => { const f = rnd(140, 360); blip(out, { freq: f, to: f * rnd(1.5, 2.2), gain: rnd(0.02, 0.04), dur: rnd(0.05, 0.1), attack: 0.006 }); })];
  },
};

function startBed(name) {
  if (!ctx || !enabled) return;
  const old = bed;
  const g = ctx.createGain(); g.gain.value = 0; g.connect(duckGain);
  g.gain.linearRampToValueAtTime(1, ctx.currentTime + 1.2);
  const parts = (BEDS[name] || BEDS.village)(g);
  bed = { name, g, parts };
  if (old) {
    old.g.gain.cancelScheduledValues(ctx.currentTime);
    old.g.gain.setTargetAtTime(0, ctx.currentTime, 0.3);
    setTimeout(() => { old.parts.forEach((p) => p.stop?.()); old.g.disconnect(); }, 1800);
  }
}

export function setAmbient(name) {
  want = BEDS[name] ? name : "village";
  if (bed?.name === want) return;
  startBed(want);
}

function duck(on) {
  ducked = on;
  if (ctx) duckGain.gain.setTargetAtTime(on ? 0.35 : 1, ctx.currentTime, 0.25);
}

// ---------- voices and birds ----------

function voiceSyllables(out, voice, count = 1, level = 1) {
  const [base, old] = voice.split("_");
  let f0 = base === "f" ? rnd(185, 230) : base === "kid" ? rnd(270, 320) : rnd(100, 135);
  if (old) f0 *= 0.88;
  for (let s = 0; s < count; s++) {
    const vowel = Object.values(VOWELS)[Math.floor(Math.random() * 5)];
    const t = ctx.currentTime + s * rnd(0.17, 0.26), dur = rnd(0.13, 0.28);
    const o = ctx.createOscillator(); o.type = "sawtooth";
    const up = Math.random() < 0.5;
    o.frequency.setValueAtTime(f0 * (up ? 0.92 : 1.1), t);
    o.frequency.linearRampToValueAtTime(f0 * (up ? 1.12 : 0.85), t + dur);
    const g = ctx.createGain(); g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.06 * level, t + 0.03); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    for (const [i, fq] of vowel.entries()) {
      const bp = ctx.createBiquadFilter(); bp.type = "bandpass"; bp.frequency.value = fq * (base === "f" || base === "kid" ? 1.15 : 1); bp.Q.value = 6;
      const lg = ctx.createGain(); lg.gain.value = i ? 0.5 : 1;
      o.connect(bp).connect(lg).connect(g);
    }
    g.connect(out);
    o.start(t); o.stop(t + dur + 0.05);
  }
}

function birdSong(out) {
  // a short two-note warble with vibrato, soft and not too high
  const base = rnd(1500, 2300), notes = Math.floor(rnd(2, 4));
  for (let i = 0; i < notes; i++) {
    const t = ctx.currentTime + i * rnd(0.16, 0.24), dur = rnd(0.1, 0.18);
    const o = ctx.createOscillator(); o.type = "sine";
    const f = base * (i % 2 ? 1.19 : 1);
    o.frequency.setValueAtTime(f, t); o.frequency.linearRampToValueAtTime(f * rnd(1.05, 1.15), t + dur);
    const v = ctx.createOscillator(); v.frequency.value = rnd(22, 32); const vg = ctx.createGain(); vg.gain.value = f * 0.03;
    v.connect(vg).connect(o.frequency);
    const g = ctx.createGain(); g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.009, t + 0.03); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(out);
    o.start(t); v.start(t); o.stop(t + dur + 0.05); v.stop(t + dur + 0.05);
  }
}

// ---------- small talk: grunts and animal sounds ----------

const VOWELS = { ah: [750, 1150], oh: [500, 850], eh: [550, 1750], uh: [600, 1050], hm: [300, 900] };

export function grunt(voice = "m", kind = "") {
  if (!ctx || !enabled) return;
  const out = duckGain;
  if (kind === "chicken") {
    for (let i = 0; i < 3; i++) blip(out, { freq: 620, to: 430, type: "square", gain: 0.03, dur: 0.07, filter: 1400, q: 2, at: i * 0.11 });
    blip(out, { freq: 520, to: 900, type: "square", gain: 0.035, dur: 0.18, filter: 1500, q: 2, at: 0.36 });
    return;
  }
  if (kind === "cat") { blip(out, { freq: 520, to: 880, type: "sawtooth", gain: 0.03, dur: 0.5, attack: 0.08, filter: 1300, q: 4 }); return; }
  if (kind === "duck") {
    for (let i = 0; i < 2; i++) blip(out, { freq: 320, to: 260, type: "sawtooth", gain: 0.04, dur: 0.14, filter: 950, q: 7, at: i * 0.2 });
    return;
  }
  // a human "hm" / "oh" / "eh": a voiced buzz through two vowel formants with a pitch contour
  voiceSyllables(out, voice, Math.random() < 0.4 ? 2 : 1);
}

// ---------- wiring to the game ----------

on("area", (a) => setAmbient(a.id === "village" ? "village" : a.id));
on("clock", (c) => { night = c.frac >= 0.85; });
on("phase", (p) => { night = p === "dusk" || p === "night" || (p === "day" ? false : night); });
on("talk-open", () => duck(true));
on("talk-close", () => duck(false));
on("smalltalk", (e) => grunt(e.voice, e.kind));

// ---------- footsteps ----------
// surface: grass | dirt | stone | wood

let steps = {};
window.__vaudvilleAudio = () => ({ state: ctx?.state ?? "not started", bed: bed?.name ?? null, steps: { ...steps }, enabled });

export function step(surface = "dirt") {
  if (!ctx || !enabled) return;
  steps[surface] = (steps[surface] || 0) + 1;
  const out = duckGain, v = rnd(0.8, 1.15);
  if (surface === "grass") {
    burst(out, { freq: rnd(1200, 1800), type: "bandpass", q: 0.8, gain: 0.02 * v, dur: 0.06 });
  } else if (surface === "stone") {
    burst(out, { freq: rnd(900, 1300), type: "bandpass", q: 1.8, gain: 0.045 * v, dur: 0.035 });
    blip(out, { freq: rnd(130, 170), gain: 0.03 * v, dur: 0.05 });
  } else if (surface === "wood") {
    blip(out, { freq: rnd(150, 200), to: 110, gain: 0.07 * v, dur: 0.09, filter: 400, q: 1.5 });
    burst(out, { freq: 900, type: "bandpass", q: 2, gain: 0.025 * v, dur: 0.04 });
  } else {
    burst(out, { freq: rnd(900, 1400), type: "bandpass", q: 0.9, gain: 0.05 * v, dur: 0.06 });
    blip(out, { freq: rnd(90, 120), gain: 0.025 * v, dur: 0.06 });
  }
}
on("step", step);

// ---------- one-shot cues for the opening sequence (js/ui/cinematic.js) ----------

export function cue(name) {
  if (!ctx || !enabled) return;
  const out = master;
  if (name === "bell") {
    for (const [f, g] of [[196, 0.09], [392.8, 0.05], [588, 0.03]]) blip(out, { freq: f, gain: g, attack: 0.01, dur: 3.2 });
  } else if (name === "thud") {
    blip(out, { freq: 90, to: 38, type: "sine", gain: 0.2, dur: 0.45 });
    burst(out, { freq: 400, type: "lowpass", gain: 0.12, dur: 0.25 });
  } else if (name === "stamp") {
    blip(out, { freq: 140, to: 70, type: "triangle", gain: 0.12, dur: 0.16 });
    burst(out, { freq: 1500, type: "bandpass", q: 0.7, gain: 0.07, dur: 0.07 });
  } else if (name === "ok") {
    blip(out, { freq: 660, gain: 0.05, dur: 0.14 }); blip(out, { freq: 880, gain: 0.05, dur: 0.22, at: 0.09 });
  } else if (name === "bad") {
    blip(out, { freq: 220, to: 150, type: "square", gain: 0.04, dur: 0.22, filter: 900, q: 1 });
  } else if (name === "tick") {
    blip(out, { freq: 1100, type: "square", gain: 0.012, dur: 0.025, filter: 1800, q: 1 });
  } else if (name === "whoosh") {
    burst(out, { freq: 700, type: "bandpass", q: 0.5, gain: 0.05, dur: 0.3 });
  } else if (name === "page") {
    burst(out, { freq: 2200, type: "highpass", gain: 0.04, dur: 0.12 });
  } else if (name === "whisper") { // a word leaves someone's mouth
    burst(out, { freq: 3200, type: "bandpass", q: 1.2, gain: 0.035, dur: 0.35 });
    blip(out, { freq: 900, to: 1500, gain: 0.012, dur: 0.3, attack: 0.05 });
  } else if (name === "hop") { // ...and lands
    blip(out, { freq: 1046, gain: 0.03, dur: 0.18 });
  } else if (name === "hop-ok") {
    blip(out, { freq: 784, gain: 0.03, dur: 0.14 }); blip(out, { freq: 1175, gain: 0.03, dur: 0.25, at: 0.08 });
  } else if (name === "hop-bad") {
    blip(out, { freq: 311, to: 233, type: "square", gain: 0.025, dur: 0.25, filter: 1000, q: 1 });
  } else if (name === "puff") {
    burst(out, { freq: 900, type: "lowpass", gain: 0.05, dur: 0.25 });
  } else if (name === "clash") { // a minor-second sting when someone hears something that clashes
    for (const f of [233, 247]) blip(out, { freq: f, type: "sawtooth", gain: 0.03, dur: 0.7, attack: 0.01, filter: 1200, q: 0.8 });
    blip(out, { freq: 80, to: 40, gain: 0.12, dur: 0.35 });
  }
}

// ---------- music for scripted scenes (gossip, rumour) ----------
// Small generative themes on a look-ahead scheduler (eighth-note steps). setMusic(name) crossfades
// between them and lowers the ambient bed; setMusic(null) brings the ambience back.
//   gossip: dusk lute arpeggios in D dorian, for the wide shots
//   close:  hushed pad, heartbeat and sparse plucks, while the camera is in on one conversation
//   rumour: pizzicato ostinato in A minor that grows tenser each round (setMusicLevel)

const D3 = 146.83, A2 = 110;
const hz = (root, semi) => root * 2 ** (semi / 12);
let music = null, musicLevel = 0, musicRate = 1;

const THEMES = {
  gossip: {
    bpm: 96,
    play(out, s, at, spb) {
      const prog = [[0, 3, 7], [-2, 2, 5], [-4, 0, 3], [-5, -1, 2]]; // Dm C Bb A
      const ch = prog[Math.floor(s / 8) % 4], k = s % 8;
      const tones = [...ch, ch[0] + 12];
      blip(out, { freq: hz(D3, tones[[0, 1, 2, 3, 2, 1, 2, 1][k]] + 12), type: "triangle", gain: 0.03, attack: 0.004, dur: spb * 1.8, at });
      if (k === 0 || k === 4) blip(out, { freq: hz(D3, ch[0] - 12), gain: 0.045, attack: 0.01, dur: spb * 3.5, at });
      if (k === 6 && Math.random() < 0.4) blip(out, { freq: hz(D3, [0, 2, 3, 5, 7, 9, 10][Math.floor(Math.random() * 7)] + 24), gain: 0.012, attack: 0.02, dur: spb * 3, at });
    },
  },
  close: {
    bpm: 72,
    play(out, s, at, spb) {
      const prog = [[0, 3, 7], [0, 3, 7], [-4, 0, 3], [-5, -1, 2]];
      const ch = prog[Math.floor(s / 8) % 4], k = s % 8;
      if (k === 0) for (const t of ch) blip(out, { freq: hz(D3, t), gain: 0.014, attack: 0.5, dur: spb * 8, at });
      if (k === 0) { blip(out, { freq: 62, to: 44, gain: 0.08, dur: 0.16, at }); blip(out, { freq: 58, to: 42, gain: 0.05, dur: 0.16, at: at + 0.24 }); }
      if (k === 3 || k === 6) blip(out, { freq: hz(D3, ch[k === 3 ? 1 : 2] + 24), type: "triangle", gain: 0.012, attack: 0.004, dur: spb * 1.2, at });
    },
  },
  // opening sequence: a music-box waltz for the night of the murder (6 eighths a bar, E minor)...
  "intro-night": {
    bpm: 80,
    play(out, s, at, spb) {
      const E4 = 329.63, bar = Math.floor(s / 6) % 4, k = s % 6;
      const tune = [[12, null, 7, 3, null, 7], [8, null, 3, 0, null, 3], [12, null, 8, 5, null, 8], [11, null, 7, 2, null, -1]]; // Em C Am B
      const n = tune[bar][k];
      if (n != null) {
        blip(out, { freq: hz(E4, n), gain: 0.032, attack: 0.002, dur: 1.4, at });
        blip(out, { freq: hz(E4, n + 12), gain: 0.008, attack: 0.002, dur: 0.6, at });
      }
      if (k === 0) blip(out, { freq: hz(E4, [0, -4, -7, -5][bar] - 24), type: "triangle", gain: 0.04, attack: 0.05, dur: spb * 6, at });
    },
  },
  // ...and a warm dawn theme for the briefing: harp arpeggios, a soft flute line, G major
  intro: {
    bpm: 100,
    play(out, s, at, spb) {
      const G3 = 196, bar = Math.floor(s / 8) % 4, k = s % 8;
      const ch = [[0, 4, 7], [-3, 0, 4], [-7, -3, 0], [-5, -1, 2]][bar]; // G Em C D
      const tones = [ch[0], ch[1], ch[2], ch[0] + 12, ch[1] + 12];
      blip(out, { freq: hz(G3, tones[[0, 1, 2, 3, 4, 3, 2, 1][k]] + 12), type: "triangle", gain: 0.022, attack: 0.003, dur: spb * 2.5, at });
      if (k === 0 || k === 4) {
        blip(out, { freq: hz(G3, ch[0] - 12), gain: 0.04, attack: 0.02, dur: spb * 3.5, at });
        blip(out, { freq: hz(G3, [[19, 16], [16, 12], [12, 16], [14, 18]][bar][k / 4] + 12), gain: 0.016, attack: 0.08, dur: spb * 3.8, at });
      }
    },
  },
  rumour: {
    bpm: 112,
    play(out, s, at, spb) {
      const shift = [0, 0, -2, -4][Math.floor(s / 8) % 4], k = s % 8;
      blip(out, { freq: hz(A2, [0, 12, 7, 12, 3, 12, 7, 12][k] + shift), type: "sawtooth", gain: 0.02, attack: 0.003, dur: 0.1, filter: 900, q: 1, at });
      if (k === 0) blip(out, { freq: hz(A2, shift - 12), gain: 0.05, attack: 0.05, dur: spb * 8, at });
      if (musicLevel >= 2) blip(out, { freq: hz(A2, 31 + shift), gain: 0.0035 * Math.min(musicLevel, 5), attack: 0.01, dur: spb * 0.5, at });
      if (s % 16 === 12) burst(out, { freq: 2600, type: "bandpass", q: 0.6, gain: 0.012 + 0.004 * musicLevel, dur: 0.9, at });
    },
  },
};

export function setMusic(name) {
  if (!ctx || !enabled) return;
  if ((music?.name ?? null) === (name ?? null)) return;
  const old = music;
  music = null;
  if (old) {
    old.g.gain.cancelScheduledValues(ctx.currentTime);
    old.g.gain.setTargetAtTime(0, ctx.currentTime, 0.3);
    setTimeout(() => { clearInterval(old.timer); old.g.disconnect(); }, 1800);
  }
  if (bed) bed.g.gain.setTargetAtTime(name ? 0.4 : 1, ctx.currentTime, 0.5);
  const th = THEMES[name];
  if (!th) return;
  const g = ctx.createGain(); g.gain.value = 0; g.connect(master);
  g.gain.setTargetAtTime(1, ctx.currentTime, 0.35);
  const spb = 60 / th.bpm / 2;
  let s = 0, next = ctx.currentTime + 0.08;
  const timer = setInterval(() => {
    if (ctx.state !== "running") return;
    while (next < ctx.currentTime + 0.25) { const step = spb / musicRate; th.play(g, s++, next - ctx.currentTime, step); next += step; }
  }, 60);
  music = { name, g, timer };
}
export function setMusicLevel(n) { musicLevel = n; }
export function setMusicRate(r) { musicRate = r; } // tempo multiplier (fast-forwarded gossip)
on("music-rate", setMusicRate);

on("music", setMusic);
on("music-level", setMusicLevel);
on("sfx", (name) => cue(name));
