// Procedural pixel art for Vaudville. Everything is drawn into canvases at boot and registered as
// Phaser textures, so the game ships with no image files. Style: 16 px tiles, 1 px dark outline,
// warm low-saturation palette, light from the top-left.

export const TILE = 16;
export const CHAR_W = 16, CHAR_H = 22;
export const DIRS = ["down", "left", "right", "up"];
const OUTLINE = "#2b1d14";

export class Pix {
  constructor(w, h) {
    this.w = w; this.h = h;
    this.canvas = document.createElement("canvas");
    this.canvas.width = w; this.canvas.height = h;
    this.ctx = this.canvas.getContext("2d", { willReadFrequently: true });
  }
  px(x, y, c) { if (c) { this.ctx.fillStyle = c; this.ctx.fillRect(x | 0, y | 0, 1, 1); } }
  rect(x, y, w, h, c) { this.ctx.fillStyle = c; this.ctx.fillRect(x | 0, y | 0, w | 0, h | 0); }
  // 1 px outline around every opaque pixel inside [x0, x0+w) x [y0, y0+h).
  outline(x0 = 0, y0 = 0, w = this.w, h = this.h, color = OUTLINE) {
    const img = this.ctx.getImageData(x0, y0, w, h), d = img.data;
    const solid = (x, y) => x >= 0 && y >= 0 && x < w && y < h && d[(y * w + x) * 4 + 3] > 200;
    const pts = [];
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++)
      if (!solid(x, y) && (solid(x - 1, y) || solid(x + 1, y) || solid(x, y - 1) || solid(x, y + 1))) pts.push([x, y]);
    for (const [x, y] of pts) this.px(x0 + x, y0 + y, color);
  }
}

export function rng(seed) {
  let s = seed >>> 0 || 7;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
}
export function hash(str) {
  let h = 2166136261;
  for (const ch of str) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return h >>> 0;
}
export function shade(hex, amt) {
  const n = parseInt(hex.slice(1), 16);
  const f = (v) => Math.max(0, Math.min(255, Math.round(v + amt * 255)));
  return `rgb(${f(n >> 16)},${f((n >> 8) & 255)},${f(n & 255)})`;
}

// ---------- characters ----------

const SKIN = ["#f2c9a0", "#e0ac7e", "#c68c5f", "#9c6b45", "#f5d6b8"];
const HAIR = ["#3b2a20", "#6b4226", "#a8642e", "#d9b25f", "#8a8a8a", "#1f1a17", "#b5482e"];
const CLOTH = ["#6d8f4e", "#4f6d8f", "#8f4f4f", "#8f7a4f", "#5e4f8f", "#4f8f86", "#9a6a3a", "#7a5a7a"];

// Role presets keep the fixture cast recognisable; unknown roles get a stable hashed palette.
const ROLE_LOOK = {
  miller: { cloth: "#c8b48a", hair: "#6b4226", apron: "#f1ead8", hat: "cap" },
  guard: { cloth: "#4f5f7a", hair: "#3b2a20", hat: "helmet", belt: "#2b2b2b" },
  herbalist: { cloth: "#5d8a55", hair: "#a8642e", hat: "hood" },
  baker: { cloth: "#b8695a", hair: "#d9b25f", apron: "#fbf6ea", hat: "chef" },
  blacksmith: { cloth: "#5a4a40", hair: "#1f1a17", apron: "#7a4e2d" },
  priest: { cloth: "#2f2f3a", hair: "#8a8a8a", hat: "skullcap", trim: "#e8d27a" },
  innkeeper: { cloth: "#8f4f6a", hair: "#b5482e", apron: "#f1ead8" },
  // townsfolk outfits, kept distinct from every case-villager look
  watch: { cloth: "#8a2f2f", hat: "cap", belt: "#3a2a1a", trim: "#d8c39a" },
  apprentice: { cloth: "#7a6a52", apron: "#5a4030", hair: "#c87a3a" },
  barmaid: { cloth: "#4f7a6a", apron: "#f6efe0", hair: "#3b2a20" },
  elder: { hair: "#e0ddd6", cloth: "#7a6a8a" },
  vendor: { apron: "#f1ead8" },
  kid: { hat: "cap", cloth: "#5a8ac0" },
  detective: { cloth: "#8a6a45", hair: "#3b2a20", hat: "brim", belt: "#5a3a22", trim: "#d8c39a" },
};

export function lookFor(id, role) {
  const r = rng(hash(id));
  const pick = (a) => a[Math.floor(r() * a.length)];
  const base = { skin: pick(SKIN), hair: pick(HAIR), cloth: pick(CLOTH), eye: "#2b1d14", boots: "#4a3324", belt: "#5a3a22" };
  return { ...base, ...(ROLE_LOOK[role] || {}) };
}

