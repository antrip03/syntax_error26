import { api } from "../api.js";
import { portraitURL } from "../art.js";
import { store, newGame, villager, nameOf, emit, on } from "../store.js";
import { h, $, openModal, closeModal, closeAllModals, block, toast, confirmModal, modalOpen } from "./dom.js";
import { claimCard, abstainCard, badge, REASON } from "./claims.js";
import { initEncounter, openEncounter, closeEncounter, encounterOpen } from "./encounter.js";
import { openJournal, setJournalScene } from "./journal.js";
import { voiceOn, setVoice } from "../voice.js";
import { soundOn, setSound } from "../audio.js";
import { icon } from "./icons.js";
import { ASK_MINUTES } from "../VillageScene.js";

let scene = null;
let dialogueFor = null;
let busy = false;
export const setScene = (s) => { scene = s; setJournalScene(() => scene); };

const SLOT_NAME = ["Morning", "Afternoon", "Evening"];
const g = () => store.game;
const portrait = (v, size = 64) => h("img", { class: "portrait", src: portraitURL(v.id, v.role?.toLowerCase(), size), alt: "", width: size, height: size });

function record(turn) { g()?.transcript.push({ day: g().state.day, ...turn }); }

export async function startCase(settings, { onMenu }) {
  showLoading(`Writing a new mystery for Vaudeville…`);
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
  scene.setCrimeScene(game.scene, game.scenePlace);
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

const hudObserver = new ResizeObserver(([e]) => document.documentElement.style.setProperty("--hud-h", `${Math.ceil(e.target.offsetHeight)}px`));

const hudBtn = (name, label, onclick, cls = "") =>
  h("button", { class: `hud-btn ${cls}`, onclick, title: label, "aria-label": label }, icon(name, "hud"), h("small", {}, label));

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
        h("span", { class: "hearts", title: "Strikes left (wrong accusations)" }, Array.from({ length: Math.max(0, st.strikes_left) }, () => icon("heart", "full")), Array.from({ length: Math.max(0, lim.strikes - st.strikes_left) }, () => icon("heart", "lost"))),
        lim.verifies_per_day > 0 && h("span", { title: "Verify checks left today" }, icon("scales"), " ", h("b", {}, st.verifies_left)),
        h("span", { title: "Claims in your notebook · confirmed contradictions" }, icon("notebook"), " ", h("b", {}, game.pinned.length), " ", icon("bolt"), " ", h("b", {}, game.links.filter((l) => l.confirmed).length)))),
    h("div", { class: "hud-actions" },
      hudBtn("journal", "Journal", () => openJournal()),
      hudBtn("notebook", "Notebook", openNotebook),
      hudBtn("board", "Board", openBoard),
      hudBtn("accuse", "Accuse", openAccuse, "warn"),
      hudBtn("sleep", "End day", endDay, game.sunset ? "pulse" : ""),
      hudBtn("menu", "Menu", openMenu)));
}

on("hud", renderHud);

function timeEl() {
  const game = g();
  const c = game?.clock || { label: "08:00", frac: 0 };
  const f = Math.max(0, Math.min(1, c.frac));
  return h("div", { class: "sky-wrap", id: "hud-time", title: "Time of day. The sun sets at 19:00; end the day whenever you're ready." },
    h("div", { class: "sky-top" }, h("b", {}, `Inquiry day ${Math.min(game.state.day, game.limits.days)}/${game.limits.days}`), h("span", {}, c.label)),
    h("div", { class: "sky" },
      h("div", { class: "sky-arc" }),
      h("div", { class: `sun ${f > 0.8 ? "low" : ""}`, style: { left: `${f * 100}%`, bottom: `${Math.sin(f * Math.PI) * 18 + 3}px` } })),
    h("div", { class: "sky-labels" }, h("span", { class: "part" }, c.part || "Morning"), h("span", {}, "sunset 19:00")));
}
on("clock", (c) => {
  if (!g()) return;
  g().clock = c;
  $("#hud-time")?.replaceWith(timeEl());
});
on("daypart", (d) => toast(d.line, "info", 2600));

