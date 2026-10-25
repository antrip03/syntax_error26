import { portraitURL } from "../art.js";
import { h, openModal } from "./dom.js";
import { icon } from "./icons.js";

const face = (id, role, size = 56) => h("img", { class: "intro-face", src: portraitURL(id, role, size), alt: "", width: size, height: size });
const seal = (kind, label) => h("span", { class: `seal ${kind}` }, h("b", {}, icon({ ok: "check", bad: "cross", grey: "none" }[kind])), label ? h("small", {}, label) : false);

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