function drawChar(P, ox, oy, L, dir, frame) {
  const R = (x, y, w, h, c) => P.rect(ox + x, oy + y, w, h, c);
  const clothDark = shade(L.cloth, -0.12);
  const step = frame === 0 ? 0 : frame === 1 ? 1 : -1;
  const side = dir === "left" || dir === "right";

  // legs + boots
  if (!side) {
    R(5, 15, 2, step === 1 ? 2 : 3, shade(L.cloth, -0.25)); R(9, 15, 2, step === -1 ? 2 : 3, shade(L.cloth, -0.25));
    R(5, step === 1 ? 17 : 18, 2, 1, L.boots); R(9, step === -1 ? 17 : 18, 2, 1, L.boots);
  } else {
    const a = step === 0 ? 0 : step;
    R(6 + a, 15, 2, 3, shade(L.cloth, -0.25)); R(8 - a, 15, 2, 3, shade(L.cloth, -0.3));
    R(6 + a, 18, 2, 1, L.boots); R(8 - a, 18, 2, 1, L.boots);
  }
  // body
  R(4, 9, 8, 6, L.cloth); R(4, 9, 1, 6, clothDark); R(11, 9, 1, 6, clothDark);
  if (L.apron && dir !== "up") R(side ? 6 : 5, 10, side ? 4 : 6, 5, L.apron);
  R(4, 13, 8, 1, L.belt || shade(L.cloth, -0.3));
  if (L.trim) R(7, 9, 2, 4, L.trim);
  // arms
  if (!side) {
    R(3, 9 + (step === 1 ? 1 : 0), 1, 4, clothDark); R(3, 13 + (step === 1 ? 1 : 0), 1, 1, L.skin);
    R(12, 9 + (step === -1 ? 1 : 0), 1, 4, clothDark); R(12, 13 + (step === -1 ? 1 : 0), 1, 1, L.skin);
  } else {
    const ax = dir === "left" ? 7 : 8;
    R(ax + step, 10, 1, 3, clothDark); R(ax + step, 13, 1, 1, L.skin);
  }
  // head
  R(4, 2, 8, 7, L.skin); P.px(ox + 4, oy + 8, null);
  P.ctx.clearRect(ox + 4, oy + 8, 1, 1); P.ctx.clearRect(ox + 11, oy + 8, 1, 1);
  // hair
  if (dir === "up") R(4, 2, 8, 6, L.hair);
  else {
    R(4, 2, 8, 2, L.hair);
    if (dir === "down") { R(4, 4, 1, 2, L.hair); R(11, 4, 1, 2, L.hair); }
    if (dir === "left") R(9, 4, 3, 3, L.hair);
    if (dir === "right") R(4, 4, 3, 3, L.hair);
  }
  // face
  if (dir === "down") { R(6, 5, 1, 1, L.eye); R(9, 5, 1, 1, L.eye); R(5, 7, 1, 1, shade(L.skin, -0.06)); R(10, 7, 1, 1, shade(L.skin, -0.06)); }
  if (dir === "left") R(5, 5, 1, 1, L.eye);
  if (dir === "right") R(10, 5, 1, 1, L.eye);
  // hats
  const hat = L.hat;
  if (hat === "brim") { R(5, 0, 6, 2, "#5a3a22"); R(3, 2, 10, 1, "#4a2f1c"); R(5, 1, 6, 1, "#7a5232"); }
  if (hat === "helmet") { R(4, 1, 8, 3, "#9aa3ad"); R(5, 1, 2, 1, "#d5dce3"); R(4, 4, 8, 1, "#6f7883"); }
  if (hat === "cap") { R(4, 1, 8, 2, "#efe6d0"); R(dir === "left" ? 2 : 4, 3, dir === "down" || dir === "up" ? 8 : 10, 1, "#d8cdb2"); }
  if (hat === "chef") { R(5, 0, 6, 3, "#ffffff"); R(4, 3, 8, 1, "#e8e2d4"); }
  if (hat === "skullcap") R(5, 1, 6, 2, "#1d1d24");
  if (hat === "hood") { R(3, 2, 10, 2, shade(L.cloth, -0.1)); R(3, 4, 1, 5, shade(L.cloth, -0.1)); R(12, 4, 1, 5, shade(L.cloth, -0.1)); if (dir === "up") R(4, 2, 8, 7, shade(L.cloth, -0.1)); }
}

// Registers texture `key` with 12 frames named `${dir}-${frame}` and walk animations.
export function makeCharacter(scene, key, look) {
  const P = new Pix(CHAR_W * 3, CHAR_H * 4);
  DIRS.forEach((dir, row) => {
    for (let f = 0; f < 3; f++) {
      const ox = f * CHAR_W, oy = row * CHAR_H;
      drawChar(P, ox, oy, look, dir, f);
      P.outline(ox, oy, CHAR_W, CHAR_H);
      // soft shadow under the feet, drawn after the outline so it stays outline-free
      P.ctx.globalCompositeOperation = "destination-over";
      P.rect(ox + 4, oy + 19, 8, 2, "rgba(30,20,10,0.28)");
      P.rect(ox + 3, oy + 19, 10, 1, "rgba(30,20,10,0.18)");
      P.ctx.globalCompositeOperation = "source-over";
    }
  });
  if (scene.textures.exists(key)) scene.textures.remove(key);
  const tex = scene.textures.addCanvas(key, P.canvas);
  DIRS.forEach((dir, row) => {
    for (let f = 0; f < 3; f++) tex.add(`${dir}-${f}`, 0, f * CHAR_W, row * CHAR_H, CHAR_W, CHAR_H);
  });
  DIRS.forEach((dir) => {
    const ak = `${key}-walk-${dir}`;
    if (scene.anims.exists(ak)) scene.anims.remove(ak);
    scene.anims.create({ key: ak, frameRate: 8, repeat: -1,
      frames: [1, 0, 2, 0].map((f) => ({ key, frame: `${dir}-${f}` })) });
  });
  return key;
}

// A full-body sprite frame, scaled up crisp, as a data URL (the interview screen).
const bodyCache = new Map();
export function fullBodyURL(id, role, dir = "down", scale = 10) {
  const k = `${id}|${role}|${dir}|${scale}`;
  if (bodyCache.has(k)) return bodyCache.get(k);
  const P = new Pix(CHAR_W, CHAR_H);
  drawChar(P, 0, 0, lookFor(id, role), dir, 0);
  P.outline();
  const out = document.createElement("canvas");
  out.width = CHAR_W * scale; out.height = (CHAR_H - 3) * scale;
  const c = out.getContext("2d");
  c.imageSmoothingEnabled = false;
  c.drawImage(P.canvas, 0, 0, CHAR_W, CHAR_H - 3, 0, 0, out.width, out.height);
  const url = out.toDataURL();
  bodyCache.set(k, url);
  return url;
}

// A portrait (head and shoulders, scaled up) as a data URL for the DOM UI.
const portraitCache = new Map();
export function portraitURL(id, role, size = 64) {
  const k = `${id}|${role}|${size}`;
  if (portraitCache.has(k)) return portraitCache.get(k);
  const look = lookFor(id, role);
  const P = new Pix(CHAR_W, CHAR_H);
  drawChar(P, 0, 0, look, "down", 0);
  P.outline();
  const out = document.createElement("canvas");
  out.width = out.height = size;
  const c = out.getContext("2d");
  c.imageSmoothingEnabled = false;
  const s = size / 14;
  c.drawImage(P.canvas, 1, 0, 14, 14, 0, size * 0.08, 14 * s, 14 * s);
  const url = out.toDataURL();
  portraitCache.set(k, url);
  return url;
}

// ---------- buildings ----------
// 3/4 top-down: a hipped roof (lit left face, staggered shingles on the front slope, shaded right face)
// whose eaves shade the wall, timber-framed plaster or coursed stone on a stone plinth, shuttered windows
// with flower boxes, a planked door with a lantern, and a landmark detail per place.

