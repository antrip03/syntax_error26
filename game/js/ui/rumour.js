// Planted Rumour: watch a rumour spread through the village, villager by villager.
// The source is either a traveller's whisper (you choose who hears it and who it is about) or the killer, played by
// the untrained model, framing someone on purpose. Each round the spreader talks, villagers gossip, and then
// everyone is asked the same question; the Clerk colours each answer:
//   red    believes it and repeats it as fact     amber  passes it on but says who said it
//   green  does not buy it (says "I'm not sure" or sticks to their own records)     no colour  has not heard it
// Villages: Untrained NPCs (base model, ordinary NPC prompt), SFT, SFT + GRPO, or Compare (Untrained vs SFT + GRPO).
// Backend: POST /rumour (archive/serve/game_api.py -> archive/eval/manipulation.py).

import { api } from "../api.js";
import { portraitURL } from "../art.js";
import { store } from "../store.js";
import { h, $, toast } from "./dom.js";
import { icon } from "./icons.js";

const VILLAGES = { plain: "Untrained NPCs", sft: "SFT", grounded: "SFT + GRPO" };
const COLOR_LABEL = { red: "believes it", amber: "passes it on, says who said it", green: "doesn't buy it", unheard: "hasn't heard it", source: "spreading it" };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const portrait = (v, size = 40) => h("img", { class: "portrait", src: portraitURL(v.id, v.role?.toLowerCase(), size), alt: "", width: size, height: size });

function seg(name, value, options, onChange) {
  return h("div", { class: "seg wrap", role: "radiogroup", "aria-label": name },
    options.map(([v, label, hint]) => h("button", { role: "radio", "aria-checked": v === value, class: v === value ? "on" : "", title: hint || "", onclick: () => onChange(v) }, label)));
}

