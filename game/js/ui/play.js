// The case flow: HUD, questioning, notebook, contradiction board, evening gossip, accusation, results.

import { api } from "../api.js";
import { portraitURL } from "../art.js";
import { store, newGame, villager, nameOf, emit, on } from "../store.js";
import { h, $, openModal, closeModal, closeAllModals, block, toast, confirmModal, modalOpen } from "./dom.js";
import { claimCard, abstainCard, badge } from "./claims.js";
import { initEncounter, openEncounter, closeEncounter, encounterOpen } from "./encounter.js";
import { openJournal, setJournalScene } from "./journal.js";
import { voiceOn, setVoice } from "../voice.js";
import { soundOn, setSound } from "../audio.js";

let scene = null;
let dialogueFor = null;
let busy = false;
export const setScene = (s) => { scene = s; setJournalScene(() => scene); };

const SLOT_NAME = ["Morning", "Afternoon", "Evening"];
const g = () => store.game;
const portrait = (v, size = 64) => h("img", { class: "portrait", src: portraitURL(v.id, v.role?.toLowerCase(), size), alt: "", width: size, height: size });

function record(turn) { g()?.transcript.push({ day: g().state.day, ...turn }); }

// ---------- start ----------

export async function startCase(settings, { onMenu }) {
  showLoading(`Writing a new mystery for Vaudville…`);
  let resp;
  try {
    resp = await api.newCase({ seed: settings.seed ? Number(settings.seed) : null, difficulty: settings.difficulty, mode: settings.mode });
  } catch (e) {
    hideLoading();
    toast(`Could not start a case: ${e.message}`, "bad");
    return false;
  }
  hideLoading();
  const game = newGame(resp, settings);
  game.transcript = [];
  game.onMenu = onMenu;
  scene.setupCase(game.villagers, game.victim.name, game.state.seed || 0);
  scene.setMode("play");
  scene.resetPlayer();
  scene.setPhase("day", 10);
  scene.newDay(game.state.day);
  renderHud();
  $("#hud").hidden = false;
  $("#help").hidden = false;
  morningBriefing(true);
  return true;
}

export function leaveCase() {
  closeDialogue();
  closeAllModals();
  $("#hud").hidden = true;
  $("#help").hidden = true;
  store.game = null;
}

// ---------- HUD ----------
// No banner: a sky strip with the day and stats in the top-left, round icon buttons top-right.

const hudObserver = new ResizeObserver(([e]) => document.documentElement.style.setProperty("--hud-h", `${Math.ceil(e.target.offsetHeight)}px`));

const ICONS = {
  journal: '<path d="M5 3h11a3 3 0 0 1 3 3v15H8a3 3 0 0 1-3-3z"/><path d="M5 18a3 3 0 0 1 3-3h11"/><path d="M10 7h5M10 10h5"/>',
  notebook: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/><path d="M5 7H3M5 12H3M5 17H3"/>',
  board: '<rect x="3" y="4" width="18" height="14" rx="1.5"/><circle cx="8" cy="9" r="1.6"/><circle cx="16" cy="13" r="1.6"/><path d="M8 9l8 4"/><path d="M9 18l-1.5 3M15 18l1.5 3"/>',
  accuse: '<path d="M14 4l6 6-3 3-6-6z"/><path d="M11 7l-7 7 3 3 7-7"/><path d="M3 21h9"/>',
  sleep: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
};
const icon = (name) => {
  const el = h("span", { class: "ico-svg", "aria-hidden": "true" });
  el.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
  return el;
};
const hudBtn = (name, label, onclick, cls = "") =>
  h("button", { class: `hud-btn ${cls}`, onclick, title: label, "aria-label": label }, icon(name), h("small", {}, label));

