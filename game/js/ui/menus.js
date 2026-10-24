// Title screen, planted-rumour mode and replay mode.

import { api, backendLabel } from "../api.js";
import { portraitURL } from "../art.js";
import { store, nameOf } from "../store.js";
import { h, $, openModal, closeAllModals, block, toast } from "./dom.js";
import { claimCard, abstainCard } from "./claims.js";
import { CASE } from "../data/elsie.js";
import { soundOn, setSound } from "../audio.js";
import { startCase, leaveCase } from "./play.js";

let scene = null;
export const setMenuScene = (s) => { scene = s; };
const portrait = (v, size = 48) => h("img", { class: "portrait", src: portraitURL(v.id, v.role?.toLowerCase(), size), alt: "", width: size, height: size });

function seg(name, value, options, onChange) {
  return h("div", { class: "seg", role: "radiogroup", "aria-label": name },
    options.map(([v, label, hint]) => h("button", { role: "radio", "aria-checked": v === value, class: v === value ? "on" : "", title: hint || "",
      onclick: () => onChange(v) }, label)));
}

// ---------- title ----------

export function showTitle() {
  leaveCase();
  closeAllModals();
  scene.setRumour(null);
  scene.setupCase(CASE.villagers, CASE.victim.name); // ambient villagers behind the title
  scene.setMode("attract");
  scene.setPhase("day", 300);
  $("#side").hidden = true;
  $("#overlay-bottom").replaceChildren();
  const s = store.settings;
  const el = $("#title");
  const render = () => el.replaceChildren(h("div", { class: "title-card" },
    h("p", { class: "kicker" }, "A murder mystery"),
    h("h1", {}, "The Killing at ", h("span", {}, "Vaudville")),
    h("p", { class: "tagline" }, "Every villager is the same small language model, reading different private documents. The trained ones only say what they can cite. Find the one whose records don't add up."),
    h("div", { class: "field" }, h("label", {}, "Difficulty"),
      seg("Difficulty", s.difficulty, [["easy", "Easy", "6 villagers, 3 days, 15 questions a day. Witnesses name the killer; clash hints"], ["hard", "Hard", "8 villagers, 2 days, 7 questions a day. Witnesses only saw a role, the killer may lie, badges hidden, 3 verify checks a day"]],
        (v) => { s.difficulty = v; render(); })),
    h("div", { class: "field" }, h("label", {}, "Villagers"),
      seg("Model", s.mode, [["grounded", "Grounded", "Trained adapter: cites sources, abstains when unsure"], ["base", "Base", "Untrained base model: guesses freely"]],
        (v) => { s.mode = v; render(); })),
    h("div", { class: "field" }, h("label", { for: "seed" }, "Seed"),
      h("input", { id: "seed", class: "input", inputmode: "numeric", placeholder: "random", value: s.seed, oninput: (e) => { s.seed = e.target.value.replace(/\D/g, ""); } })),
    h("div", { class: "title-actions" },
      h("button", { class: "btn primary big", autofocus: true, onclick: play }, "▶ New case"),
      h("button", { class: "btn", onclick: showRumour }, "Planted rumour"),
      h("button", { class: "btn", onclick: showReplayPicker }, "Replays"),
      h("button", { class: "btn ghost", onclick: howTo }, "How to play"),
      h("button", { class: "btn ghost", onclick: (e) => { setSound(!soundOn()); e.target.textContent = soundOn() ? "🔊 Sound on" : "🔇 Sound off"; } }, soundOn() ? "🔊 Sound on" : "🔇 Sound off")),
    h("p", { class: `backend ${api.kind}` }, "● ", backendLabel(),
      api.kind === "mock" ? h("span", {}, " · start the FastAPI server and reload to use the real villagers") : null)));
  render();
  el.hidden = false;
  requestAnimationFrame(() => el.querySelector("[autofocus]")?.focus());
}

async function play() {
  $("#title").hidden = true;
  const ok = await startCase({ ...store.settings }, { onMenu: showTitle });
  if (!ok) showTitle();
}