const PLACE_STYLE = {
  mill: { roof: "#8a5a3a", wall: "#e2d0ac", trim: "#6b4a30", shutter: "#6a7a4a", frame: "timber" },
  bakery: { roof: "#b5523e", wall: "#f3e2c6", trim: "#7a4030", shutter: "#c0503c", frame: "timber", chimney: true, boxes: true },
  chapel: { roof: "#5a6478", wall: "#dad5c9", trim: "#4a4a58", frame: "stone", tall: true },
  guildhall: { roof: "#4a5a48", wall: "#bfb7a6", trim: "#5a4a38", frame: "stone", dormer: "clock" },
  inn: { roof: "#7a3e4a", wall: "#ecdcbc", trim: "#5a3424", shutter: "#3f6a5a", frame: "timber", chimney: true, boxes: true, dormer: "window" },
  smithy: { roof: "#4a4440", wall: "#a39484", trim: "#3a3028", frame: "stone", chimney: true },
  house: { roof: "#9a6a3a", wall: "#eddcbc", trim: "#6a4a2a", shutter: "#4f6d8f", frame: "timber", chimney: true, boxes: true },
  house2: { roof: "#5a7a8a", wall: "#e6dcc6", trim: "#4a5a64", shutter: "#8f4f4f", frame: "timber", chimney: true, boxes: true },
  cottage: { roof: "#6a8a4a", wall: "#efe0c0", trim: "#5a4a30", shutter: "#a8784a", frame: "timber", chimney: true, boxes: true },
};
const FLOWERS = ["#e86a8a", "#f2d45a", "#b07ad8", "#ffffff", "#f08a4a"];