export function renderHud() {
  const game = g();
  if (!game) return;
  const st = game.state, lim = game.limits;
  const hud = $("#hud");
  hudObserver.observe(hud);
  hud.replaceChildren(
    h("div", { class: "hud-time" },
      timeEl(),
      h("div", { class: "hud-stats" },
        h("span", { title: "Questions left today" }, h("b", {}, st.questions_left), `/${lim.questions_per_day} questions`),
        h("span", { class: "hearts", title: "Strikes left (wrong accusations)" }, "♥".repeat(Math.max(0, st.strikes_left)), h("s", {}, "♥".repeat(Math.max(0, lim.strikes - st.strikes_left)))),
        lim.verifies_per_day > 0 && h("span", { title: "Verify checks left today" }, "⚖ ", h("b", {}, st.verifies_left)),
        h("span", { title: "Pinned claims · confirmed contradictions" }, "📌 ", h("b", {}, game.pinned.length), " ⚡ ", h("b", {}, game.links.filter((l) => l.confirmed).length)))),
    h("div", { class: "hud-actions" },
      hudBtn("journal", "Journal", () => openJournal()),
      hudBtn("notebook", "Notebook", openNotebook),
      hudBtn("board", "Board", openBoard),
      hudBtn("accuse", "Accuse", openAccuse, "warn"),
      hudBtn("sleep", "End day", endDay, game.sunset ? "pulse" : ""),
      hudBtn("menu", "Menu", openMenu)));
}

on("hud", renderHud);

// The sky strip: sunrise -> midday -> sunset, with the sun moving along it (cosmetic clock).
function timeEl() {
  const game = g();
  const c = game?.clock || { label: "08:00", frac: 0 };
  const f = Math.max(0, Math.min(1, c.frac));
  return h("div", { class: "sky-wrap", id: "hud-time", title: "Time of day. The sun sets at 19:00; end the day whenever you're ready." },
    h("div", { class: "sky-top" }, h("b", {}, `Day ${Math.min(game.state.day, game.limits.days)} of ${game.limits.days}`), h("span", {}, c.label)),
    h("div", { class: "sky" },
      h("div", { class: "sky-arc" }),
      h("div", { class: `sun ${f > 0.8 ? "low" : ""}`, style: { left: `${f * 100}%`, bottom: `${Math.sin(f * Math.PI) * 18 + 3}px` } })),
    h("div", { class: "sky-labels" }, h("span", {}, "sunrise"), h("span", {}, "midday"), h("span", {}, "sunset")));
}
on("clock", (c) => {
  if (!g()) return;
  g().clock = c;
  $("#hud-time")?.replaceWith(timeEl());
});
on("sunset", () => {
  if (!g() || g().over) return;
  g().sunset = true;
  toast("The sun is setting over Vaudville. End the day when you're ready.", "info", 4500);
  renderHud();
});
on("area", (a) => { if (g()) g().area = a.title; });
let smalltalkHint = false;
on("smalltalk", () => {
  if (smalltalkHint || !g()) return;
  smalltalkHint = true;
  toast("Townsfolk chat is just local colour. Only the case villagers keep records you can check.", "info", 5000);
});

// ---------- briefing / inspect ----------

function evidenceList(compact = false) {
  const game = g();
  return h("div", { class: "evidence" },
    game.evidence.map((doc) => h("div", { class: "doc" },
      h("h4", {}, "📜 ", doc.title),
      doc.sentences.map((s) => {
        const c = game.evidenceClaimIds.map((id) => game.claims[id]).find((c) => (c.cites || []).includes(s.id));
        return c ? claimCard(c, { compact, pinned: game.pinned.includes(c.claim_id), onPin }) : h("p", {}, s.text);
      }))));
}

