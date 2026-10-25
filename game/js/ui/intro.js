// First-run intro ("The Archive" in four parchment cards) and "How were these villagers taught?".
// The checker appears in-world as the Clerk, who stamps every claim with a wax seal: green (it's in their
// records), red (it isn't), grey ("not in my records"). Numbers quoted here are our measured results.

import { portraitURL } from "../art.js";
import { h, openModal, closeModal } from "./dom.js";
import { icon } from "./icons.js";

const SEEN = "archive_intro_seen_v1";
const seen = () => { try { return localStorage.getItem(SEEN) === "1"; } catch { return false; } };
const markSeen = () => { try { localStorage.setItem(SEEN, "1"); } catch { /* private window */ } };

const face = (id, role, size = 56) => h("img", { class: "intro-face", src: portraitURL(id, role, size), alt: "", width: size, height: size });
const seal = (kind, label) => h("span", { class: `seal ${kind}` }, h("b", {}, icon({ ok: "check", bad: "cross", grey: "none" }[kind])), label ? h("small", {}, label) : false);

const CARDS = [
  () => ({
    kicker: "Hollowmere, last week",
    title: "A villager was killed. Someone is lying.",
    art: h("div", { class: "intro-art row" }, face("v1", "baker"), face("v2", "guard"), face("killer?", "miller"), face("v4", "priest")),
    body: [
      "Everyone in the village kept written records: diaries, ledgers, patrol logs.",
      "The records cover days 1 to 3. The murder happened on the night of day 2.",
      "You have three days to question the villagers and find the killer.",
    ],
  }),
  () => ({
    kicker: "Meet Clerk Ambrose of the guildhall",
    title: "Villagers may only say what they wrote down.",
    art: h("div", { class: "intro-art row" }, face("x_clerk", "townsfolk", 64),
      h("div", { class: "seals" }, seal("ok", "in their records"), seal("bad", "not in their records"), seal("grey", "\"I'm not sure\": not in their records"))),
    body: [
      "Ambrose checks every sentence a villager says against that villager's own records, and stamps it with a seal.",
      "Green shows the exact line it came from. Red means it isn't in their records. He's not clever, just exact: a fixed rulebook, never a guess.",
    ],
  }),
  () => ({
    kicker: "Your notebook",
    title: "Two green claims that can't both be true?",
    art: h("div", { class: "intro-art clash" },
      h("div", { class: "mini-claim" }, face("v_tom", "miller", 36), seal("ok"), "\"I was at the mill all night.\""),
      h("span", { class: "vs" }, "can't both be true"),
      h("div", { class: "mini-claim" }, face("v_nell", "herbalist", 36), seal("ok"), "\"The mill was empty at midnight.\"")),
    body: [
      "Add green claims to your notebook, open the Board, and link two that clash. The Clerk confirms real contradictions.",
      "Someone's records don't add up. Usually the killer's alibi.",
    ],
  }),
  () => ({
    kicker: "The verdict",
    title: "Two contradictions and a motive. Then accuse.",
    art: h("div", { class: "intro-art row" }, h("span", { class: "token" }, "contradiction"), h("b", { class: "op" }, "+"),
      h("span", { class: "token" }, "contradiction"), h("b", { class: "op" }, "+"), h("span", { class: "token gold" }, "motive"),
      h("b", { class: "op" }, "→"), face("v_killer", "miller", 44)),
    body: [
      "The motive is in the evidence the victim left behind.",
      "In the evening the villagers gossip, and they must say who told them what. Wrong accusations cost strikes.",
    ],
    keys: true,
  }),
];