on("sunset", () => {
  if (!g() || g().over) return;
  g().sunset = true;
  toast("The sun is setting over Vaudeville. End the day when you're ready.", "info", 4500);
  renderHud();
});
on("area", (a) => { if (g()) g().area = a.title; });
let smalltalkHint = false;
on("smalltalk", () => {
  if (smalltalkHint || !g()) return;
  smalltalkHint = true;
  toast("Townsfolk chat is just local colour. Only the case villagers keep records you can check.", "info", 5000);
});

function evidenceList(compact = false) {
  const game = g();
  return h("div", { class: "evidence" },
    game.evidence.map((doc) => h("div", { class: "doc" },
      h("h4", {}, icon("scroll"), " ", doc.title),
      doc.sentences.map((s) => {
        const c = game.evidenceClaimIds.map((id) => game.claims[id]).find((c) => (c.cites || []).includes(s.id));
        return c ? claimCard(c, { compact, pinned: game.pinned.includes(c.claim_id), onPin }) : h("p", {}, s.text);
      }))));
}

function morningBriefing(first) {
  const game = g();
  const day = game.state.day, last = game.gossip[game.gossip.length - 1];
  const body = h("div", { class: "briefing" },
    h("p", { class: "kicker" }, `Inquiry day ${day} · Morning briefing`),
    h("h2", {}, first ? "A death in Vaudeville" : "The village wakes"),
    first && h("p", { class: "lead" }, game.briefing),
    first && h("p", { class: "muted small" }, "The villagers' records cover days 1 to 3 of last week. Ask them about those days."),
    first && h("div", { class: "cast" }, game.villagers.map((v) => h("div", { class: "cast-card" }, portrait(v, 48), h("b", {}, v.name), h("small", {}, v.role)))),
    first && h("h3", {}, "Evidence added to your notebook"),
    first && evidenceList(true),
    !first && last && h("div", {},
      h("h3", {}, "Last night's gossip"),
      h("p", {}, `${last.events.filter((e) => e.status !== "abstained").length} things were passed between villagers. They may now repeat what they heard, with attribution.`),
      last.hints.length ? h("ul", { class: "hints" }, last.hints.map((x) => h("li", {}, icon("thought"), " ", x))) : null),
    h("div", { class: "rules" },
      h("h3", {}, "How to solve it"),
      h("ol", {},
        h("li", {}, "Walk up to villagers (WASD / arrows, or click the ground) and press ", h("kbd", {}, "E"), ", or click them, to question them."),
        h("li", {}, "Every claim is checked against the villager's own documents: ", badge("supported"), " ", badge("unsupported"), " ", badge("abstained"),
          game.limits.badges ? "" : h("span", {}, " On Hard, badges are hidden: spend verify checks.")),
        h("li", {}, "Add green claims to your notebook. On the board, link two that can't both be true."),
        h("li", {}, "Accuse with at least 2 confirmed contradictions involving the killer, plus the motive from your notebook."))),
    h("div", { class: "row end" }, h("button", { class: "btn primary", autofocus: true, onclick: () => m.close() }, first ? "Begin the investigation" : "Start the day")));
  const m = openModal(body, { wide: true });
}

on("inspect", (where) => {
  if (!g() || modalOpen()) return;
  const game = g();
  const inside = where && where !== "village";
  openModal(h("div", {},
    h("p", { class: "kicker" }, "The scene"),
    h("h2", {}, inside ? "The chalk outline" : `The ${game.scenePlace}`),
    h("p", { class: "lead" }, inside
      ? `Chalk marks the floor of the ${game.scenePlace} where ${game.victim.name} was found. A few dark stains. ${game.briefing}`
      : `${game.briefing} Someone has chalked the spot where the body lay.`),
    evidenceList()), { wide: true });
});

on("talk", (id) => { if (g() && !modalOpen() && !encounterOpen()) openDialogue(id); });