function morningBriefing(first) {
  const game = g();
  const day = game.state.day, last = game.gossip[game.gossip.length - 1];
  const body = h("div", { class: "briefing" },
    h("p", { class: "kicker" }, `Day ${day} · Morning briefing`),
    h("h2", {}, first ? "A death in Vaudville" : "The village wakes"),
    first && h("p", { class: "lead" }, game.briefing),
    first && h("div", { class: "cast" }, game.villagers.map((v) => h("div", { class: "cast-card" }, portrait(v, 48), h("b", {}, v.name), h("small", {}, v.role)))),
    first && h("h3", {}, "Evidence added to your notebook"),
    first && evidenceList(true),
    !first && last && h("div", {},
      h("h3", {}, "Last night's gossip"),
      h("p", {}, `${last.events.filter((e) => e.status !== "abstained").length} things were passed between villagers. They may now repeat what they heard, with attribution.`),
      last.hints.length ? h("ul", { class: "hints" }, last.hints.map((x) => h("li", {}, "💭 ", x))) : null),
    h("div", { class: "rules" },
      h("h3", {}, "How to solve it"),
      h("ol", {},
        h("li", {}, "Walk up to villagers (WASD / arrows, or click the ground) and press ", h("kbd", {}, "E"), ", or click them, to question them."),
        h("li", {}, "Every claim is checked against the villager's own documents: ", badge("supported"), " ", badge("unsupported"), " ", badge("abstained"),
          game.limits.badges ? "" : h("span", {}, " On Hard, badges are hidden: spend verify checks.")),
        h("li", {}, "Pin green claims. On the board, link two pinned claims that can't both be true."),
        h("li", {}, "Accuse with at least 2 confirmed contradictions involving the killer, plus a pinned motive."))),
    h("div", { class: "row end" }, h("button", { class: "btn primary", autofocus: true, onclick: () => m.close() }, first ? "Begin the investigation" : "Start the day")));
  const m = openModal(body, { wide: true });
}

on("inspect", (where) => {
  if (!g() || modalOpen()) return;
  const game = g();
  const inside = where && where !== "village";
  openModal(h("div", {},
    h("p", { class: "kicker" }, "The scene"),
    h("h2", {}, inside ? "The chalk outline" : "The guildhall side door"),
    h("p", { class: "lead" }, inside
      ? `Chalk marks the floor where ${game.victim.name} was found. A few dark stains, the side door still ajar. ${game.briefing}`
      : `${game.briefing} The side door hangs open on its latch.`),
    evidenceList()), { wide: true });
});

// ---------- interviews (the encounter screen) ----------

on("talk", (id) => { if (g() && !modalOpen() && !encounterOpen()) openDialogue(id); });

function quickAsks(v) {
  const game = g();
  const others = game.villagers.filter((x) => x.id !== v.id);
  const other = others[(game.state.questions_used + v.id.length) % others.length];
  return [
    "Where were you on the night of the murder?",
    `What do you know about ${game.victim.name}?`,
    `Who did you see near the ${game.scene} on day 2?`,
    `When did you last see ${other.name}?`,
    `Did anyone quarrel with ${game.victim.name}?`,
    "Tell me about your records.",
    game.state.day > 1 && "What did anyone tell you last night?",
  ].filter(Boolean);
}

initEncounter({
  scene: () => scene,
  quickAsks,
  askApi: (vid, q) => ask(vid, q),
  pin: (c) => onPin(c),
  verify: (c) => onVerify(c),
  history: (vid) => openHistory(vid),
  onOpen: (vid) => { dialogueFor = vid; emit("talk-open", vid); },
  onClose: () => { dialogueFor = null; emit("talk-close"); renderHud(); },
});

export function openDialogue(id) {
  if (!villager(id) || encounterOpen()) return;
  openEncounter(id);
}

export function closeDialogue() { closeEncounter(); }
export const dialogueOpen = () => encounterOpen();

function claimOpts() {
  const game = g();
  return {
    onPin, onVerify: game.limits.verifies_per_day > 0 ? onVerify : null,
    verifiesLeft: game.state.verifies_left,
  };
}