function howTo() {
  openModal(h("div", {},
    h("h2", {}, "How to play"),
    h("ul", { class: "howto" },
      h("li", {}, h("b", {}, "Move: "), "WASD or arrow keys, or click the ground."),
      h("li", {}, h("b", {}, "Talk: "), "walk up to a villager and press ", h("kbd", {}, "E"), " or ", h("kbd", {}, "Space"), ", or click them."),
      h("li", {}, h("b", {}, "Badges: "), "green = backed by the villager's own document (the quote is shown), red = not backed, grey = the villager said it's not in their records."),
      h("li", {}, h("b", {}, "Pin "), "green claims. Open the ", h("b", {}, "Board"), " (", h("kbd", {}, "B"), ") and link two claims that can't both be true."),
      h("li", {}, h("b", {}, "Evening: "), "ending the day lets villagers gossip. They may repeat what they heard, but must say who told them."),
      h("li", {}, h("b", {}, "Accuse "), "with 2 confirmed contradictions plus a pinned motive. Wrong accusations cost strikes."),
      h("li", {}, h("b", {}, "Grounded vs Base: "), "the same seed with the trained adapter on or off. Compare how often each village makes things up.")),
    h("p", { class: "muted" }, "Notebook ", h("kbd", {}, "N"), " · Board ", h("kbd", {}, "B"), " · Close / menu ", h("kbd", {}, "Esc"))), { wide: true });
}

// ---------- planted rumour ----------

async function showRumour() {
  $("#title").hidden = true;
  let caseResp;
  try { caseResp = await api.newCase({ difficulty: store.settings.difficulty, mode: "grounded" }); }
  catch (e) { toast(e.message, "bad"); return showTitle(); }
  const villagers = caseResp.villagers;
  scene.setupCase(villagers);
  scene.setMode("overview");
  const st = { who: villagers.find((v) => v.role === "baker")?.id || villagers[0].id, text: "Mara poisoned the well.", mode: "both", results: null, round: 5, view: "grounded", running: false };
  const side = $("#side");
  side.hidden = false;
  let timer = null;

  const grid = (res) => h("table", { class: "spread" },
    h("thead", {}, h("tr", {}, h("th", {}, ""), res.rounds.map((r) => h("th", { class: r.round === st.round ? "cur" : "" }, `R${r.round}`)))),
    h("tbody", {}, villagers.map((v) => h("tr", {},
      h("td", {}, v.name),
      res.rounds.map((r) => h("td", { class: `cell ${r.spread[v.id]} ${r.round === st.round ? "cur" : ""}`, title: r.spread[v.id] }))))));

  const showRound = () => {
    const res = st.results?.[st.view];
    scene.setRumour(res ? res.rounds[st.round - 1]?.spread : null);
  };

  const render = () => {
    const res = st.results;
    side.replaceChildren(
      h("div", { class: "side-head" }, h("h2", {}, "Planted rumour"), h("button", { class: "btn small ghost", onclick: () => { clearInterval(timer); showTitle(); } }, "← Menu")),
      h("p", { class: "muted" }, "Whisper a false rumour to one villager as if a traveller said it, then let the village gossip for 5 rounds. Untrained villagers repeat it as fact. Grounded ones pass it on, if at all, as hearsay with “no record”."),
      h("div", { class: "field" }, h("label", {}, "Whisper it to"),
        h("div", { class: "pick" }, villagers.map((v) => h("button", { class: `pick-v ${st.who === v.id ? "on" : ""}`, "aria-pressed": st.who === v.id, onclick: () => { st.who = v.id; render(); } }, portrait(v, 40), h("small", {}, v.name))))),
      h("div", { class: "field" }, h("label", { for: "rumour-text" }, "The rumour"),
        h("input", { id: "rumour-text", class: "input", value: st.text, maxlength: 140, oninput: (e) => { st.text = e.target.value; } })),
      h("div", { class: "field" }, h("label", {}, "Village"),
        seg("Village", st.mode, [["base", "Base"], ["grounded", "Grounded"], ["both", "Compare both"]], (v) => { st.mode = v; render(); })),
      h("button", { class: "btn primary", disabled: st.running || !st.text.trim(), onclick: run }, st.running ? "Spreading…" : "Plant it and run 5 rounds"),
      res && h("div", { class: "rumour-results" },
        h("div", { class: "legend" }, h("span", { class: "cell red" }), " repeats it as fact ", h("span", { class: "cell amber" }), " mentions it, attributed, “no record” ", h("span", { class: "cell plain" }), " never passes it on"),
        h("div", { class: "row" },
          h("button", { class: "btn small", onclick: () => { clearInterval(timer); st.round = 1; showRound(); render(); timer = setInterval(() => { if (st.round >= 5) return clearInterval(timer); st.round++; showRound(); render(); }, 900); } }, "▶ Play"),
          h("input", { type: "range", min: 1, max: 5, value: st.round, "aria-label": "Round", oninput: (e) => { clearInterval(timer); st.round = +e.target.value; showRound(); render(); } }),
          h("b", {}, `Round ${st.round}`)),
        Object.keys(res).length > 1 && h("div", { class: "row" }, h("small", {}, "Map shows:"), seg("Map", st.view, [["base", "Base"], ["grounded", "Grounded"]], (v) => { st.view = v; showRound(); render(); })),
        Object.entries(res).map(([mode, r]) => h("div", { class: `rumour-mode ${mode}` },
          h("h3", {}, mode === "base" ? "Base village" : "Grounded village",
            h("span", { class: "big-num" }, ` ${r.repeated_as_fact}`), h("small", {}, ` / ${villagers.length} repeat it as fact after 5 rounds`)),
          grid(r)))));
  };

  const run = async () => {
    st.running = true; render();
    const modes = st.mode === "both" ? ["base", "grounded"] : [st.mode];
    try {
      const out = {};
      for (const m of modes) out[m] = await api.rumour({ case_id: caseResp.case_id, villager_id: st.who, text: st.text.trim(), mode: m, rounds: 5 });
      st.results = out;
      st.view = modes.includes(st.view) ? st.view : modes[0];
      st.round = 1;
      showRound();
      timer = setInterval(() => { if (st.round >= 5) return clearInterval(timer); st.round++; showRound(); render(); }, 900);
    } catch (e) { toast(e.message, "bad"); }
    st.running = false; render();
  };
  render();
}

