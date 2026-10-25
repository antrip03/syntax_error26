// More procedural pixel art: building interiors and their furniture, animals, and outdoor decor.
// Same conventions as art.js (16 px tiles, 1 px dark outline, light from the top-left).

import { Pix, TILE, shade, rng } from "./art.js";

const OUT = "#2b1d14";
const T = TILE;

function register(scene, key, canvas) {
  if (scene.textures.exists(key)) scene.textures.remove(key);
  return scene.textures.addCanvas(key, canvas);
}

// ---------- furniture (drawn straight into the room canvas) ----------

function box(P, x, y, w, h, fill, edge = OUT) {
  P.rect(x, y, w, h, edge);
  P.rect(x + 1, y + 1, w - 2, h - 2, fill);
}

const FURNITURE = {
  counter(P, x, y, w, h) {
    box(P, x, y + 2, w, h - 2, "#9a6a3a");
    P.rect(x + 1, y + 3, w - 2, 2, "#b8854e");
    for (let i = x + 6; i < x + w - 2; i += 8) P.rect(i, y + 6, 1, h - 6, "#7a5030");
  },
  oven(P, x, y, w, h) {
    box(P, x, y, w, h, "#a8603e");
    for (let r = y + 3; r < y + h - 2; r += 4) for (let c = x + 2 + ((r / 4) % 2) * 3; c < x + w - 3; c += 6) P.rect(c, r, 5, 1, "#8a4a30");
    P.rect(x + 6, y + h - 13, w - 12, 9, OUT); P.rect(x + 7, y + h - 12, w - 14, 7, "#ff9a3a"); P.rect(x + 9, y + h - 10, w - 18, 3, "#ffd27a");
  },
  shelf_bread(P, x, y, w) {
    box(P, x, y + 2, w, 12, "#8a5a32");
    for (let i = x + 3; i < x + w - 4; i += 6) { P.rect(i, y + 4, 5, 3, "#d9a05a"); P.rect(i + 1, y + 3, 3, 1, "#e8b870"); P.rect(i, y + 9, 5, 3, "#c08040"); }
  },
  shelf_bottles(P, x, y, w) {
    box(P, x, y + 2, w, 12, "#6a4428");
    const cs = ["#4a8a5a", "#8a3a3a", "#3a5a8a", "#c8a040"];
    for (let i = x + 3, k = 0; i < x + w - 3; i += 4, k++) { P.rect(i, y + 4, 2, 4, cs[k % 4]); P.rect(i + 0.5, y + 3, 1, 1, cs[k % 4]); P.rect(i, y + 10, 2, 3, cs[(k + 2) % 4]); }
  },
  shelf_books(P, x, y, w) {
    box(P, x, y + 1, w, 13, "#5a3a22");
    const cs = ["#8a3a3a", "#3a5a8a", "#4a7a4a", "#a88a3a", "#6a4a7a"];
    for (let i = x + 2, k = 0; i < x + w - 2; i += 3, k++) { P.rect(i, y + 3, 2, 4, cs[k % 5]); P.rect(i, y + 9, 2, 4, cs[(k + 3) % 5]); }
  },
  shelf_jars(P, x, y, w) {
    box(P, x, y + 2, w, 12, "#7a5a32");
    const cs = ["#7ab04a", "#d8a63a", "#b07ad8", "#5aa0c0"];
    for (let i = x + 3, k = 0; i < x + w - 4; i += 6, k++) { P.rect(i, y + 4, 4, 4, "#e8f0f0"); P.rect(i + 1, y + 5, 2, 3, cs[k % 4]); P.rect(i, y + 9, 4, 4, "#e8f0f0"); P.rect(i + 1, y + 10, 2, 3, cs[(k + 1) % 4]); }
  },
  sacks(P, x, y, w, h) {
    for (let j = 0; j < h / T; j++) for (let i = 0; i < w / T; i++) {
      const sx = x + i * T + 2, sy = y + j * T + 2;
      box(P, sx, sy + 2, 12, 11, "#e8dcc0"); P.rect(sx + 3, sy, 6, 3, "#d8cba8"); P.rect(sx + 4, sy + 6, 4, 3, "#c8b890");
    }
  },
  table(P, x, y, w, h) {
    box(P, x + 1, y + 1, w - 2, h + 2, "#a8784a");
    P.rect(x + 2, y + 2, w - 4, 2, "#c09060");
    P.rect(x + 4, y + 6, 4, 3, "#e8e0d0"); P.rect(x + w - 8, y + 5, 3, 4, "#c8b07a");
  },
  longtable(P, x, y, w, h) {
    box(P, x, y, w, h + 4, "#7a5232");
    P.rect(x + 1, y + 1, w - 2, 2, "#9a6a42");
    for (let i = x + 6; i < x + w - 6; i += 18) { P.rect(i, y + 6, 8, 6, "#f2ead6"); P.rect(i + 1, y + 7, 6, 1, "#9a9080"); P.rect(i + 1, y + 9, 5, 1, "#9a9080"); }
    P.rect(x + w / 2, y + 5, 3, 5, "#c8a040");
  },
  stool(P, x, y) { box(P, x + 4, y + 4, 8, 8, "#8a5a32"); P.rect(x + 5, y + 5, 6, 2, "#a8784a"); },
  chair(P, x, y) { box(P, x + 3, y + 2, 10, 12, "#6a4428"); P.rect(x + 4, y + 3, 8, 3, "#8a5a32"); },
  rug(P, x, y, w, h) {
    P.rect(x + 2, y + 2, w - 4, h - 4, "#8a3a3a"); P.rect(x + 4, y + 4, w - 8, h - 8, "#b8604a");
    P.rect(x + 6, y + 6, w - 12, h - 12, "#d8a040");
    for (let i = x + 2; i < x + w - 2; i += 3) { P.rect(i, y + 1, 1, 1, "#d8a040"); P.rect(i, y + h - 2, 1, 1, "#d8a040"); }
  },
  runner(P, x, y, w, h) { P.rect(x + 4, y, w - 8, h, "#7a2a3a"); P.rect(x + 6, y, 1, h, "#c8a040"); P.rect(x + w - 7, y, 1, h, "#c8a040"); },
  plant(P, x, y) {
    box(P, x + 4, y + 9, 8, 6, "#a8603e");
    for (const [dx, dy] of [[5, 3], [8, 1], [3, 6], [10, 5], [7, 6]]) P.rect(x + dx, y + dy, 4, 4, "#4f8a3c");
    P.rect(x + 8, y + 2, 2, 2, "#74b25a");
  },
  barrels(P, x, y, w, h) {
    for (let j = 0; j < h / T; j++) for (let i = 0; i < w / T; i++) FURNITURE.barrel(P, x + i * T, y + j * T);
  },
  barrel(P, x, y) {
    box(P, x + 2, y + 1, 12, 14, "#8a5a32");
    P.rect(x + 3, y + 3, 10, 1, "#4a4a4a"); P.rect(x + 3, y + 11, 10, 1, "#4a4a4a"); P.rect(x + 5, y + 2, 1, 12, "#a8784a");
  },
  fireplace(P, x, y, w, h) {
    box(P, x, y, w, h, "#8a8478");
    for (let r = y + 2; r < y + h; r += 4) for (let c = x + 1 + ((r / 4) % 2) * 3; c < x + w - 2; c += 6) P.rect(c, r, 5, 1, "#6a6458");
    P.rect(x + 8, y + 10, w - 16, h - 10, OUT); P.rect(x + 9, y + 12, w - 18, h - 12, "#ff8a2a"); P.rect(x + 12, y + 16, w - 24, h - 17, "#ffd27a");
    P.rect(x - 1, y + 8, w + 2, 3, "#6a4428");
  },
  banner(P, x, y) { P.rect(x + 3, y + 4, 10, 22, OUT); P.rect(x + 4, y + 5, 8, 18, "#7a2a2a"); P.rect(x + 6, y + 10, 4, 5, "#e8c860"); P.rect(x + 4, y + 23, 2, 2, "#7a2a2a"); P.rect(x + 10, y + 23, 2, 2, "#7a2a2a"); },
  glass(P, x, y) {
    P.rect(x + 3, y + 4, 10, 24, OUT);
    const cs = ["#d84a4a", "#4a7ad8", "#e8c860", "#4ab06a"];
    for (let j = 0; j < 5; j++) for (let i = 0; i < 2; i++) P.rect(x + 4 + i * 4, y + 5 + j * 4, 4, 4, cs[(i + j) % 4]);
    P.rect(x + 3, y + 4, 10, 2, "#5a5a68");
  },
  altar(P, x, y, w, h) { box(P, x, y, w, h + 3, "#e8e0cc"); P.rect(x + 1, y + 1, w - 2, 3, "#7a2a3a"); P.rect(x + w / 2 - 2, y + 5, 4, 8, "#c8a040"); P.rect(x + w / 2 - 4, y + 7, 8, 2, "#c8a040"); },
  candle(P, x, y) { P.rect(x + 6, y + 6, 4, 9, "#f2ead6"); P.rect(x + 7, y + 3, 2, 3, "#ffb84a"); P.rect(x + 5, y + 14, 6, 2, "#c8a040"); },
  pew(P, x, y, w, h) { box(P, x, y + 1, w, h + 3, "#7a5232"); P.rect(x + 1, y + 2, w - 2, 3, "#9a6a42"); },
  chalk(P, x, y, w, h) {
    // body outline in chalk on the floor
    const pts = [[8, 4], [12, 4], [13, 8], [20, 9], [26, 7], [28, 10], [22, 13], [14, 14], [18, 22], [16, 24], [10, 16], [6, 22], [3, 21], [8, 13], [5, 9]];
    for (let i = 0; i < pts.length; i++) {
      const [ax, ay] = pts[i], [bx, by] = pts[(i + 1) % pts.length];
      const n = Math.max(Math.abs(bx - ax), Math.abs(by - ay));
      for (let k = 0; k <= n; k++) P.px(x + 6 + ax + ((bx - ax) * k) / n, y + 2 + ay + ((by - ay) * k) / n, "#f4f0e8");
    }
    P.rect(x + 34, y + 20, 4, 3, "#6a2a2a"); P.rect(x + 36, y + 24, 2, 2, "#6a2a2a");
  },
  sidedoor(P, x, y, w, h) { P.rect(x, y, 6, h, "#1a1410"); P.rect(x + 6, y, 2, h, "#5a3a24"); P.rect(x + 1, y + h - 3, 10, 2, "rgba(255,230,160,0.35)"); },
  forge(P, x, y, w, h) {
    box(P, x, y, w, h, "#5a5048");
    P.rect(x + 4, y + 8, w - 8, h - 12, OUT); P.rect(x + 5, y + 9, w - 10, h - 14, "#ff7a2a"); P.rect(x + 8, y + 12, w - 16, h - 20, "#ffd27a");
    P.rect(x + w / 2 - 4, y - 2, 8, 6, "#3a3028");
  },
  rack(P, x, y, w) {
    P.rect(x, y + 3, w, 2, "#6a4428"); P.rect(x, y + 11, w, 2, "#6a4428");
    for (let i = x + 4; i < x + w - 3; i += 8) { P.rect(i, y + 1, 2, 13, "#b8c0c8"); P.rect(i - 1, y + 9, 4, 1, "#6a4428"); P.rect(i + 4, y + 2, 1, 11, "#8a9098"); }
  },
  anvil(P, x, y, w) { P.rect(x + 3, y + 3, w - 6, 6, OUT); P.rect(x + 4, y + 4, w - 8, 4, "#5a5a62"); P.rect(x + 8, y + 9, w - 16, 5, "#3a3a40"); P.rect(x + 1, y + 4, 4, 2, "#5a5a62"); P.rect(x + 4, y + 4, w - 8, 1, "#8a8a92"); },
  coal(P, x, y, w, h) { box(P, x + 1, y + 4, w - 2, h - 5, "#5a4030"); for (let i = 0; i < 30; i++) P.px(x + 3 + Math.random() * (w - 6), y + 5 + Math.random() * 5, "#2a2a2a"); },
  bench(P, x, y, w, h) { box(P, x, y + 2, w, h + 2, "#7a5a3a"); P.rect(x + 4, y + 4, 6, 3, "#9aa3ad"); P.rect(x + 14, y + 5, 8, 2, "#6a6a6a"); P.rect(x + 28, y + 4, 4, 4, "#c8a040"); },
  gears(P, x, y) {
    for (const [cx, cy, r] of [[x + 10, y + 14, 8], [x + 26, y + 10, 6]]) {
      for (let a = 0; a < 48; a++) P.px(cx + Math.cos(a / 7.6) * r, cy + Math.sin(a / 7.6) * r, "#6a4a30");
      for (let a = 0; a < 8; a++) P.rect(cx + Math.cos(a * 0.785) * (r + 1) - 1, cy + Math.sin(a * 0.785) * (r + 1) - 1, 2, 2, "#6a4a30");
      P.rect(cx - 1, cy - 1, 3, 3, "#3a2a1a");
    }
  },
  grindstone(P, x, y, w, h) {
    const cx = x + w / 2, cy = y + h / 2, R = Math.min(w, h) / 2 - 2;
    for (let yy = -R; yy <= R; yy++) for (let xx = -R; xx <= R; xx++) {
      const d = xx * xx + yy * yy;
      if (d <= R * R) P.px(cx + xx, cy + yy, d > (R - 2) ** 2 ? OUT : d > (R - 6) ** 2 ? "#a8a090" : "#8a8478");
    }
    for (let a = 0; a < 6; a++) for (let r = 4; r < R - 6; r++) P.px(cx + Math.cos(a * 1.05) * r, cy + Math.sin(a * 1.05) * r, "#6a6458");
    P.rect(cx - 3, cy - 3, 6, 6, "#5a3a22"); P.rect(cx - 1, y - 2, 2, h / 2, "#6a4428");
    for (let i = 0; i < 20; i++) P.px(x + Math.random() * w, y + h + Math.random() * 4, "#f2ead6");
  },
  herbs(P, x, y, w) {
    P.rect(x, y + 6, w, 1, "#6a4428");
    for (let i = x + 3; i < x + w - 2; i += 6) { P.rect(i, y + 7, 1, 3, "#6a4428"); P.rect(i - 2, y + 10, 5, 8, "#5d8a55"); P.rect(i - 1, y + 17, 3, 3, "#7aa060"); P.px(i, y + 12, "#d8c860"); }
  },
  cauldron(P, x, y, w, h) {
    const cx = x + w / 2, cy = y + h / 2 + 2, R = w / 2 - 3;
    for (let yy = -R; yy <= R; yy++) for (let xx = -R; xx <= R; xx++) if (xx * xx + yy * yy <= R * R) P.px(cx + xx, cy + yy, "#2a2a30");
    P.rect(cx - R + 2, cy - R + 2, 2 * R - 4, 5, "#6ac05a"); P.rect(cx - 3, cy - R + 3, 3, 2, "#a8e07a");
    P.rect(cx - R - 1, cy - R + 1, 2 * R + 2, 2, "#4a4a52");
    P.rect(cx - 5, cy + R, 10, 3, "#ff8a2a");
  },
};