export function showIntro({ force = false } = {}) {
  if (!force && seen()) return;
  let i = 0, entry = null;
  const wrap = h("div", { class: "intro" });
  const render = () => {
    const c = CARDS[i]();
    wrap.replaceChildren(...[
      h("p", { class: "kicker" }, c.kicker),
      h("h2", {}, c.title),
      c.art,
      ...c.body.map((t) => h("p", { class: "intro-line" }, t)),
      c.keys ? h("p", { class: "muted small" }, "Move WASD / click · Talk ", h("kbd", {}, "E"), " · Notebook ", h("kbd", {}, "N"), " · Board ", h("kbd", {}, "B"), " · Menu ", h("kbd", {}, "Esc")) : false,
      h("div", { class: "intro-nav" },
        h("div", { class: "dots" }, CARDS.map((_, k) => h("i", { class: k === i ? "on" : "" }))),
        h("div", {},
          i > 0 ? h("button", { class: "btn ghost", onclick: () => { i--; render(); } }, "◂ Back") : h("button", { class: "btn ghost", onclick: done }, "Skip"),
          i < CARDS.length - 1
            ? h("button", { class: "btn primary", autofocus: true, onclick: () => { i++; render(); } }, "Next ▸")
            : h("button", { class: "btn primary", autofocus: true, onclick: done }, "Start investigating ▸")))].filter(Boolean));
    requestAnimationFrame(() => wrap.querySelector("[autofocus]")?.focus());
  };
  const done = () => { markSeen(); if (entry) closeModal(entry); };
  render();
  const onKey = (e) => {
    if (e.key === "ArrowRight" && i < CARDS.length - 1) { i++; render(); e.preventDefault(); }
    if (e.key === "ArrowLeft" && i > 0) { i--; render(); e.preventDefault(); }
  };
  wrap.addEventListener("keydown", onKey);
  entry = openModal(wrap, { cls: "parchment", onClose: markSeen });
}

// "How were these villagers taught?": three panels, one per Villagers choice on the title screen.
export function showTraining() {
  const panel = (cls, icon, name, line, detail, stat) => h("div", { class: `teach ${cls}` },
    h("div", { class: "teach-art" }, icon),
    h("h3", {}, name),
    h("p", { class: "teach-line" }, line),
    h("p", { class: "muted small" }, detail),
    stat && h("p", { class: "teach-stat" }, stat));
  openModal(h("div", { class: "training" },
    h("p", { class: "kicker" }, "Every villager is the same small language model (Qwen3, 1.7B)"),
    h("h2", {}, "How were these villagers taught?"),
    h("div", { class: "teach-row" },
      panel("base", h("span", { class: "teach-figs" }, face("v_demo", "baker", 40), h("span", { class: "bubble" }, "?")), "Base",
        "Never taught. Reads its records, then makes things up.",
        "The model as it comes: it guesses, invents sightings and copies the example in its instructions.",
        "Gets 1 answer in 9 exactly right"),
      h("span", { class: "arrow" }, "→"),
      panel("sft", h("span", { class: "teach-figs" }, face("v_demo", "baker", 40), h("span", { class: "page" }, h("i"), h("i"), h("i"))), "SFT only",
        "Learned by copying 4,800 worked examples.",
        "Supervised fine-tuning: shown the right reply to thousands of questions, it learns to answer from its records, cite the line, or say \"I'm not sure\".",
        "Nearly 9 in 10 right, even on questions worded in new ways"),
      h("span", { class: "arrow" }, "→"),
      panel("grpo", h("span", { class: "teach-figs" }, face("v_demo", "baker", 40), h("span", { class: "rehearse" }, seal("ok"), seal("bad"), seal("ok")), face("x_clerk", "townsfolk", 40)), "SFT + GRPO",
        "Then practised with Clerk Ambrose.",
        "Reinforcement learning (GRPO): for each question it tried 6 answers, Clerk Ambrose stamped them, and it kept the habits of the stamped ones. No one writes the right answers here: his seal is the only teacher.",
        "Fewer slips when villagers answer freely (unreliable answers 4.5% → 2.2% in our tests)")),
    h("p", { class: "muted small center" }, "Try the same case with each: the seed on the title screen replays it exactly.")), { wide: true, cls: "parchment" });
}
