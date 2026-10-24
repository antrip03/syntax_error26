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

const PLACE_STYLE = {
  mill: { roof: "#8a5a3a", wall: "#d8c4a0", trim: "#6b4a30" },
  bakery: { roof: "#b5523e", wall: "#f0dcc0", trim: "#7a4030" },
  chapel: { roof: "#5a6478", wall: "#d9d4c8", trim: "#4a4a58" },
  guildhall: { roof: "#4a5a48", wall: "#b8b0a0", trim: "#5a4a38" },
  inn: { roof: "#7a3e4a", wall: "#e6d2b0", trim: "#5a3424" },
  smithy: { roof: "#4a4440", wall: "#9a8a78", trim: "#3a3028" },
  house: { roof: "#9a6a3a", wall: "#e8d8b8", trim: "#6a4a2a" },
  house2: { roof: "#5a7a8a", wall: "#e0d6c0", trim: "#4a5a64" },
  cottage: { roof: "#6a8a4a", wall: "#eadcbc", trim: "#5a4a30" },
};

export function makeBuilding(scene, key, kind, wTiles, hTiles) {
  const st = PLACE_STYLE[kind] || PLACE_STYLE.house;
  const W = wTiles * TILE, H = hTiles * TILE;
  const extraTop = kind === "chapel" ? 28 : 0;
  const P = new Pix(W + 2, H + extraTop + 2);
  const ox = 1, oy = 1 + extraTop;
  const roofH = Math.round(H * 0.55), wallY = oy + roofH, wallH = H - roofH;

  // wall
  P.rect(ox + 2, wallY, W - 4, wallH, st.wall);
  if (kind === "guildhall" || kind === "chapel" || kind === "smithy") {
    for (let y = wallY + 2; y < wallY + wallH; y += 4)
      for (let x = ox + 2 + ((y / 4) % 2) * 3; x < ox + W - 4; x += 6) P.rect(x, y, 5, 1, shade(st.wall, -0.08));
  } else {
    for (let x = ox + 6; x < ox + W - 4; x += 7) P.rect(x, wallY, 1, wallH, shade(st.wall, -0.05));
  }
  P.rect(ox + 2, wallY, W - 4, 2, shade(st.wall, -0.18));
  P.rect(ox + 2, oy + H - 2, W - 4, 2, st.trim);
  // roof with shingles
  P.rect(ox, oy, W, roofH, st.roof);
  for (let y = oy + 3; y < oy + roofH; y += 3) {
    P.rect(ox, y, W, 1, shade(st.roof, -0.1));
    for (let x = ox + ((y / 3) % 2) * 3; x < ox + W; x += 6) P.px(x, y + 1, shade(st.roof, 0.06));
  }
  P.rect(ox, oy, W, 2, shade(st.roof, 0.12));
  P.rect(ox, oy + roofH - 2, W, 2, shade(st.roof, -0.22));
  // door
  const dw = 8, dh = Math.min(12, wallH - 2), dx = ox + Math.floor(W / 2 - dw / 2), dy = oy + H - dh;
  P.rect(dx - 1, dy - 1, dw + 2, dh + 1, st.trim);
  P.rect(dx, dy, dw, dh, "#5a3a24");
  P.rect(dx + 3, dy, 1, dh, "#4a2e1c");
  P.px(dx + dw - 2, dy + Math.floor(dh / 2), "#e8c860");
  // windows (warm glass)
  const winY = wallY + 4;
  const wins = W >= 96 ? [0.18, 0.34, 0.66, 0.82] : [0.22, 0.78];
  for (const f of wins) {
    const wx = ox + Math.round(W * f) - 3;
    if (Math.abs(wx + 3 - (dx + dw / 2)) < 9) continue;
    P.rect(wx - 1, winY - 1, 8, 8, st.trim);
    P.rect(wx, winY, 6, 6, "#f3d98a"); P.rect(wx, winY, 6, 2, "#fbeab5"); P.rect(wx + 3, winY, 1, 6, st.trim); P.rect(wx, winY + 3, 6, 1, st.trim);
  }

  // per-place details
  if (kind === "mill") {
    const cx = ox + W - 8, cy = wallY + 2;
    P.ctx.fillStyle = "#6b4a30";
    for (let a = 0; a < 8; a++) {
      const ang = (a * Math.PI) / 4;
      for (let r = 0; r < 12; r++) P.px(cx + Math.cos(ang) * r, cy + Math.sin(ang) * r, "#7a5636");
    }
    for (let a = 0; a < 64; a++) P.px(cx + Math.cos(a / 10.2) * 12, cy + Math.sin(a / 10.2) * 12, "#5a3a22");
    P.rect(cx - 1, cy - 1, 3, 3, "#3a2a1a");
    P.rect(ox + 6, wallY + wallH - 7, 6, 5, "#e8dcc0"); P.rect(ox + 7, wallY + wallH - 8, 4, 1, "#e8dcc0"); // flour sack
  }
  if (kind === "bakery") {
    for (let x = ox + 2; x < ox + W - 2; x += 4) P.rect(x, wallY, 2, 4, x % 8 < 4 ? "#f6efe0" : "#c0503c");
    P.rect(ox + 4, oy + H - 5, 7, 3, "#d9a05a"); P.rect(ox + 5, oy + H - 6, 5, 1, "#e8b870");
  }
  if (kind === "chapel") {
    const tw = 16, tx = ox + Math.floor(W / 2 - tw / 2);
    P.rect(tx, oy - extraTop + 8, tw, extraTop + roofH - 6, shade(st.wall, -0.04));
    P.rect(tx - 2, oy - extraTop + 4, tw + 4, 6, st.roof);
    P.rect(tx + 2, oy - extraTop + 1, tw - 4, 4, st.roof);
    P.rect(tx + 5, oy - extraTop + 13, 6, 7, "#3a3a48"); P.rect(tx + 7, oy - extraTop + 15, 2, 3, "#e8c860"); // bell
    P.rect(tx + 7, oy - extraTop - 1, 2, 6, "#e8c860"); P.rect(tx + 5, oy - extraTop + 1, 6, 2, "#e8c860"); // cross
  }
  if (kind === "guildhall") {
    for (const f of [0.12, 0.88]) {
      const bx = ox + Math.round(W * f) - 3;
      P.rect(bx, wallY + 1, 6, 10, "#7a2a2a"); P.rect(bx + 2, wallY + 4, 2, 3, "#e8c860");
    }
    P.rect(ox + 3, wallY + 2, 3, wallH - 4, shade(st.wall, -0.15)); // side door (open)
    P.rect(ox + 3, wallY + 2, 1, wallH - 4, "#1a1410");
  }
  if (kind === "smithy") {
    P.rect(ox + W - 14, oy - 6, 8, 10, "#5a5048"); P.rect(ox + W - 13, oy - 7, 6, 2, "#3a3028");
    P.rect(ox + W - 12, oy - 5, 4, 2, "#ff9a3a");
    P.rect(ox + 5, oy + H - 6, 9, 3, "#3a3a3a"); P.rect(ox + 7, oy + H - 3, 5, 2, "#2a2a2a"); // anvil
  }
  if (kind === "inn") {
    P.rect(ox + W - 16, wallY + 2, 12, 8, "#8a5a32"); P.rect(ox + W - 13, wallY + 4, 5, 4, "#e8c860"); P.rect(ox + W - 8, wallY + 5, 1, 2, "#e8c860");
  }

  P.outline();
  if (scene.textures.exists(key)) scene.textures.remove(key);
  scene.textures.addCanvas(key, P.canvas);
  return { key, extraTop };
}