const GLOWING = { oven: 0.7, fireplace: 1, forge: 1, candle: 0.5, cauldron: 0.5 };

// Draws a whole room; returns {key, solids:[px rects], glows:[{x,y,scale}]} in room-local pixels.
// The chalk outline as its own texture (3 x 2 tiles), so it can be laid in whichever room the victim died.
export function makeChalk(scene, key = "chalk") {
  if (scene.textures.exists(key)) return key;
  const P = new Pix(3 * T, 2 * T);
  FURNITURE.chalk(P, 0, 0, 3 * T, 2 * T);
  register(scene, key, P.canvas);
  return key;
}

export function makeRoom(scene, key, room) {
  const W = room.w * T, H = room.h * T;
  const P = new Pix(W, H);
  const r = rng(room.w * 31 + room.h);
  // floor
  if (room.floor === "wood") {
    P.rect(0, 0, W, H, "#b8875a");
    for (let y = 0; y < H; y += 6) {
      P.rect(0, y, W, 1, "#9a6a42");
      for (let x = (y * 7) % 37; x < W; x += 37) P.rect(x, y, 1, 6, "#9a6a42");
    }
    for (let i = 0; i < W * H * 0.01; i++) P.px(r() * W, r() * H, "#c8976a");
  } else if (room.floor === "stone") {
    P.rect(0, 0, W, H, "#a8a29a");
    for (let y = 0; y < H; y += 8) for (let x = ((y / 8) % 2) * 8; x < W; x += 16) { P.rect(x, y, 15, 7, r() < 0.5 ? "#b4aea4" : "#9c968c"); }
  } else {
    P.rect(0, 0, W, H, "#8a7258");
    for (let i = 0; i < W * H * 0.05; i++) P.px(r() * W, r() * H, r() < 0.5 ? "#7a6248" : "#9a8268");
  }
  // walls (top two rows) with skirting
  P.rect(0, 0, W, 2 * T, room.wall);
  for (let x = 0; x < W; x += 8) P.rect(x, 0, 1, 2 * T - 3, shade(room.wall, -0.06));
  P.rect(0, 2 * T - 4, W, 4, room.trim);
  P.rect(0, 2 * T, W, 2, "rgba(30,20,10,0.25)");
  // windows on the wall
  for (const f of [0.25, 0.75]) {
    const wx = Math.round(W * f) - 6;
    if (room.furniture.some(([k, fx, , fw]) => ["glass", "banner", "gears", "herbs"].includes(k) && Math.abs(fx * T + (fw * T) / 2 - (wx + 6)) < 20)) continue;
    P.rect(wx - 1, 5, 14, 14, room.trim); P.rect(wx, 6, 12, 12, "#bfe0f0"); P.rect(wx, 6, 12, 4, "#e6f4fa"); P.rect(wx + 6, 6, 1, 12, room.trim); P.rect(wx, 12, 12, 1, room.trim);
  }
  // side and bottom walls
  P.rect(0, 0, 3, H, room.trim); P.rect(W - 3, 0, 3, H, room.trim); P.rect(0, H - 4, W, 4, room.trim);
  // doorway + mat
  const dx = W / 2 - T;
  P.rect(dx, H - 4, 2 * T, 4, "#2b1d14");
  P.rect(dx + 2, H - 12, 2 * T - 4, 8, "#7a5a3a"); P.rect(dx + 4, H - 10, 2 * T - 8, 4, "#9a7a4a");

  const solids = [], glows = [];
  for (const [kind, fx, fy, fw, fh, solid] of room.furniture) {
    const x = fx * T, y = fy * T, w = fw * T, h = fh * T;
    FURNITURE[kind]?.(P, x, y, w, h);
    if (solid) solids.push([x + 1, y + (kind === "counter" || kind.startsWith("shelf") ? 3 : 2), w - 2, h - 2]);
    if (GLOWING[kind]) glows.push({ x: x + w / 2, y: y + h / 2 + 2, scale: (3 + (w / T) * GLOWING[kind] * 2) / 4 });
  }
  register(scene, key, P.canvas);
  return { key, W, H, solids, glows };
}

