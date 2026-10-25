// Opening sequence, played every time the game boots (and from "How to play"):
//   0. a title page at dusk, then a short animated cold open: night falls, the bell, the victim, the stamp
//   1. the briefing at dawn: four instructions, each animated, lines appearing one by one
//   2. why and how the villagers were trained: the goal, then Base -> SFT -> GRPO, each with why we added
//      it and what it does, then what the Planted rumour mode tests
// Space / Enter / click = next (first press finishes the current animation), Left = back, Esc = skip all.
// Everything is DOM + CSS animation and synthesised music, so it needs no assets. Numbers are our measured
// results (the same ones intro.js quotes); the reward terms are those in archive/rewards.

import { portraitURL } from "../art.js";
import { h, block } from "./dom.js";
import { icon } from "./icons.js";
import { cue, setMusic, unlockAudio } from "../audio.js";

const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const face = (id, role, size = 56, cls = "") => h("img", { class: `cf ${cls}`, src: portraitURL(id, role, size), alt: "", width: size, height: size });
const seal = (kind, cls = "") => h("span", { class: `seal ${kind} ${cls}` }, h("b", {}, icon({ ok: "check", bad: "cross", grey: "none" }[kind])));
const delay = (s) => ({ style: { "--d": `${s}s` } });
const CAST = [["v1", "baker"], ["v2", "guard"], ["v3", "miller"], ["v4", "priest"], ["v5", "herbalist"], ["v6", "blacksmith"]];

// ---------- backdrop: a sky that goes dusk -> night -> dawn behind every step ----------

function skyline() {
  // [x, width, height, roof] for a stepped pixel silhouette; the inn (index 3) loses its light at the bell
  const blocks = [[0, 70, 70, 1], [70, 55, 100, 0], [125, 80, 62, 1], [205, 110, 90, 1], [315, 60, 118, 0], [375, 90, 70, 1], [465, 70, 96, 1], [535, 85, 66, 0], [620, 70, 108, 1], [690, 110, 76, 1]];
  let svg = "";
  blocks.forEach(([x, w, ht, roof], i) => {
    const y = 200 - ht;
    svg += `<rect x="${x}" y="${y}" width="${w}" height="${ht}"/>`;
    if (roof) svg += `<polygon points="${x - 4},${y} ${x + w / 2},${y - 26} ${x + w + 4},${y}"/>`;
    for (let k = 0; k < Math.floor(w / 24); k++) {
      for (let r = 0; r < Math.min(2, Math.floor(ht / 44)); r++) {
        svg += `<rect class="win${i === 3 ? " inn" : ""}" style="--w:${((i * 7 + k * 3 + r) % 9) * 0.37}s" x="${x + 10 + k * 24}" y="${y + 14 + r * 30}" width="9" height="12"/>`;
      }
    }
  });
  return `<svg viewBox="0 0 800 200" preserveAspectRatio="xMidYMax slice" aria-hidden="true">${svg}</svg>`;
}

const HILLS = `<svg viewBox="0 0 800 200" preserveAspectRatio="none" aria-hidden="true">
  <path class="far" d="M0 120 Q90 70 180 104 T360 92 T560 108 T800 78 V200 H0Z"/>
  <path class="near" d="M0 150 Q120 118 240 140 T480 132 T800 128 V200 H0Z"/></svg>`;
