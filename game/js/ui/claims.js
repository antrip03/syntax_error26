// Claim cards: the badge (green / red / grey / unchecked), the quoted source line, and actions.

import { h } from "./dom.js";
import { nameOf } from "../store.js";

export const STATUS = {
  supported: { label: "Verified", cls: "ok", icon: "✔" },
  unsupported: { label: "Fails recompute", cls: "bad", icon: "✖" },
  abstained: { label: "No working", cls: "grey", icon: "∅" },
  unchecked: { label: "Unchecked", cls: "unk", icon: "?" },
};

export const REASON = {
  ok: "matches the verifier's recompute",
  value_mismatch: "the value written differs from the recompute",
  wrong_final: "the final figure differs from the verified answer",
  duplicate_or_bad_reference: "repeats an earlier step or cites a step that does not exist",
  not_a_checkable_step: "not an S<k>: op(args) = value line, so nothing can be recomputed",
  bad_cite: "no valid source cited",
  vacuous: "says nothing checkable",
  no_attribution: "hearsay without saying who said it",
};

export function badge(status) {
  const s = STATUS[status] || STATUS.unchecked;
  return h("span", { class: `badge ${s.cls}`, title: s.label }, h("i", {}, s.icon), s.label);
}

// opts: { pinned, onPin, onVerify, verifiesLeft, compact, showVillager }
export function claimCard(c, opts = {}) {
  const hearsay = c.hearsay_from || (c.cites || []).some((x) => /^H\d+/.test(x));
  const card = h("div", { class: `claim ${STATUS[c.status]?.cls || "unk"} ${c.highlight ? "highlight" : ""}` },
    h("div", { class: "claim-top" },
      badge(c.status),
      hearsay && h("span", { class: "tag" }, `hearsay · ${nameOf(c.hearsay_from) || "attributed"}`),
      c.highlight && h("span", { class: "tag star", title: "Easy-mode hint: this line looks useful" }, "★ useful"),
      opts.showVillager && c.villager_id && h("span", { class: "who" }, nameOf(c.villager_id)),
    ),
    h("p", { class: "claim-text" }, c.text),
  );
  if (c.quote && c.status !== "unchecked") {
    card.append(h("blockquote", { class: "source" },
      h("span", { class: "src-title" }, `${c.source_title || "Verifier"} `, (c.cites || []).map((x) => h("code", {}, x))),
      h("span", {}, `“${c.quote}”`)));
  } else if (c.status === "unsupported") {
    card.append(h("p", { class: "reason" }, `Checker: ${REASON[c.reason] || "the verifier could not confirm it"}`,
      c.cites?.length ? h("span", {}, " · cited ", c.cites.map((x) => h("code", {}, x))) : null));
  }
  if (c.status === "unsupported" && c.quote) {
    card.append(h("p", { class: "reason" }, `Checker: ${REASON[c.reason] || "the verifier could not confirm it"}`));
  }
  if (!opts.compact) {
    const acts = h("div", { class: "claim-acts" });
    if (c.status === "unchecked" && opts.onVerify) {
      acts.append(h("button", { class: "btn small", disabled: !(opts.verifiesLeft > 0), onclick: () => opts.onVerify(c) },
        `Verify (${opts.verifiesLeft ?? 0} left)`));
    }
    if (c.status === "supported" && opts.onPin) {
      acts.append(opts.pinned
        ? h("span", { class: "pinned" }, "📌 Pinned")
        : h("button", { class: "btn small", onclick: () => opts.onPin(c) }, "📌 Pin to notebook"));
    }
    if (acts.childNodes.length) card.append(acts);
  }
  return card;
}

export function abstainCard() {
  return h("div", { class: "claim grey" },
    h("div", { class: "claim-top" }, badge("abstained")),
    h("p", { class: "claim-text" }, "“I have no working for that.”"),
    h("p", { class: "reason" }, "The desk found nothing in its workings and declined to guess."));
}