// ---------- animals ----------

export function makeAnimal(scene, key, kind) {
  const w = 14, h = 12;
  const P = new Pix(w * 3, h * 4);
  const dirs = ["down", "left", "right", "up"];
  dirs.forEach((dir, row) => {
    for (let f = 0; f < 3; f++) {
      const ox = f * w, oy = row * h, flip = dir === "right";
      const X = (x) => (flip ? ox + w - 1 - x : ox + x);
      const R = (x, y, ww, hh, c) => { for (let i = 0; i < ww; i++) P.rect(X(x + i), oy + y, 1, hh, c); };
      const bob = f === 1 ? 1 : 0;
      if (kind === "chicken") {
        R(4, 4 - bob, 7, 5, "#f6f2ea"); R(3, 2 - bob, 3, 3, "#f6f2ea"); R(2, 3 - bob, 1, 1, "#e8a030"); R(3, 1 - bob, 2, 1, "#d8402a");
        R(4, 3 - bob, 1, 1, OUT); R(10, 4 - bob, 2, 2, "#e8e0d0"); R(6, 9, 1, 2 - bob, "#e8a030"); R(8, 9, 1, 1 + bob, "#e8a030");
      } else if (kind === "duck") {
        R(4, 5 - bob, 7, 4, "#f2f0e8"); R(3, 2 - bob, 3, 4, "#3a7a4a"); R(1, 4 - bob, 2, 1, "#e8a030"); R(4, 3 - bob, 1, 1, OUT); R(9, 5 - bob, 3, 2, "#d8d4c8");
      } else { // cat
        R(4, 5, 8, 4, "#d89a5a"); R(2, 3 - bob, 4, 4, "#d89a5a"); R(2, 2 - bob, 1, 1, "#d89a5a"); R(5, 2 - bob, 1, 1, "#d89a5a");
        R(3, 4 - bob, 1, 1, OUT); R(11, 3 + bob, 1, 3, "#c08040"); R(12, 2 + bob, 1, 2, "#c08040");
        R(5, 9, 1, 2 - bob, "#c08040"); R(10, 9, 1, 1 + bob, "#c08040"); R(6, 6, 4, 1, "#c08040");
      }
      P.outline(ox, oy, w, h);
    }
  });
  const tex = register(scene, key, P.canvas);
  dirs.forEach((dir, row) => { for (let f = 0; f < 3; f++) tex.add(`${dir}-${f}`, 0, f * w, row * h, w, h); });
  for (const dir of dirs) {
    const ak = `${key}-walk-${dir}`;
    if (scene.anims.exists(ak)) scene.anims.remove(ak);
    scene.anims.create({ key: ak, frameRate: 7, repeat: -1, frames: [1, 0, 2, 0].map((f) => ({ key, frame: `${dir}-${f}` })) });
  }
  return key;
}

