// DOM helpers: element builder, a modal screen stack (top screen owns focus; Esc pops), toasts.

import { emit } from "../store.js";

export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

export const $ = (sel, root = document) => root.querySelector(sel);

// ---------- screen stack ----------

const stack = [];
let blockers = 0; // other UI (dialogue drawer, scripted sequences) that also block the world

function syncBlock() { emit("ui-block", stack.length > 0 || blockers > 0); }
export function block(on) { blockers = Math.max(0, blockers + (on ? 1 : -1)); syncBlock(); }

export function openModal(content, { wide = false, full = false, dismissable = true, onClose, cls = "" } = {}) {
  const root = $("#modal-root");
  const card = h("div", { class: `modal ${wide ? "wide" : ""} ${full ? "full" : ""} ${cls}`, role: "dialog", "aria-modal": "true" });
  const backdrop = h("div", { class: "backdrop" }, card);
  const entry = { backdrop, card, dismissable, onClose };
  if (dismissable) {
    card.append(h("button", { class: "modal-x", "aria-label": "Close", onclick: () => closeModal(entry) }, "×"));
    backdrop.addEventListener("mousedown", (e) => { if (e.target === backdrop) closeModal(entry); });
  }
  card.append(content);
  root.append(backdrop);
  stack.push(entry);
  syncBlock();
  requestAnimationFrame(() => {
    const f = card.querySelector("[autofocus]") || card.querySelector("button:not(.modal-x), input, select, textarea, [tabindex]");
    f?.focus();
  });
  entry.close = () => closeModal(entry);
  entry.replace = (node) => { [...card.childNodes].forEach((n) => { if (!n.classList?.contains("modal-x")) n.remove(); }); card.append(node); };
  return entry;
}

export function closeModal(entry = stack[stack.length - 1]) {
  const i = stack.indexOf(entry);
  if (i < 0) return;
  stack.splice(i, 1);
  entry.backdrop.remove();
  syncBlock();
  entry.onClose?.();
}

export function closeAllModals() { while (stack.length) closeModal(); }
export const modalOpen = () => stack.length > 0;
export function topModalDismissable() { return stack.length && stack[stack.length - 1].dismissable; }

// ---------- toasts ----------

export function toast(text, tone = "info", ms = 3200) {
  const t = h("div", { class: `toast ${tone}`, role: "status" }, text);
  $("#toasts").append(t);
  setTimeout(() => t.classList.add("out"), ms);
  setTimeout(() => t.remove(), ms + 400);
}

export function confirmModal(title, body, okLabel = "OK") {
  return new Promise((resolve) => {
    let decided = false;
    const m = openModal(h("div", {},
      h("h2", {}, title), h("p", {}, body),
      h("div", { class: "row end" },
        h("button", { class: "btn ghost", onclick: () => { decided = true; m.close(); resolve(false); } }, "Cancel"),
        h("button", { class: "btn primary", autofocus: true, onclick: () => { decided = true; m.close(); resolve(true); } }, okLabel))),
    { onClose: () => { if (!decided) resolve(false); } });
  });
}