// Everything said so far with one villager (opened from the encounter's Notes).
function openHistory(vid) {
  const game = g(), v = villager(vid);
  const body = h("div");
  const render = () => {
    const chats = game.chats[vid] || [];
    const opts = claimOpts();
    body.replaceChildren(
      h("h2", {}, `Notes on ${v.name}`),
      chats.length === 0 ? h("p", { class: "muted" }, "You haven't asked anything yet.") :
        h("div", { class: "chat-log" }, chats.map((t) => h("div", { class: "turn" },
          h("div", { class: "q" }, h("span", {}, `You · day ${t.day}`), t.question),
          h("div", { class: "a" },
            t.speech.map((s) => h("p", { class: "speech" }, s.replace(/^#\s*/, ""))),
            t.abstained && !t.claims.length ? abstainCard() : null,
            t.claims.map((cid) => claimCard(game.claims[cid], { ...opts, pinned: game.pinned.includes(cid) })))))));
  };
  render();
  refreshers.add(render);
  openModal(body, { wide: true, onClose: () => refreshers.delete(render) });
}

// One question to the backend; updates the store and returns the reply.
async function ask(vid, question) {
  const game = g();
  busy = true;
  try {
    const r = await api.ask({ case_id: game.caseId, villager_id: vid, question });
    for (const c of r.claims) game.claims[c.claim_id] = c;
    (game.chats[vid] ||= []).push({ question, speech: r.speech || [], abstained: r.abstained, claims: r.claims.map((c) => c.claim_id), day: game.state.day });
    game.state.questions_left = r.questions_left;
    game.state.questions_used = (game.state.questions_used || 0) + 1;
    record({ type: "ask", villager_id: vid, question, speech: r.speech, abstained: r.abstained, claims: r.claims });
    scene.advanceClock(20);
    return r;
  } finally {
    busy = false;
    renderHud();
  }
}

async function onPin(c) {
  try {
    const r = await api.pin({ claim_id: c.claim_id });
    if (!r.ok) return toast(r.reason || "Only green claims can be pinned.", "bad");
    g().pinned = r.pinned;
    toast("Pinned to your notebook.", "ok", 1600);
  } catch (e) { toast(e.message, "bad"); }
  refreshAll();
}

async function onVerify(c) {
  try {
    const r = await api.verify({ claim_id: c.claim_id });
    const game = g();
    game.claims[c.claim_id] = { ...game.claims[c.claim_id], status: r.status, reason: r.reason ?? game.claims[c.claim_id].reason };
    game.state.verifies_left = r.verifies_left;
    toast(`Verified: ${r.status}.`, r.status === "supported" ? "ok" : "bad", 2000);
  } catch (e) { toast(e.message, "bad"); }
  refreshAll();
}

const refreshers = new Set();
function refreshAll() {
  renderHud();
  for (const f of refreshers) f();
}

// ---------- notebook ----------

export function openNotebook() {
  if (!g()) return;
  const game = g();
  let tab = "pinned";
  const body = h("div");
  const render = () => {
    const tabs = [["pinned", `Pinned (${game.pinned.length})`], ["evidence", "Evidence"], ["interviews", "Interviews"], ["gossip", "Gossip log"]];
    let pane;
    if (tab === "pinned") {
      pane = game.pinned.length
        ? h("div", { class: "cards" }, game.pinned.map((id) => claimCard(game.claims[id], { compact: true, showVillager: true })))
        : h("p", { class: "muted" }, "Nothing pinned yet. Pin green claims from conversations or evidence.");
    } else if (tab === "evidence") pane = evidenceList();
    else if (tab === "interviews") {
      pane = h("div", { class: "interviews" }, game.villagers.map((v) => {
        const claims = (game.chats[v.id] || []).flatMap((t) => t.claims.map((id) => game.claims[id]));
        const n = (s) => claims.filter((c) => c.status === s).length;
        const abst = (game.chats[v.id] || []).filter((t) => t.abstained && !t.claims.length).length;
        return h("button", { class: "interview", onclick: () => { m.close(); openDialogue(v.id); } },
          portrait(v, 40), h("div", {}, h("b", {}, v.name), h("small", {}, v.role)),
          h("div", { class: "counts" },
            h("span", { class: "ok" }, `✔ ${n("supported")}`), h("span", { class: "bad" }, `✖ ${n("unsupported")}`),
            h("span", { class: "grey" }, `∅ ${abst}`), n("unchecked") ? h("span", { class: "unk" }, `? ${n("unchecked")}`) : null));
      }));
    } else {
      pane = game.gossip.length ? h("div", {}, game.gossip.map((d) => h("div", { class: "gossip-day" },
        h("h4", {}, `Evening of day ${d.day}`),
        d.hints.length ? h("ul", { class: "hints" }, d.hints.map((x) => h("li", {}, "💭 ", x))) : null,
        d.events.map(gossipRow)))) : h("p", { class: "muted" }, "No gossip yet. It happens each evening when you end the day.");
    }
    body.replaceChildren(
      h("h2", {}, "Notebook"),
      h("div", { class: "tabs", role: "tablist" }, tabs.map(([k, label]) =>
        h("button", { role: "tab", class: `tab ${tab === k ? "on" : ""}`, "aria-selected": tab === k, onclick: () => { tab = k; render(); } }, label))),
      h("div", { class: "pane" }, pane));
  };
  render();
  refreshers.add(render);
  const m = openModal(body, { wide: true, onClose: () => refreshers.delete(render) });
}

function gossipRow(e) {
  const hidden = g() && !g().limits.badges;
  return h("div", { class: `gossip-row ${e.clash ? "clash" : ""}` },
    h("div", { class: "who" }, h("b", {}, nameOf(e.asker)), " asked ", h("b", {}, nameOf(e.responder))),
    h("div", { class: "q" }, `“${e.question}”`),
    h("div", { class: "a" }, hidden ? null : badge(e.status === "abstained" ? "abstained" : e.status),
      " ", e.status === "abstained" ? "Not in my records." : e.reply, e.heard_id ? h("code", {}, ` → ${e.heard_id}`) : null),
    e.clash ? h("div", { class: "clash-note" }, "⚑ this clashed with what the asker had written down") : null);
}

// ---------- contradiction board ----------

export function openBoard() {
  if (!g()) return;
  const game = g();
  const sel = new Set();
  let checking = false;
  const body = h("div");
  const render = () => {
    const pins = game.pinned.map((id) => game.claims[id]);
    body.replaceChildren(
      h("h2", {}, "Contradiction board"),
      h("p", { class: "muted" }, "Pick two pinned claims that can't both be true, then check them. The checker compares the underlying facts: the same person, the same time, different places."),
      pins.length < 2 ? h("p", { class: "empty" }, "Pin at least two green claims to start linking.") :
        h("div", { class: "board" }, pins.map((c) => {
          const on = sel.has(c.claim_id);
          return h("button", { class: `board-card ${on ? "on" : ""}`, "aria-pressed": on, onclick: () => {
            if (on) sel.delete(c.claim_id); else { if (sel.size >= 2) sel.delete([...sel][0]); sel.add(c.claim_id); }
            render();
          } }, h("span", { class: "who" }, nameOf(c.villager_id)), h("span", {}, c.text), on ? h("span", { class: "sel" }, "●") : null);
        })),
      h("div", { class: "row end" },
        h("button", { class: "btn primary", disabled: sel.size !== 2 || checking, onclick: check }, checking ? "Checking…" : "⚡ Check link")),
      game.links.length ? h("div", { class: "links" }, h("h3", {}, "Links checked"),
        game.links.map((l) => h("div", { class: `link ${l.confirmed ? "ok" : "bad"}` },
          h("span", { class: "mark" }, l.confirmed ? "⚡ Confirmed" : "✖ No clash"),
          h("span", {}, `${nameOf(game.claims[l.a].villager_id)}: “${game.claims[l.a].text}”`),
          h("span", { class: "vs" }, "vs"),
          h("span", {}, `${nameOf(game.claims[l.b].villager_id)}: “${game.claims[l.b].text}”`),
          h("small", {}, l.reason)))) : null);
  };
  const check = async () => {
    const [a, b] = [...sel];
    if (game.links.some((l) => (l.a === a && l.b === b) || (l.a === b && l.b === a))) return toast("You already checked that pair.", "info");
    checking = true; render();
    try {
      const r = await api.link({ claim_a: a, claim_b: b });
      game.links.push({ a, b, confirmed: r.confirmed, reason: r.reason });
      record({ type: "link", claim_a: game.claims[a].text, claim_b: game.claims[b].text, confirmed: r.confirmed, reason: r.reason });
      toast(r.confirmed ? `Contradiction confirmed: ${r.reason}` : "No contradiction between those.", r.confirmed ? "ok" : "bad");
      sel.clear();
    } catch (e) { toast(e.message, "bad"); }
    checking = false;
    renderHud(); render();
  };
  render();
  refreshers.add(render);
  openModal(body, { wide: true, onClose: () => refreshers.delete(render) });
}

// ---------- end of day: gossip ----------

export async function endDay() {
  const game = g();
  if (!game || busy) return;
  closeDialogue();
  const last = game.state.day >= game.limits.days;
  const ok = await confirmModal(`End day ${game.state.day}?`,
    last ? "This is the last day. If you sleep without accusing anyone, the trail goes cold." : "Unused questions are lost. In the evening the villagers gossip, and what they hear can change what they tell you tomorrow.",
    "End the day");
  if (!ok) return;
  busy = true;
  block(true);
  let r;
  try { r = await api.dayEnd({ case_id: game.caseId }); } catch (e) { toast(e.message, "bad"); busy = false; block(false); return; }
  const day = game.state.day;
  game.gossip.push({ day, events: r.events, hints: r.hints || [] });
  record({ type: "gossip", events: r.events, hints: r.hints || [] });
  scene.setPhase("dusk");
  const feed = h("div", { class: "feed" });
  const panel = h("div", { class: "gossip-panel" },
    h("div", { class: "row" }, h("h3", {}, `Evening of day ${day} · gossip`), h("button", { class: "btn small ghost", onclick: () => scene.skipScripted() }, "Skip ▸▸")),
    feed);
  $("#overlay-bottom").replaceChildren(panel);
  scene.showWhole();
  await scene.playGossip(r.events, { onEvent: (e) => { feed.append(gossipRow(e)); feed.scrollTop = feed.scrollHeight; } });
  if (r.hints?.length) feed.append(h("ul", { class: "hints" }, r.hints.map((x) => h("li", {}, "💭 ", x))));
  await new Promise((res) => {
    const sleepBtn = h("button", { class: "btn primary", onclick: res }, "🌙 Sleep");
    panel.append(h("div", { class: "row end" }, sleepBtn));
    sleepBtn.focus();
  });
  $("#overlay-bottom").replaceChildren();
  scene.setPhase("night", 600);
  await scene.fade(700);
  game.state = { ...game.state, ...r.state, day: r.day };
  busy = false;
  block(false);
  if (r.game_over) return showResults({ correct: false, outOfDays: true });
  scene.setPhase("day", 800);
  scene.resetPlayer();
  game.sunset = false;
  scene.newDay(game.state.day);
  scene.setMode("play");
  renderHud();
  morningBriefing(false);
}

// ---------- accusation ----------

export function openAccuse() {
  const game = g();
  if (!game) return;
  closeDialogue();
  let suspect = null;
  const confirmed = game.links.filter((l) => l.confirmed);
  const chosen = new Set(confirmed.map((l) => `${l.a}|${l.b}`));
  let motive = game.pinned.find((id) => game.evidenceClaimIds.includes(id)) || "";
  const body = h("div");
  const render = () => {
    body.replaceChildren(
      h("h2", {}, "Make an accusation"),
      h("p", { class: "muted" }, `A wrong accusation costs a strike (${game.state.strikes_left} left).`),
      h("h3", {}, "1 · Who did it?"),
      h("div", { class: "suspects" }, game.villagers.map((v) => h("button", { class: `suspect ${suspect === v.id ? "on" : ""}`, "aria-pressed": suspect === v.id, onclick: () => { suspect = v.id; render(); } },
        portrait(v, 56), h("b", {}, v.name), h("small", {}, v.role)))),
      h("h3", {}, "2 · Contradictions"),
      confirmed.length ? h("div", { class: "checks" }, confirmed.map((l) => {
        const k = `${l.a}|${l.b}`;
        return h("label", { class: "check" }, h("input", { type: "checkbox", checked: chosen.has(k), onchange: (e) => { e.target.checked ? chosen.add(k) : chosen.delete(k); } }), ` ${l.reason}`);
      })) : h("p", { class: "empty" }, "No confirmed contradictions yet. Use the board."),
      h("h3", {}, "3 · Motive"),
      game.pinned.length ? h("select", { class: "select", onchange: (e) => { motive = e.target.value; } },
        h("option", { value: "" }, "Choose a pinned claim…"),
        game.pinned.map((id) => h("option", { value: id, selected: id === motive }, `${nameOf(game.claims[id].villager_id)}: ${game.claims[id].text.slice(0, 90)}`)))
        : h("p", { class: "empty" }, "Pin the claim that shows the motive."),
      h("div", { class: "row end" },
        h("button", { class: "btn ghost", onclick: () => m.close() }, "Not yet"),
        h("button", { class: "btn warn", disabled: !suspect, onclick: submit }, suspect ? `Accuse ${nameOf(suspect)}` : "Accuse")));
  };
  const submit = async () => {
    const links = [...chosen].map((k) => k.split("|"));
    let r;
    try { r = await api.accuse({ case_id: game.caseId, villager_id: suspect, links, motive_claim: motive || null }); }
    catch (e) { return toast(e.message, "bad"); }
    record({ type: "accuse", villager_id: suspect, correct: r.correct, confirmed_links: r.confirmed_links, motive_ok: r.motive_ok });
    game.state.strikes_left = r.strikes_left;
    m.close();
    renderHud();
    if (r.correct || r.reveal) return showResults(r, suspect);
    scene.cameras.main.shake(300, 0.006);
    toast(`${nameOf(suspect)} is not charged. ${r.confirmed_links < 2 ? "You need 2 confirmed contradictions. " : ""}${!r.motive_ok ? "The motive doesn't hold. " : ""}Strikes left: ${r.strikes_left}.`, "bad", 5200);
  };
  render();
  const m = openModal(body, { wide: true });
}

// ---------- results ----------

function groundingStats(game) {
  const claims = Object.values(game.claims).filter((c) => c.villager_id !== "evidence");
  const turns = Object.values(game.chats).flat();
  const n = (s) => claims.filter((c) => c.status === s).length;
  const abst = turns.filter((t) => t.abstained && !t.claims.length).length;
  const total = n("supported") + n("unsupported");
  return { supported: n("supported"), unsupported: n("unsupported"), abstained: abst, questions: turns.length,
    unsupportedRate: total ? n("unsupported") / total : 0 };
}

function showResults(r, suspect) {
  const game = g();
  game.over = true;
  closeAllModals();
  const stats = groundingStats(game);
  (store.compare ||= {})[game.settings.mode] = { ...stats, won: !!r.correct, score: r.score ?? 0 };
  const LABEL = { grounded: "SFT + GRPO", sft: "SFT only", base: "Base" };
  const other = game.settings.mode === "grounded" ? "sft" : "grounded";  // GRPO vs SFT on the same seed
  const reveal = r.reveal;
  const killer = reveal && villager(reveal.killer);
  const cmp = store.compare;
  const body = h("div", { class: "results" },
    h("p", { class: "kicker" }, r.correct ? "Case closed" : "Case unsolved"),
    h("h2", {}, r.correct ? `You caught ${nameOf(suspect)}!` : r.outOfDays ? "The trail went cold" : "The village has lost faith in you"),
    r.correct && h("div", { class: "score" }, h("small", {}, "Score"), h("b", {}, r.score)),
    reveal ? h("div", { class: "reveal" },
      killer && portrait(killer, 72),
      h("div", {},
        h("h3", {}, `The killer: ${nameOf(reveal.killer)}`),
        h("p", {}, reveal.motive),
        h("ul", {}, (reveal.contradictions || []).map((c) => h("li", {}, "⚡ ", c))))) :
      h("p", { class: "muted" }, "The truth stays buried. (The backend reveals the killer once the game is over.)"),
    h("h3", {}, `Grounding report · ${LABEL[game.settings.mode] || game.settings.mode} village`),
    h("div", { class: "stats" },
      h("div", { class: "statbox ok" }, h("b", {}, stats.supported), h("small", {}, "supported claims")),
      h("div", { class: "statbox bad" }, h("b", {}, stats.unsupported), h("small", {}, "unsupported claims")),
      h("div", { class: "statbox grey" }, h("b", {}, stats.abstained), h("small", {}, "honest abstains")),
      h("div", { class: "statbox" }, h("b", {}, `${Math.round(stats.unsupportedRate * 100)}%`), h("small", {}, "unsupported-claim rate"))),
    cmp.grounded && cmp.base ? h("table", { class: "compare" },
      h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", {}, "Base"), h("th", {}, "Grounded"))),
      h("tbody", {},
        [["Unsupported-claim rate", (s) => `${Math.round(s.unsupportedRate * 100)}%`], ["Supported claims", (s) => s.supported],
          ["Unsupported claims", (s) => s.unsupported], ["Abstains", (s) => s.abstained], ["Solved", (s) => (s.won ? `yes (${s.score})` : "no")]]
          .map(([k, f]) => h("tr", {}, h("td", {}, k), h("td", {}, f(cmp.base)), h("td", {}, f(cmp.grounded)))))) :
      h("p", { class: "muted" }, `Play the same seed with the ${other} village to compare them side by side.`),
    h("div", { class: "row end wrap" },
      h("button", { class: "btn ghost", onclick: () => downloadTranscript(game) }, "⬇ Save transcript"),
      h("button", { class: "btn", onclick: () => { const s = { ...game.settings, mode: other, seed: game.state.seed ?? game.settings.seed }; m.close(); leaveCase(); startCase(s, { onMenu: game.onMenu }); } },
        `Replay this case · ${LABEL[other]} village`),
      h("button", { class: "btn", onclick: () => { m.close(); leaveCase(); startCase({ ...game.settings, seed: "" }, { onMenu: game.onMenu }); } }, "New case"),
      h("button", { class: "btn primary", onclick: () => { m.close(); game.onMenu(); } }, "Main menu")));
  const m = openModal(body, { wide: true, dismissable: false });
}

// Transcripts recorded in play use the replay format (see game/README.md), so real model runs
// can be saved here and dropped into game/replays/.
export function downloadTranscript(game = g()) {
  const data = {
    replay_id: `${game.caseId}_${game.settings.mode}`,
    title: `Case ${game.caseId} · ${game.settings.mode} village · ${game.settings.difficulty}`,
    recorded: new Date().toISOString(),
    source: api.kind === "api" ? "live API" : "offline mock",
    mode: game.settings.mode, difficulty: game.settings.difficulty,
    briefing: game.briefing, villagers: game.villagers, evidence: game.evidence, victim: game.victim,
    turns: game.transcript,
  };
  const a = h("a", { href: URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })), download: `${data.replay_id}.json` });
  document.body.append(a); a.click(); a.remove();
}