// ---------- outdoor decor ----------

export function makeDecor(scene) {
  const add = (key, P) => { P.outline(); register(scene, key, P.canvas); };
  let P;

  P = new Pix(14, 10); // rock
  P.rect(2, 3, 10, 6, "#8a8a84"); P.rect(3, 2, 7, 2, "#9a9a94"); P.rect(4, 3, 3, 2, "#b4b4ae"); P.rect(9, 6, 3, 3, "#74746e");
  add("rock", P);
  P = new Pix(10, 7); // small rock
  P.rect(1, 2, 8, 4, "#8a8a84"); P.rect(2, 1, 4, 2, "#a4a49e");
  add("pebble", P);
  P = new Pix(14, 10); // stump
  P.rect(2, 3, 10, 6, "#7a5232"); P.rect(2, 2, 10, 3, "#c8a070"); P.rect(5, 3, 4, 1, "#a8804e"); P.rect(0, 8, 3, 1, "#7a5232"); P.rect(11, 8, 3, 1, "#7a5232");
  add("stump", P);
  P = new Pix(22, 18); // haystack
  for (let y = 0; y < 15; y++) { const half = Math.min(10, 3 + y); P.rect(11 - half, 2 + y, half * 2, 1, y % 3 ? "#e0c060" : "#c8a040"); }
  for (let i = 0; i < 18; i++) P.px(3 + Math.random() * 16, 4 + Math.random() * 12, "#f2d87a");
  add("haystack", P);
  P = new Pix(14, 16); // barrel
  P.rect(2, 1, 10, 14, "#8a5a32"); P.rect(2, 3, 10, 1, "#4a4a4a"); P.rect(2, 11, 10, 1, "#4a4a4a"); P.rect(4, 1, 1, 14, "#a8784a"); P.rect(3, 1, 8, 2, "#6a4428");
  add("barrel", P);
  P = new Pix(34, 22); // cart
  P.rect(2, 4, 26, 10, "#9a6a3a"); P.rect(2, 4, 26, 2, "#b8854e"); for (let x = 6; x < 28; x += 6) P.rect(x, 6, 1, 8, "#7a5030");
  P.rect(5, 1, 6, 4, "#e05a3a"); P.rect(12, 2, 5, 3, "#7ab04a"); P.rect(18, 1, 6, 4, "#f2d45a");
  P.rect(28, 9, 6, 2, "#6a4428");
  for (const cx of [8, 22]) { for (let a = 0; a < 40; a++) P.px(cx + Math.cos(a / 6.4) * 5, 16 + Math.sin(a / 6.4) * 5, "#4a2e1c"); P.rect(cx - 1, 15, 2, 2, "#4a2e1c"); }
  add("cart", P);
  P = new Pix(18, 24); // signpost
  P.rect(8, 6, 2, 17, "#6a4428"); P.rect(1, 3, 16, 6, "#a8784a"); P.rect(14, 4, 3, 4, "#a8784a"); P.rect(3, 5, 9, 1, "#5a3a22"); P.rect(2, 11, 12, 5, "#a8784a"); P.rect(4, 13, 7, 1, "#5a3a22");
  add("sign", P);
  P = new Pix(16, 12); // fence segment
  P.rect(1, 2, 2, 10, "#8a6038"); P.rect(13, 2, 2, 10, "#8a6038"); P.rect(0, 4, 16, 2, "#a8784a"); P.rect(0, 8, 16, 2, "#a8784a"); P.rect(1, 1, 2, 1, "#a8784a"); P.rect(13, 1, 2, 1, "#a8784a");
  add("fence", P);
  P = new Pix(16, 12); // tall grass clump
  for (const [x, hgt, c] of [[2, 7, "#5f9443"], [4, 10, "#6fa850"], [6, 8, "#5f9443"], [8, 11, "#7ab85a"], [10, 7, "#5f9443"], [12, 9, "#6fa850"]]) P.rect(x, 12 - hgt, 2, hgt, c);
  register(scene, "tallgrass", P.canvas);
  P = new Pix(10, 10); // mushroom
  P.rect(2, 2, 6, 3, "#c0443a"); P.rect(3, 1, 4, 1, "#c0443a"); P.rect(3, 2, 1, 1, "#f6efe0"); P.rect(6, 3, 1, 1, "#f6efe0"); P.rect(4, 5, 2, 3, "#f2ead6");
  add("mushroom", P);
  P = new Pix(30, 26); // pine-ish round tree variant
  for (let y = 0; y < 20; y++) { const half = Math.round(3 + y * 0.55); P.rect(15 - half, 1 + y, half * 2, 1, y % 4 < 2 ? "#3f7a3a" : "#4a8a40"); }
  P.rect(13, 20, 4, 5, "#6a4428");
  add("pine", P);
}

