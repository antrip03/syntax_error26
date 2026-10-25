
import { fullBodyURL } from "../art.js";
import { store, villager } from "../store.js";
import { h, $, block, toast } from "./dom.js";
import { badge, REASON } from "./claims.js";
import { speak, stopVoice, voiceOn, setVoice } from "../voice.js";
import { icon } from "./icons.js";

let deps = null; 
export function initEncounter(d) { deps = d; }

let cur = null; 
export const encounterOpen = () => !!cur;

const g = () => store.game;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));


function onKey(e) {
  if (!cur || document.querySelector("#modal-root .backdrop")) return; 
  const k = e.key;
  const typing = document.activeElement?.tagName === "INPUT";
  if (k === "Escape") {
    e.preventDefault(); e.stopImmediatePropagation();
    if (cur.back) { const b = cur.back; cur.back = null; b(); } else closeEncounter();
    return;
  }
  if (typing) return;
  if (k === "Enter" || k === " " || k === "e" || k === "E") {
    if (document.activeElement?.tagName === "BUTTON" && cur.box.contains(document.activeElement) && !cur.advance) return; 
    e.preventDefault(); e.stopImmediatePropagation();
    if (cur.advance) cur.advance();
    else document.activeElement?.click?.();
    return;
  }
  if (k.startsWith("Arrow")) {
    const items = [...cur.box.querySelectorAll(".enc-choice:not(:disabled)")];
    if (!items.length) return;
    e.preventDefault(); e.stopImmediatePropagation();
    const i = Math.max(0, items.indexOf(document.activeElement));
    const cols = cur.box.querySelector(".enc-menu") ? 2 : 1;
    const step = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: cols, ArrowUp: -cols }[k];
    items[(i + step + items.length) % items.length].focus();
  }
}


function say(html, { wait: needAdvance = true, cls = "", speaker = null } = {}) {
  return new Promise((resolve) => {
    const textEl = h("p", { class: `enc-line ${cls}` });
    const arrow = h("span", { class: "enc-next", hidden: true }, "▼");
    cur.text.replaceChildren(...[speaker && h("span", { class: "enc-speaker" }, speaker), textEl, arrow].filter(Boolean));
    cur.side.replaceChildren();
    const full = html;
    let i = 0, done = false;
    const finish = () => {
      done = true; clearInterval(timer);
      if (!cur) return;
      textEl.textContent = full;
      if (!needAdvance) { cur.advance = null; resolve(); return; }
      arrow.hidden = false;
      cur.advance = () => { cur.advance = null; resolve(); };
    };
    const timer = setInterval(() => { if (!cur) return clearInterval(timer); i += 2; textEl.textContent = full.slice(0, i); if (i >= full.length) finish(); }, 18);
    cur.advance = () => { if (!done) finish(); };
    cur.box.onclick = (e) => { if (e.target.closest("button, input")) return; cur.advance?.(); };
  });
}

function menu(items) {
  return new Promise((resolve) => {
    cur.advance = null;
    cur.side.replaceChildren(h("div", { class: "enc-menu" }, items.map(([key, label, disabled]) =>
      h("button", { class: "enc-choice", disabled, onclick: () => resolve(key) }, "▸ ", label))));
    cur.back = null;
    requestAnimationFrame(() => cur.side.querySelector(".enc-choice:not(:disabled)")?.focus());
  });
}

function askPanel(v, list) {
  return new Promise((resolve) => {
    cur.advance = null;
    const input = h("input", { class: "enc-input", maxlength: 200, placeholder: `Type a question for ${v.name}…`, autocomplete: "off" });
    const submit = () => { const q = input.value.trim(); if (q) resolve(q); };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); submit(); }
      if (e.key === "ArrowDown") { e.preventDefault(); cur.text.querySelector(".enc-choice.q")?.focus(); }
    });
    cur.text.replaceChildren(
      h("div", { class: "enc-ask-row" }, input),
      h("p", { class: "enc-speaker" }, "or pick one"),
      h("div", { class: "enc-list" }, list.map((q) => h("button", { class: "enc-choice q", onclick: () => resolve(q) }, q))));
    cur.side.replaceChildren(h("div", { class: "enc-menu one" },
      h("button", { class: "enc-choice", onclick: submit }, "▸ Ask"),
      h("button", { class: "enc-choice", onclick: () => resolve(null) }, "◂ Back")));
    cur.back = () => resolve(null);
    requestAnimationFrame(() => input.focus());
  });
}

