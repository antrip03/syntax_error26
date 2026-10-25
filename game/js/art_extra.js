
import { Pix, TILE, shade, rng, groundShadow } from "./art.js";

const OUT = "#2b1d14";
const T = TILE;

function register(scene, key, canvas) {
  if (scene.textures.exists(key)) scene.textures.remove(key);
  return scene.textures.addCanvas(key, canvas);
}


function box(P, x, y, w, h, fill, edge = OUT) {
  P.rect(x, y, w, h, edge);
  P.rect(x + 1, y + 1, w - 2, h - 2, fill);
}

const FURNITURE = {
  counter(P, x, y, w, h) { 
    box(P, x, y + 2, w, h - 1, "#8a5a32");
    P.rect(x + 1, y + 3, w - 2, 4, "#b8854e"); P.rect(x + 1, y + 3, w - 2, 1, "#d8a670"); P.rect(x + 1, y + 7, w - 2, 1, "#5a3a22");
    for (let i = x + 3; i < x + w - 6; i += 9) { P.rect(i, y + 9, 7, h - 10, "#7a4e2c"); P.rect(i, y + 9, 7, 1, "#9a6a42"); P.rect(i, y + 9, 1, h - 10, "#9a6a42"); }
    for (let i = x + 6; i < x + w - 4; i += 14) { P.rect(i, y, 3, 4, "#e8e0d0"); P.rect(i, y, 3, 1, "#ffffff"); } 
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
      const sx = x + i * T + 1, sy = y + j * T + 1;
      for (let yy = 0; yy < 11; yy++) for (let xx = 0; xx < 13; xx++) if ((xx - 6) ** 2 / 42 + (yy - 5.5) ** 2 / 34 <= 1) P.px(sx + xx, sy + 4 + yy, yy < 3 ? "#f2e8d0" : xx > 9 || yy > 8 ? "#c8b890" : "#e2d4b4");
      P.rect(sx + 4, sy + 1, 5, 4, "#d8cba8"); P.rect(sx + 4, sy + 4, 5, 1, "#8a6a3a"); P.px(sx + 6, sy, "#d8cba8");
      P.rect(sx + 4, sy + 9, 5, 1, "#b8a888");
    }
  },
  table(P, x, y, w, h) { 
    P.rect(x + 3, y + h + 1, 2, 3, "#5a3a22"); P.rect(x + w - 5, y + h + 1, 2, 3, "#5a3a22");
    box(P, x + 1, y + 1, w - 2, h + 1, "#a8784a");
    P.rect(x + 2, y + 2, w - 4, 2, "#c89a66"); P.rect(x + 2, y + h, w - 4, 1, "#7a5232");
    P.rect(x + w / 2 - 5, y + 4, 10, 6, "#e8dcc0"); P.rect(x + w / 2 - 5, y + 4, 10, 1, "#f6efe0");
    P.rect(x + w / 2 - 1, y + 2, 2, 4, "#f2ead6"); P.px(x + w / 2 - 1, y + 1, "#ffb84a");
    P.rect(x + 4, y + 6, 3, 3, "#c8b07a"); P.px(x + 4, y + 6, "#e8d8a0");
  },
  longtable(P, x, y, w, h) { 
    box(P, x, y, w, h + 4, "#6a4428");
    P.rect(x + 1, y + 1, w - 2, 2, "#9a6a42"); P.rect(x + 1, y + h + 2, w - 2, 1, "#4e3018");
    P.rect(x + 6, y + 4, w - 12, 3, "#7a2a3a"); P.rect(x + 6, y + 4, w - 12, 1, "#9a3a4a");
    for (let i = x + 6; i < x + w - 10; i += 22) { P.rect(i, y + 6, 9, 7, "#f2ead6"); P.rect(i + 1, y + 8, 7, 1, "#9a9080"); P.rect(i + 1, y + 10, 5, 1, "#9a9080"); }
    P.rect(x + w / 2, y + 6, 3, 4, "#2a2a36"); P.px(x + w / 2 + 2, y + 4, "#f2ead6");
    for (const cx of [x + 4, x + w - 6]) { P.rect(cx, y + 3, 2, 5, "#f2ead6"); P.px(cx, y + 2, "#ffb84a"); }
  },
  stool(P, x, y) { 
    P.rect(x + 5, y + 11, 1, 3, "#5a3a22"); P.rect(x + 10, y + 11, 1, 3, "#5a3a22"); P.rect(x + 8, y + 12, 1, 2, "#4e3018");
    for (let j = 0; j < 6; j++) for (let i = 0; i < 8; i++) if ((i - 3.5) ** 2 / 16 + (j - 2.5) ** 2 / 9 <= 1) P.px(x + 4 + i, y + 5 + j, j < 2 ? "#c89a66" : j < 4 ? "#a8784a" : "#7a5232");
  },
  chair(P, x, y) { 
    box(P, x + 3, y + 1, 10, 6, "#6a4428"); P.rect(x + 5, y + 2, 1, 4, "#8a5a36"); P.rect(x + 8, y + 2, 1, 4, "#8a5a36"); P.rect(x + 4, y + 2, 8, 1, "#9a6a42");
    box(P, x + 3, y + 7, 10, 6, "#8a5a32"); P.rect(x + 4, y + 8, 8, 2, "#b8854e");
    P.rect(x + 4, y + 13, 1, 2, "#4e3018"); P.rect(x + 11, y + 13, 1, 2, "#4e3018");
  },
  rug(P, x, y, w, h) { 
    P.rect(x + 2, y + 2, w - 4, h - 4, "#7a2a32"); P.rect(x + 4, y + 4, w - 8, h - 8, "#b8604a"); P.rect(x + 5, y + 5, w - 10, h - 10, "#c8784e");
    const cx = x + w / 2, cy = y + h / 2, R = Math.min(w, h) / 2 - 7;
    for (let j = -R; j <= R; j++) for (let i = -R * 1.6; i <= R * 1.6; i++) if (Math.abs(i) / 1.6 + Math.abs(j) <= R) P.px(cx + i, cy + j, Math.abs(i) / 1.6 + Math.abs(j) > R - 2 ? "#e8b84a" : "#7a2a32");
    for (let i = x + 4; i < x + w - 4; i += 4) { P.px(i, y + 3, "#e8b84a"); P.px(i + 2, y + h - 4, "#e8b84a"); }
    for (let i = x + 3; i < x + w - 3; i += 2) { P.px(i, y + 1, "#e8dcc0"); P.px(i, y + h - 2, "#e8dcc0"); }
  },
  runner(P, x, y, w, h) { P.rect(x + 4, y, w - 8, h, "#7a2a3a"); P.rect(x + 6, y, 1, h, "#c8a040"); P.rect(x + w - 7, y, 1, h, "#c8a040"); },
  plant(P, x, y) { 
    P.rect(x + 4, y + 9, 8, 6, "#b8603e"); P.rect(x + 3, y + 9, 10, 2, "#d07a52"); P.rect(x + 4, y + 13, 8, 2, "#8a4a30"); P.rect(x + 5, y + 11, 1, 2, "#e09a72");
    for (const [dx, dy, c] of [[8, 1, "#4f8a3c"], [4, 4, "#3e7432"], [11, 3, "#4f8a3c"], [6, 6, "#5d9e47"], [10, 6, "#3e7432"], [7, 3, "#73b456"]]) { P.rect(x + dx - 1, y + dy, 3, 4, c); P.px(x + dx - 1, y + dy, "#93cc6c"); }
  },
  barrels(P, x, y, w, h) {
    for (let j = 0; j < h / T; j++) for (let i = 0; i < w / T; i++) FURNITURE.barrel(P, x + i * T, y + j * T);
  },
  barrel(P, x, y) { 
    box(P, x + 2, y + 1, 12, 14, "#8a5a32");
    for (let i = x + 4; i < x + 13; i += 3) P.rect(i, y + 2, 1, 12, "#6e4626");
    P.rect(x + 3, y + 2, 2, 12, "#a8784a");
    P.rect(x + 3, y + 4, 10, 1, "#3a3a40"); P.rect(x + 3, y + 11, 10, 1, "#3a3a40"); P.rect(x + 3, y + 4, 2, 1, "#7a7a84"); P.rect(x + 3, y + 11, 2, 1, "#7a7a84");
    P.rect(x + 3, y + 2, 10, 1, "#b8854e");
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
  altar(P, x, y, w, h) { 
    box(P, x, y, w, h + 3, "#e2dacb"); P.rect(x + 1, y + 1, w - 2, 2, "#f2ece0");
    P.rect(x + 1, y + 3, w - 2, 6, "#8a2a3a"); P.rect(x + 1, y + 3, w - 2, 1, "#a83a4a"); P.rect(x + 1, y + 8, w - 2, 1, "#e8c860");
    for (let i = x + 3; i < x + w - 3; i += 4) P.px(i, y + 9, "#e8c860");
    P.rect(x + w / 2 - 1, y - 4, 2, 9, "#e8c860"); P.rect(x + w / 2 - 3, y - 2, 6, 2, "#e8c860"); P.px(x + w / 2 - 1, y - 4, "#fff6c8");
    P.rect(x + 6, y + 1, 7, 3, "#f6efe0"); P.rect(x + 9, y + 1, 1, 3, "#c8b898");
  },
  candle(P, x, y) { P.rect(x + 6, y + 6, 4, 9, "#f2ead6"); P.rect(x + 7, y + 3, 2, 3, "#ffb84a"); P.rect(x + 5, y + 14, 6, 2, "#c8a040"); },
  pew(P, x, y, w, h) { 
    box(P, x, y + 1, w, 5, "#6a4428"); P.rect(x + 1, y + 2, w - 2, 1, "#8a5a36");
    box(P, x, y + 6, w, h - 3, "#7a5232"); P.rect(x + 1, y + 7, w - 2, 3, "#a87a4a"); P.rect(x + 1, y + 7, w - 2, 1, "#c89a66");
    P.rect(x, y + 1, 2, h + 2, "#5a3a22"); P.rect(x + w - 2, y + 1, 2, h + 2, "#5a3a22");
  },
  chalk(P, x, y, w, h) {
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
    P.rect(x, y + 2, w, 2, "#6a4428"); P.rect(x, y + 2, w, 1, "#8a5a36"); P.rect(x, y + 11, w, 2, "#6a4428");
    for (let i = x + 4, k = 0; i < x + w - 4; i += 7, k++) {
      if (k % 3 === 0) { P.rect(i, y + 3, 1, 11, "#8a9098"); P.rect(i + 2, y + 3, 1, 11, "#8a9098"); P.rect(i, y + 3, 3, 1, "#b8c0c8"); }
      else if (k % 3 === 1) { P.rect(i + 1, y + 6, 1, 8, "#7a5232"); P.rect(i - 1, y + 4, 5, 3, "#5a5a62"); P.rect(i - 1, y + 4, 5, 1, "#8a8a92"); }
      else { P.rect(i + 1, y + 2, 2, 10, "#c8d0d8"); P.rect(i + 1, y + 2, 1, 10, "#eef2f6"); P.rect(i, y + 11, 4, 1, "#6a4428"); P.rect(i + 1, y + 12, 2, 2, "#6a4428"); }
    }
  },
  anvil(P, x, y, w) { 
    P.rect(x + 8, y + 10, w - 16, 5, "#6a4428"); P.rect(x + 8, y + 10, 2, 5, "#8a5a36");
    P.rect(x + 3, y + 3, w - 6, 6, OUT); P.rect(x + 4, y + 4, w - 8, 4, "#4a4a52"); P.rect(x + 4, y + 4, w - 8, 1, "#9a9aa4");
    P.rect(x + 1, y + 4, 4, 2, "#4a4a52"); P.px(x, y + 5, "#4a4a52"); P.rect(x + 10, y + 8, w - 20, 3, "#3a3a40");
  },
  coal(P, x, y, w, h) { 
    box(P, x + 1, y + 4, w - 2, h - 5, "#6a4428"); P.rect(x + 2, y + 5, w - 4, 1, "#8a5a36");
    for (let j = 0; j < h - 9; j++) for (let i = 0; i < w - 6; i++) {
      const hump = Math.sin((i / (w - 6)) * Math.PI) * 4;
      if (j < 3 - hump + (h - 12)) P.px(x + 3 + i, y + 6 + j, (i * 7 + j * 3) % 5 === 0 ? "#5a5a62" : (i + j) % 3 ? "#2a2a2e" : "#3a3a40");
    }
    for (let i = x + 2; i < x + w - 2; i += 6) P.rect(i, y + 6, 1, h - 7, "#5a3a22");
  },
  bench(P, x, y, w, h) { 
    P.rect(x + 2, y + h + 1, 2, 3, "#4e3018"); P.rect(x + w - 4, y + h + 1, 2, 3, "#4e3018");
    box(P, x, y + 2, w, h + 1, "#7a5a3a"); P.rect(x + 1, y + 3, w - 2, 2, "#9a7448"); P.rect(x + 1, y + h + 1, w - 2, 1, "#5a3a22");
    P.rect(x + 4, y + 5, 7, 2, "#8a9098"); P.rect(x + 4, y + 5, 7, 1, "#c8d0d8"); 
    for (let a = 0; a < 14; a++) { const ang = Math.PI * (0.1 + (a / 14) * 1.8); P.px(x + 18 + Math.cos(ang) * 3, y + 9 - Math.sin(ang) * 3, "#9a9aa0"); } 
    P.rect(x + w - 10, y + 3, 6, 5, "#3a3a40"); P.rect(x + w - 10, y + 3, 6, 1, "#6a6a72"); P.rect(x + w - 8, y + 8, 2, 3, "#3a3a40"); 
  },
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
  const pick = (a) => a[Math.floor(r() * a.length)];
  if (room.floor === "wood") { 
    const tones = ["#b8875a", "#b0804f", "#bf9062", "#a97a4c", "#b48454"];
    for (let y = 0; y < H; y += 6) {
      for (let x = -Math.floor(r() * 30); x < W;) {
        const len = 22 + Math.floor(r() * 26), c = pick(tones);
        P.rect(x, y, len, 6, c);
        P.rect(x, y, len, 1, shade(c, 0.05));
        for (let g = 0; g < 3; g++) P.rect(x + 3 + r() * (len - 10), y + 2 + Math.floor(r() * 3), 3 + r() * 6, 1, shade(c, -0.06));
        P.rect(x + len - 1, y, 1, 6, "#7a5232");
        P.px(x + 2, y + 3, "#6a4428"); P.px(x + len - 3, y + 3, "#6a4428");
        x += len;
      }
      P.rect(0, y + 5, W, 1, "#8a5c38");
    }
  } else if (room.floor === "stone") { 
    P.rect(0, 0, W, H, "#77716a");
    for (let y = 0, row = 0; y < H; y += 11, row++) for (let x = -(row % 2) * 9; x < W;) {
      const w = 14 + Math.floor(r() * 10), c = pick(["#aaa498", "#b4aea2", "#9e988c", "#a49e92", "#bab4a8"]);
      P.rect(x + 1, y + 1, w - 1, 10, c);
      P.rect(x + 1, y + 1, w - 1, 1, shade(c, 0.07)); P.rect(x + 1, y + 1, 1, 10, shade(c, 0.05));
      P.rect(x + 1, y + 10, w - 1, 1, shade(c, -0.08));
      if (r() < 0.25) P.rect(x + 3 + r() * (w - 8), y + 3 + r() * 5, 3, 1, shade(c, -0.1)); 
      x += w;
    }
  } else { 
    P.rect(0, 0, W, H, "#8a7258");
    for (let i = 0; i < W * H * 0.08; i++) P.px(r() * W, r() * H, pick(["#7a6248", "#9a8268", "#836b51"]));
    for (let i = 0; i < W * H * 0.0012; i++) { const x = r() * W, y = r() * H; P.rect(x, y, 2 + r() * 3, 1, pick(["#b8a060", "#a89050"])); }
  }
  for (let k = 0; k < 6; k++) P.rect(0, 2 * T + k, W, 1, `rgba(30,20,10,${0.3 - k * 0.05})`);
  for (let k = 0; k < 5; k++) { P.rect(3 + k, 2 * T, 1, H - 2 * T, `rgba(30,20,10,${0.2 - k * 0.04})`); P.rect(W - 4 - k, 2 * T, 1, H - 2 * T, `rgba(30,20,10,${0.2 - k * 0.04})`); }

  const wainY = 2 * T - 12;
  P.rect(0, 0, W, wainY, room.wall);
  for (let x = 0; x < W; x += 8) { P.rect(x, 0, 1, wainY, shade(room.wall, -0.05)); if ((x / 8) % 2 === 0) for (let y = 4; y < wainY; y += 8) P.px(x + 4, y, shade(room.wall, -0.08)); }
  P.rect(0, 0, W, 2, shade(room.wall, -0.15)); 
  P.rect(0, wainY, W, 2, shade(room.trim, 0.15)); P.rect(0, wainY + 2, W, 10, shade(room.trim, 0.05));
  for (let x = 4; x < W - 10; x += 14) { P.rect(x, wainY + 4, 10, 6, shade(room.trim, -0.06)); P.rect(x, wainY + 4, 10, 1, shade(room.trim, -0.14)); P.rect(x, wainY + 9, 10, 1, shade(room.trim, 0.12)); }
  P.rect(0, 2 * T - 2, W, 2, shade(room.trim, -0.12));
  for (const f of [0.25, 0.75]) {
    const wx = Math.round(W * f) - 6;
    if (room.furniture.some(([k, fx, , fw]) => ["glass", "banner", "gears", "herbs"].includes(k) && Math.abs(fx * T + (fw * T) / 2 - (wx + 6)) < 20)) continue;
    P.ctx.fillStyle = "rgba(255,240,200,0.06)";
    P.ctx.beginPath(); P.ctx.moveTo(wx, 2 * T); P.ctx.lineTo(wx + 12, 2 * T); P.ctx.lineTo(wx + 30, 2 * T + 34); P.ctx.lineTo(wx + 14, 2 * T + 34); P.ctx.fill();
    P.rect(wx - 1, 3, 14, 15, room.trim); P.rect(wx, 4, 12, 13, "#bfe0f0"); P.rect(wx, 4, 12, 5, "#e6f4fa");
    P.rect(wx + 6, 4, 1, 13, room.trim); P.rect(wx, 10, 12, 1, room.trim); P.px(wx + 2, 5, "#ffffff"); P.px(wx + 3, 6, "#ffffff");
    P.rect(wx - 2, 17, 16, 2, shade(room.trim, 0.2)); 
    P.rect(wx - 5, 2, 20, 2, "#5a3a22"); 
    for (const cx of [wx - 4, wx + 12]) { P.rect(cx, 3, 4, 15, "#9a3a3a"); P.rect(cx + 1, 3, 1, 15, "#b8504a"); P.rect(cx + 3, 3, 1, 15, "#7a2a2a"); }
  }
  P.rect(0, 0, 4, H, room.trim); P.rect(3, 2 * T, 1, H - 2 * T, shade(room.trim, 0.18));
  P.rect(W - 4, 0, 4, H, room.trim); P.rect(W - 4, 2 * T, 1, H - 2 * T, shade(room.trim, -0.12));
  P.rect(0, H - 5, W, 5, room.trim); P.rect(0, H - 5, W, 1, shade(room.trim, 0.18));
  const dx = W / 2 - T;
  P.rect(dx, H - 5, 2 * T, 5, "#2b1d14");
  P.rect(dx + 2, H - 13, 2 * T - 4, 8, "#7a5a3a"); P.rect(dx + 4, H - 11, 2 * T - 8, 4, "#9a7a4a");
  for (let i = dx + 3; i < dx + 2 * T - 3; i += 2) P.px(i, H - 6, "#c8a878");

  const solids = [], glows = [];
  const FLAT = new Set(["rug", "runner", "chalk", "sidedoor", "banner", "glass", "gears", "herbs"]);
  for (const [kind, fx, fy, fw, fh] of room.furniture) { 
    if (FLAT.has(kind)) continue;
    const x = fx * T, y = fy * T, w = fw * T, h = fh * T;
    P.rect(x + 3, y + h, w - 2, 3, "rgba(40,25,10,0.28)"); P.rect(x + w - 1, y + 5, 2, h - 3, "rgba(40,25,10,0.2)");
  }
  for (const [kind, fx, fy, fw, fh, solid] of room.furniture) {
    const x = fx * T, y = fy * T, w = fw * T, h = fh * T;
    FURNITURE[kind]?.(P, x, y, w, h);
    if (solid) solids.push([x + 1, y + (kind === "counter" || kind.startsWith("shelf") ? 3 : 2), w - 2, h - 2]);
    if (GLOWING[kind]) glows.push({ x: x + w / 2, y: y + h / 2 + 2, scale: (3 + (w / T) * GLOWING[kind] * 2) / 4 });
  }
  register(scene, key, P.canvas);
  return { key, W, H, solids, glows };
}


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
      } else { 
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


export function makeDecor(scene) {
  const add = (key, P) => { P.outline(); register(scene, key, P.canvas); };
  let P;

  P = new Pix(14, 10); 
  P.rect(2, 3, 10, 6, "#8a8a84"); P.rect(3, 2, 7, 2, "#9a9a94"); P.rect(4, 3, 3, 2, "#b4b4ae"); P.rect(9, 6, 3, 3, "#74746e");
  add("rock", P);
  P = new Pix(10, 7); 
  P.rect(1, 2, 8, 4, "#8a8a84"); P.rect(2, 1, 4, 2, "#a4a49e");
  add("pebble", P);
  P = new Pix(14, 10); 
  P.rect(2, 3, 10, 6, "#7a5232"); P.rect(2, 2, 10, 3, "#c8a070"); P.rect(5, 3, 4, 1, "#a8804e"); P.rect(0, 8, 3, 1, "#7a5232"); P.rect(11, 8, 3, 1, "#7a5232");
  add("stump", P);
  P = new Pix(22, 18); 
  for (let y = 0; y < 15; y++) { const half = Math.min(10, 3 + y); P.rect(11 - half, 2 + y, half * 2, 1, y % 3 ? "#e0c060" : "#c8a040"); }
  for (let i = 0; i < 18; i++) P.px(3 + Math.random() * 16, 4 + Math.random() * 12, "#f2d87a");
  add("haystack", P);
  P = new Pix(14, 16); 
  P.rect(2, 1, 10, 14, "#8a5a32"); P.rect(2, 3, 10, 1, "#4a4a4a"); P.rect(2, 11, 10, 1, "#4a4a4a"); P.rect(4, 1, 1, 14, "#a8784a"); P.rect(3, 1, 8, 2, "#6a4428");
  add("barrel", P);
  P = new Pix(34, 22); 
  P.rect(2, 4, 26, 10, "#9a6a3a"); P.rect(2, 4, 26, 2, "#b8854e"); for (let x = 6; x < 28; x += 6) P.rect(x, 6, 1, 8, "#7a5030");
  P.rect(5, 1, 6, 4, "#e05a3a"); P.rect(12, 2, 5, 3, "#7ab04a"); P.rect(18, 1, 6, 4, "#f2d45a");
  P.rect(28, 9, 6, 2, "#6a4428");
  for (const cx of [8, 22]) { for (let a = 0; a < 40; a++) P.px(cx + Math.cos(a / 6.4) * 5, 16 + Math.sin(a / 6.4) * 5, "#4a2e1c"); P.rect(cx - 1, 15, 2, 2, "#4a2e1c"); }
  add("cart", P);
  P = new Pix(18, 24); 
  P.rect(8, 6, 2, 17, "#6a4428"); P.rect(1, 3, 16, 6, "#a8784a"); P.rect(14, 4, 3, 4, "#a8784a"); P.rect(3, 5, 9, 1, "#5a3a22"); P.rect(2, 11, 12, 5, "#a8784a"); P.rect(4, 13, 7, 1, "#5a3a22");
  add("sign", P);
  P = new Pix(16, 12); 
  P.rect(1, 2, 2, 10, "#8a6038"); P.rect(13, 2, 2, 10, "#8a6038"); P.rect(0, 4, 16, 2, "#a8784a"); P.rect(0, 8, 16, 2, "#a8784a"); P.rect(1, 1, 2, 1, "#a8784a"); P.rect(13, 1, 2, 1, "#a8784a");
  add("fence", P);
  P = new Pix(16, 12); 
  for (const [x, hgt, c] of [[2, 7, "#5f9443"], [4, 10, "#6fa850"], [6, 8, "#5f9443"], [8, 11, "#7ab85a"], [10, 7, "#5f9443"], [12, 9, "#6fa850"]]) P.rect(x, 12 - hgt, 2, hgt, c);
  register(scene, "tallgrass", P.canvas);
  P = new Pix(10, 10); 
  P.rect(2, 2, 6, 3, "#c0443a"); P.rect(3, 1, 4, 1, "#c0443a"); P.rect(3, 2, 1, 1, "#f6efe0"); P.rect(6, 3, 1, 1, "#f6efe0"); P.rect(4, 5, 2, 3, "#f2ead6");
  add("mushroom", P);
  P = new Pix(30, 34); 
  groundShadow(P, 15, 31, 10, 2);
  P.rect(13, 24, 4, 8, "#6a4428"); P.rect(13, 24, 1, 8, "#8a5a36"); P.rect(16, 24, 1, 8, "#4e3018");
  const PINE = ["#1f4a2a", "#2a5e34", "#36723e", "#468a4a", "#5aa05a"];
  for (const [t0, hw] of [[16, 14], [11, 12], [6, 10], [1, 7]]) for (let j = 0; j < 10; j++) {
    const half = Math.round(1 + ((hw - 1) * j) / 9);
    for (let x = -half; x <= half; x++) {
      if (j === 9 && (x + t0) % 3 === 0) continue;
      const lit = x < -half * 0.45 ? 4 : x < 0 ? 3 : x < half * 0.5 ? 2 : j > 6 ? 0 : 1;
      P.px(15 + x, t0 + j, PINE[lit]);
    }
  }
  P.px(15, 0, "#5aa05a");
  add("pine", P);
  P = new Pix(22, 14); 
  P.rect(1, 3, 20, 2, "#a8784a"); P.rect(1, 3, 20, 1, "#c09060"); 
  P.rect(1, 7, 20, 3, "#a8784a"); P.rect(1, 7, 20, 1, "#c8986a"); P.rect(1, 9, 20, 1, "#7a5232"); 
  for (const x of [2, 18]) { P.rect(x, 1, 2, 12, "#3a3a40"); P.rect(x, 1, 2, 1, "#5a5a62"); }
  add("bench", P);
  P = new Pix(16, 16); 
  P.rect(1, 8, 14, 7, "#a8a090"); P.rect(1, 8, 14, 1, "#c8c0b0"); P.rect(1, 13, 14, 2, "#8a8274"); P.rect(3, 10, 10, 1, "#968e7e");
  for (let y = 0; y < 6; y++) for (let x = 0; x < 12; x++) if ((x - 6) ** 2 / 36 + (y - 5) ** 2 / 25 <= 1) P.px(2 + x, 3 + y, (x + y) % 3 ? "#4f8a3c" : "#5fa046");
  for (const [x, y, c] of [[4, 4, "#e86a8a"], [8, 3, "#f2d45a"], [11, 5, "#e86a8a"], [6, 6, "#ffffff"], [10, 7, "#b07ad8"], [3, 7, "#f2d45a"]]) { P.px(x, y, c); P.px(x + 1, y, c); }
  add("planter", P);
}

export function makeBunting(scene, key, w, sag = 12) {
  const P = new Pix(w, sag + 10);
  const colors = ["#c0443a", "#f2d45a", "#4f7ac0", "#5fa046", "#f6efe0"];
  const yAt = (x) => 1 + Math.round(sag * 4 * (x / w) * (1 - x / w));
  for (let x = 0; x < w; x++) P.px(x, yAt(x), "#4a3a2a");
  for (let x = 4, k = 0; x + 5 < w; x += 9, k++) {
    const y0 = yAt(x + 3) + 1, c = colors[k % colors.length];
    for (let j = 0; j < 6; j++) { const half = Math.max(0, 3 - Math.floor(j / 2)); P.rect(x + 3 - half, y0 + j, half * 2 + 1, 1, j === 0 ? shade(c, -0.15) : c); }
  }
  register(scene, key, P.canvas);
}

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
      for (let i = 0; i < 6; i++) { const bx = x + r() * 14, by = y + r() * 10; px(bx, by, "#58893a"); px(bx, by - 1, "#6c9c46"); px(bx, by - 2, "#a8d676"); }
    } else if (kind === "dirt") { 
      const w = 6 + r() * 6, h = 3 + r() * 3;
      for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
        const e = ((i - w / 2) / (w / 2)) ** 2 + ((j - h / 2) / (h / 2)) ** 2;
        if (e < 0.55 || (e < 1 && (i + j) % 2)) px(x + i, y + j, e < 0.3 ? "#b8945c" : "#a88650");
      }
    } else if (kind === "pebbles") {
      for (let i = 0; i < 3; i++) px(x + r() * 10, y + r() * 8, "#a8a29a");
    }
  }
  tex.refresh();
}

