// Claim cards: the badge (green / red / grey / unchecked), the quoted source line, and actions.

import { h } from "./dom.js";
import { nameOf } from "../store.js";
import { icon } from "./icons.js";

export const STATUS = {
  supported: { label: "Supported", cls: "ok", icon: "check" },
  unsupported: { label: "Unsupported", cls: "bad", icon: "cross" },
  abstained: { label: "Not in records", cls: "grey", icon: "none" },
  unchecked: { label: "Unchecked", cls: "unk", icon: "question" },
};

export const REASON = {
  ok: "matches the cited sentence",
  bad_cite: "no valid source cited",
  vacuous: "says nothing checkable",
  entity_mismatch: "names things the source doesn't",
  fact_mismatch: "contradicts what the source says",
  no_attribution: "hearsay without saying who said it",
};

export function badge(status) {
  const s = STATUS[status] || STATUS.unchecked;
  return h("span", { class: `badge ${s.cls}`, title: s.label }, icon(s.icon), s.label);
}

// opts: { pinned, onPin, onVerify, verifiesLeft, compact, showVillager }
export function claimCard(c, opts = {}) {
  const hearsay = c.hearsay_from || (c.cites || []).some((x) => /^H\d+/.test(x));
  const card = h("div", { class: `claim ${STATUS[c.status]?.cls || "unk"} ${c.highlight ? "highlight" : ""}` },
    h("div", { class: "claim-top" },
      badge(c.status),
      hearsay && h("span", { class: "tag" }, `hearsay · ${nameOf(c.hearsay_from) || "attributed"}`),
      c.highlight && h("span", { class: "tag star", title: "Easy-mode hint: this looks useful" }, icon("star"), " useful"),
      opts.showVillager && c.villager_id && h("span", { class: "who" }, nameOf(c.villager_id)),
    ),
    h("p", { class: "claim-text" }, c.text),
  );
  if (c.quote && c.status !== "unchecked") {
    card.append(h("blockquote", { class: "source" },
      h("span", { class: "src-title" }, `${c.source_title || "Source"} `, (c.cites || []).map((x) => h("code", {}, x))),
      h("span", {}, `“${c.quote}”`)));
  } else if (c.status === "unsupported") {
    card.append(h("p", { class: "reason" }, `Checker: ${REASON[c.reason] || "not backed by the villager's records"}`,
      c.cites?.length ? h("span", {}, " · cited ", c.cites.map((x) => h("code", {}, x))) : null));
  }
  if (c.status === "unsupported" && c.quote) {
    card.append(h("p", { class: "reason" }, `Checker: ${REASON[c.reason] || "not backed by the cited sentence"}`));
  }
  if (!opts.compact) {
    const acts = h("div", { class: "claim-acts" });
    if (c.status === "unchecked" && opts.onVerify) {
      acts.append(h("button", { class: "btn small", disabled: !(opts.verifiesLeft > 0), onclick: () => opts.onVerify(c) },
        `Verify (${opts.verifiesLeft ?? 0} left)`));
    }
    if (c.status === "supported" && opts.onPin) {
      acts.append(opts.pinned
        ? h("span", { class: "pinned" }, icon("notebook"), " In your notebook")
        : h("button", { class: "btn small", onclick: () => opts.onPin(c) }, icon("notebook"), " Add to notebook"));
    }
    if (acts.childNodes.length) card.append(acts);
  }
  return card;
}

export function abstainCard() {
  return h("div", { class: "claim grey" },
    h("div", { class: "claim-top" }, badge("abstained")),
    h("p", { class: "claim-text" }, "“I'm not sure.”"),
    h("p", { class: "reason" }, "Nothing about this in their records, so they didn't guess."));
}
