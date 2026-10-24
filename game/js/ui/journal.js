// The journal: one profile page per villager, with their portrait, bio, habits, where they are
// right now, what they've told you, and your own remarks (saved per case in this browser).

import { portraitURL } from "../art.js";
import { profileFor } from "../profiles.js";
import { store, on } from "../store.js";
import { h, openModal } from "./dom.js";
import { claimCard } from "./claims.js";

let getScene = () => null;
export const setJournalScene = (fn) => { getScene = fn; };

const g = () => store.game;
const remarkKey = () => `vaudville-remarks-${g()?.caseId}`;

function loadRemarks() {
  const game = g();
  if (game.remarks) return game.remarks;
  try { game.remarks = JSON.parse(localStorage.getItem(remarkKey()) || "{}"); } catch { game.remarks = {}; }
  return game.remarks;
}
function saveRemark(id, text) {
  const r = loadRemarks();
  r[id] = text;
  try { localStorage.setItem(remarkKey(), JSON.stringify(r)); } catch { /* private mode: keep in memory */ }
}

let refresh = null;
on("villager-moved", () => refresh?.(false));

export function openJournal(focusId) {
  const game = g();
  if (!game) return;
  let sel = focusId || game.villagers[0]?.id;
  const body = h("div", { class: "journal" });

  const render = (full = true) => {
    const scene = getScene();
    const loc = (id) => scene?.locationOf(id) ?? "";
    const list = h("nav", { class: "j-list", "aria-label": "Villagers" }, game.villagers.map((v) =>
      h("button", { class: `j-tab ${v.id === sel ? "on" : ""}`, "aria-current": v.id === sel, onclick: () => { sel = v.id; render(); } },
        h("img", { class: "portrait", src: portraitURL(v.id, v.role?.toLowerCase(), 40), width: 40, height: 40, alt: "" }),
        h("span", {}, h("b", {}, v.name), h("small", {}, loc(v.id))))));
    if (!full && body.querySelector(".j-list")) {
      // a villager moved: refresh the list and the location line, keep the remarks box as it is
      body.querySelector(".j-list").replaceWith(list);
      const l = body.querySelector(".j-loc b");
      if (l) l.textContent = loc(sel);
      return;
    }
    const v = game.villagers.find((x) => x.id === sel);
    const p = profileFor(v);
    const claims = (game.chats[v.id] || []).flatMap((t) => t.claims.map((id) => game.claims[id]));
    const n = (s) => claims.filter((c) => c.status === s).length;
    const abst = (game.chats[v.id] || []).filter((t) => t.abstained && !t.claims.length).length;
    const pins = game.pinned.map((id) => game.claims[id]).filter((c) => c.villager_id === v.id);
    const remarks = loadRemarks();
    const ta = h("textarea", { class: "j-remarks", rows: 5, placeholder: `Your thoughts on ${v.name}… (only you see these)`,
      oninput: (e) => saveRemark(v.id, e.target.value) });
    ta.value = remarks[v.id] || "";
    body.replaceChildren(
      h("h2", {}, "Journal"),
      h("div", { class: "j-wrap" },
        list,
        h("article", { class: "j-page" },
          h("header", { class: "j-head" },
            h("img", { class: "portrait big", src: portraitURL(v.id, v.role?.toLowerCase(), 112), width: 112, height: 112, alt: "" }),
            h("div", {},
              h("h3", {}, v.name),
              h("p", { class: "j-role" }, `${v.label || v.role} · age ${p.age}`),
              h("p", { class: "j-loc" }, "📍 Now ", h("b", {}, loc(v.id))),
              h("div", { class: "j-tally" },
                h("span", { class: "ok" }, `✔ ${n("supported")} supported`), h("span", { class: "bad" }, `✖ ${n("unsupported")} unsupported`),
                h("span", { class: "grey" }, `∅ ${abst} abstained`)))),
          h("dl", { class: "j-facts" },
            h("dt", {}, "Personality"), h("dd", {}, v.persona || "—"),
            h("dt", {}, "Habits"), h("dd", {}, h("ul", {}, p.habits.map((x) => h("li", {}, x)))),
            h("dt", {}, "About"), h("dd", {}, p.bio)),
          p.flavour && h("p", { class: "j-note" }, "Age, habits and bio are village colour, not evidence. Only claims checked against records count."),
          h("h4", {}, "Your remarks"),
          ta,
          h("h4", {}, `Pinned from ${v.name} (${pins.length})`),
          pins.length ? h("div", { class: "cards" }, pins.map((c) => claimCard(c, { compact: true }))) : h("p", { class: "muted" }, "Nothing pinned from them yet."))));
  };
  render();
  refresh = render;
  const timer = setInterval(() => render(false), 3000);
  openModal(body, { wide: true, cls: "journal-modal", onClose: () => { refresh = null; clearInterval(timer); } });
}