export function paintPond(scene, key, [tx, ty, tw, th]) {
  const tex = scene.textures.get(key);
  const ctx = tex.getSourceImage().getContext("2d");
  const px = (x, y, c) => { ctx.fillStyle = c; ctx.fillRect(x | 0, y | 0, 1, 1); };
  const r = rng(771);
  const B4 = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
  const cx = (tx + tw / 2) * T, cy = (ty + th / 2) * T, rx = (tw * T) / 2 - 2, ry = (th * T) / 2 - 2;
  const shore = (a) => 1 + 0.07 * Math.sin(a * 3 + 1) + 0.05 * Math.sin(a * 5 + 2.5) + 0.03 * Math.sin(a * 9);
  for (let y = -ry - 5; y <= ry + 5; y++) for (let x = -rx - 5; x <= rx + 5; x++) {
    const a = Math.atan2(y / ry, x / rx), d = Math.hypot(x / rx, y / ry) / shore(a);
    const X = Math.round(cx + x), Y = Math.round(cy + y), dd = d + (B4[(Y & 3) * 4 + (X & 3)] / 16 - 0.5) * 0.06;
    if (d > 1.13) continue;
    if (d > 1.04) { px(X, Y, dd > 1.09 ? "#8aa860" : "#d2bd88"); continue; } 
    if (dd > 0.93) { px(X, Y, "#79b8dc"); continue; }
    if (dd > 0.7) { px(X, Y, "#5a9ccc"); continue; }
    px(X, Y, dd > 0.42 ? "#4888bf" : "#3a76ad");
  }
  for (let i = 0; i < 26; i++) {
    const a = -2.4 + r() * 1.3, k = 0.45 + r() * 0.35;
    ctx.fillStyle = "#a6d4ee"; ctx.fillRect(cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k, 2 + r() * 3, 1);
  }
  ctx.fillStyle = "#8ac4e8"; for (let i = 0; i < 8; i++) ctx.fillRect(cx - rx * 0.4 + i * 7, cy + 2 + (i % 3) * 4, 3, 1);
  for (let i = 0; i < 14; i++) {
    const a = r() * Math.PI * 2, X = cx + Math.cos(a) * rx * shore(a) * 1.06, Y = cy + Math.sin(a) * ry * shore(a) * 1.06;
    px(X, Y, "#8f8a80"); px(X + 1, Y, "#8f8a80"); px(X, Y - 1, "#c9c3b5"); px(X + 1, Y + 1, "#6e695f");
  }
  for (const [a0, n] of [[0.15, 7], [2.5, 6], [-0.5, 4]]) for (let i = 0; i < n; i++) {
    const a = a0 + (i - n / 2) * 0.06, X = Math.round(cx + Math.cos(a) * rx * 0.98), Y = Math.round(cy + Math.sin(a) * ry * 0.98), hgt = 5 + Math.floor(r() * 5);
    for (let k = 0; k < hgt; k++) px(X + (k > hgt - 3 ? (i % 2 ? 1 : 0) : 0), Y - k, k % 3 ? "#5f8a3a" : "#4a7430");
    if (i % 2 === 0) { px(X, Y - hgt, "#6a4428"); px(X, Y - hgt - 1, "#6a4428"); px(X, Y - hgt - 2, "#8a5a36"); }
  }
  for (const [dx, dy, flower] of [[-16, -5, false], [9, 5, true], [18, -7, false], [-5, 9, false]]) {
    const X = cx + dx, Y = cy + dy;
    for (let j = -2; j <= 2; j++) for (let i = -3; i <= 3; i++) if (i * i / 9 + j * j / 4 <= 1 && !(i > 0 && j === 0)) px(X + i, Y + j, i + j < -1 ? "#7cc060" : "#5fa046");
    px(X - 1, Y + 2, "#3e7432");
    if (flower) { px(X - 1, Y - 1, "#f6c8d8"); px(X, Y - 2, "#f2a8c0"); px(X + 1, Y - 1, "#f6c8d8"); px(X, Y - 1, "#f2d45a"); }
  }
  tex.refresh();
}
