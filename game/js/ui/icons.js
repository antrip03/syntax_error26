// Line icons in the HUD style (24x24, 2px stroke, round caps), used everywhere instead of emoji or symbol
// glyphs, which render differently (or as empty boxes) across systems. icon(name) -> inline <span>.

import { h } from "./dom.js";

export const ICONS = {
  journal: '<path d="M5 3h11a3 3 0 0 1 3 3v15H8a3 3 0 0 1-3-3z"/><path d="M5 18a3 3 0 0 1 3-3h11"/><path d="M10 7h5M10 10h5"/>',
  notebook: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/><path d="M5 7H3M5 12H3M5 17H3"/>',
  board: '<rect x="3" y="4" width="18" height="14" rx="1.5"/><circle cx="8" cy="9" r="1.6"/><circle cx="16" cy="13" r="1.6"/><path d="M8 9l8 4"/><path d="M9 18l-1.5 3M15 18l1.5 3"/>',
  accuse: '<path d="M14 4l6 6-3 3-6-6z"/><path d="M11 7l-7 7 3 3 7-7"/><path d="M3 21h9"/>',
  sleep: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  cross: '<path d="M6 6l12 12M18 6L6 18"/>',
  none: '<circle cx="12" cy="12" r="8"/><path d="M6.5 17.5l11-11"/>',
  question: '<path d="M9 9a3 3 0 1 1 4.5 2.6c-1 .6-1.5 1.2-1.5 2.4"/><path d="M12 18h.01"/>',
  pin: '<path d="M9 3h6l-1 6 3 3H7l3-3z"/><path d="M12 12v9"/>',
  scroll: '<path d="M7 4h11a2 2 0 0 1 2 2v1h-4"/><path d="M7 4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7"/><path d="M8 9h6M8 13h6M8 17h4"/>',
  star: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
  bolt: '<path d="M13 2L5 13h6l-1 9 8-11h-6z"/>',
  scales: '<path d="M12 4v16M8 20h8"/><path d="M5 7h14"/><path d="M5 7l-3 6a3 3 0 0 0 6 0zM19 7l-3 6a3 3 0 0 0 6 0z"/>',
  heart: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
  place: '<path d="M12 21s-6-5.6-6-11a6 6 0 0 1 12 0c0 5.4-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/>',
  thought: '<path d="M7 16a5 5 0 0 1 .5-10 6 6 0 0 1 11 2.5A3.8 3.8 0 0 1 17 16z"/><circle cx="7" cy="19.5" r="1.2"/><circle cx="4" cy="21.5" r=".6"/>',
  flag: '<path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/>',
  download: '<path d="M12 4v11"/><path d="M7 10l5 5 5-5"/><path d="M5 20h14"/>',
  sound: '<path d="M4 10v4h4l5 4V6L8 10z"/><path d="M16.5 9a4 4 0 0 1 0 6M19 6.5a7.5 7.5 0 0 1 0 11"/>',
  mute: '<path d="M4 10v4h4l5 4V6L8 10z"/><path d="M17 10l4 4M21 10l-4 4"/>',
  pause: '<path d="M9 5v14M15 5v14"/>',
  play: '<path d="M7 5l12 7-12 7z"/>',
  sparkle: '<path d="M12 3v6M12 15v6M3 12h6M15 12h6"/>',
};

export function icon(name, cls = "") {
  const el = h("span", { class: `ico-i ${cls}`, "aria-hidden": "true" });
  el.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
  return el;
}