function showClaim(c, idx, total) {
  return new Promise((resolve) => {
    const game = g();
    const render = () => {
      const claim = game.claims[c.claim_id] || c;
      const pinned = game.pinned.includes(claim.claim_id);
      const hearsay = claim.hearsay_from || (claim.cites || []).some((x) => /^H\d+/.test(x));
      cur.text.replaceChildren(
        h("div", { class: "enc-claim-top" }, badge(claim.status), hearsay ? h("span", { class: "tag" }, "hearsay") : null,
          claim.highlight ? h("span", { class: "tag star" }, icon("star"), " useful") : null, total > 1 ? h("small", {}, `claim ${idx + 1} of ${total}`) : null),
        h("p", { class: "enc-line enc-claimtext" }, claim.text),
        claim.quote && claim.status !== "unchecked"
          ? h("p", { class: "enc-source" }, icon("scroll"), ` ${claim.source_title || "Source"} `, (claim.cites || []).map((x) => h("code", {}, x)), ` “${claim.quote}”`)
          : claim.status === "unsupported" ? h("p", { class: "enc-source bad" }, `Checker: ${REASON[claim.reason] || "not backed by their records"}`)
          : claim.status === "unchecked" ? h("p", { class: "enc-source" }, "Badges are hidden on Hard. Spend a verify check to see if this holds.") : null);
      const acts = [];
      if (claim.status === "supported") acts.push(pinned ? h("button", { class: "enc-choice", disabled: true }, icon("notebook"), " In your notebook")
        : h("button", { class: "enc-choice", onclick: async () => { await deps.pin(claim); plateStats(); render(); } }, icon("notebook"), " Add to notebook"));
      if (claim.status === "unchecked" && game.limits.verifies_per_day > 0)
        acts.push(h("button", { class: "enc-choice", disabled: !(game.state.verifies_left > 0), onclick: async () => { await deps.verify(claim); react(game.claims[claim.claim_id]); plateStats(); render(); } },
          icon("scales"), ` Verify (${game.state.verifies_left})`));
      acts.push(h("button", { class: "enc-choice", onclick: () => resolve() }, idx + 1 < total ? "Next ▸" : "Done ▸"));
      cur.side.replaceChildren(h("div", { class: "enc-menu one" }, acts));
      cur.advance = null;
      requestAnimationFrame(() => cur.side.querySelector(".enc-choice:not(:disabled)")?.focus());
    };
    cur.back = null;
    render();
    react(c);
    speak(cur.v, c.text);
  });
}

function react(c) {
  const el = cur?.npcImg;
  if (!el) return;
  const cls = c?.status === "unsupported" ? "shake" : "hop";
  el.classList.remove("hop", "shake"); void el.offsetWidth; el.classList.add(cls);
  cur.npcGlow.className = `enc-glow ${c?.status || ""}`;
}

function plateStats() {
  const game = g();
  cur.mePlate.replaceChildren(
    h("b", {}, "Detective"),
    h("div", { class: "enc-bar" }, h("span", {}, "Questions"), h("i", {}, h("u", { style: { width: `${(game.state.questions_left / game.limits.questions_per_day) * 100}%` } })), h("small", {}, `${game.state.questions_left}/${game.limits.questions_per_day}`)),
    h("small", {}, icon("notebook"), ` ${game.pinned.length} in notebook · `, icon("bolt"), ` ${game.links.filter((l) => l.confirmed).length} confirmed`));
  const claims = (game.chats[cur.v.id] || []).flatMap((t) => t.claims.map((id) => game.claims[id]));
  const n = (s) => claims.filter((c) => c.status === s).length;
  const abst = (game.chats[cur.v.id] || []).filter((t) => t.abstained && !t.claims.length).length;
  cur.npcPlate.replaceChildren(
    h("b", {}, cur.v.name), h("span", { class: "enc-role" }, cur.v.role),
    cur.v.persona ? h("small", { class: "enc-persona" }, `“${cur.v.persona}”`) : null,
    h("div", { class: "enc-tally" }, h("span", { class: "ok" }, icon("check"), ` ${n("supported")}`), h("span", { class: "bad" }, icon("cross"), ` ${n("unsupported")}`), h("span", { class: "grey" }, icon("none"), ` ${abst}`)));
}

function voiceToggle() {
  const b = h("button", { class: "enc-voice", title: "Villager voices", "aria-pressed": voiceOn() });
  const paint = () => { b.replaceChildren(icon(voiceOn() ? "sound" : "mute"), voiceOn() ? " Voices on" : " Voices off"); b.setAttribute("aria-pressed", voiceOn()); };
  b.onclick = (e) => { e.stopPropagation(); setVoice(!voiceOn()); paint(); };
  paint();
  return b;
}