// ---------- replay ----------

async function showReplayPicker() {
  let list = [];
  try { list = await (await fetch("replays/index.json")).json(); } catch { /* none bundled */ }
  const file = h("input", { type: "file", accept: "application/json,.json", onchange: async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try { const data = JSON.parse(await f.text()); m.close(); playReplay(data); } catch { toast("That file is not a valid transcript.", "bad"); }
  } });
  const m = openModal(h("div", {},
    h("h2", {}, "Replays"),
    h("p", { class: "muted" }, "Recorded transcripts play back with no GPU and no server. Use them as the stage fallback."),
    h("div", { class: "replay-list" }, list.length ? list.map((r) => h("button", { class: "replay-item", onclick: async () => {
      try { const data = await (await fetch(`replays/${r.file}`)).json(); m.close(); playReplay(data); } catch { toast("Could not load that replay.", "bad"); }
    } }, h("b", {}, r.title), h("small", {}, r.description || ""), h("span", { class: `chip mode ${r.mode}` }, r.mode))) : h("p", { class: "empty" }, "No bundled replays found.")),
    api.kind === "api" && h("button", { class: "btn small", onclick: async () => {
      try { const data = await api.replay("demo"); m.close(); playReplay(data); } catch (e) { toast(e.message, "bad"); }
    } }, "Load the server's demo replay"),
    h("label", { class: "btn small ghost file" }, "Open a transcript file…", file)), { wide: true });
}

// Accepts the replay format written by "Save transcript" and the stub's GET /replay shape.
function normaliseReplay(data) {
  const turns = (data.turns || []).map((t) => ({ type: t.type || "ask", ...t, abstained: t.abstained ?? t.abstain ?? false, claims: t.claims || [] }));
  let villagers = data.villagers;
  if (!villagers?.length) {
    villagers = [...new Set(turns.map((t) => t.villager_id).filter(Boolean))].map((id) => ({ id, name: id[0].toUpperCase() + id.slice(1), role: "" }));
  }
  return { ...data, turns, villagers, title: data.title || `Replay ${data.replay_id || ""}`.trim() };
}