function quickAsks(v) {
  const game = g();
  const others = game.villagers.filter((x) => x.id !== v.id);
  const other = others[(game.state.questions_used + v.id.length) % others.length];
  return [
    "Where were you on the night of the murder?",
    `What do you know about ${game.victim.name}?`,
    `Who did you see near the ${game.scenePlace} on the night of the murder?`,
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
    scene.advanceClock(ASK_MINUTES);
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
    toast("Added to your notebook.", "ok", 1600);
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

export function openNotebook() {
  if (!g()) return;
  const game = g();
  let tab = "pinned";
  const body = h("div");
  const render = () => {
    const tabs = [["pinned", `Saved claims (${game.pinned.length})`], ["evidence", "Evidence"], ["interviews", "Interviews"], ["gossip", "Gossip log"]];
    let pane;
    if (tab === "pinned") {
      pane = game.pinned.length
        ? h("div", { class: "cards" }, game.pinned.map((id) => claimCard(game.claims[id], { compact: true, showVillager: true })))
        : h("p", { class: "muted" }, "Your notebook is empty. Add green claims from conversations or evidence.");
    } else if (tab === "evidence") pane = evidenceList();
    else if (tab === "interviews") {
      pane = h("div", { class: "interviews" }, game.villagers.map((v) => {
        const claims = (game.chats[v.id] || []).flatMap((t) => t.claims.map((id) => game.claims[id]));
        const n = (s) => claims.filter((c) => c.status === s).length;
        const abst = (game.chats[v.id] || []).filter((t) => t.abstained && !t.claims.length).length;
        return h("button", { class: "interview", onclick: () => { m.close(); openDialogue(v.id); } },
          portrait(v, 40), h("div", {}, h("b", {}, v.name), h("small", {}, v.role)),
          h("div", { class: "counts" },
            h("span", { class: "ok" }, icon("check"), ` ${n("supported")}`), h("span", { class: "bad" }, icon("cross"), ` ${n("unsupported")}`),
            h("span", { class: "grey" }, icon("none"), ` ${abst}`), n("unchecked") ? h("span", { class: "unk" }, icon("question"), ` ${n("unchecked")}`) : null));
      }));
    } else {
      pane = game.gossip.length ? h("div", {}, game.gossip.map((d) => h("div", { class: "gossip-day" },
        h("h4", {}, `Evening of day ${d.day}`),
        d.hints.length ? h("ul", { class: "hints" }, d.hints.map((x) => h("li", {}, icon("thought"), " ", x))) : null,
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

const noCites = (t = "") => t.replace(/\s*\[[A-Z]+\d+(\.S\d+)?\]/g, "").replace(/<[^>]+>/g, "").trim();

function gossipRow(e) {
  const hidden = g() && !g().limits.badges;
  return h("div", { class: `gossip-row ${e.clash ? "clash" : ""}` },
    h("div", { class: "who" }, h("b", {}, nameOf(e.asker)), " asked ", h("b", {}, nameOf(e.responder))),
    h("div", { class: "q" }, `“${e.question}”`),
    e.claims?.length
      ? e.claims.map((c) => gossipClaim(c, hidden))
      : h("div", { class: "a" }, hidden ? null : badge(e.status === "abstained" ? "abstained" : e.status),
          " ", e.status === "abstained" ? "I'm not sure." : noCites(e.reply)),
    e.clash ? h("div", { class: "clash-note" }, icon("flag"), " this clashed with what the asker had written down") : null);
}

function gossipClaim(c, hidden) {
  const game = g();
  const ok = c.status === "supported";
  const row = h("div", { class: `gossip-claim ${ok ? "ok" : "bad"}` });
  const paint = () => row.replaceChildren(
    h("span", { class: "gc-text" }, hidden ? null : badge(c.status), " ", noCites(c.text),
      !ok && !hidden ? h("small", { class: "gc-why" }, ` · ${REASON[c.reason] || "not backed by their records"}`) : null),
    !ok ? null : game.pinned.includes(c.claim_id)
      ? h("span", { class: "pinned" }, icon("notebook"), " In your notebook")
      : h("button", { class: "btn small", onclick: async () => { await onPin(c); paint(); } }, icon("notebook"), " Add to notebook"));
  paint();
  return row;
}

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
      pins.length < 2 ? h("p", { class: "empty" }, "Add at least two green claims to your notebook to start linking.") :
        h("div", { class: "board" }, pins.map((c) => {
          const on = sel.has(c.claim_id);
          return h("button", { class: `board-card ${on ? "on" : ""}`, "aria-pressed": on, onclick: () => {
            if (on) sel.delete(c.claim_id); else { if (sel.size >= 2) sel.delete([...sel][0]); sel.add(c.claim_id); }
            render();
          } }, h("span", { class: "who" }, nameOf(c.villager_id)), h("span", {}, c.text), on ? h("span", { class: "sel" }, "●") : null);
        })),
      h("div", { class: "row end" },
        h("button", { class: "btn primary", disabled: sel.size !== 2 || checking, onclick: check }, ...(checking ? ["Checking…"] : [icon("bolt"), " Check link"]))),
      game.links.length ? h("div", { class: "links" }, h("h3", {}, "Links checked"),
        game.links.map((l) => h("div", { class: `link ${l.confirmed ? "ok" : "bad"}` },
          h("span", { class: "mark" }, icon(l.confirmed ? "bolt" : "cross"), l.confirmed ? " Confirmed" : " No clash"),
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
  for (const e of r.events) for (const c of e.claims || []) game.claims[c.claim_id] = c;
  game.gossip.push({ day, events: r.events, hints: r.hints || [] });
  record({ type: "gossip", events: r.events, hints: r.hints || [] });
  scene.setPhase("dusk");
  const feed = h("div", { class: "feed" });
  const shown = new Set();
  const show = (e) => { if (shown.has(e)) return; shown.add(e); feed.append(gossipRow(e)); feed.scrollTop = feed.scrollHeight; };
  const title = h("h3", {}, `Evening of day ${day} · gossip`);
  const skipBtn = h("button", { class: "btn small ghost", onclick: () => {
    const fast = scene.fast > 1;
    scene.setFastForward(!fast);
    skipBtn.textContent = fast ? "Fast-forward ▸▸" : "Normal speed ▸";
  } }, "Fast-forward ▸▸");
  const panel = h("div", { class: "gossip-panel" }, h("div", { class: "row" }, title, skipBtn), feed);
  $("#overlay-bottom").replaceChildren(panel);
  scene.viewInset = { bottom: panel.offsetHeight + 24 };
  await scene.playGossip(r.events, {
    hideStatus: !game.limits.badges,
    onRound: (n, of) => { title.textContent = `Evening of day ${day} · gossip · round ${n} of ${of}`; },
    onEvent: show,
  });
  scene.viewInset = {};
  r.events.forEach(show);
  skipBtn.remove();
  if (!r.events.length) feed.append(h("p", { class: "muted" }, "Nobody had much to say tonight."));
  if (r.hints?.length) feed.append(h("ul", { class: "hints" }, r.hints.map((x) => h("li", {}, icon("thought"), " ", x))));
  await new Promise((res) => {
    const sleepBtn = h("button", { class: "btn primary", onclick: res }, icon("sleep"), " Sleep");
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
      h("p", { class: "muted" }, `To charge someone you need 2 confirmed contradictions and the motive. Charging the wrong person costs a strike (${game.state.strikes_left} left).`),
      h("h3", {}, "1 · Who did it?"),
      h("div", { class: "suspects" }, game.villagers.map((v) => h("button", { class: `suspect ${suspect === v.id ? "on" : ""}`, "aria-pressed": suspect === v.id, onclick: () => { suspect = v.id; render(); } },
        portrait(v, 56), h("b", {}, v.name), h("small", {}, v.role)))),
      h("h3", {}, "2 · Contradictions"),
      confirmed.length ? h("div", { class: "checks" }, confirmed.map((l) => {
        const k = `${l.a}|${l.b}`;
        return h("label", { class: "check" }, h("input", { type: "checkbox", checked: chosen.has(k), onchange: (e) => { e.target.checked ? chosen.add(k) : chosen.delete(k); render(); } }), ` ${l.reason}`);
      })) : h("p", { class: "empty" }, "No confirmed contradictions yet. Use the board."),
      h("h3", {}, "3 · Motive"),
      game.pinned.length ? h("select", { class: "select", onchange: (e) => { motive = e.target.value; render(); } },
        h("option", { value: "" }, "Choose a pinned claim…"),
        game.pinned.map((id) => h("option", { value: id, selected: id === motive }, `${nameOf(game.claims[id].villager_id)}: ${game.claims[id].text.slice(0, 90)}`)))
        : h("p", { class: "empty" }, "Add the claim that shows the motive to your notebook."),
      h("div", { class: "row end" },
        h("button", { class: "btn ghost", onclick: () => m.close() }, "Not yet"),
        missing().length ? h("small", { class: "muted" }, `Still needed: ${missing().join(" · ")}`) : null,
        h("button", { class: "btn warn", disabled: missing().length > 0, onclick: submit }, suspect ? `Accuse ${nameOf(suspect)}` : "Accuse")));
  };
  const missing = () => {
    const out = [];
    if (!suspect) out.push("pick a suspect");
    if (chosen.size < 2) out.push(`2 contradictions (you have ${chosen.size})`);
    if (!motive) out.push("a motive");
    return out;
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
    if (r.insufficient) return toast(r.reason, "info", 5200);
    scene.cameras.main.shake(300, 0.006);
    toast(`${nameOf(suspect)} is not charged. ${r.confirmed_links < 2 ? "You need 2 confirmed contradictions. " : ""}${!r.motive_ok ? "The motive doesn't hold. " : ""}Strikes left: ${r.strikes_left}.`, "bad", 5200);
  };
  render();
  const m = openModal(body, { wide: true });
}

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
  const other = game.settings.mode === "grounded" ? "sft" : "grounded";
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
        h("ul", {}, (reveal.contradictions || []).map((c) => h("li", {}, icon("bolt"), " ", c))))) :
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
      h("button", { class: "btn ghost", onclick: () => downloadTranscript(game) }, icon("download"), " Save transcript"),
      h("button", { class: "btn", onclick: () => { const s = { ...game.settings, mode: other, seed: game.state.seed ?? game.settings.seed }; m.close(); leaveCase(); startCase(s, { onMenu: game.onMenu }); } },
        `Replay this case · ${LABEL[other]} village`),
      h("button", { class: "btn", onclick: () => { m.close(); leaveCase(); startCase({ ...game.settings, seed: "" }, { onMenu: game.onMenu }); } }, "New case"),
      h("button", { class: "btn primary", onclick: () => { m.close(); game.onMenu(); } }, "Main menu")));
  const m = openModal(body, { wide: true, dismissable: false });
}

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

function openMenu() {
  const game = g();
  const m = openModal(h("div", { class: "menu" },
    h("h2", {}, "Paused"),
    h("button", { class: "btn primary", autofocus: true, onclick: () => m.close() }, "Resume"),
    h("button", { class: "btn", onclick: () => { m.close(); openNotebook(); } }, "Notebook"),
    h("button", { class: "btn", onclick: (e) => { setSound(!soundOn()); e.target.textContent = `Sound & ambience: ${soundOn() ? "on" : "off"}`; } }, `Sound & ambience: ${soundOn() ? "on" : "off"}`),
    h("button", { class: "btn", onclick: (e) => { setVoice(!voiceOn()); e.target.textContent = `Villager voices: ${voiceOn() ? "on" : "off"}`; } }, `Villager voices: ${voiceOn() ? "on" : "off"}`),
    h("button", { class: "btn", onclick: () => downloadTranscript(game) }, icon("download"), " Save transcript so far"),
    h("button", { class: "btn ghost", onclick: async () => { m.close(); if (await confirmModal("Abandon this case?", "Your progress will be lost.", "Abandon")) game.onMenu(); } }, "Quit to main menu")));
}

function showLoading(text) {
  $("#loading").replaceChildren(h("div", { class: "loading-card" }, h("div", { class: "spinner" }), h("p", {}, text)));
  $("#loading").hidden = false;
}
function hideLoading() { $("#loading").hidden = true; }

export function playKeys(e) {
  if (!g() || g().over) return false;
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName);
  if (encounterOpen()) return false;
  if (e.key === "Escape") {
    if (modalOpen()) return false;
    if (!busy) openMenu();
    return true;
  }
  if (typing || modalOpen() || dialogueFor || busy) return false;
  if (e.key === "n" || e.key === "N") { openNotebook(); return true; }
  if (e.key === "b" || e.key === "B") { openBoard(); return true; }
  if (e.key === "j" || e.key === "J") { openJournal(); return true; }
  return false;
}