export function makeBuilding(scene, key, kind, wTiles, hTiles) {
  const st = PLACE_STYLE[kind] || PLACE_STYLE.house;
  const W = wTiles * TILE, H = hTiles * TILE;
  const extraTop = kind === "chapel" ? 28 : st.chimney ? 7 : 0; // room above the roof for a spire or chimney
  const P = new Pix(W + 2, H + extraTop + 2);
  const ox = 1, oy = 1 + extraTop;
  const roofH = Math.round(H * 0.55), wallY = oy + roofH, wallH = H - roofH, base = oy + H;
  const r = rng(hash(key));
  const dw = 8, dh = Math.min(12, wallH - 4), dx = ox + Math.floor(W / 2 - dw / 2), dy = base - dh;

  // ----- wall -----
  if (st.frame === "stone") {
    P.rect(ox + 2, wallY, W - 4, wallH, shade(st.wall, -0.2)); // mortar
    for (let y = wallY, row = 0; y < base - 3; y += 4, row++) {
      for (let x = ox + 2 - (row % 2) * 4; x < ox + W - 2;) {
        const w = 6 + Math.floor(r() * 4), x0 = Math.max(x, ox + 2), x1 = Math.min(x + w - 1, ox + W - 2);
        if (x1 > x0) {
          const c = (r() - 0.5) * 0.1;
          P.rect(x0, y, x1 - x0, 3, shade(st.wall, c));
          P.rect(x0, y, x1 - x0, 1, shade(st.wall, c + 0.07));
        }
        x += w;
      }
    }
  } else {
    P.rect(ox + 2, wallY, W - 4, wallH, st.wall);
    for (let i = 0; i < W * wallH * 0.05; i++) P.px(ox + 2 + r() * (W - 4), wallY + r() * wallH, shade(st.wall, -0.05));
  }
  // windows first decide where the timber posts go
  const winW = 7, winH = st.tall ? 12 : 7, winY = wallY + (st.tall ? 7 : 6);
  const wins = (W >= 96 ? [0.17, 0.33, 0.67, 0.83] : [0.22, 0.78]).map((f) => ox + Math.round(W * f) - 3).filter((wx) => Math.abs(wx + 3 - (dx + dw / 2)) >= 10);
  if (st.frame === "timber") {
    const beam = shade(st.trim, 0.04);
    const stops = [ox + 2, ...[...wins.map((x) => x + 3), dx + dw / 2].sort((a, b) => a - b), ox + W - 2];
    for (let k = 0; k + 1 < stops.length; k++) {
      const px = Math.round((stops[k] + stops[k + 1]) / 2) - 1;
      if (k > 0 && k < stops.length - 2) P.rect(px, wallY, 2, wallH - 3, beam);
    }
    P.rect(ox + 2, wallY, 2, wallH - 3, beam); P.rect(ox + W - 4, wallY, 2, wallH - 3, beam); // corner posts
    P.rect(ox + 2, wallY + 3, W - 4, 2, beam); // top plate under the eaves
    P.rect(ox + 2, base - 5, W - 4, 2, beam); // sill beam
  }
  P.rect(ox + 2, wallY, 1, wallH, "rgba(255,255,255,0.18)"); // lit left edge
  P.rect(ox + W - 5, wallY, 3, wallH, "rgba(40,20,10,0.16)"); // shaded right edge
  // stone plinth
  P.rect(ox + 2, base - 3, W - 4, 3, "#8e877a");
  P.rect(ox + 2, base - 3, W - 4, 1, "#aaa395");
  for (let x = ox + 4 + Math.floor(r() * 3); x < ox + W - 3; x += 5 + Math.floor(r() * 3)) P.rect(x, base - 2, 1, 2, "#6e685c");

  // ----- roof: hipped, three faces -----
  const ridge = Math.min(Math.round(W * 0.16), 16);
  for (let t = 0; t < roofH; t++) {
    const y = oy + t, f = t / roofH, inset = Math.round(ridge * (1 - f));
    const band = Math.floor(t / 4), bt = t % 4;
    for (let x = 0; x < W; x++) {
      let adj = 0.07 - 0.14 * f;
      if (x < inset) adj += 0.08; else if (x >= W - inset) adj -= 0.15;
      if (bt === 3) adj -= 0.08;
      else if ((x + (band % 2) * 3) % 6 === 0) adj -= 0.06;
      else if (bt === 0) adj += 0.04;
      adj += ((band * 7 + Math.floor((x + (band % 2) * 3) / 6) * 13) % 5 - 2) * 0.012; // tile-to-tile variation
      if (inset > 0 && (x === inset || x === inset - 1)) adj = 0.2;
      if (inset > 0 && (x === W - inset || x === W - inset - 1)) adj = -0.28;
      if (t < 2 && x >= ridge && x < W - ridge) adj = t === 0 ? 0.2 : 0.12 - (x % 4 === 0 ? 0.08 : 0);
      if (t >= roofH - 2) adj = t === roofH - 1 ? -0.34 : -0.22; // fascia board
      P.px(ox + x, y, shade(st.roof, adj));
    }
  }
  P.rect(ox + 2, wallY, W - 4, 3, "rgba(40,20,10,0.28)"); // eave shadow on the wall

  if (st.chimney && kind !== "smithy") {
    const cx = ox + Math.round(W * 0.7), top = oy - 6, ch = Math.round(roofH * 0.4) + 6;
    P.rect(cx, top, 7, ch, "#9a5a44");
    for (let y = top + 2; y < top + ch; y += 3) { P.rect(cx, y, 7, 1, "#7a4434"); P.px(cx + ((y / 3) % 2 ? 2 : 5), y + 1, "#7a4434"); }
    P.rect(cx, top, 2, ch, "rgba(255,255,255,0.15)");
    P.rect(cx - 1, top, 9, 2, "#5a4a44"); P.rect(cx + 1, top, 5, 1, "#2a2020");
  }
  if (st.dormer) {
    const cx = ox + Math.round(W / 2), y0 = oy + Math.round(roofH * 0.3);
    for (let i = 0; i < 6; i++) P.rect(cx - 2 - i, y0 + i, 5 + i * 2, 1, shade(st.roof, 0.1 - i * 0.02)); // little gable
    P.rect(cx - 6, y0 + 6, 13, 9, st.frame === "stone" ? st.wall : st.wall);
    P.rect(cx - 6, y0 + 6, 13, 1, "rgba(40,20,10,0.3)");
    if (st.dormer === "clock") {
      for (let a = 0; a < 40; a++) P.px(cx + Math.cos(a / 6.4) * 4, y0 + 10 + Math.sin(a / 6.4) * 4, st.trim);
      P.rect(cx - 3, y0 + 7, 7, 7, "#f6efe0"); P.rect(cx - 2, y0 + 6, 5, 9, "#f6efe0"); P.rect(cx - 4, y0 + 8, 9, 5, "#f6efe0");
      P.rect(cx, y0 + 8, 1, 3, "#2a2420"); P.rect(cx, y0 + 10, 3, 1, "#2a2420");
    } else {
      P.rect(cx - 3, y0 + 8, 7, 6, st.trim); P.rect(cx - 2, y0 + 9, 5, 4, "#f3d98a"); P.rect(cx, y0 + 9, 1, 4, st.trim); P.px(cx - 2, y0 + 9, "#fff6d6");
    }
  }

  // ----- windows -----
  for (const wx of wins) {
    if (st.shutter) for (const sx of [wx - 4, wx + winW + 1]) {
      P.rect(sx, winY - 1, 3, winH + 2, st.shutter);
      P.rect(sx + 1, winY, 1, winH, shade(st.shutter, -0.15));
      P.rect(sx, winY - 1, 3, 1, shade(st.shutter, 0.12));
    }
    P.rect(wx - 1, winY - 1, winW + 2, winH + 2, st.trim);
    if (st.tall) { // stained glass under a pointed arch
      P.rect(wx, winY, winW, winH, "#3a5a8a");
      for (let y = 0; y < winH; y++) for (let x = 0; x < winW; x++) if ((x + y) % 3 === 0) P.px(wx + x, winY + y, ["#c0443a", "#e8c860", "#5a8ac0"][(x + y) % 9 / 3 | 0]);
      P.px(wx, winY, st.wall); P.px(wx + winW - 1, winY, st.wall); P.rect(wx + 3, winY - 2, 1, 1, st.trim);
      P.rect(wx + 3, winY, 1, winH, st.trim);
    } else {
      P.rect(wx, winY, winW, winH, "#f3d98a"); P.rect(wx, winY, winW, 2, "#fbeab5"); P.rect(wx, winY + winH - 1, winW, 1, "#dcb45e");
      P.px(wx + 1, winY + 1, "#fffbea"); P.px(wx + 2, winY + 2, "#fffbea");
      P.rect(wx + 3, winY, 1, winH, st.trim); P.rect(wx, winY + 3, winW, 1, st.trim);
    }
    P.rect(wx - 2, winY + winH + 1, winW + 4, 1, shade(st.trim, 0.25)); // sill
    if (st.boxes) {
      P.rect(wx - 1, winY + winH + 2, winW + 2, 2, "#7a5232");
      for (let k = 0; k < winW + 2; k++) P.px(wx - 1 + k, winY + winH + 1, k % 2 ? "#4f8a3c" : FLOWERS[Math.floor(r() * 5)]);
    }
  }

  // ----- door -----
  P.rect(dx - 1, dy - 2, dw + 2, dh + 2, st.trim);
  P.px(dx - 1, dy - 2, st.frame === "stone" ? shade(st.wall, -0.2) : st.wall); P.px(dx + dw, dy - 2, st.frame === "stone" ? shade(st.wall, -0.2) : st.wall); // rounded arch
  P.rect(dx, dy - 1, dw, dh + 1, "#6a4428");
  P.rect(dx + 2, dy - 1, 1, dh + 1, "#4e3018"); P.rect(dx + 5, dy - 1, 1, dh + 1, "#4e3018");
  P.rect(dx, dy - 1, dw, 1, "#7e5434");
  P.rect(dx, dy + 2, 3, 1, "#2a2420"); P.rect(dx, dy + dh - 3, 3, 1, "#2a2420"); // hinges
  P.px(dx + dw - 2, dy + Math.floor(dh / 2), "#e8c860");
  P.rect(dx - 2, base - 1, dw + 4, 1, "#b4ad9f"); // step
  if (st.frame === "timber") { P.rect(dx + dw + 2, dy, 3, 5, "#3a3028"); P.rect(dx + dw + 3, dy + 1, 1, 3, "#ffd870"); } // lantern

  // ----- landmarks -----
  if (kind === "mill") { // windmill sails, lattice on one side of each spar
    const cx = ox + W - 10, cy = oy + roofH - 1;
    for (let a = 0; a < 4; a++) {
      const ang = Math.PI / 4 + (a * Math.PI) / 2, ux = Math.cos(ang), uy = Math.sin(ang), nx = -uy, ny = ux;
      for (let s = 3; s <= 14; s++) for (let w = 1; w <= 3; w++) P.px(cx + ux * s + nx * w, cy + uy * s + ny * w, (s % 3 === 0 || w === 3) ? "#a89878" : "#f1e8d2");
      for (let s = 0; s <= 15; s++) P.px(cx + ux * s, cy + uy * s, "#5a3a22");
    }
    P.rect(cx - 1, cy - 1, 3, 3, "#3a2a1a");
    P.rect(ox + 6, base - 9, 6, 5, "#e8dcc0"); P.rect(ox + 7, base - 10, 4, 1, "#e8dcc0"); P.rect(ox + 7, base - 7, 4, 1, "#c8b898"); // flour sack
  }
  if (kind === "bakery") { // scalloped awning and a bread sign
    for (let x = ox + 2; x < ox + W - 2; x++) {
      const stripe = Math.floor((x - ox) / 4) % 2 ? "#f6efe0" : "#c0503c";
      P.rect(x, wallY + 3, 1, (x - ox) % 4 === 1 || (x - ox) % 4 === 2 ? 5 : 4, stripe);
    }
    P.rect(ox + 4, base - 6, 8, 3, "#d9a05a"); P.rect(ox + 5, base - 7, 6, 1, "#e8b870"); P.px(ox + 7, base - 5, "#b8803e"); P.px(ox + 9, base - 5, "#b8803e");
  }
  if (kind === "chapel") { // bell tower with a spire, rose window over the door
    const tw = 16, tx = ox + Math.floor(W / 2 - tw / 2), top = oy - extraTop + 12, bottom = oy + Math.round(roofH * 0.55);
    P.rect(tx, top, tw, bottom - top, shade(st.wall, -0.03));
    for (let y = top + 2; y < bottom; y += 4) P.rect(tx, y, tw, 1, shade(st.wall, -0.14));
    P.rect(tx + tw - 4, top, 4, bottom - top, "rgba(40,20,10,0.15)");
    for (let i = 0; i < 12; i++) { const half = Math.round(1 + (i * (tw / 2 + 1)) / 12); P.rect(tx + tw / 2 - half, top - 12 + i, half * 2, 1, shade(st.roof, i < 6 ? 0.06 : -0.02)); }
    P.rect(tx + 5, top + 3, 6, 8, "#2a2a36"); P.rect(tx + 6, top + 5, 4, 4, "#e8c860"); P.rect(tx + 7, top + 9, 2, 1, "#c8a840"); // belfry and bell
    P.rect(tx + 7, oy - extraTop, 2, 6, "#e8c860"); P.rect(tx + 5, oy - extraTop + 2, 6, 2, "#e8c860"); // cross
    const rx = ox + Math.round(W / 2), ry = wallY + 9;
    for (let y = -4; y <= 4; y++) for (let x = -4; x <= 4; x++) {
      const d2 = x * x + y * y;
      if (d2 <= 20) P.px(rx + x, ry + y, d2 > 13 ? st.trim : (x === 0 || y === 0) ? st.trim : ["#c0443a", "#5a8ac0", "#e8c860", "#6aa060"][((x > 0) + (y > 0) * 2)]);
    }
  }
  if (kind === "guildhall") { // banners, pillars by the door, the open side door
    for (const f of [0.12, 0.88]) {
      const bx = ox + Math.round(W * f) - 3;
      P.rect(bx, wallY + 4, 6, 11, "#8a2a2a"); P.rect(bx, wallY + 4, 6, 1, "#c8a840"); P.rect(bx + 2, wallY + 7, 2, 3, "#e8c860");
      P.px(bx, wallY + 15, "#8a2a2a"); P.px(bx + 5, wallY + 15, "#8a2a2a"); P.rect(bx + 1, wallY + 15, 4, 1, "#6a1a1a");
    }
    for (const px of [dx - 5, dx + dw + 3]) { P.rect(px, dy - 4, 3, dh + 3, "#e6dfd0"); P.rect(px, dy - 4, 1, dh + 3, "#fffaf0"); P.rect(px - 1, dy - 5, 5, 1, "#cfc6b4"); }
    P.rect(ox + 3, wallY + 4, 3, wallH - 7, shade(st.wall, -0.15));
    P.rect(ox + 3, wallY + 4, 1, wallH - 7, "#1a1410");
  }
  if (kind === "smithy") { // tall stack with sparks, glowing forge window, anvil, horseshoe sign
    const cx = ox + W - 15, top = oy - 6;
    P.rect(cx, top, 9, Math.round(roofH * 0.5) + 6, "#5a5048");
    for (let y = top + 2; y < top + roofH * 0.5 + 6; y += 3) P.rect(cx, y, 9, 1, "#4a4038");
    P.rect(cx - 1, top, 11, 2, "#3a3028"); P.rect(cx + 2, top, 5, 1, "#ff9a3a"); P.px(cx + 3, top - 1, "#ffd870"); P.px(cx + 6, top - 2, "#ff9a3a");
    P.rect(ox + W - 18, wallY + 6, 10, 7, "#2a1a14"); P.rect(ox + W - 17, wallY + 9, 8, 4, "#e8622a"); P.rect(ox + W - 15, wallY + 10, 4, 2, "#ffd870");
    P.rect(ox + 5, base - 7, 9, 3, "#3a3a3a"); P.rect(ox + 5, base - 7, 9, 1, "#6a6a6a"); P.rect(ox + 7, base - 4, 5, 2, "#2a2a2a");
    for (let a = 0; a < 20; a++) { const ang = Math.PI * (0.15 + (a / 20) * 1.7); P.px(ox + 20 + Math.cos(ang) * 3, wallY + 9 - Math.sin(ang) * 3, "#9a9aa0"); }
  }
  if (kind === "inn") { // hanging sign on a bracket
    P.rect(ox + W - 18, wallY + 4, 14, 1, "#3a3028");
    P.rect(ox + W - 17, wallY + 6, 12, 8, "#8a5a32"); P.rect(ox + W - 17, wallY + 6, 12, 1, "#a8784a");
    P.rect(ox + W - 14, wallY + 8, 5, 4, "#e8c860"); P.rect(ox + W - 9, wallY + 9, 1, 2, "#e8c860"); P.px(ox + W - 13, wallY + 8, "#fff6c8");
    P.px(ox + W - 15, wallY + 5, "#3a3028"); P.px(ox + W - 7, wallY + 5, "#3a3028");
  }

  P.outline();
  if (scene.textures.exists(key)) scene.textures.remove(key);
  scene.textures.addCanvas(key, P.canvas);
  return { key, extraTop };
}