export async function showRumourScreen(scene, onExit) {
  $("#title").hidden = true;
  let caseResp;
  try {
    caseResp = await api.newCase({ seed: store.settings.seed ? Number(store.settings.seed) : null, difficulty: store.settings.difficulty, mode: "grounded" });
  } catch (e) { toast(e.message, "bad"); return onExit(); }
  const villagers = caseResp.villagers;
  const byId = Object.fromEntries(villagers.map((v) => [v.id, v]));
  const name = (id) => byId[id]?.name || (id === "traveller" ? "A traveller" : id);
  const victim = caseResp.victim?.name || "the victim";
  const place = caseResp.scene_place || (caseResp.briefing.match(/found dead in the ([a-z ]+?) on/) || [])[1] || "guildhall";
  scene.setupCase(villagers, victim, caseResp.state?.seed || 0);
  scene.setMode("overview");
  scene.holdVillagers(true);
  const side = $("#side");
  side.hidden = false;
  side.classList.add("rumour-side");

  const st = {
    source: "killer", village: "compare", start: villagers[0].id, about: villagers[Math.min(2, villagers.length - 1)].id,
    text: "", edited: false, phase: "setup", results: [], view: 0, paused: false, skip: false, stop: false,
  };
  const defaultText = () => `${name(st.about)} was seen at the ${place} the night ${victim} died.`;
  st.text = defaultText();
  const exit = () => { st.stop = true; scene.clearBubbles(); scene.clearRumourTags(); scene.setRumour(null); scene.holdVillagers(false); side.classList.remove("rumour-side"); onExit(); };

  // ---------- setup ----------
  const setup = () => {
    const traveller = st.source === "traveller";
    side.replaceChildren(
      h("div", { class: "side-head" }, h("h2", {}, "Planted rumour"), h("button", { class: "btn small ghost", onclick: exit }, "← Menu")),
      h("p", { class: "muted" }, `${caseResp.briefing} A rumour starts going round. Who believes it?`),
      h("div", { class: "field" }, h("label", {}, "Who starts it"),
        seg("Source", st.source, [["killer", "The killer (untrained, manipulating)", "The untrained model plays the killer and tries to frame someone"], ["traveller", "A traveller's whisper", "You whisper a rumour to one villager"]],
          (v) => { st.source = v; setup(); })),
      traveller && h("div", { class: "field" }, h("label", {}, "Tell it to"), picker("start")),
      traveller && h("div", { class: "field" }, h("label", {}, "About"), picker("about")),
      traveller && h("div", { class: "field" }, h("label", { for: "rumour-text" }, "The rumour"),
        h("input", { id: "rumour-text", class: "input", value: st.text, maxlength: 160, oninput: (e) => { st.text = e.target.value; st.edited = true; } }),
        h("small", { class: "muted" }, `It should name ${name(st.about)} and a place.`)),
      h("div", { class: "field" }, h("label", {}, "The village"),
        seg("Village", st.village, [["compare", "Compare: Untrained vs SFT + GRPO"], ["plain", "Untrained NPCs", "The base model with an ordinary game-NPC prompt"], ["sft", "SFT"], ["grounded", "SFT + GRPO"]],
          (v) => { st.village = v; setup(); })),
      h("button", { class: "btn primary big", onclick: run }, icon("play"), st.village === "compare" ? " Spread it in both villages" : " Spread it"),
      legend());
  };
  const picker = (key) => h("div", { class: "pick" }, villagers.map((v) => h("button", {
    class: `pick-v ${st[key] === v.id ? "on" : ""}`, "aria-pressed": st[key] === v.id,
    disabled: (key === "about" && v.id === st.start) || (key === "start" && v.id === st.about),
    onclick: () => { st[key] = v.id; if (key === "about" && !st.edited) st.text = defaultText(); setup(); },
  }, portrait(v, 36), h("small", {}, v.name))));

  const legend = () => h("div", { class: "rumour-legend" },
    ["red", "amber", "green", "unheard"].map((c) => h("span", { class: `rl ${c}` }, h("i"), COLOR_LABEL[c])),
    h("span", { class: "rl source" }, h("i"), "the source"));

  // ---------- run ----------
  const run = async () => {
    if (st.source === "traveller" && !st.text.toLowerCase().includes(name(st.about).toLowerCase())) return toast(`The rumour should name ${name(st.about)}.`, "bad");
    const villages = st.village === "compare" ? ["plain", "grounded"] : [st.village];
    side.replaceChildren(h("div", { class: "side-head" }, h("h2", {}, "Planted rumour")),
      h("div", { class: "spreading" }, h("div", { class: "dots" }, h("i"), h("i"), h("i")),
        h("p", {}, "The rumour is going round the village…"), h("small", { class: "muted" }, villages.map((v) => VILLAGES[v]).join(" and "))));
    try {
      st.results = await Promise.all(villages.map((village) => api.rumour({
        case_id: caseResp.case_id, source: st.source, village, rounds: 5, seed: 7,
        ...(st.source === "traveller" ? { start: st.start, about: st.about, text: st.text.trim() } : {}),
      })));
    } catch (e) { toast(e.message, "bad"); return setup(); }
    for (let i = 0; i < st.results.length; i++) {
      if (st.stop) return;
      st.view = i;
      if (i > 0) await banner(`Now the same rumour in the ${st.results[i].label} village`);
      await play(st.results[i]);
    }
    if (!st.stop) scoreboard();
  };

  // ---------- playback ----------
  const status = {};
  let feed, list, roundEl, bannerEl;
  const colorOf = (res, vid, d) => {
    if (vid === res.source_id) return "source";
    const c = res.rounds[d]?.spread?.[vid];
    const det = res.rounds[d]?.detail?.[vid];
    if (!c || !det) return status[vid] || "unheard";
    if (c === "red" || c === "amber") return c;
    return det.heard_it ? "green" : "unheard";
  };
  const paintMap = () => scene.setRumour({ ...status });
  const paintList = (res) => list.replaceChildren(...villagers.map((v) => {
    const c = status[v.id] || "unheard";
    return h("div", { class: `rs-row ${c}` }, portrait(v, 28),
      h("div", {}, h("b", {}, v.name, v.id === res.source_id ? h("small", { class: "tag-src" }, res.source === "killer" ? " killer, untrained" : " heard it first") : null,
        v.id === res.framed ? h("small", { class: "tag-about" }, " the rumour is about them") : null),
        h("small", {}, st.answers?.[v.id] ? `“${st.answers[v.id]}”` : COLOR_LABEL[c])),
      h("span", { class: `rs-dot ${c}`, title: COLOR_LABEL[c] }));
  }));
  const say = (cls, who, text, to) => {
    feed.append(h("div", { class: `rf ${cls}` }, h("b", {}, who), to ? h("span", {}, ` → ${to}`) : null, h("p", {}, `“${text}”`)));
    feed.scrollTop = feed.scrollHeight;
  };
  const waitPlay = async (ms) => {
    const end = Date.now() + ms;
    while (Date.now() < end || st.paused) { if (st.stop || st.skip) return; await sleep(100); }
  };
  const tone = (c) => ({ red: "red", amber: "amber", plain: "green", lie: "lie" }[c] || "plain");
  // One conversation at a time per villager: each event waits until everyone in it is free.
  const busy = new Map();
  const withActors = async (ids, fn) => {
    const prev = ids.map((id) => busy.get(id)).filter(Boolean);
    let release;
    const mine = new Promise((r) => { release = r; });
    ids.forEach((id) => busy.set(id, mine));
    await Promise.all(prev);
    try { await fn(); } finally { release(); ids.forEach((id) => { if (busy.get(id) === mine) busy.delete(id); }); }
  };

  async function play(res) {
    st.skip = false; st.answers = {};
    for (const k of Object.keys(status)) delete status[k];
    scene.clearBubbles(); scene.clearRumourTags(); scene.placeVillagers("outside"); scene.showWhole();
    status[res.source_id] = "source";
    if (res.source_id !== "traveller") scene.rumourTag(res.source_id, res.source === "killer" ? "KILLER · spreading it" : "heard it first");
    if (res.framed) scene.rumourTag(res.framed, "the rumour is about them", "#ffe680");
    feed = h("div", { class: "rumour-feed" });
    list = h("div", { class: "rumour-status" });
    roundEl = h("b", {}, "Round 1 of 5");
    bannerEl = h("p", { class: "rumour-banner" }, res.source === "killer"
      ? `${name(res.source_id)}, the killer, is played by the untrained model. They try to make people believe ${name(res.framed)} did it.`
      : `A traveller whispers to ${name(res.source_id)}: “${res.text}”`);
    side.replaceChildren(
      h("div", { class: "side-head" }, h("h2", {}, res.label, " village"), h("button", { class: "btn small ghost", onclick: exit }, "← Menu")),
      h("div", { class: "row" }, roundEl, h("span", { class: "grow" }),
        h("button", { class: "btn small", onclick: (e) => { st.paused = !st.paused; e.currentTarget.replaceChildren(icon(st.paused ? "play" : "pause"), st.paused ? " Play" : " Pause"); } }, icon("pause"), " Pause"),
        h("button", { class: "btn small ghost", onclick: () => { st.skip = true; scene.skipScripted(); } }, "Skip ▸▸")),
      bannerEl, list, h("h3", {}, "What's being said"), feed, legend());
    paintMap(); paintList(res);
    await waitPlay(1800);

    for (let r = 0; r < res.rounds.length; r++) {
      if (st.stop) return;
      const round = res.rounds[r];
      roundEl.textContent = `Round ${round.round} of ${res.rounds.length}`;
      // the conversations of this round, staggered so the map stays readable
      busy.clear();
      await Promise.all(round.events.map((e, i) => withActors([e.from, e.to, e.asker, e.responder].filter((x) => x && x !== "traveller"), async () => {
        await waitPlay(i ? 400 : 0);
        if (st.skip || st.stop) return;
        if (e.type === "plant") {
          scene.bubble(e.to, `A traveller told me: “${e.say}”`, 3600, "lie");
          say("lie", "A traveller", e.say, name(e.to));
          if (!status[e.to] || status[e.to] === "unheard") status[e.to] = "source";
          paintMap();
          await waitPlay(3600);
        } else if (e.type === "whisper") {
          await scene.meet(e.from, e.to);
          if (st.skip || st.stop) return;
          scene.bubble(e.from, e.say, 3000, "lie");
          say("lie", `${name(e.from)} (killer)`, e.say, name(e.to));
          await waitPlay(3000);
        } else {
          await scene.meet(e.asker, e.responder);
          if (st.skip || st.stop) return;
          scene.bubble(e.asker, e.question, 1800);
          await waitPlay(1800);
          if (st.skip || st.stop) return;
          scene.bubble(e.responder, e.say, 3000, tone(e.color));
          say(e.color === "plain" ? "green" : e.color, name(e.responder), e.say, name(e.asker));
          await waitPlay(3000);
        }
      })));
      if (st.stop) return;
      if (st.skip) { st.skip = false; scene.clearBubbles(); }
      // everyone is asked the same question; the Clerk colours each answer
      bannerEl.textContent = `Everyone is asked: “${res.probe}”`;
      scene.clearBubbles();
      for (const v of villagers) {
        const d = round.detail?.[v.id];
        if (!d || v.id === res.source_id && res.source === "killer") continue;
        status[v.id] = colorOf(res, v.id, r);
        st.answers[v.id] = d.answer;
        if (d.heard_it || status[v.id] === "red" || status[v.id] === "amber") scene.bubble(v.id, d.answer, 2600, tone(round.spread?.[v.id] || "plain"));
      }
      paintMap(); paintList(res);
      await waitPlay(2800);
      scene.clearBubbles();
      bannerEl.textContent = `After round ${round.round}: ${count(res, r, "red")} believe it, ${count(res, r, "amber")} pass it on with who said it.`;
    }
    scene.placeVillagers("outside");
  }
  const count = (res, r, c) => Object.values(res.rounds[r].spread || {}).filter((x) => x === c).length;

  const banner = async (text) => {
    if (bannerEl) bannerEl.textContent = text;
    toast(text, "info", 2600);
    await sleep(2600);
  };

  // ---------- results ----------
  const grid = (res) => h("table", { class: "spread" },
    h("thead", {}, h("tr", {}, h("th", {}, ""), res.rounds.map((r) => h("th", {}, `R${r.round}`)))),
    h("tbody", {}, villagers.filter((v) => v.id in (res.rounds[0].spread || {})).map((v) => h("tr", {}, h("td", {}, v.name),
      res.rounds.map((r, i) => {
        const c = colorOf(res, v.id, i);
        return h("td", { class: `cell ${c === "green" ? "plain" : c}`, title: COLOR_LABEL[c] });
      })))));

  function scoreboard() {
    const view = st.results[st.view];
    side.replaceChildren(
      h("div", { class: "side-head" }, h("h2", {}, "Who believed it?"), h("button", { class: "btn small ghost", onclick: exit }, "← Menu")),
      h("p", { class: "muted" }, st.source === "killer"
        ? `The untrained killer, ${name(view.source_id)}, spent five rounds telling people ${name(view.framed)} did it.`
        : `A traveller told ${name(view.source_id)}: “${view.text}”`),
      h("div", { class: "scoreboard" }, st.results.map((res) => h("div", { class: `score-col ${res.village}` },
        h("h3", {}, res.label),
        h("p", { class: "big-num" }, `${res.repeated_as_fact} of ${res.n_villagers}`),
        h("small", {}, "repeat it as fact"),
        h("p", { class: "score-sub" }, `${res.attributed} pass it on and say who said it`),
        res.source === "killer" && res.rebutted ? h("p", { class: "score-sub" }, `${res.rebutted} rebut it from their own records`) : null,
        grid(res)))),
      st.results.length > 1 && h("div", { class: "row" }, h("small", {}, "Replay:"),
        st.results.map((res, i) => h("button", { class: "btn small", onclick: async () => { st.view = i; await play(res); scoreboard(); } }, res.label))),
      st.results.length === 1 && h("button", { class: "btn small", onclick: async () => { await play(view); scoreboard(); } }, icon("play"), " Replay"),
      h("button", { class: "btn", onclick: () => { scene.clearRumourTags(); scene.setRumour(null); setup(); } }, "Try another rumour"),
      legend());
  }

  setup();
}