// Paints flowers, tall-grass tufts and pebbles straight into an existing ground canvas texture.
export function paintGroundDetails(scene, key, decals) {
  const tex = scene.textures.get(key);
  const canvas = tex.getSourceImage();
  const ctx = canvas.getContext("2d");
  const px = (x, y, c) => { ctx.fillStyle = c; ctx.fillRect(x | 0, y | 0, 1, 1); };
  const r = rng(4242);
  for (const [kind, tx, ty] of decals) {
    const x = tx * T + r() * 10, y = ty * T + r() * 10;
    if (kind === "flowers") {
      const c = ["#e86a8a", "#f2d45a", "#b07ad8", "#ffffff", "#f08a4a"][Math.floor(r() * 5)];
      for (let i = 0; i < 4; i++) { const fx = x + r() * 9, fy = y + r() * 7; px(fx, fy, c); px(fx, fy + 1, "#4f8a3c"); }
    } else if (kind === "meadow") {
      ctx.fillStyle = "rgba(70,120,50,0.18)"; ctx.fillRect(tx * T, ty * T, T * 2, T * 2);
    } else if (kind === "dirt") {
      ctx.fillStyle = "rgba(150,110,60,0.35)"; ctx.fillRect(x, y, 6 + r() * 6, 3 + r() * 3);
    } else if (kind === "pebbles") {
      for (let i = 0; i < 3; i++) px(x + r() * 10, y + r() * 8, "#a8a29a");
    }
  }
  tex.refresh();
}