// ---------- ground ----------
// Painted straight into an RGBA buffer: dithered grass from three octaves of value noise, dirt roads with
// ragged grassy edges, wheel ruts and pebbles, a cobbled plaza with a stone rosette round the well, and
// soft shadows under the buildings.

const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => v / 16 - 0.47);
const RGB = new Map();
const rgbOf = (c) => {
  if (!RGB.has(c)) { const n = parseInt(c.slice(1), 16); RGB.set(c, [n >> 16, (n >> 8) & 255, n & 255]); }
  return RGB.get(c);
};

function valueNoise(r, W, H, cell) {
  const gw = Math.ceil(W / cell) + 2, gh = Math.ceil(H / cell) + 2;
  const g = Float32Array.from({ length: gw * gh }, () => r());
  const s = (t) => t * t * (3 - 2 * t);
  return (x, y) => {
    const fx = Math.max(0, x) / cell, fy = Math.max(0, y) / cell, ix = fx | 0, iy = fy | 0, tx = s(fx - ix), ty = s(fy - iy);
    const a = g[iy * gw + ix], b = g[iy * gw + ix + 1], c = g[(iy + 1) * gw + ix], d = g[(iy + 1) * gw + ix + 1];
    return a + (b - a) * tx + (c - a) * ty + (a - b - c + d) * tx * ty;
  };
}