// ---------- menu / loading ----------

function openMenu() {
  const game = g();
  const m = openModal(h("div", { class: "menu" },
    h("h2", {}, "Paused"),
    h("button", { class: "btn primary", autofocus: true, onclick: () => m.close() }, "Resume"),
    h("button", { class: "btn", onclick: () => { m.close(); openNotebook(); } }, "Notebook"),
    h("button", { class: "btn", onclick: (e) => { setSound(!soundOn()); e.target.textContent = `Sound & ambience: ${soundOn() ? "on" : "off"}`; } }, `Sound & ambience: ${soundOn() ? "on" : "off"}`),
    h("button", { class: "btn", onclick: (e) => { setVoice(!voiceOn()); e.target.textContent = `Villager voices: ${voiceOn() ? "on" : "off"}`; } }, `Villager voices: ${voiceOn() ? "on" : "off"}`),
    h("button", { class: "btn", onclick: () => downloadTranscript(game) }, "⬇ Save transcript so far"),
    h("button", { class: "btn ghost", onclick: async () => { m.close(); if (await confirmModal("Abandon this case?", "Your progress will be lost.", "Abandon")) game.onMenu(); } }, "Quit to main menu")));
}

function showLoading(text) {
  $("#loading").replaceChildren(h("div", { class: "loading-card" }, h("div", { class: "spinner" }), h("p", {}, text)));
  $("#loading").hidden = false;
}
function hideLoading() { $("#loading").hidden = true; }

// Keyboard shortcuts for play.
export function playKeys(e) {
  if (!g() || g().over) return false;
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName);
  if (encounterOpen()) return false; // the encounter has its own key handler
  if (e.key === "Escape") {
    if (modalOpen()) return false; // handled by the modal stack
    if (!busy) openMenu();
    return true;
  }
  if (typing || modalOpen() || dialogueFor || busy) return false;
  if (e.key === "n" || e.key === "N") { openNotebook(); return true; }
  if (e.key === "b" || e.key === "B") { openBoard(); return true; }
  if (e.key === "j" || e.key === "J") { openJournal(); return true; }
  return false;
}