export async function openEncounter(vid) {
  const v = villager(vid);
  if (!v || cur) return;
  const scene = deps.scene();
  block(true);
  const bgURL = await scene.snapshotFor(vid);
  const area = scene.area;
  const npcImg = h("img", { class: "enc-npc", src: fullBodyURL(v.id, v.role?.toLowerCase(), "down"), alt: v.name });
  const meImg = h("img", { class: "enc-me", src: fullBodyURL("player", "detective", "up"), alt: "" });
  const npcGlow = h("div", { class: "enc-glow" });
  const text = h("div", { class: "enc-text" });
  const side = h("div", { class: "enc-side" });
  const box = h("div", { class: "enc-box" }, text, side);
  const npcPlate = h("div", { class: "enc-plate npc" });
  const mePlate = h("div", { class: "enc-plate me" });
  const root = h("div", { class: `enc ${area === "village" ? "outdoor" : "indoor"}`, role: "dialog", "aria-label": `Talking to ${v.name}` },
    h("div", { class: "enc-bg", style: { backgroundImage: `url(${bgURL})` } }),
    h("div", { class: "enc-vignette" }),
    npcPlate,
    h("div", { class: "enc-stage npc" }, npcGlow, h("div", { class: "enc-platform" }), npcImg),
    h("div", { class: "enc-stage me" }, h("div", { class: "enc-platform" }), meImg),
    mePlate, box,
    voiceToggle(),
    h("div", { class: "enc-flash" }));
  $("#encounter").replaceChildren(root);
  $("#encounter").hidden = false;
  cur = { v, root, box, text, side, npcImg, npcGlow, npcPlate, mePlate, advance: null, back: null };
  window.addEventListener("keydown", onKey, true);
  deps.onOpen?.(vid);
  plateStats();

  const game = g();
  const chats = game.chats[vid] || [];
  await say(chats.length ? `${v.name} sees you coming back.` : `You approach ${v.name}, the ${v.role}.`, { wait: false });
  await wait(450);

  for (;;) {
    if (!cur) return;
    const out = g().state.questions_left <= 0;
    if (out) await say("You've used every question for today. End the day to keep investigating.", { wait: false });
    else await say(`What will you ask ${v.name}?`, { wait: false });
    const choice = await menu([["ask", "Ask", out], ["log", "Notes"], ["leave", "Leave"]]);
    if (choice === "leave") break;
    if (choice === "log") { deps.history(vid); await waitClosed(); continue; }
    const q = await askPanel(v, deps.quickAsks(v));
    if (cur) cur.back = null;
    if (!q) continue;
    await interview(v, q);
  }
  closeEncounter();
}

function waitClosed() {
  return new Promise((resolve) => {
    const t = setInterval(() => { if (!document.querySelector("#modal-root .backdrop")) { clearInterval(t); resolve(); } }, 150);
  });
}

async function interview(v, q) {
  await say(`“${q}”`, { speaker: "You", wait: false });
  await wait(350);
  cur.text.append(h("p", { class: "enc-thinking" }, `${v.name} is checking their records`, h("i", {}, "…")));
  cur.side.replaceChildren();
  cur.advance = null; cur.back = null;
  let r;
  try { r = await deps.askApi(v.id, q); } catch (e) { toast(e.message, "bad"); return; }
  if (!cur) return;
  plateStats();
  for (const s of r.speech || []) { react(null); speak(v, s.replace(/^#\s*/, "")); await say(`“${s.replace(/^#\s*/, "")}”`, { speaker: v.name, cls: "speech" }); if (!cur) return; }
  if (r.abstained && !r.claims.length) {
    cur.npcGlow.className = "enc-glow abstained";
    speak(v, "I'm not sure.");
    cur.text.replaceChildren(h("div", { class: "enc-claim-top" }, badge("abstained")),
      h("p", { class: "enc-line enc-claimtext" }, "“I'm not sure.”"),
      h("p", { class: "enc-source" }, `Nothing about this in ${v.name}'s records, so they didn't guess.`));
    await new Promise((resolve) => {
      cur.side.replaceChildren(h("div", { class: "enc-menu one" }, h("button", { class: "enc-choice", onclick: resolve }, "Done ▸")));
      cur.back = null; cur.advance = null;
      requestAnimationFrame(() => cur.side.querySelector(".enc-choice")?.focus());
    });
  }
  for (let i = 0; i < r.claims.length; i++) { if (!cur) return; await showClaim(r.claims[i], i, r.claims.length); }
  plateStats();
}

export function closeEncounter() {
  if (!cur) return;
  const vid = cur.v.id;
  stopVoice();
  cur.root.classList.add("out");
  window.removeEventListener("keydown", onKey, true);
  cur = null;
  setTimeout(() => { $("#encounter").hidden = true; $("#encounter").replaceChildren(); }, 220);
  block(false);
  deps.onClose?.(vid);
}