export function makeGround(scene, key, map) {
  const { cols, rows, roads, plaza, river, bridge, gardens, buildings = [], well } = map;
  const W = cols * TILE, H = rows * TILE;
  const P = new Pix(W, H);
  const r = rng(99);
  const img = P.ctx.createImageData(W, H), d = img.data;
  const put = (x, y, c) => {
    x |= 0; y |= 0;
    if (x < 0 || y < 0 || x >= W || y >= H) return;
    const [R, G, B] = rgbOf(c), i = (y * W + x) * 4;
    d[i] = R; d[i + 1] = G; d[i + 2] = B; d[i + 3] = 255;
  };
  const fill = (x, y, w, h, c) => { for (let j = y | 0; j < y + h; j++) for (let i = x | 0; i < x + w; i++) put(i, j, c); };
  const dither = (x, y) => BAYER[(y & 3) * 4 + (x & 3)];
  const big = valueNoise(r, W, H, 56), mid = valueNoise(r, W, H, 18), fine = valueNoise(r, W, H, 5), jagN = valueNoise(r, W, H, 3);

  // grass: five greens chosen by layered noise, ordered-dithered at the boundaries
  const GRASS = ["#68a046", "#74ac4e", "#80b857", "#8cc260", "#98ca6a"];
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const v = big(x, y) * 0.6 + mid(x, y) * 0.3 + fine(x, y) * 0.1 + dither(x, y) * 0.16;
    put(x, y, GRASS[Math.max(0, Math.min(4, Math.floor((v - 0.12) * 6.2)))]);
  }
  const tuft = (x, y) => {
    put(x, y, "#58893a"); put(x - 1, y - 1, "#58893a"); put(x + 1, y - 1, "#58893a");
    put(x, y - 2, "#6c9c46"); put(x - 2, y - 2, "#a8d676"); put(x + 2, y - 2, "#a8d676");
  };
  for (let i = 0; i < 1100; i++) tuft(r() * W, r() * H);
  for (let i = 0; i < 160; i++) { // clover patches
    const x = r() * W, y = r() * H;
    for (let k = 0; k < 5; k++) put(x + r() * 6, y + r() * 4, k % 2 ? "#5e9640" : "#a2d070");
  }
  for (let i = 0; i < 280; i++) { const x = r() * W, y = r() * H; put(x, y, r() < 0.6 ? "#f6f2e4" : "#f2d45a"); put(x, y + 1, "#58893a"); }

  // river: sandy banks, deeper water in the middle, ripples and a little foam
  const ry = river.y * TILE, rh = river.h * TILE;
  for (let x = 0; x < W; x++) {
    const wob = Math.round((jagN(x, 2) - 0.5) * 3);
    fill(x, ry - 4 + wob, 1, 1, "#6c8f44"); fill(x, ry - 3 + wob, 1, 3 - wob, "#d4bd84");
    fill(x, ry + rh, 1, 3 + wob, "#d4bd84"); fill(x, ry + rh + 3 + wob, 1, 1, "#6c8f44");
  }
  for (let y = ry; y < ry + rh; y++) for (let x = 0; x < W; x++) {
    const depth = 1 - Math.abs((2 * (y - ry)) / rh - 1) + dither(x, y) * 0.25 + (mid(x, y + 300) - 0.5) * 0.2;
    put(x, y, depth > 0.62 ? "#3a7bb2" : depth > 0.28 ? "#4889bf" : "#5d9fce");
  }
  for (let i = 0; i < 300; i++) { const x = r() * W, y = ry + 3 + r() * (rh - 6); fill(x, y, 3 + r() * 5, 1, r() < 0.6 ? "#8cc4e8" : "#2f6c9e"); }
  for (let x = 0; x < W; x++) { if (r() < 0.45) put(x, ry, "#cfe6f2"); if (r() < 0.45) put(x, ry + rh - 1, "#cfe6f2"); }

  // roads: a mask (the plaza counts as road so lanes run into it without a grassy seam)
  const mask = new Uint8Array(W * H);
  const [px0, py0, pw, ph] = plaza.map((v) => v * TILE);
  const area = (x, y, w, h) => { for (let j = y; j < y + h; j++) for (let i = x; i < x + w; i++) if (i >= 0 && j >= 0 && i < W && j < H) mask[j * W + i] = 1; };
  for (const [x, y, w, h] of roads) area(x * TILE, y * TILE, w * TILE, h * TILE);
  area(px0, py0, pw, ph);
  const isRoad = (x, y) => x >= 0 && y >= 0 && x < W && y < H && mask[y * W + x] === 1;
  const inPlaza = (x, y) => x >= px0 && x < px0 + pw && y >= py0 && y < py0 + ph;
  const edgeDist = (x, y) => {
    for (let k = 1; k <= 4; k++) if (!isRoad(x - k, y) || !isRoad(x + k, y) || !isRoad(x, y - k) || !isRoad(x, y + k)) return k;
    return 5;
  };
  const DIRT = ["#bc9660", "#c7a36c", "#d1b07a"];
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    if (!mask[y * W + x] || inPlaza(x, y)) continue;
    const e = edgeDist(x, y), jag = 1 + Math.floor(jagN(x, y) * 2.4);
    if (e < jag) continue; // grass bites into the edge
    if (e === jag) { put(x, y, "#9a7846"); continue; }
    if (e === jag + 1) { put(x, y, "#b08a56"); continue; }
    const v = mid(x, y) * 0.45 + fine(x, y) * 0.55 + dither(x, y) * 0.22;
    put(x, y, DIRT[Math.max(0, Math.min(2, Math.floor(v * 3)))]);
  }
  for (const [x, y, w, h] of roads) { // wheel ruts along the longer side
    const horiz = w >= h, len = (horiz ? w : h) * TILE, across = (horiz ? h : w) * TILE;
    if (len < 6 * TILE) continue;
    for (const f of [0.33, 0.67]) for (let s = 0; s < len; s++) {
      const X = horiz ? x * TILE + s : x * TILE + Math.round(across * f), Y = horiz ? y * TILE + Math.round(across * f) : y * TILE + s;
      if (!isRoad(X, Y) || inPlaza(X, Y) || edgeDist(X, Y) < 4 || r() < 0.12) continue;
      put(X, Y, "#a6824e");
      put(horiz ? X : X + 1, horiz ? Y + 1 : Y, "#d6b886");
    }
  }
  for (let i = 0; i < 900; i++) { // pebbles
    const x = (r() * W) | 0, y = (r() * H) | 0;
    if (!isRoad(x, y) || inPlaza(x, y) || edgeDist(x, y) < 3) continue;
    put(x, y, "#8f8a80"); put(x + 1, y, "#8f8a80"); put(x, y - 1, "#cfc9bb");
  }
  for (let i = 0; i < 1600; i++) { // grass spilling over the road edges
    const x = (r() * W) | 0, y = (r() * H) | 0;
    if (isRoad(x, y) && !inPlaza(x, y) && edgeDist(x, y) <= 2) tuft(x, y);
  }

  // plaza: hand-laid cobbles in staggered courses, a rosette round the well, a kerb
  const STONE = ["#b7ad9a", "#c3b9a6", "#aba18f", "#cdc3b0"];
  fill(px0, py0, pw, ph, "#857b6b");
  const cobble = (x, y, w, h, c) => {
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
      const X = x + i, Y = y + j;
      if (!inPlaza(X, Y) || ((i === 0 || i === w - 1) && (j === 0 || j === h - 1))) continue;
      let adj = 0;
      if (j === 0 || i === 0) adj = 0.07; else if (j === h - 1 || i === w - 1) adj = -0.08;
      put(X, Y, adj ? shadeHex(c, adj) : c);
    }
  };
  for (let y = py0 + 1, row = 0; y < py0 + ph; y += 5, row++) {
    for (let x = px0 + 1 - (row % 2) * 3; x < px0 + pw;) {
      const w = 4 + Math.floor(r() * 4);
      cobble(x, y, w, 4, STONE[Math.floor(r() * 4)]);
      x += w + 1;
    }
  }
  if (well) {
    const cx = well[0] * TILE + 8, cy = well[1] * TILE + 10, R = 46;
    const RING = ["#d8cbb0", "#c8b896"], INNER = ["#cfc2a8", "#c2b49a", "#dacdb6"];
    for (let y = cy - R; y <= cy + R; y++) for (let x = cx - R; x <= cx + R; x++) {
      const dx = x - cx, dy = y - cy, dist = Math.hypot(dx, dy);
      if (dist > R || !inPlaza(x, y)) continue;
      const ang = (Math.atan2(dy, dx) + Math.PI) / (2 * Math.PI);
      if (dist > R - 1.2 || (dist > R - 8 && dist < R - 6.8)) { put(x, y, "#6f6656"); continue; }
      if (dist > R - 8) { // outer band of long radial stones
        const s = ang * 56, seg = Math.floor(s);
        if (s - seg < 0.12) { put(x, y, "#6f6656"); continue; }
        put(x, y, shadeHex(RING[seg % 2], dist > R - 3 ? -0.05 : s - seg < 0.3 ? 0.05 : 0));
        continue;
      }
      if (dist < 5) { put(x, y, "#8e8472"); continue; }
      const ring = Math.floor(dist / 5), segs = Math.max(6, Math.round((2 * Math.PI * dist) / 6)), s = ang * segs + ring * 0.5, seg = Math.floor(s);
      if (dist % 5 < 1 || s - seg < 0.15) { put(x, y, "#7c7262"); continue; }
      put(x, y, shadeHex(INNER[(seg + ring) % 3], dist % 5 < 2 ? 0.05 : 0));
    }
  }
  for (let x = px0; x < px0 + pw; x++) { // kerb, broken where a road runs in
    if (!isRoad(x, py0 - 1)) { put(x, py0, "#6f6656"); put(x, py0 + 1, "#ddd4c2"); }
    if (!isRoad(x, py0 + ph)) { put(x, py0 + ph - 1, "#6f6656"); put(x, py0 + ph - 2, "#a59b89"); }
  }
  for (let y = py0; y < py0 + ph; y++) {
    if (!isRoad(px0 - 1, y)) { put(px0, y, "#6f6656"); put(px0 + 1, y, "#ddd4c2"); }
    if (!isRoad(px0 + pw, y)) { put(px0 + pw - 1, y, "#6f6656"); put(px0 + pw - 2, y, "#a59b89"); }
  }

  // bridge planks with rails
  const [bx, bw] = bridge;
  fill(bx * TILE, ry - 4, bw * TILE, rh + 8, "#8a6038");
  for (let y = ry - 4; y < ry + rh + 4; y += 4) { fill(bx * TILE, y, bw * TILE, 1, "#6a4626"); fill(bx * TILE + 2, y + 1, bw * TILE - 4, 1, "#9e7046"); }
  for (const x of [bx * TILE, (bx + bw) * TILE - 3]) { fill(x, ry - 6, 3, rh + 12, "#5a3a20"); fill(x + 1, ry - 6, 1, rh + 12, "#7a5434"); }

  // flower gardens: tilled rows with flowers and leaves
  for (const [gx, gy, gw, gh] of gardens) {
    const X = gx * TILE, Y = gy * TILE, w = gw * TILE, h = gh * TILE;
    fill(X, Y, w, h, "#6a4a30");
    for (let y = Y + 1; y < Y + h; y += 3) fill(X + 1, y, w - 2, 1, "#7e5a3a");
    fill(X, Y, w, 1, "#4e3420"); fill(X, Y, 1, h, "#4e3420");
    for (let y = Y + 3; y < Y + h - 2; y += 4) for (let x = X + 3 + ((y / 4) % 2) * 2; x < X + w - 2; x += 4) {
      const c = FLOWERS[Math.floor(r() * 5)];
      put(x, y + 1, "#4f8a3c"); put(x - 1, y + 1, "#5fa046");
      put(x, y - 1, c); put(x - 1, y, c); put(x + 1, y, c); put(x, y, "#f2d45a");
    }
  }

  P.ctx.putImageData(img, 0, 0);
  // soft shadows to the right of and below each building (light from the top-left)
  P.ctx.fillStyle = "rgba(30,40,20,0.22)";
  for (const b of buildings) {
    const x = b.x * TILE, y = b.y * TILE, w = b.w * TILE, h = b.h * TILE;
    P.ctx.fillRect(x + w, y + 8, 4, h - 6);
    P.ctx.fillRect(x + 6, y + h, w - 2, 3);
  }
  if (scene.textures.exists(key)) scene.textures.remove(key);
  scene.textures.addCanvas(key, P.canvas);
}