// The pond: drawn into the ground with lily pads.
export function paintPond(scene, key, [tx, ty, tw, th]) {
  const tex = scene.textures.get(key);
  const ctx = tex.getSourceImage().getContext("2d");
  const cx = (tx + tw / 2) * T, cy = (ty + th / 2) * T, rx = (tw * T) / 2, ry = (th * T) / 2;
  for (let y = -ry; y <= ry; y++) for (let x = -rx; x <= rx; x++) {
    const d = (x * x) / (rx * rx) + (y * y) / (ry * ry);
    if (d > 1) continue;
    ctx.fillStyle = d > 0.82 ? "#5a7a3a" : d > 0.7 ? "#3a7aae" : "#4a8cc0";
    ctx.fillRect(cx + x, cy + y, 1, 1);
  }
  const pads = [[-18, -6], [10, 4], [20, -8], [-6, 10]];
  for (const [dx, dy] of pads) { ctx.fillStyle = "#5fa046"; ctx.fillRect(cx + dx, cy + dy, 6, 4); ctx.fillStyle = "#4a8a3a"; ctx.fillRect(cx + dx + 3, cy + dy + 1, 1, 2); }
  ctx.fillStyle = "#f2b8c8"; ctx.fillRect(cx + 21, cy - 9, 2, 2);
  ctx.fillStyle = "#8ac4e8"; for (let i = 0; i < 10; i++) ctx.fillRect(cx - rx * 0.6 + i * 6, cy - 2 + (i % 3) * 4, 3, 1);
  tex.refresh();
}