// ---------- ground ----------

export function makeGround(scene, key, map) {
  const { cols, rows, roads, plaza, river, bridge, gardens } = map;
  const W = cols * TILE, H = rows * TILE;
  const P = new Pix(W, H);
  const r = rng(99);
  P.rect(0, 0, W, H, "#86b85c");
  for (let i = 0; i < W * H * 0.06; i++) P.px(r() * W, r() * H, r() < 0.5 ? "#79ab52" : "#93c468");
  for (let i = 0; i < 380; i++) { // grass tufts
    const x = r() * W, y = r() * H;
    P.px(x, y, "#5f9443"); P.px(x + 1, y - 1, "#5f9443"); P.px(x + 2, y, "#5f9443");
  }
  // river with banks
  const ry = river.y * TILE, rh = river.h * TILE;
  P.rect(0, ry - 2, W, rh + 4, "#6a8a4a");
  P.rect(0, ry, W, rh, "#4a8cc0");
  for (let i = 0; i < 260; i++) { const x = r() * W, y = ry + 3 + r() * (rh - 6); P.rect(x, y, 3 + r() * 5, 1, r() < 0.6 ? "#6aaad8" : "#3a7aae"); }
  // roads
  const road = (x, y, w, h) => {
    P.rect(x * TILE, y * TILE, w * TILE, h * TILE, "#c9a66e");
    for (let i = 0; i < w * h * 6; i++) P.px(x * TILE + r() * w * TILE, y * TILE + r() * h * TILE, r() < 0.5 ? "#b8945c" : "#d8b880");
  };
  for (const [x, y, w, h] of roads) road(x, y, w, h);
  // plaza cobbles
  const [px0, py0, pw, ph] = plaza;
  P.rect(px0 * TILE, py0 * TILE, pw * TILE, ph * TILE, "#b4ab9a");
  for (let y = py0 * TILE; y < (py0 + ph) * TILE; y += 5)
    for (let x = px0 * TILE + ((y / 5) % 2) * 3; x < (px0 + pw) * TILE; x += 6) {
      P.rect(x, y, 5, 4, r() < 0.5 ? "#c2b9a8" : "#a9a08e");
    }
  // bridge planks
  const [bx, bw] = bridge;
  P.rect(bx * TILE, ry - 4, bw * TILE, rh + 8, "#8a6038");
  for (let y = ry - 4; y < ry + rh + 4; y += 4) P.rect(bx * TILE, y, bw * TILE, 1, "#6a4626");
  P.rect(bx * TILE, ry - 4, 2, rh + 8, "#5a3a20"); P.rect((bx + bw) * TILE - 2, ry - 4, 2, rh + 8, "#5a3a20");
  // flower gardens
  for (const [gx, gy, gw, gh] of gardens) {
    P.rect(gx * TILE, gy * TILE, gw * TILE, gh * TILE, "#6a4a30");
    for (let i = 0; i < gw * gh * 10; i++) {
      const x = gx * TILE + 2 + r() * (gw * TILE - 4), y = gy * TILE + 2 + r() * (gh * TILE - 4);
      P.px(x, y, ["#e86a8a", "#f2d45a", "#b07ad8", "#ffffff", "#5fa046"][Math.floor(r() * 5)]);
    }
  }
  if (scene.textures.exists(key)) scene.textures.remove(key);
  scene.textures.addCanvas(key, P.canvas);
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