function shadeHex(c, amt) {
  const k = `${c}|${amt}`;
  if (!RGB.has(k)) {
    const [R, G, B] = rgbOf(c), f = (v) => Math.max(0, Math.min(255, Math.round(v + amt * 255)));
    RGB.set(k, [f(R), f(G), f(B)]);
  }
  return k;
}

// ---------- props ----------

export function makeProps(scene) {
  const add = (key, P) => { P.outline(); if (scene.textures.exists(key)) scene.textures.remove(key); scene.textures.addCanvas(key, P.canvas); };

  let P = new Pix(28, 34); // tree
  P.rect(12, 22, 4, 9, "#6a4428"); P.rect(12, 22, 1, 9, "#4a2e1a");
  const canopy = [[14, 12, 12, "#4f8a3c"], [9, 15, 7, "#46803a"], [19, 15, 7, "#46803a"], [14, 9, 8, "#5c9a46"]];
  for (const [cx, cy, rad, c] of canopy)
    for (let y = -rad; y <= rad; y++) for (let x = -rad; x <= rad; x++) if (x * x + y * y <= rad * rad) P.px(cx + x, cy + y, c);
  for (let i = 0; i < 30; i++) P.px(8 + Math.random() * 12, 4 + Math.random() * 10, "#74b25a");
  P.ctx.globalCompositeOperation = "destination-over"; P.rect(7, 30, 14, 3, "rgba(30,20,10,0.25)"); P.ctx.globalCompositeOperation = "source-over";
  add("tree", P);

  P = new Pix(14, 10); // bush
  for (let y = -4; y <= 4; y++) for (let x = -6; x <= 6; x++) if ((x * x) / 36 + (y * y) / 16 <= 1) P.px(7 + x, 5 + y, "#4f8a3c");
  P.px(5, 3, "#74b25a"); P.px(8, 2, "#74b25a"); P.px(9, 5, "#e86a8a");
  add("bush", P);

  P = new Pix(26, 26); // well
  P.rect(3, 12, 20, 11, "#8a8478"); for (let x = 3; x < 23; x += 5) P.rect(x, 12, 1, 11, "#6a6458");
  P.rect(5, 12, 16, 4, "#2a4a6a"); P.rect(4, 2, 2, 12, "#6a4428"); P.rect(20, 2, 2, 12, "#6a4428");
  P.rect(2, 0, 22, 3, "#8a4a32"); P.rect(12, 3, 1, 6, "#3a2a1a"); P.rect(11, 9, 3, 3, "#7a5636");
  add("well", P);

  for (const [k, c] of [["stall_a", "#c0503c"], ["stall_b", "#3c7ac0"], ["stall_c", "#d8a63a"]]) {
    P = new Pix(34, 30); // market stall
    P.rect(3, 16, 28, 10, "#8a6038"); P.rect(3, 16, 28, 2, "#a8784a");
    P.rect(5, 13, 4, 3, "#e05a3a"); P.rect(11, 13, 4, 3, "#f2d45a"); P.rect(18, 13, 5, 3, "#7ab04a"); P.rect(25, 13, 4, 3, "#d9a05a");
    P.rect(4, 4, 2, 22, "#6a4428"); P.rect(28, 4, 2, 22, "#6a4428");
    for (let x = 1; x < 33; x += 4) P.rect(x, 1, 4, 6, (x / 4) % 2 < 1 ? c : "#f6efe0");
    for (let x = 1; x < 33; x += 4) P.rect(x + 1, 7, 2, 1, (x / 4) % 2 < 1 ? c : "#f6efe0");
    add(k, P);
  }

  P = new Pix(8, 26); // lamp post
  P.rect(3, 6, 2, 19, "#3a3a40"); P.rect(1, 1, 6, 6, "#3a3a40"); P.rect(2, 2, 4, 4, "#f6d878"); P.rect(2, 24, 4, 2, "#3a3a40");
  add("lamp", P);

  P = new Pix(12, 10); // crate
  P.rect(0, 0, 12, 10, "#a8784a"); P.rect(0, 0, 12, 1, "#c09060"); P.rect(0, 4, 12, 1, "#7a5232"); P.rect(5, 0, 1, 10, "#7a5232");
  add("crate", P);

  P = new Pix(32, 32); // glow (for lamps/windows at night); 4x the old 8 px so scaled glows stay smooth
  for (let y = -16; y < 16; y++) for (let x = -16; x < 16; x++) {
    const d = Math.sqrt((x + 0.5) ** 2 + (y + 0.5) ** 2) / 16;
    if (d < 1) { P.ctx.fillStyle = `rgba(255,214,120,${((1 - d) ** 2) * 0.9})`; P.ctx.fillRect(16 + x, 16 + y, 1, 1); }
  }
  if (scene.textures.exists("glow")) scene.textures.remove("glow");
  scene.textures.addCanvas("glow", P.canvas);

  P = new Pix(18, 6); // selection ring
  for (let a = 0; a < 80; a++) P.px(9 + Math.cos(a / 12.7) * 8, 3 + Math.sin(a / 12.7) * 2.4, "#ffffff");
  if (scene.textures.exists("ring")) scene.textures.remove("ring");
  scene.textures.addCanvas("ring", P.canvas);
}