const BIRD = `<svg viewBox="0 0 20 8" aria-hidden="true"><path d="M1 6 Q5 0 10 5 Q15 0 19 6" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;

function backdrop() {
  const stars = Array.from({ length: 70 }, (_, i) => h("i", { style: { left: `${(i * 37) % 100}%`, top: `${(i * 53) % 55}%`, "--d": `${(i % 9) * 0.45}s`, "--s": i % 5 === 0 ? "3px" : "2px" } }));
  const clouds = [[6, 16, 1.1], [44, 8, 0.8], [70, 24, 1.3], [26, 30, 0.7]].map(([x, y, s], i) => h("i", { style: { left: `${x}%`, top: `${y}%`, "--s": s, "--d": `${-i * 11}s` } }));
  const motes = Array.from({ length: 22 }, (_, i) => h("i", { style: { left: `${(i * 29) % 100}%`, "--d": `${-(i % 7) * 1.7}s`, "--t": `${10 + (i % 5) * 2.5}s` } }));
  const birds = [0, 1, 2, 3].map((i) => h("i", { html: BIRD, style: { top: `${16 + (i % 2) * 4}%`, "--d": `${-i * 1.3}s`, "--o": `${i * 22}px` } }));
  return h("div", { class: "cn-bg" },
    h("div", { class: "cn-grad dusk" }), h("div", { class: "cn-grad night" }), h("div", { class: "cn-grad dawn" }),
    h("div", { class: "cn-stars" }, stars),
    h("div", { class: "cn-sun" }), h("div", { class: "cn-moon" }),
    h("div", { class: "cn-clouds" }, clouds),
    h("div", { class: "cn-birds" }, birds),
    h("div", { class: "cn-hills", html: HILLS }),
    h("div", { class: "cn-sky", html: skyline() }),
    h("div", { class: "cn-motes" }, motes),
    h("div", { class: "cn-fog a" }), h("div", { class: "cn-fog b" }),
    h("div", { class: "cn-vignette" }));
}

// ---------- steps ----------
// A step is (ctx) => void, rendering into ctx.stage. ctx.later(fn, sec) schedules a timer that is
// cancelled when the step changes; ctx.lines(parent, items, start, gap) reveals lines (strings or nodes)
// one by one; ctx.settle(fn) says what Next does while the step is still animating.

function brief(kicker, title, art, lines) {
  return (ctx) => {
    const p = h("div", { class: "cn-lines" });
    ctx.stage.append(h("div", { class: "cn-card" }, h("p", { class: "kicker" }, kicker), h("h2", {}, title), art(ctx), p));
    ctx.lines(p, lines, 1.4, 1.5);
  };
}

const box = (cls, label, text) => h("div", { class: `cn-box ${cls}` }, h("h4", {}, label), h("p", {}, text));
const result = (text) => h("p", { class: "cn-result" }, text);

// One stage of training: the art, then "why we added it", "what it does" and the result, one by one.
function learn(stage, kicker, title, art, why, what, res) {
  return (ctx) => {
    const order = ["base", "sft", "grpo"];
    const pipe = h("ol", { class: "cn-pipe" }, ...[["base", "Base"], ["sft", "SFT"], ["grpo", "GRPO"]].map(([k, l]) =>
      h("li", { class: k === stage ? "on" : order.indexOf(k) < order.indexOf(stage) ? "done" : "" }, l)));
    const p = h("div", { class: "cn-lines ww" });
    const a = art(ctx);
    ctx.stage.append(h("div", { class: `cn-card wide st-${stage}` }, pipe, h("p", { class: "kicker" }, kicker), h("h2", {}, title), a, p));
    const say = a.querySelector(".cn-says");
    if (say) ctx.later(() => ctx.type(say, say.dataset.say), Number(say.dataset.at || 1.0));
    const cnt = a.querySelector(".count");
    if (cnt) ctx.later(() => ctx.count(cnt, 4800, 2.4), 0.6);
    a.querySelectorAll(".cn-slip .seal").forEach((s, i) => ctx.later(() => cue(s.classList.contains("ok") ? "ok" : "bad"), 1.0 + i * 0.35));
    if (stage === "base") ctx.later(() => cue("bad"), 3.6);
    if (stage === "sft") ctx.later(() => cue("ok"), 6);
    ctx.lines(p, [box("why", stage === "base" ? "Why we show it" : "Why we added it", why), box("what", "What it does", what), result(res)], 2.4, 2.2);
  };
}

function claimRow(id, role, text, kind, note, d) {
  return h("div", { class: `cn-claim ${kind}`, ...delay(d) }, face(id, role, 40), h("div", {}, h("p", {}, text), h("small", {}, note)), seal(kind, "stampd"));
}

const village = (label, states, d0, note) => h("div", { class: "cn-vil" }, h("b", {}, label),
  h("div", { class: "cn-six" }, states.map((st, i) => h("span", { class: `cn-v ${st}`, ...delay(d0 + i * 0.45) }, face(`r${i}`, CAST[i][1], 34)))),
  note && h("small", { class: "cn-note", ...delay(d0 + states.length * 0.45 + 0.2) }, note));

const OPENING = (ctx) => {
  const { stage, later, root } = ctx;
  const cap = h("p", { class: "cn-cap", "aria-live": "polite" });
  // the victim is never named here: each case has its own
  const frame = h("div", { class: "cn-victim" }, h("span", { class: "cn-unknown" }, "?"), h("span", { class: "x" }, icon("cross")), h("small", {}, "A villager"));
  const stamp = h("div", { class: "cn-stamp" }, h("span", {}, "Murder"), h("small", {}, "Case file · Vaudville"));
  const sub = h("p", { class: "cn-sub" }, "Someone in Vaudville is lying. Find out who.");
  const gate = h("button", { class: "cn-gate", autofocus: true, "aria-label": "Begin" },
    h("div", { class: "cn-plaque" },
      h("small", {}, "A murder mystery"),
      h("b", {}, "The Killing", h("br"), "at Vaudville"),
      h("i", { class: "cn-rule" }),
      h("em", {}, "Every villager keeps records. Not every villager can be trusted."),
      h("div", { class: "cn-gate-cast" }, CAST.map(([id, role], i) => h("span", delay(0.6 + i * 0.12), face(id, role, 44)))),
      h("span", { class: "cn-press" }, "Click or press any key")));
  stage.append(h("div", { class: "cn-open" }, frame, cap, stamp, sub));
  root.classList.add("hold");
  ctx.sky("dusk");

  let started = false;
  const say = (text) => { cap.classList.remove("in"); void cap.offsetWidth; cap.textContent = ""; ctx.type(cap, text, 42); };
  const finish = () => {
    ctx.cancelPending(); // stop the typewriter and the remaining beats before jumping to the end
    stage.firstChild.classList.add("bell", "victim", "stamped"); root.classList.add("bell-on");
    cap.classList.add("in"); cap.textContent = "By morning, one of them was dead.";
    ctx.ready();
  };
  const start = () => {
    if (started) return;
    started = true; gate.classList.add("away"); root.classList.remove("hold");
    unlockAudio(); setMusic("intro-night");
    later(() => gate.remove(), 0.8);
    ctx.sky("night");
    ctx.settle(finish);
    const open = stage.firstChild;
    later(() => say("Vaudville. The second night."), 1.2);
    later(() => say("Every window glows. Every door is barred."), 4.8);
    later(() => { open.classList.add("bell"); root.classList.add("bell-on"); cue("bell"); say("Then the bell tolls once."); }, 8.6);
    later(() => { open.classList.add("victim"); say("By morning, one of them was dead."); }, 12.6);
    later(() => { open.classList.add("stamped"); cue("thud"); ctx.shake(); }, 17);
    later(() => ctx.ready(), 18);
  };
  stage.append(gate);
  ctx.onStart(start);
  ctx.holding(true);
};

const STEPS = [
  { part: "Cold open", run: OPENING, opening: true },

  { part: "Briefing 1 of 4", run: brief("Your orders", "Question the villagers.",
    () => h("div", { class: "cn-art" }, h("div", { class: "cn-cast" },
      ...CAST.slice(0, 5).map(([id, role], i) =>
        h("div", { class: `cn-person${i === 2 ? " talk" : ""}`, ...delay(0.2 + i * 0.15) }, face(id, role, 56), i === 2 && h("span", { class: "cn-bubble" }, "…")))),
      h("p", { class: "cn-keyrow", ...delay(1.0) }, "Walk up to someone and press ", h("kbd", { class: "pulse" }, "E"))),
    ["Everyone in Vaudville kept written records: diaries, ledgers, patrol logs.",
      "You have a few questions each day. Spend them well.",
      "The murder happened on the night of day two. You have three days."]) },

  { part: "Briefing 2 of 4", run: brief("Clerk Ambrose checks every word", "Watch for the seals.",
    () => h("div", { class: "cn-art col" },
      claimRow("v_a", "baker", "“I was at the mill all night.”", "ok", "it's in their records", 0.5),
      claimRow("v_b", "guard", "“I saw Tom by the well at midnight.”", "bad", "it isn't in their records", 1.6),
      claimRow("v_c", "priest", "“I'm not sure.”", "grey", "not in their records", 2.7)),
    ["A villager may only say what they wrote down.",
      "Green: the exact line it came from is shown. Red: it isn't in their records.",
      "Ambrose is not clever, just exact: a fixed rulebook, never a guess."]) },

  { part: "Briefing 3 of 4", run: brief("Your notebook and the Board", "Catch two claims that clash.",
    () => h("div", { class: "cn-art clash" },
      h("div", { class: "cn-mini left" }, face("v_tom", "miller", 40), seal("ok"), "“I was at the mill all night.”"),
      h("div", { class: "cn-spark" }, icon("bolt"), h("span", {}, "can't both be true")),
      h("div", { class: "cn-mini right" }, face("v_nell", "herbalist", 40), seal("ok"), "“The mill was empty at midnight.”")),
    ["Pin green claims to your notebook (N).", "Open the Board (B) and link two that contradict each other.",
      "The Clerk confirms real contradictions. Usually the killer's alibi is one of them."]) },

  { part: "Briefing 4 of 4", run: brief("The verdict", "Two contradictions and a motive. Then accuse.",
    () => h("div", { class: "cn-art" },
      h("div", { class: "cn-tokens" },
        h("span", { class: "token", ...delay(0.5) }, "contradiction"), h("b", { class: "op", ...delay(0.8) }, "+"),
        h("span", { class: "token", ...delay(1.4) }, "contradiction"), h("b", { class: "op", ...delay(1.7) }, "+"),
        h("span", { class: "token gold", ...delay(2.3) }, "motive"), h("b", { class: "op", ...delay(2.9) }, "→"),
        h("span", { class: "cn-killer", ...delay(3.2) }, face("v_killer", "miller", 56))),
      h("div", { class: "cn-strikes", ...delay(3.8) }, h("small", {}, "Strikes"), icon("heart"), icon("heart"), icon("heart", "lost"))),
    ["The motive is in the evidence the victim left behind.",
      "Accuse the wrong person and you lose a strike.",
      "In the evening the villagers gossip, and they must say who told them what."]) },

  { part: "The villagers 1 of 6", run: (ctx) => {
    const p = h("div", { class: "cn-lines" });
    const rules = ["Answer only from your own records.", "Cite the exact line it came from.", "Say “I'm not sure” when it isn't there."];
    ctx.stage.append(h("div", { class: "cn-card wide" }, h("p", { class: "kicker" }, "Why the villagers were trained"), h("h2", {}, "The goal: no made-up answers."),
      h("div", { class: "cn-art goal" },
        h("div", { class: "cn-bad", ...delay(0.3) }, face("v_demo", "baker", 44, "gray"),
          h("div", {}, h("p", {}, "“I saw the miller at the well at midnight!”"), h("small", {}, "sounds sure, written nowhere: a hallucination"))),
        h("span", { class: "cn-arr", ...delay(1.3) }, "→"),
        h("ol", { class: "cn-rules" }, rules.map((t, i) => h("li", delay(1.6 + i * 0.6), seal("ok", "stampd"), t)))), p));
    ctx.later(() => cue("bad"), 1.0);
    [0, 1, 2].forEach((i) => ctx.later(() => cue("ok"), 2.1 + i * 0.6));
    ctx.lines(p, ["Our challenge (Problem Statement 3) is grounded answers: a model that answers only from its own documents, and says so when the answer isn't there.",
      "Small language models often make things up and sound sure doing it. In a murder case, one invented sentence is a false alibi or a wrong accusation.",
      "Every villager is the same small model (Qwen3, 1.7B). We trained it in two stages, SFT then GRPO, to follow the three rules. Here is why each stage exists."], 3.6, 2.2);
  } },

  { part: "The villagers 2 of 6", run: learn("base", "Stage 0 · Base", "The model as it comes.",
    () => h("div", { class: "cn-art learn" },
      h("div", { class: "cn-model" }, face("v_demo", "baker", 64, "gray"), h("small", {}, "Qwen3 · 1.7B")),
      h("div", { class: "cn-says", "data-say": "I saw the miller at the well at midnight!" }),
      h("div", { class: "cn-verdict", ...delay(3.6) }, seal("bad", "big"), h("small", {}, "not in anyone's records"))),
    "It is the starting point: without it you can't see what training changed. You can still pick it on the title screen.",
    "Reads its records, then answers however it likes: it guesses, invents sightings and copies the example in its instructions.",
    "Only 1 answer in 9 is exactly right.") },

  { part: "The villagers 3 of 6", run: learn("sft", "Stage 1 · SFT: supervised fine-tuning", "Learning by copying worked examples.",
    () => h("div", { class: "cn-art learn" },
      h("div", { class: "cn-deck" }, ...[0, 1, 2, 3].map((i) => h("div", { class: "cn-ex", ...delay(0.4 + i * 0.5) }, h("b", {}, "Q"), " Where was Tom?", h("br"), h("b", {}, "A"), " At the mill ", h("em", {}, "[Ledger 2]")))),
      h("div", { class: "cn-model" }, face("v_demo", "baker", 64, "learning"), h("small", { class: "count" }, "0 examples")),
      h("div", { class: "cn-says", "data-say": "Tom's ledger says: “at the mill all night.” [Ledger 2]", "data-at": "3.4" }),
      h("div", { class: "cn-verdict", ...delay(6) }, seal("ok", "big"), h("small", {}, "it's in the records"))),
    "The base model doesn't know the rules or the answer format. The fastest way to teach a habit is to show it, thousands of times.",
    "We train on 4,800 worked examples: a question plus the villager's records, and the right reply, with citations or “I'm not sure”. The model learns to imitate them.",
    "Nearly 9 in 10 right, even on new wording. But it only copies, so free-form answers still slip sometimes.") },

  { part: "The villagers 4 of 6", run: learn("grpo", "Stage 2 · GRPO: reinforcement learning", "Practising with Clerk Ambrose.",
    () => h("div", { class: "cn-art learn" },
      h("div", { class: "cn-model" }, face("v_demo", "baker", 64), h("small", {}, "writes 6 answers")),
      h("div", { class: "cn-slips-wrap" },
        h("div", { class: "cn-slips" }, ...[["ok", "0.95"], ["bad", "0.20"], ["ok", "0.85"], ["ok", "0.90"], ["bad", "0.35"], ["ok", "0.80"]].map(([k, sc], i) =>
          h("div", { class: `cn-slip ${k}`, ...delay(0.5 + i * 0.35) }, h("i"), h("i"), h("i"), seal(k, "stampd"), h("span", { class: "rw" }, `${sc} ${k === "ok" ? "▲" : "▼"}`)))),
        h("small", { class: "cn-avg", ...delay(3.0) }, "group average 0.68: above it is reinforced ▲, below it discouraged ▼")),
      h("div", { class: "cn-clerk", ...delay(0.4) }, face("x_clerk", "townsfolk", 56), h("small", {}, "Clerk Ambrose"), h("small", { class: "terms" }, "correct? backed? cites? abstains? format?"))),
    "Copying has a ceiling: the model never learns which of its own answers were wrong. We want it to learn straight from the checker, with no one writing answers.",
    "For each question it writes 6 answers. Ambrose scores each one: is it correct, is every sentence backed, are citations right, did it abstain only when it should, is the format clean? Answers better than the group's average are reinforced.",
    "Unreliable answers fall from 4.5% to 2.2% in our tests.") },

  { part: "The villagers 5 of 6", run: (ctx) => {
    const p = h("div", { class: "cn-lines" });
    // the villages show our end-to-end check (killer as the source): Untrained NPCs 4 of 4 repeat it, SFT + GRPO 0 of 4
    ctx.stage.append(h("div", { class: "cn-card wide" }, h("p", { class: "kicker" }, "Title screen · Planted rumour"), h("h2", {}, "Can one lie take over the village?"),
      h("div", { class: "cn-art rumour" },
        h("div", { class: "cn-srcs" },
          h("div", { class: "cn-src", ...delay(0.3) }, h("span", { class: "cn-v source" }, face("v_killer", "miller", 34)), h("small", {}, "the killer", h("br"), "(untrained) frames someone")),
          h("b", { class: "cn-or", ...delay(0.6) }, "or"),
          h("div", { class: "cn-src", ...delay(0.8) }, h("span", { class: "cn-trav-i" }, icon("scroll")), h("small", {}, "a traveller's whisper", h("br"), "that you write"))),
        h("div", { class: "cn-vils" },
          village("Untrained NPCs", ["red", "red", "red", "red"], 1.4, "4 of 4 believe it"),
          village("SFT + GRPO", ["green", "amber", "green", "green"], 1.4, "0 of 4 believe it"))),
      h("div", { class: "legend cn-legend", ...delay(3.6) }, h("span", { class: "cell red" }), " believes it ", h("span", { class: "cell amber" }), " passes it on, says who said it ", h("span", { class: "cell green" }), " doesn't buy it ", h("span", { class: "cell plain" }), " hasn't heard it"),
      p));
    ctx.lines(p, ["Choose who starts a lie: the killer, played by the untrained model and trying to frame someone, or a traveller whose whisper you write yourself.",
      "Over five rounds the villagers gossip; then everyone is asked the same question and the Clerk colours each answer. Compare runs an untrained village beside an SFT + GRPO one.",
      "In our end-to-end check with the killer as the source, all 4 untrained villagers repeated the lie as fact. None of the 4 trained ones did."], 4.2, 2.2);
  } },

  { part: "The villagers 6 of 6", last: true, run: (ctx) => {
    const col = (cls, name, line, stat, i) => h("div", { class: `cn-sum ${cls}`, ...delay(0.3 + i * 0.7) }, h("h3", {}, name), h("p", {}, line), h("b", {}, stat));
    const p = h("div", { class: "cn-lines" });
    ctx.stage.append(h("div", { class: "cn-card wide" }, h("p", { class: "kicker" }, "Same village, three kinds of villager"), h("h2", {}, "You choose who you question."),
      h("div", { class: "cn-sums" },
        col("base", "Base", "Never taught. Makes things up.", "1 in 9 exactly right", 0), h("span", { class: "cn-arr", ...delay(0.9) }, "→"),
        col("sft", "SFT only", "Copied 4,800 worked examples.", "Nearly 9 in 10 right", 1), h("span", { class: "cn-arr", ...delay(1.6) }, "→"),
        col("grpo", "SFT + GRPO", "Then practised against the Clerk's score.", "Fewest unreliable answers", 2)), p));
    ctx.lines(p, ["Pick the villagers on the title screen, and replay the same seed with each to see the difference.", "The case is waiting. Find the one whose records don't add up."], 2.8, 1.5);
  } },
];

// ---------- runner ----------

let running = null;

export function playOpening({ replay = false } = {}) {
  if (running) return running.done;
  const root = h("div", { id: "cine", class: "cine", role: "dialog", "aria-modal": "true", "aria-label": "Introduction" });
  const stage = h("div", { class: "cn-stage" });
  const label = h("span", { class: "cn-part" });
  const dots = h("div", { class: "cn-dots" }, STEPS.map(() => h("i")));
  const back = h("button", { class: "btn ghost", onclick: () => go(i - 1) }, "◂ Back");
  const skip = h("button", { class: "btn ghost", onclick: () => close() }, replay ? "Close (Esc)" : "Skip intro (Esc)");
  const next = h("button", { class: "btn primary", onclick: () => advance() }, "Next ▸");
  root.append(backdrop(), stage, h("div", { class: "cn-bar" }, h("div", { class: "cn-left" }, skip, label), dots, h("div", { class: "cn-right" }, back, next)));
  document.body.append(root);
  block(true);

  let i = -1, timers = [], cleaners = [], onSettle = null, onStart = null, holding = false, isReady = true, closed = false;
  const clear = () => { timers.forEach(clearTimeout); timers = []; cleaners.forEach((f) => f()); cleaners = []; onSettle = onStart = null; holding = false; };

  const ctx = {
    stage, root,
    later: (fn, sec) => timers.push(setTimeout(fn, reduced() ? Math.min(sec, 0.3) * 1000 : sec * 1000)),
    onClean: (f) => cleaners.push(f),
    cancelPending: () => { timers.forEach(clearTimeout); timers = []; cleaners.forEach((f) => f()); cleaners = []; },
    settle: (f) => { onSettle = f; isReady = false; setNext(); },
    ready: () => { isReady = true; onSettle = null; setNext(); },
    onStart: (f) => { onStart = f; },
    holding: (v) => { holding = v; setNext(); },
    sky: (name) => { root.classList.remove("sky-dusk", "sky-night", "sky-dawn"); root.classList.add(`sky-${name}`); },
    shake: () => { if (reduced()) return; root.classList.remove("shake"); void root.offsetWidth; root.classList.add("shake"); },
    lines(parent, items, start, gap) {
      const els = items.map((t) => t instanceof Node ? t : h("p", {}, t));
      els.forEach((e) => e.classList.add("cn-line"));
      parent.append(...els);
      const show = (k) => { els[k].classList.add("in"); cue("page"); if (k === els.length - 1) ctx.ready(); };
      els.forEach((_, k) => ctx.later(() => show(k), start + k * gap));
      ctx.settle(() => { els.forEach((e) => e.classList.add("in")); ctx.ready(); });
    },
    type(el, text, speed = 38) {
      el.classList.add("in");
      if (reduced()) { el.textContent = text; return; }
      let n = 0; const id = setInterval(() => { el.textContent = text.slice(0, ++n); if (n % 3 === 0) cue("tick"); if (n >= text.length) clearInterval(id); }, speed);
      cleaners.push(() => clearInterval(id));
    },
    count(el, to, sec) {
      const t0 = performance.now();
      const id = setInterval(() => {
        const f = reduced() ? 1 : Math.min(1, (performance.now() - t0) / (sec * 1000));
        el.textContent = `${Math.round(to * f).toLocaleString("en-US")} examples`;
        if (f >= 1) clearInterval(id);
      }, 40);
      cleaners.push(() => clearInterval(id));
    },
  };

  function setNext() {
    const last = STEPS[i]?.last;
    next.textContent = holding ? "" : last ? "Begin the investigation ▸" : isReady ? "Next ▸" : "Skip animation ▸";
    next.hidden = holding;
    back.hidden = i <= 1;
    next.classList.toggle("pulse", isReady && !holding);
  }

  function go(n) {
    if (n < 0 || n >= STEPS.length || (n === 0 && i > 0)) return;
    clear();
    i = n;
    stage.replaceChildren();
    const opening = !!STEPS[i].opening;
    root.classList.toggle("opening", opening);
    if (opening) root.classList.remove("bell-on");
    else { ctx.sky("dawn"); setMusic("intro"); }
    isReady = true;
    STEPS[i].run(ctx);
    label.textContent = STEPS[i].part;
    [...dots.children].forEach((d, k) => { d.className = k === i ? "on" : k < i ? "past" : ""; });
    if (!opening) { cue("whoosh"); next.focus(); }
    setNext();
  }

  function advance() {
    if (holding) { onStart?.(); holding = false; setNext(); return; }
    if (!isReady) { onSettle?.(); return; }
    if (i >= STEPS.length - 1) close(); else go(i + 1);
  }

  let resolve;
  const done = new Promise((r) => { resolve = r; });
  function close() {
    if (closed) return;
    closed = true; clear();
    document.removeEventListener("keydown", onKey, true);
    root.classList.add("out");
    block(false);
    setMusic(null);
    setTimeout(() => root.remove(), 450);
    running = null;
    resolve();
  }

  function onKey(e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "Escape") close();
    else if (holding) advance();
    else if (e.key === "ArrowRight") advance();
    else if (e.key === " " || e.key === "Enter") { if (e.target.closest?.(".cn-bar")) return; advance(); } // buttons click themselves
    else if (e.key === "ArrowLeft") go(i - 1);
    else return;
    e.preventDefault(); e.stopPropagation();
  }
  document.addEventListener("keydown", onKey, true);
  stage.addEventListener("click", () => { if (holding) advance(); });

  go(0);
  running = { done };
  return done;
}