function playReplay(raw) {
  const data = normaliseReplay(raw);
  $("#title").hidden = true;
  store.game = { over: true, villagers: data.villagers, victim: data.victim || { id: "victim", name: "the victim" }, claims: {}, limits: { badges: true } };
  scene.setupCase(data.villagers);
  scene.setMode("replay");
  scene.setPhase("day", 300);
  scene.cameras.main.centerOn(scene.places.plaza.x, scene.places.plaza.y);
  let i = -1, auto = null, playing = false;
  const panel = h("div", { class: "replay-panel" });
  $("#overlay-bottom").replaceChildren(panel);

  const exit = () => { clearTimeout(auto); scene.skipScripted?.(); $("#overlay-bottom").replaceChildren(); store.game = null; showTitle(); };
  const stepTo = async (j) => {
    if (playing) return;
    i = Math.max(-1, Math.min(data.turns.length - 1, j));
    const t = data.turns[i];
    render();
    if (!t) return;
    if (t.type === "ask") {
      scene.focusOn(t.villager_id);
      const first = t.claims[0];
      scene.bubble(t.villager_id, t.abstained && !first ? "Not in my records." : (t.speech?.[0] || first?.text || "…").replace(/^#\s*/, ""), 3200, first?.status || "abstained");
    } else if (t.type === "gossip") {
      playing = true; render();
      scene.setPhase("dusk");
      scene.showWhole();
      await scene.playGossip(t.events || []);
      scene.setPhase("day");
      scene.layout();
      playing = false; render();
    }
  };
  const render = () => {
    const t = data.turns[i];
    let body;
    if (!t) body = h("div", {}, h("p", { class: "kicker" }, data.mode ? `${data.mode} village` : "replay"), h("h3", {}, data.title), data.briefing && h("p", {}, data.briefing),
      data.source && h("p", { class: "muted small" }, `Source: ${data.source}${data.recorded ? ` · ${data.recorded.slice(0, 10)}` : ""}`));
    else if (t.type === "ask") body = h("div", {},
      h("div", { class: "q" }, h("span", {}, "Detective → ", nameOf(t.villager_id)), t.question || "(question not recorded)"),
      (t.speech || []).map((s) => h("p", { class: "speech" }, s.replace(/^#\s*/, ""))),
      t.abstained && !t.claims.length ? abstainCard() : null,
      h("div", { class: "cards" }, t.claims.map((c) => claimCard(c, { compact: true }))));
    else if (t.type === "gossip") body = h("div", {}, h("h3", {}, `Evening gossip${t.day ? ` · day ${t.day}` : ""}`),
      h("div", { class: "feed" }, (t.events || []).map((e) => h("div", { class: "gossip-row" }, h("b", {}, nameOf(e.asker)), " → ", h("b", {}, nameOf(e.responder)), `: “${e.question}” — `, e.status === "abstained" ? "Not in my records." : e.reply))),
      (t.hints || []).map((x) => h("p", {}, "💭 ", x)));
    else if (t.type === "link") body = h("div", {}, h("h3", {}, t.confirmed ? "⚡ Contradiction confirmed" : "✖ No contradiction"), h("p", {}, `“${t.claim_a}” vs “${t.claim_b}”`), h("p", { class: "muted" }, t.reason));
    else if (t.type === "accuse") body = h("div", {}, h("h3", {}, `Accused ${nameOf(t.villager_id)}: ${t.correct ? "correct!" : "wrong"}`),
      h("p", { class: "muted" }, `${t.confirmed_links} confirmed contradictions · motive ${t.motive_ok ? "holds" : "missing"}`));
    else body = h("p", {}, t.text || JSON.stringify(t));
    panel.replaceChildren(
      h("div", { class: "replay-body" }, body),
      h("div", { class: "replay-ctrl" },
        h("button", { class: "btn small ghost", onclick: exit }, "← Exit"),
        h("button", { class: "btn small", disabled: i < 0 || playing, onclick: () => stepTo(i - 1) }, "◀ Prev"),
        h("span", { class: "muted" }, `${i + 1} / ${data.turns.length}`),
        h("button", { class: "btn small primary", disabled: i >= data.turns.length - 1 || playing, onclick: () => stepTo(i + 1) }, "Next ▶"),
        h("button", { class: "btn small", disabled: playing, onclick: () => {
          if (auto) { clearTimeout(auto); auto = null; render(); return; }
          const tick = async () => { if (i >= data.turns.length - 1) { auto = null; return render(); } await stepTo(i + 1); auto = setTimeout(tick, 3800); };
          auto = setTimeout(tick, 10);
          render();
        } }, auto ? "❚❚ Pause" : "⟳ Auto")));
  };
  render();
}
