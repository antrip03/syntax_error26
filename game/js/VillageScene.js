// The walkable village (Phaser 4, Arcade Physics, top-down). Renders Vaudville and its interiors,
// moves the detective, runs villager / townsfolk / animal wander behaviour, keeps the day clock and
// lighting, and plays the evening-gossip and rumour visuals. It reports player intent ("talk",
// "inspect", "area") on the bus; the DOM UI owns everything text-heavy.

import { TILE, CHAR_H, makeCharacter, makeBuilding, makeGround, makeProps, lookFor, rng, hash } from "./art.js";
import { makeRoom, makeAnimal, makeDecor, paintGroundDetails, paintPond, makeChalk, makeBunting } from "./art_extra.js";
import { MAP, ROLE_HOME, FALLBACK_HOMES, ROOMS, EXTRAS, ANIMALS, SMALL_TALK, OUTDOOR_SPOTS } from "./map.js";
import { emit, on } from "./store.js";

const W = MAP.cols * TILE, H = MAP.rows * TILE;
const PLAYER_SPEED = 92, NPC_SPEED = 30, TALK_RANGE = 31;
const PHASES = { dusk: [0xff8a45, 0.95], night: [0x3c4280, 0.95] }; // multiply tints for gossip / night
const RUMOUR_TINT = { red: 0xff7a7a, amber: 0xffd27a, plain: 0xffffff };
const RUMOUR_RING = { red: 0xe0453a, amber: 0xf0a830, plain: 0x9aa0a6 };
// colour of a travelling word, by seal (gossip) or rumour state
const WORD_TINT = { supported: 0x5fd06a, unsupported: 0xff5a4a, abstained: 0xb8b4ac, red: 0xff5a4a, amber: 0xffc040, neutral: 0xfff0b0 };
// Day clock (cosmetic): 08:00 -> 19:00 sunset, about 9 real minutes plus 20 minutes per question.
export const DAY_START = 8 * 60, SUNSET = 19 * 60;
const CLOCK_RATE = 2.75; // game minutes per real second: a full day in about 4 real minutes (plus 45 per question)
export const ASK_MINUTES = 45; // each question moves the clock this much
// Parts of the day, by hour: name and the line announced when it begins.
export const DAYPARTS = [
  [8, "Morning", "Morning light over Vaudville."],
  [10.5, "Midday", "The sun is high."],
  [14, "Afternoon", "Afternoon. Shadows start to lengthen."],
  [16.5, "Late afternoon", "The sun is getting low."],
  [18, "Evening", "Evening falls. The lamps are lit."],
];
export function daypart(min) {
  const h = min / 60;
  let cur = DAYPARTS[0];
  for (const d of DAYPARTS) if (h >= d[0]) cur = d;
  return cur;
}
const ROOM_Y = H + 8 * TILE, ROOM_GAP = 12 * TILE;

const sleep = (scene, ms) => new Promise((r) => scene.time.delayedCall(ms, r));
const strip = (t) => t.replace(/\s*\[[A-Z]\d+(\.S\d+)?\]/g, "").replace(/<[^>]+>/g, "").trim();
const lerp = (a, b, t) => a + (b - a) * t;
const mixColor = (c1, c2, t) => {
  const ch = (c, s) => (c >> s) & 255;
  return (Math.round(lerp(ch(c1, 16), ch(c2, 16), t)) << 16) | (Math.round(lerp(ch(c1, 8), ch(c2, 8), t)) << 8) | Math.round(lerp(ch(c1, 0), ch(c2, 0), t));
};

// Ambient light for a clock time: [color, alpha, lampLevel].
// Multiply tints (white = no change): pale gold morning, clear midday, bright golden-yellow afternoon,
// deep amber low sun, orange evening, violet dusk with the lamps lit.
const LIGHT = [ // [hour, color, strength, lamps]
  [8, 0xffe2a8, 0.9, 0], [10, 0xfff3d6, 0.6, 0], [11, 0xffffff, 0, 0], [13.5, 0xffffff, 0, 0],
  [15, 0xffd45c, 0.85, 0], [16.5, 0xffb048, 0.95, 0], [17.7, 0xff8a45, 1, 0.3], [19, 0x9070b8, 1, 1],
];
function ambient(min) {
  const h = Math.max(LIGHT[0][0], Math.min(LIGHT[LIGHT.length - 1][0], min / 60));
  let i = 0;
  while (i < LIGHT.length - 2 && h >= LIGHT[i + 1][0]) i++;
  const [h0, c0, a0, l0] = LIGHT[i], [h1, c1, a1, l1] = LIGHT[i + 1];
  const t = Math.min(1, Math.max(0, (h - h0) / (h1 - h0)));
  return [mixColor(c0, c1, t), lerp(a0, a1, t), lerp(l0, l1, t)];
}

export function clockLabel(min) {
  const h = Math.floor(min / 60), m = Math.floor(min % 60);
  return `${String(h).padStart(2, "0")}:${String(m - (m % 5)).padStart(2, "0")}`;
}

export class VillageScene extends Phaser.Scene {
  constructor() { super("village"); }

  init() {
    this.npcs = new Map(); // case villagers
    this.actors = new Map(); // case villagers + townsfolk + animals
    this.blocked = false;
    this.mode = "attract";
    this.moveTarget = null;
    this.talkingTo = null;
    this.bubbles = [];
    this.fx = new Set(); // travelling words in flight
    this.rumourRun = 0;
    this.viewInset = {}; // screen px covered by DOM panels, for framing close-ups
    this.facing = "down";
    this.nearest = null;
    this.area = "village";
    this.transitioning = false;
    this.clock = DAY_START + 120;
    this.phase = null;
    this.victimName = "the victim";
    this.talkIdx = {};
  }

  create() {
    // Road spurs from each door down to the next lane.
    const lanes = MAP.roads.filter((r) => r[2] > 10);
    const roads = [...MAP.roads];
    for (const b of MAP.buildings) {
      const bottom = b.y + b.h;
      const lane = lanes.filter((r) => r[1] >= bottom).sort((a, c) => a[1] - c[1])[0];
      if (lane) roads.push([b.x + Math.floor(b.w / 2) - 1, bottom, 2, lane[1] - bottom]);
    }
    makeGround(this, "ground", { ...MAP, roads });
    paintPond(this, "ground", MAP.pond);
    makeProps(this);
    makeDecor(this);
    this.add.image(0, 0, "ground").setOrigin(0).setDepth(-10000);

    this.solids = [];
    const solid = (x, y, w, h) => {
      const z = this.add.zone(x + w / 2, y + h / 2, w, h);
      this.physics.add.existing(z, true);
      this.solids.push(z);
    };
    // river (except the bridge) and the pond
    const [bx, bw] = MAP.bridge, ry = MAP.river.y * TILE, rh = MAP.river.h * TILE;
    solid(0, ry - 2, bx * TILE, rh + 4);
    solid((bx + bw) * TILE, ry - 2, W - (bx + bw) * TILE, rh + 4);
    solid(W, 0, 16, H); solid(0, H, W, 16); // village edges (the world also holds the rooms)
    const [pdx, pdy, pdw, pdh] = MAP.pond;
    solid(pdx * TILE + 6, pdy * TILE + 6, pdw * TILE - 12, pdh * TILE - 12);

    // occupancy grid so scattered decor never lands on roads, doors or props
    const occ = Array.from({ length: MAP.rows }, () => new Array(MAP.cols).fill(false));
    const mark = (x, y, w = 1, h = 1) => {
      for (let j = Math.floor(y); j < Math.ceil(y + h); j++) for (let i = Math.floor(x); i < Math.ceil(x + w); i++)
        if (occ[j] && i >= 0 && i < MAP.cols) occ[j][i] = true;
    };
    roads.forEach((r) => mark(...r));
    this.roadGrid = occ.map((row) => row.slice()); // before props are marked: true = road or plaza
    mark(...MAP.plaza);
    { const [x0, y0, w0, h0] = MAP.plaza; for (let j = y0; j < y0 + h0; j++) for (let i = x0; i < x0 + w0; i++) this.roadGrid[j][i] = "stone"; }
    MAP.gardens.forEach((g) => mark(...g)); mark(MAP.pond[0] - 1, MAP.pond[1] - 1, MAP.pond[2] + 2, MAP.pond[3] + 2);
    mark(0, MAP.river.y - 1, MAP.cols, MAP.river.h + 2);

    this.places = {};
    this.doors = [];
    this.glows = [];
    for (const b of MAP.buildings) {
      const { key, extraTop } = makeBuilding(this, `bld_${b.id}`, b.kind, b.w, b.h);
      const x = b.x * TILE, y = b.y * TILE, w = b.w * TILE, h = b.h * TILE;
      this.add.image(x - 1, y - 1 - extraTop, key).setOrigin(0).setDepth(y + h);
      solid(x + 2, y + h * 0.35, w - 4, h * 0.65 - 2);
      mark(b.x, b.y - 1, b.w, b.h + 3);
      const door = { x: x + w / 2, y: y + h + 10 };
      this.places[b.id] = door;
      this.doors.push({ id: b.id, x: x + w / 2, y: y + h + 3, label: b.label || "this house", enterable: !!ROOMS[b.id] });
      if (b.label) {
        this.add.text(x + w / 2, y + 3, b.label, this.textStyle(7, "#fff8e8"))
          .setOrigin(0.5, 0).setDepth(y + h + 1).setStroke("#2b1d14", 3).setResolution(4);
      }
      if (ROOMS[b.id]) {
        (this.residentTags ||= {})[b.id] = this.add.text(x + w / 2, y + 13, "", this.textStyle(6, "#ffe27a"))
          .setOrigin(0.5, 0).setDepth(y + h + 1).setStroke("#2b1d14", 3).setResolution(4).setVisible(false);
      }
    }
    const [px, py, pw, ph] = MAP.plaza;
    this.places.plaza = { x: (px + pw / 2) * TILE, y: (py + ph / 2) * TILE + 20 };

    const prop = (key, tx, ty, body) => {
      const img = this.add.image(tx * TILE + 8, ty * TILE + 16, key).setOrigin(0.5, 1);
      img.setDepth(img.y);
      if (body) solid(img.x - body[0] / 2, img.y - body[1], body[0], body[1]);
      return img;
    };
    const markProp = (x, y, w = 1) => mark(x - 0.5, y - 0.5, w + 1, 2);
    MAP.trees.forEach(([x, y]) => { prop("tree", x, y, [8, 5]); markProp(x, y); });
    MAP.bushes.forEach(([x, y]) => { prop("bush", x, y, [12, 5]); markProp(x, y); });
    MAP.stalls.forEach(([x, y, k]) => { prop(k, x, y, [30, 10]); markProp(x - 1, y, 3); });
    MAP.crates.forEach(([x, y]) => { prop("crate", x, y, [12, 8]); markProp(x, y); });
    MAP.haystacks.forEach(([x, y]) => { prop("haystack", x, y, [18, 8]); markProp(x, y); });
    MAP.barrels.forEach(([x, y]) => { prop("barrel", x, y, [12, 8]); markProp(x, y); });
    MAP.carts.forEach(([x, y]) => { prop("cart", x, y, [30, 10]); markProp(x - 1, y, 3); });
    MAP.signs.forEach(([x, y]) => { prop("sign", x, y, [4, 4]); markProp(x, y); });
    MAP.fences.forEach(([x, y, n]) => { for (let i = 0; i < n; i++) prop("fence", x + i, y, [16, 5]); markProp(x, y, n); });
    prop("well", MAP.well[0], MAP.well[1], [20, 10]);
    MAP.benches.forEach(([x, y]) => { prop("bench", x, y); markProp(x, y); });
    MAP.planters.forEach(([x, y]) => { prop("planter", x, y, [12, 5]); markProp(x, y); });
    MAP.bunting.forEach(([x1, y1, x2, sag], i) => {
      makeBunting(this, `bunting${i}`, x2 - x1, sag);
      this.add.image(x1, y1, `bunting${i}`).setOrigin(0).setDepth(8990); // above walkers, under the light overlay
    });
    MAP.lamps.forEach(([x, y]) => {
      const l = prop("lamp", x, y);
      markProp(x, y);
      this.glows.push(this.add.image(l.x, l.y - 22, "glow").setScale(1.75).setAlpha(0).setBlendMode(Phaser.BlendModes.ADD).setDepth(9001));
    });
    for (const e of [...EXTRAS, ...ANIMALS]) if (!e.area || e.area === "village") mark(e.at[0] - 1, e.at[1] - 1, 2, 2);
    this.scatterDecor(occ, prop);

    // The crime scene is placed per case (setCrimeScene); nothing is marked until a case starts.
    this.inspects = [];
    this.crimeObjs = [];

    this.buildRooms(solid);

    // Player
    makeCharacter(this, "char_player", lookFor("player", "detective"));
    this.player = this.physics.add.sprite(this.places.plaza.x, this.places.plaza.y + 30, "char_player", "up-0").setOrigin(0.5, 1);
    this.player.body.setSize(10, 6).setOffset(3, 15);
    this.player.setVisible(false).setCollideWorldBounds(true);
    // footsteps on the two stepping frames of the walk cycle
    this.player.on("animationupdate", (_anim, frame) => {
      if (this.mode !== "play" || !/-(1|2)$/.test(frame.textureFrame)) return;
      emit("step", this.surfaceUnder());
    });
    this.physics.add.collider(this.player, this.solids);
    this.physics.world.setBounds(0, 0, Math.max(W, this.roomsRight), ROOM_Y + 20 * TILE);

    this.ring = this.add.image(0, 0, "ring").setVisible(false).setTint(0xffe680);
    if (!this.textures.exists("word")) { // the travelling word: a soft dot with a bright core
      const wg = this.make.graphics({ x: 0, y: 0 }, false);
      wg.fillStyle(0xffffff, 0.45).fillCircle(4, 4, 4).fillStyle(0xffffff, 1).fillCircle(4, 4, 2.4);
      wg.generateTexture("word", 8, 8); wg.destroy();
    }
    this.prompt = this.add.text(0, 0, "", this.textStyle(7, "#fff8e8")).setOrigin(0.5, 1).setStroke("#2b1d14", 3).setResolution(4).setDepth(9500).setVisible(false);
    // Multiply-tinted: the whole scene takes on the colour of the light (lamps glow above it, labels stay readable).
    this.overlay = this.add.rectangle(0, 0, 10, 10, 0xffffff, 0).setOrigin(0).setScrollFactor(0).setDepth(9000)
      .setBlendMode(Phaser.BlendModes.MULTIPLY);

    this.spawnExtras();

    this.keys = this.input.keyboard.addKeys("W,A,S,D,UP,DOWN,LEFT,RIGHT,E,SPACE", false);
    this.input.on("pointerdown", (p, over) => {
      if (this.mode !== "play" || this.blocked || over.length || this.transitioning) return;
      this.moveTarget = { x: p.worldX, y: p.worldY };
    });

    this.scale.on("resize", () => this.layout());
    this.layout();

    on("ui-block", (b) => { this.blocked = b; if (b) this.moveTarget = null; });
    on("talk-open", (id) => { this.talkingTo = id; });
    on("talk-close", () => { this.talkingTo = null; });

    this.setMode("attract");
    emit("scene-ready", this);
  }

  surfaceUnder() {
    if (this.area !== "village") {
      const f = ROOMS[this.area]?.floor;
      return f === "wood" ? "wood" : f === "stone" ? "stone" : "dirt";
    }
    const tx = Math.floor(this.player.x / TILE), ty = Math.floor((this.player.y - 2) / TILE);
    if (ty >= MAP.river.y - 1 && ty <= MAP.river.y + MAP.river.h) return "wood"; // the bridge
    const c = this.roadGrid?.[ty]?.[tx];
    return c === "stone" ? "stone" : c ? "dirt" : "grass";
  }

  textStyle(size, color) {
    return { fontFamily: '"Pixelify Sans", monospace', fontSize: `${size}px`, color };
  }

  // ---------- world building ----------

  scatterDecor(occ, prop) {
    const r = rng(7331);
    const decals = [];
    for (let y = 0; y < MAP.rows; y++) for (let x = 0; x < MAP.cols; x++) {
      if (occ[y][x]) continue;
      const edge = x <= 1 || x >= MAP.cols - 2 || y >= MAP.rows - 1 || y === 0;
      const roll = r();
      if (edge && roll < 0.42 && (x + y) % 2 === 0) { prop(r() < 0.5 ? "pine" : "tree", x, y, [8, 5]); occ[y][x] = true; continue; }
      if (roll < 0.03) prop("bush", x, y, [12, 5]);
      else if (roll < 0.05) prop("rock", x, y, [10, 4]);
      else if (roll < 0.062) prop("stump", x, y, [10, 4]);
      else if (roll < 0.072) prop("mushroom", x, y);
      else if (roll < 0.075 && !edge) prop("tree", x, y, [8, 5]);
      else if (roll < 0.14) prop("tallgrass", x, y).setDepth(y * TILE + 12);
      else if (roll < 0.16) prop("pebble", x, y);
      const d = r();
      if (d < 0.09) decals.push(["flowers", x, y]);
      else if (d < 0.13 && x % 2 === 0 && y % 2 === 0) decals.push(["meadow", x, y]);
      else if (d < 0.15) decals.push(["dirt", x, y]);
      else if (d < 0.18) decals.push(["pebbles", x, y]);
    }
    paintGroundDetails(this, "ground", decals);
  }

  buildRooms(solid) {
    this.rooms = {};
    let ox = 0;
    for (const [id, room] of Object.entries(ROOMS)) {
      const art = makeRoom(this, `room_${id}`, room);
      const oy = ROOM_Y;
      this.add.image(ox, oy, art.key).setOrigin(0).setDepth(-9000);
      // walls: top, sides, and the bottom either side of the doorway
      solid(ox, oy, art.W, 2 * TILE - 2);
      solid(ox - 8, oy, 11, art.H);
      solid(ox + art.W - 3, oy, 11, art.H);
      solid(ox, oy + art.H - 4, art.W / 2 - TILE, 12);
      solid(ox + art.W / 2 + TILE, oy + art.H - 4, art.W / 2 - TILE, 12);
      for (const [x, y, w, h] of art.solids) solid(ox + x, oy + y, w, h);
      for (const g of art.glows) {
        const img = this.add.image(ox + g.x, oy + g.y, "glow").setScale(g.scale).setAlpha(0.55).setBlendMode(Phaser.BlendModes.ADD).setDepth(9001);
        this.tweens.add({ targets: img, alpha: 0.35, yoyo: true, repeat: -1, duration: 600 + Math.random() * 500 });
      }
      this.add.text(ox + art.W / 2, oy + 4, room.title, this.textStyle(7, "#fff8e8")).setOrigin(0.5, 0).setStroke("#2b1d14", 3).setResolution(4).setDepth(9400);
      const rec = {
        id, title: room.title, ox, oy, W: art.W, H: art.H,
        entry: { x: ox + art.W / 2, y: oy + art.H - 16 },
        station: { x: ox + room.station[0] * TILE, y: oy + room.station[1] * TILE },
      };
      this.rooms[id] = rec;
      ox += art.W + ROOM_GAP;
    }
    this.roomsRight = ox;
  }

  toWorld(area, [tx, ty]) {
    if (area === "village") return { x: tx * TILE, y: ty * TILE };
    const r = this.rooms[area];
    return { x: r.ox + tx * TILE, y: r.oy + ty * TILE };
  }

  makeActor(id, v, key, pos, extra) {
    const s = this.physics.add.sprite(pos.x, pos.y, key, "down-0").setOrigin(0.5, 1);
    if (extra.animal) s.body.setSize(8, 4).setOffset(3, 8);
    else s.body.setSize(10, 6).setOffset(3, 15);
    s.body.setImmovable(true);
    s.body.pushable = false;
    if (!extra.ghost) this.physics.add.collider(s, this.solids);
    if (!extra.animal) this.physics.add.collider(this.player, s);
    s.setInteractive({ useHandCursor: true });
    s.on("pointerdown", () => {
      if (this.mode !== "play" || this.blocked || this.transitioning) return;
      if (extra.kind === "case") emit("talk", id); else this.smallTalk(id);
    });
    const label = this.add.text(0, 0, extra.animal ? "" : v.name,
      this.textStyle(extra.kind === "case" ? 7 : 6, extra.kind === "case" ? "#ffe27a" : "#e8dcc0")).setOrigin(0.5, 1).setStroke("#2b1d14", 3).setResolution(4);
    label.setVisible(extra.kind === "case");
    const ring = this.add.image(0, 0, "ring").setVisible(false);
    const a = { id, v, sprite: s, label, ring, key, home: { ...pos }, state: "idle", t: Math.random() * 2000, target: null, walked: 0,
      scripted: null, dir: "down", wander: extra.wander ?? 34, speed: extra.speed ?? NPC_SPEED, area: extra.area ?? "village",
      kind: extra.kind, animal: !!extra.animal, talkKind: extra.talkKind, h: extra.animal ? 12 : CHAR_H };
    this.actors.set(id, a);
    return a;
  }

  spawnExtras() {
    for (const e of EXTRAS) {
      const key = makeCharacter(this, `char_${e.id}`, lookFor(e.id, e.role));
      this.makeActor(e.id, e, key, this.toWorld(e.area, e.at), { kind: "extra", talkKind: e.kind, area: e.area, wander: e.wander, speed: e.speed });
    }
    for (const a of ANIMALS) {
      const key = this.textures.exists(`ani_${a.kind}`) ? `ani_${a.kind}` : makeAnimal(this, `ani_${a.kind}`, a.kind);
      this.makeActor(a.id, { name: a.kind }, key, this.toWorld("village", a.at),
        { kind: "extra", animal: true, talkKind: a.kind, area: "village", wander: a.kind === "duck" ? 14 : 40, speed: 22, ghost: a.kind === "duck" });
    }
  }

  // ---------- camera / modes ----------

  layout() {
    const { width, height } = this.scale;
    this.overlay.setSize(width, height);
    const cam = this.cameras.main;
    if (this.area !== "village") {
      const r = this.rooms[this.area];
      cam.removeBounds();
      cam.setZoom(Phaser.Math.Clamp(Math.floor(Math.min(width / (r.W + 24), (height - 70) / (r.H + 24))), 2, 5));
      cam.centerOn(r.ox + r.W / 2, r.oy + r.H / 2 - 6);
      return;
    }
    cam.setBounds(0, 0, W, H);
    if (this.mode === "overview") {
      cam.setZoom(Math.max(width / W, height / H, 1));
      cam.centerOn(W / 2, H / 2 - 20);
    } else {
      cam.setZoom(Phaser.Math.Clamp(Math.round(Math.min(width / (20 * TILE), height / (13 * TILE))), 2, 5));
    }
  }

  // Fit the whole village on screen (gossip); layout() restores the normal zoom.
  showWhole() {
    const { width, height } = this.scale, cam = this.cameras.main;
    cam.stopFollow();
    cam.zoomTo(Math.max(width / W, height / H, 1), 700, "Sine.easeInOut");
    cam.pan(W / 2, H / 2 - 10, 700, "Sine.easeInOut");
  }

  // attract: title-screen pan, no player. play: follow the detective. overview: whole village.
  setMode(mode) {
    if (mode !== "play" && this.area !== "village") this.exitBuilding(true);
    this.mode = mode;
    this.placeVillagers(mode === "play" ? "inside" : "outside");
    const cam = this.cameras.main;
    this.attractTween?.remove();
    cam.stopFollow();
    this.player.setVisible(mode === "play");
    this.player.body.enable = mode === "play";
    this.layout();
    if (mode === "play") {
      if (this.area === "village") cam.startFollow(this.player, true, 0.12, 0.12);
    } else if (mode === "attract") {
      const pts = [[this.places.plaza.x, this.places.plaza.y], [this.places.mill.x, 150], [this.places.chapel.x, 140], [this.places.smithy.x, 330]];
      let i = 0;
      cam.centerOn(...pts[0]);
      const next = () => {
        i = (i + 1) % pts.length;
        this.attractTween = this.tweens.add({ targets: cam, scrollX: pts[i][0] - cam.width / 2, scrollY: pts[i][1] - cam.height / 2,
          duration: 9000, ease: "Sine.easeInOut", onComplete: next });
      };
      next();
    }
  }

  resetPlayer() {
    if (this.area !== "village") this.exitBuilding(true);
    this.player.setPosition(this.places.plaza.x, this.places.plaza.y + 30);
    this.player.setFrame("up-0");
    this.moveTarget = null;
  }

  // ---------- entering / leaving buildings ----------

  async enterBuilding(id) {
    const room = this.rooms[id];
    if (!room || this.transitioning || this.mode !== "play") return;
    this.transitioning = true;
    this.moveTarget = null;
    this.player.body.setVelocity(0);
    const cam = this.cameras.main;
    cam.fadeOut(220, 20, 12, 6);
    await sleep(this, 240);
    this.clearBubbles();
    this.area = id;
    this.player.setPosition(room.entry.x, room.entry.y);
    this.facing = "up"; this.player.setFrame("up-0");
    cam.stopFollow();
    this.layout();
    cam.fadeIn(260, 20, 12, 6);
    emit("area", { id, title: room.title });
    await sleep(this, 280);
    this.transitioning = false;
  }

  exitBuilding(instant = false) {
    const id = this.area;
    if (id === "village") return;
    const finish = () => {
      this.area = "village";
      const d = this.doors.find((x) => x.id === id);
      this.player.setPosition(d.x, d.y + 12);
      this.facing = "down"; this.player.setFrame("down-0");
      this.clearBubbles();
      this.layout();
      if (this.mode === "play") this.cameras.main.startFollow(this.player, true, 0.12, 0.12);
      emit("area", { id: "village", title: "Vaudville" });
    };
    if (instant) return finish();
    this.transitioning = true;
    this.moveTarget = null;
    const cam = this.cameras.main;
    cam.fadeOut(220, 20, 12, 6);
    this.time.delayedCall(240, () => { finish(); cam.fadeIn(260, 20, 12, 6); this.time.delayedCall(280, () => { this.transitioning = false; }); });
  }

  // ---------- where the case villagers are (each in exactly one place) ----------
  // Each villager has a spot: a room ({type:"room", id}) or an outdoor place ({type:"out", id}).
  // Spots are re-rolled every morning (seeded by case + day) and a couple of villagers move on
  // every minute or so while you play. "outside" mode (gossip, rumour map, replays, title) puts
  // everyone outdoors: at their outdoor spot, or by the door of the building they were in.

  assignSpots(day) {
    const r = rng(hash(`${this.caseSeed}|spots|${day}`));
    for (const a of this.npcs.values()) a.spot = this.randomSpot(a, r);
  }

  randomSpot(a, r = Math.random) {
    const rooms = Object.keys(this.rooms);
    const roll = r();
    if (roll < 0.4 && this.rooms[a.homePlace]) return { type: "room", id: a.homePlace };
    if (roll < 0.62) return { type: "room", id: rooms[Math.floor(r() * rooms.length)] };
    return { type: "out", id: OUTDOOR_SPOTS[Math.floor(r() * OUTDOOR_SPOTS.length)].id };
  }

  // Where a villager stands for a spot; n = how many others already share it.
  spotPoint(a, spot, n) {
    const off = n ? (n % 2 ? 22 : -22) * Math.ceil(n / 2) : 0;
    if (spot.type === "room") {
      const room = this.rooms[spot.id];
      if (spot.id === a.homePlace && n === 0) return { x: room.station.x, y: room.station.y };
      return { x: room.entry.x + off + (n === 0 ? 18 : 0), y: room.entry.y - 26 };
    }
    const o = OUTDOOR_SPOTS.find((x) => x.id === spot.id);
    return { x: o.at[0] * TILE + off, y: o.at[1] * TILE };
  }

  placeVillagers(where) {
    const used = {};
    for (const a of this.npcs.values()) {
      a.moveGen = (a.moveGen || 0) + 1; // cancels any walk in progress
      const spot = a.spot || { type: "out", id: "plaza" };
      let target;
      if (where === "outside" && spot.type === "room") {
        const d = this.doors.find((x) => x.id === spot.id);
        const k = `door:${spot.id}`, n = (used[k] = (used[k] || 0) + 1) - 1;
        target = { area: "village", x: d.x + (n % 2 ? -1 : 1) * (26 + Math.floor(n / 2) * 18), y: d.y + 9 };
      } else {
        const k = `${spot.type}:${spot.id}`, n = (used[k] = (used[k] || 0) + 1) - 1;
        target = { area: spot.type === "room" ? spot.id : "village", ...this.spotPoint(a, spot, n) };
      }
      this.setVillagerAt(a, target);
    }
    this.refreshTags();
  }

  setVillagerAt(a, { area, x, y }) {
    if (a.scripted) { const done = a.scripted.done; a.scripted = null; done(); }
    a.area = area;
    a.home = { x, y };
    a.wander = area === "village" ? 30 : 12;
    a.state = "idle"; a.t = 800 + Math.random() * 1500; a.scripted = null;
    a.sprite.setPosition(x, y);
  }

  // Move one villager to a new spot. If you can see them, they walk there (through doors).
  async moveVillager(a, spot) {
    if (a.moving) return;
    a.moving = true;
    a.spot = spot;
    const gen = a.moveGen = (a.moveGen || 0) + 1;
    const cancelled = () => a.moveGen !== gen;
    const toArea = spot.type === "room" ? spot.id : "village";
    const sharing = [...this.npcs.values()].filter((b) => b !== a && b.spot?.type === spot.type && b.spot?.id === spot.id).length;
    const dest = this.spotPoint(a, spot, sharing);
    const seen = () => a.area === this.area && this.mode === "play";
    if (seen() && a.area !== "village") {
      const room = this.rooms[a.area];
      await this.walkTo(a.id, room.entry.x, room.entry.y + 8, 40, 6000);
      if (cancelled()) { a.moving = false; return; } // out through the doormat
    }
    if (a.area !== "village" && toArea !== a.area) {
      const d = this.doors.find((x) => x.id === a.area);
      this.setVillagerAt(a, { area: "village", x: d.x, y: d.y + 10 });
    }
    if (toArea === "village") {
      if (seen()) await this.walkTo(a.id, dest.x, dest.y, 40, 9000);
      if (cancelled()) { a.moving = false; return; }
      this.setVillagerAt(a, { area: "village", ...dest });
    } else if (toArea !== a.area) {
      const d = this.doors.find((x) => x.id === toArea);
      if (seen()) await this.walkTo(a.id, d.x, d.y + 4, 40, 9000);
      if (cancelled()) { a.moving = false; return; } // walk up to the door and go in
      const room = this.rooms[toArea];
      this.setVillagerAt(a, { area: toArea, x: room.entry.x, y: room.entry.y });
      if (seen()) await this.walkTo(a.id, dest.x, dest.y, 40, 4000);
      if (cancelled()) { a.moving = false; return; }
      this.setVillagerAt(a, { area: toArea, ...dest });
    } else {
      if (seen()) await this.walkTo(a.id, dest.x, dest.y, 40, 5000);
      if (cancelled()) { a.moving = false; return; }
      this.setVillagerAt(a, { area: toArea, ...dest });
    }
    a.moving = false;
    this.refreshTags();
    emit("villager-moved", { id: a.id });
  }

  // Building signs say who is in right now.
  refreshTags() {
    const inside = {};
    for (const a of this.npcs.values()) if (a.area !== "village") (inside[a.area] ||= []).push(a.v.name);
    for (const [id, t] of Object.entries(this.residentTags || {})) {
      const names = inside[id] || [];
      t.setText(names.length ? `${names.join(" & ")} ${names.length > 1 ? "are" : "is"} in` : "").setVisible(names.length > 0);
    }
  }

  // "inside the Bakery" / "outside, by the well" (journal).
  locationOf(id) {
    const a = this.npcs.get(id);
    if (!a) return "nowhere to be seen";
    if (a.area !== "village") { const t = this.rooms[a.area].title; return `inside ${t.startsWith("The ") ? t : `the ${t}`}`; }
    let best = null, bd = Infinity;
    for (const o of OUTDOOR_SPOTS) {
      const d = Phaser.Math.Distance.Between(a.sprite.x, a.sprite.y, o.at[0] * TILE, o.at[1] * TILE);
      if (d < bd) { bd = d; best = o.label; }
    }
    for (const d of this.doors) {
      const dd = Phaser.Math.Distance.Between(a.sprite.x, a.sprite.y, d.x, d.y);
      if (dd < bd && dd < 70) { bd = dd; best = d.label === "this house" ? "by the cottages" : `by the ${d.label.replace(/^The /, "")}`; }
    }
    return `outside, ${best}`;
  }

  homeFor(v, i, used) {
    let place = ROLE_HOME[v.role?.toLowerCase()];
    if (!place || !this.places[place]) place = FALLBACK_HOMES[i % FALLBACK_HOMES.length];
    const n = (used[place] = (used[place] || 0) + 1) - 1;
    const p = this.places[place];
    const side = n % 2 ? -1 : 1, step = Math.floor(n / 2);
    return { place, x: p.x + side * (26 + step * 18), y: p.y + 4 };
  }

  // The crime scene for this case: chalk outline + "!" in the room where the victim was found (or on the ground
  // by the plaza for outdoor places like the market), and a "!" at that building's door outside.
  setCrimeScene(key, placeName = "") {
    for (const o of this.crimeObjs) o.destroy();
    this.crimeObjs = [];
    this.inspects = [];
    if (!key) return;
    const mark = (x, y, depth) => {
      const m = this.add.text(x, y, "!", this.textStyle(11, "#ffe680")).setOrigin(0.5).setDepth(depth).setStroke("#2b1d14", 3).setResolution(4);
      this.tweens.add({ targets: m, alpha: 0.35, yoyo: true, repeat: -1, duration: 700 });
      this.crimeObjs.push(m);
    };
    const chalk = makeChalk(this);
    const room = this.rooms[key], spot = ROOMS[key]?.crime;
    if (room && spot) {
      const x = room.ox + spot[0] * TILE, y = room.oy + spot[1] * TILE;
      this.crimeObjs.push(this.add.image(x, y, chalk).setOrigin(0).setDepth(-8999));
      mark(x + 1.5 * TILE, y - 4, 9300);
      this.inspects.push({ area: key, x: x + 1.5 * TILE, y: y + TILE, label: "examine the chalk outline" });
      const d = this.doors.find((x) => x.id === key);
      if (d) {
        mark(d.x + 14, d.y - 10, d.y);
        this.inspects.push({ area: "village", x: d.x + 14, y: d.y, label: `inspect the ${ROOMS[key].title.toLowerCase()}` });
      }
    } else {
      const p = this.places.plaza, x = p.x + 30, y = p.y - 24;
      this.crimeObjs.push(this.add.image(x, y, chalk).setOrigin(0.5).setDepth(y - 20));
      mark(x, y - 22, y);
      this.inspects.push({ area: "village", x, y: y + 6, label: `examine the chalk outline${placeName ? ` at the ${placeName}` : ""}` });
    }
  }

  // Spawn villagers for a case. villagers: [{id, name, role}]
  setupCase(villagers, victimName, seed = 0) {
    if (this.area !== "village") this.exitBuilding(true);
    if (victimName) this.victimName = victimName;
    this.caseSeed = seed;
    for (const n of this.npcs.values()) { n.sprite.destroy(); n.label.destroy(); n.ring.destroy(); this.actors.delete(n.id); }
    this.npcs.clear();
    this.clearBubbles();
    const used = {};
    villagers.forEach((v, i) => {
      const key = makeCharacter(this, `char_${v.id}`, lookFor(v.id, v.role?.toLowerCase()));
      const home = this.homeFor(v, i, used);
      const a = this.makeActor(v.id, v, key, home, { kind: "case" });
      a.homePlace = home.place;
      this.npcs.set(v.id, a);
    });
    this.assignSpots(1);
    this.placeVillagers(this.mode === "play" ? "inside" : "outside");
  }

  // ---------- clock ----------

  newDay(day = 1) {
    this.clock = DAY_START; this.phase = null; this.sunsetSent = false; this.lastPart = null; this.emitClock(true);
    this.assignSpots(day);
    if (this.mode === "play") this.placeVillagers("inside");
    this.relocT = 45000;
  }
  advanceClock(minutes) { this.clock = Math.min(SUNSET, this.clock + minutes); this.emitClock(true); }
  emitClock(force) {
    const slot = Math.floor(this.clock / 5);
    if (!force && slot === this.lastClockSlot) return;
    this.lastClockSlot = slot;
    const part = daypart(this.clock);
    emit("clock", { min: this.clock, label: clockLabel(this.clock), frac: (this.clock - DAY_START) / (SUNSET - DAY_START), part: part[1] });
    if (part[1] !== this.lastPart) {
      if (this.lastPart && this.mode === "play") emit("daypart", { name: part[1], line: part[2] });
      this.lastPart = part[1];
    }
    if (this.clock >= SUNSET && !this.sunsetSent) { this.sunsetSent = true; emit("sunset"); }
  }

  updateLight() {
    if (this.phase) return; // gossip / night sequences own the overlay
    const [color, alpha, lamps] = ambient(this.mode === "play" ? this.clock : 11 * 60);
    this.overlay.fillColor = color;
    this.overlay.fillAlpha = this.area === "village" ? alpha : alpha * 0.5;
    for (const g of this.glows) g.setAlpha(Math.min(0.9, lamps * 0.9));
  }

  // ---------- per-frame ----------

  update(_time, delta) {
    if (this.mode === "play" && !this.blocked && !this.transitioning && !this.phase && this.clock < SUNSET) {
      this.clock = Math.min(SUNSET, this.clock + (delta / 1000) * CLOCK_RATE);
      this.emitClock(false);
    }
    this.updateLight();
    if (this.mode === "play" && !this.blocked && !this.transitioning && !this.phase && !this.gossiping) {
      this.relocT = (this.relocT ?? 45000) - delta;
      if (this.relocT < 0) {
        this.relocT = Phaser.Math.Between(50000, 80000);
        const pool = [...this.npcs.values()].filter((a) => !a.moving && a.id !== this.talkingTo);
        Phaser.Utils.Array.Shuffle(pool).slice(0, Phaser.Math.Between(1, 2)).forEach((a) => this.moveVillager(a, this.randomSpot(a)));
      }
    }
    if (this.mode === "play" && !this.transitioning) this.updatePlayer();
    else if (this.player.body.enable) this.player.body.setVelocity(0);
    for (const a of this.actors.values()) this.updateActor(a, delta);
    if (this.mode === "play" && !this.transitioning) this.updateProximity();
    else { this.ring.setVisible(false); this.prompt.setVisible(false); }
    for (const b of this.bubbles) b.follow();
  }

  updatePlayer() {
    const k = this.keys, body = this.player.body;
    let vx = 0, vy = 0;
    if (!this.blocked) {
      if (k.LEFT.isDown || k.A.isDown) vx -= 1;
      if (k.RIGHT.isDown || k.D.isDown) vx += 1;
      if (k.UP.isDown || k.W.isDown) vy -= 1;
      if (k.DOWN.isDown || k.S.isDown) vy += 1;
    }
    if (vx || vy) this.moveTarget = null;
    else if (this.moveTarget && !this.blocked) {
      const dx = this.moveTarget.x - this.player.x, dy = this.moveTarget.y - this.player.y;
      if (Math.hypot(dx, dy) < 3) this.moveTarget = null;
      else { vx = dx; vy = dy; }
    }
    const len = Math.hypot(vx, vy);
    if (len) {
      body.setVelocity((vx / len) * PLAYER_SPEED, (vy / len) * PLAYER_SPEED);
      this.facing = Math.abs(vx) > Math.abs(vy) ? (vx < 0 ? "left" : "right") : vy < 0 ? "up" : "down";
      this.player.anims.play(`char_player-walk-${this.facing}`, true);
      if (this.moveTarget && body.speed < 5) this.moveTarget = null;
    } else {
      body.setVelocity(0);
      this.player.anims.stop();
      this.player.setFrame(`${this.facing}-0`);
    }
    this.player.setDepth(this.player.y);
    // leaving a room: walk out through the doorway
    if (this.area !== "village") {
      const r = this.rooms[this.area];
      if (this.player.y > r.oy + r.H - 5) return this.exitBuilding();
    } else if (vy < 0 && body.blocked.up) {
      // walking into a door enters the building
      const d = this.doors.find((x) => x.enterable && Math.abs(x.x - this.player.x) < 9 && Math.abs(x.y - this.player.y) < 10);
      if (d) return this.enterBuilding(d.id);
    }
    if (!this.blocked && (Phaser.Input.Keyboard.JustDown(k.E) || Phaser.Input.Keyboard.JustDown(k.SPACE))) this.interact();
  }

  interact() {
    const n = this.nearest;
    if (!n) return;
    if (n.type === "case") emit("talk", n.id);
    else if (n.type === "extra") this.smallTalk(n.id);
    else if (n.type === "inspect") emit("inspect", n.area);
    else if (n.type === "door") n.enterable ? this.enterBuilding(n.id) : this.bubblePlayer("Locked. Nobody's home.");
    else if (n.type === "exit") this.exitBuilding();
  }

  updateProximity() {
    let best = null, bd = TALK_RANGE;
    const consider = (d, c) => { if (d < bd) { bd = d; best = c; } };
    const P = this.player;
    for (const a of this.actors.values()) {
      if (a.area !== this.area) continue;
      // case villagers win ties against townsfolk standing nearby
      consider(Phaser.Math.Distance.Between(P.x, P.y, a.sprite.x, a.sprite.y) - (a.kind === "case" ? 8 : 0), { type: a.kind === "case" ? "case" : "extra", id: a.id, t: a.sprite, name: a.v.name, h: a.h, animal: a.animal });
    }
    for (const s of this.inspects) if (s.area === this.area) consider(Phaser.Math.Distance.Between(P.x, P.y, s.x, s.y) + 2, { type: "inspect", area: s.area, t: s, label: s.label, h: 4 });
    if (this.area === "village") {
      for (const d of this.doors) consider(Phaser.Math.Distance.Between(P.x, P.y, d.x, d.y) + (this.facing === "up" ? -10 : 4), { type: "door", id: d.id, enterable: d.enterable, t: d, label: d.label, h: 6 });
    } else {
      const r = this.rooms[this.area];
      consider(Phaser.Math.Distance.Between(P.x, P.y, r.entry.x, r.entry.y + 8) + 6, { type: "exit", t: { x: r.entry.x, y: r.entry.y + 8 }, h: 4 });
    }
    this.nearest = best;
    // townsfolk labels only show up close, so the village doesn't drown in names
    for (const a of this.actors.values()) if (a.kind !== "case") a.label.setVisible(Phaser.Math.Distance.Between(P.x, P.y, a.sprite.x, a.sprite.y) < 70);
    if (!best || this.blocked) { this.ring.setVisible(false); this.prompt.setVisible(false); return; }
    const t = best.t;
    const text = {
      case: `E · talk to ${best.name}`, extra: best.animal ? `E · pet the ${best.name}` : `E · chat with ${best.name}`,
      inspect: `E · ${best.label}`, door: best.enterable ? `E · enter the ${best.label}` : "E · knock", exit: "E · go outside",
    }[best.type];
    this.ring.setVisible(best.type === "case" || best.type === "extra").setPosition(t.x, t.y - 1).setDepth(t.y - 1);
    this.prompt.setVisible(true).setPosition(t.x, t.y - (best.h || CHAR_H) - 9).setText(text);
  }

  updateActor(a, delta) {
    const s = a.sprite;
    let vx = 0, vy = 0, speed = a.speed;
    if (this.talkingTo === a.id && this.mode === "play") {
      const dx = this.player.x - s.x, dy = this.player.y - s.y;
      a.dir = Math.abs(dx) > Math.abs(dy) ? (dx < 0 ? "left" : "right") : dy < 0 ? "up" : "down";
    } else if (a.scripted) {
      const dx = a.scripted.x - s.x, dy = a.scripted.y - s.y;
      speed = a.scripted.speed;
      a.scripted.elapsed += delta;
      if (Math.hypot(dx, dy) < 3 || a.scripted.elapsed > a.scripted.timeout) {
        const done = a.scripted.done; a.scripted = null; done();
      } else { vx = dx; vy = dy; }
    } else if (this.mode === "play" && this.closeToPlayer(a)) {
      const dx = this.player.x - s.x, dy = this.player.y - s.y;
      a.dir = Math.abs(dx) > Math.abs(dy) ? (dx < 0 ? "left" : "right") : dy < 0 ? "up" : "down";
      if (a.state === "walk") { a.state = "idle"; a.t = 1200; }
    } else if (this.gossiping && a.kind === "case") {
      // hold still unless scripted
    } else if (a.chatUntil && a.chatUntil > this.time.now) {
      // paused for small talk
    } else if (a.state === "idle") {
      a.t -= delta;
      if (a.t < 0) {
        a.state = "walk"; a.walked = 0;
        a.target = { x: a.home.x + Phaser.Math.Between(-a.wander, a.wander), y: a.home.y + Phaser.Math.Between(-Math.min(4, a.wander), Math.min(26, a.wander)) };
      }
    } else if (a.state === "walk") {
      const dx = a.target.x - s.x, dy = a.target.y - s.y;
      a.walked += delta;
      if (Math.hypot(dx, dy) < 3 || a.walked > 4000) { a.state = "idle"; a.t = Phaser.Math.Between(1500, 4500); }
      else { vx = dx; vy = dy; }
    }
    const len = Math.hypot(vx, vy);
    if (len) {
      s.body.setVelocity((vx / len) * speed, (vy / len) * speed);
      a.dir = Math.abs(vx) > Math.abs(vy) ? (vx < 0 ? "left" : "right") : vy < 0 ? "up" : "down";
      s.anims.play(`${a.key}-walk-${a.dir}`, true);
    } else {
      s.body.setVelocity(0);
      s.anims.stop();
      s.setFrame(`${a.dir}-0`);
    }
    s.setDepth(s.y);
    a.label.setPosition(s.x, s.y - a.h - 1).setDepth(9400);
    a.ring.setPosition(s.x, s.y - 1).setDepth(s.y - 1);
  }

  areaOf(a) { return a.area; }
  closeToPlayer(a) {
    return this.areaOf(a) === this.area && Phaser.Math.Distance.Between(this.player.x, this.player.y, a.sprite.x, a.sprite.y) < 40;
  }

  // A clean snapshot of the current view (without the villager and detective) for the interview backdrop.
  snapshotFor(id) {
    const a = this.actors.get(id);
    const hide = [this.player, this.prompt, this.ring, a?.sprite, a?.label, a?.ring].filter(Boolean);
    const was = hide.map((o) => o.visible);
    hide.forEach((o) => o.setVisible(false));
    this.clearBubbles();
    if (a) this.cameras.main.centerOn((a.sprite.x + this.player.x) / 2, (a.sprite.y + this.player.y) / 2 - 10);
    return new Promise((resolve) => {
      this.game.renderer.snapshot((img) => {
        hide.forEach((o, i) => o.setVisible(was[i]));
        resolve(img?.src || "");
      });
    });
  }

  // Townsfolk and animals: colour only. Not part of the case, never sent to the model.
  smallTalk(id) {
    const a = this.actors.get(id);
    if (!a) return;
    const lines = SMALL_TALK[a.talkKind] || SMALL_TALK.townsfolk;
    const i = (this.talkIdx[id] = ((this.talkIdx[id] ?? -1) + 1) % lines.length);
    const dx = this.player.x - a.sprite.x, dy = this.player.y - a.sprite.y;
    a.dir = Math.abs(dx) > Math.abs(dy) ? (dx < 0 ? "left" : "right") : dy < 0 ? "up" : "down";
    a.chatUntil = this.time.now + 2600;
    a.state = "idle"; a.t = 2600;
    this.bubble(id, lines[i].replace("{victim}", this.victimName), 2600);
    emit("smalltalk", { id, name: a.v.name, voice: a.v.voice || "m", kind: a.animal ? a.talkKind : "" });
  }

  // ---------- scripted visuals ----------

  walkTo(id, x, y, speed = 48, timeout = 7000) {
    const n = this.actors.get(id);
    if (!n) return Promise.resolve();
    return new Promise((done) => { n.scripted = { x, y, speed, timeout, elapsed: 0, done }; });
  }

  face(id, otherId) {
    const a = this.actors.get(id), b = this.actors.get(otherId);
    if (!a || !b) return;
    const dx = b.sprite.x - a.sprite.x, dy = b.sprite.y - a.sprite.y;
    a.dir = Math.abs(dx) > Math.abs(dy) ? (dx < 0 ? "left" : "right") : dy < 0 ? "up" : "down";
  }

  bubbleOn(target, id, text, ms, tone, h = CHAR_H) {
    for (const b of this.bubbles.filter((b) => b.id === id)) b.destroy();
    const t = this.add.text(0, 0, strip(text), { ...this.textStyle(7, "#2b1d14"), wordWrap: { width: 110 }, align: "center" })
      .setOrigin(0.5, 1).setResolution(4).setDepth(9601);
    const g = this.add.graphics().setDepth(9600);
    const border = { supported: 0x3f8f4a, unsupported: 0xc0443a, abstained: 0x8a8a8a, plain: 0x2b1d14 }[tone] ?? 0x2b1d14;
    const bub = {
      id,
      follow: () => {
        const x = target.x, y = target.y - h - 10;
        t.setPosition(x, y - 3);
        const w = t.width + 8, hh = t.height + 6;
        g.clear().fillStyle(0xfff8e8, 0.96).lineStyle(1, border, 1)
          .fillRoundedRect(x - w / 2, y - hh, w, hh, 3).strokeRoundedRect(x - w / 2, y - hh, w, hh, 3)
          .fillTriangle(x - 3, y, x + 3, y, x, y + 4);
      },
      destroy: () => { t.destroy(); g.destroy(); this.bubbles = this.bubbles.filter((b) => b !== bub); },
    };
    bub.follow();
    this.bubbles.push(bub);
    this.time.delayedCall(ms, () => bub.destroy());
  }

  bubble(id, text, ms = 3200, tone = "plain") {
    const a = this.actors.get(id);
    if (a) this.bubbleOn(a.sprite, id, text, ms, tone, a.h);
  }

  bubblePlayer(text, ms = 1800) { this.bubbleOn(this.player, "player", text, ms, "plain"); }

  clearBubbles() { [...this.bubbles].forEach((b) => b.destroy()); }

  setPhase(phase, duration = 1200) {
    emit("phase", phase);
    if (phase === "day") { this.phase = null; return; }
    const [color, alpha] = PHASES[phase] ?? PHASES.dusk;
    this.phase = phase;
    this.overlay.fillColor = color;
    this.tweens.add({ targets: this.overlay, fillAlpha: alpha, duration });
    this.tweens.add({ targets: this.glows, alpha: phase === "night" ? 0.9 : 0.6, duration });
  }

  async fade(ms = 600) {
    const cam = this.cameras.main;
    cam.fadeOut(ms, 10, 8, 20);
    await sleep(this, ms + 150);
    cam.fadeIn(ms, 10, 8, 20);
  }

  // ---------- cinematic camera + travelling words (gossip and rumour) ----------
  // viewInset: screen pixels covered by DOM panels ({left, right, bottom}), so close-ups frame the
  // pair in the part of the screen you can actually see.

  closeZoom() {
    const { width, height } = this.scale;
    const wide = Math.max(width / W, height / H, 1);
    return Phaser.Math.Clamp(Math.round(Math.min(width / (16 * TILE), height / (10 * TILE))), Math.ceil(wide) + 1, 6);
  }

  async closeOn(ids, ms = 750) {
    const pts = ids.map((id) => this.npcs.get(id)?.sprite).filter(Boolean);
    if (!pts.length) return;
    const cam = this.cameras.main, z = this.closeZoom(), inset = this.viewInset || {};
    const x = pts.reduce((s, p) => s + p.x, 0) / pts.length, y = pts.reduce((s, p) => s + p.y, 0) / pts.length - 14;
    cam.stopFollow();
    cam.zoomTo(z, ms, "Sine.easeInOut", true);
    cam.pan(x - ((inset.left || 0) - (inset.right || 0)) / 2 / z, y + (inset.bottom || 0) / 2 / z, ms, "Sine.easeInOut", true);
    await sleep(this, ms + 60);
  }

  async wideShot(ms = 900) {
    const { width, height } = this.scale, cam = this.cameras.main, inset = this.viewInset || {};
    const z = Math.max(width / W, height / H, 1);
    cam.stopFollow();
    cam.zoomTo(z, ms, "Sine.easeInOut", true);
    cam.pan(W / 2 - ((inset.left || 0) - (inset.right || 0)) / 2 / z, H / 2 - 10 + (inset.bottom || 0) / 2 / z, ms, "Sine.easeInOut", true);
    await sleep(this, ms + 60);
  }

  // Camera rides along with a word in flight (rumour hops between far-apart villagers).
  followWord(obj) {
    const cam = this.cameras.main, z = Math.max(2, this.closeZoom() - 1), inset = this.viewInset || {};
    cam.zoomTo(z, 500, "Sine.easeInOut", true);
    cam.startFollow(obj, false, 0.12, 0.12);
    cam.setFollowOffset(((inset.left || 0) - (inset.right || 0)) / 2 / z, -(inset.bottom || 0) / 2 / z);
  }

  // A glowing word that flies on an arc from one villager's mouth to another's ear, leaving a trail.
  // tone: supported | unsupported | abstained | red | amber | neutral. Abstained words fizzle halfway.
  sendWord(fromId, toId, tone = "neutral", { from = null, follow = false } = {}) {
    const a = from ? { sprite: from, h: 0 } : this.npcs.get(fromId), b = this.npcs.get(toId);
    if (!a || !b) return Promise.resolve();
    const color = WORD_TINT[tone] ?? WORD_TINT.neutral;
    const p0 = { x: a.sprite.x, y: a.sprite.y - (a.h || CHAR_H) + 4 }, p2 = { x: b.sprite.x, y: b.sprite.y - b.h + 4 };
    const dist = Phaser.Math.Distance.Between(p0.x, p0.y, p2.x, p2.y);
    const p1 = { x: (p0.x + p2.x) / 2, y: Math.min(p0.y, p2.y) - Math.min(70, 14 + dist * 0.35) };
    const glow = this.add.image(p0.x, p0.y, "word").setTint(color).setDepth(9550).setScale(2.2).setAlpha(0.35).setBlendMode(Phaser.BlendModes.ADD);
    const core = this.add.image(p0.x, p0.y, "word").setTint(color).setDepth(9551);
    const fizzle = tone === "abstained";
    const fx = { trail: null, end: null };
    this.fx.add(fx);
    emit("sfx", "whisper");
    if (follow) this.followWord(core);
    return new Promise((done) => {
      let over = false;
      const end = (arrived) => {
        if (over) return;
        over = true;
        if (follow) this.cameras.main.stopFollow();
        fx.trail?.remove(); glow.destroy(); core.destroy(); this.fx.delete(fx);
        if (arrived) this.landWord(toId, tone, color);
        done();
      };
      fx.end = () => end(false);
      fx.trail = this.time.addEvent({ delay: 34, loop: true, callback: () => {
        const d = this.add.image(core.x, core.y, "word").setTint(color).setDepth(9549).setScale(0.8).setAlpha(0.7);
        this.tweens.add({ targets: d, alpha: 0, scale: 0.2, duration: 520, onComplete: () => d.destroy() });
      } });
      const o = { t: 0 };
      this.tweens.add({
        targets: o, t: fizzle ? 0.5 : 1, duration: Phaser.Math.Clamp(dist * 6, 650, 2200) * (fizzle ? 0.6 : 1), ease: "Sine.easeInOut",
        onUpdate: () => {
          if (over) return;
          const t = o.t, u = 1 - t;
          const x = u * u * p0.x + 2 * u * t * p1.x + t * t * p2.x, y = u * u * p0.y + 2 * u * t * p1.y + t * t * p2.y;
          core.setPosition(x, y); glow.setPosition(x, y).setScale(2.2 + Math.sin(t * 20) * 0.4);
        },
        onComplete: () => {
          if (over) return;
          if (!fizzle) return end(true);
          emit("sfx", "puff");
          fx.trail.remove();
          this.tweens.add({ targets: [core, glow], alpha: 0, scale: 4, duration: 380, onComplete: () => end(false) });
        },
      });
    });
  }

  landWord(id, tone, color) {
    const n = this.npcs.get(id);
    if (!n) return;
    emit("sfx", tone === "unsupported" || tone === "red" ? "hop-bad" : tone === "supported" ? "hop-ok" : "hop");
    this.tweens.add({ targets: n.sprite, y: n.sprite.y - 4, duration: 110, yoyo: true, ease: "Quad.easeOut" });
    const burst = this.add.image(n.sprite.x, n.sprite.y - n.h + 4, "word").setTint(color).setDepth(9552).setScale(1.5).setBlendMode(Phaser.BlendModes.ADD);
    this.tweens.add({ targets: burst, scale: 6, alpha: 0, duration: 450, onComplete: () => burst.destroy() });
  }

  clearFx() { for (const f of [...this.fx]) f.end?.(); }

  // Letterbox bars + a music theme while a scripted sequence plays (the DOM and audio listen on the bus).
  cinema(on, music = null) {
    emit("cinema", on);
    emit("music", on ? music : null);
  }

  // Evening gossip. Each round: a wide shot while the askers walk over, then the camera cuts in on each
  // conversation in turn. The answer flies to the asker as a word coloured by its seal.
  async playGossip(events, { onEvent, onRound, hideStatus = false } = {}) {
    if (this.area !== "village") this.exitBuilding(true);
    this.placeVillagers("outside");
    this.skip = false;
    this.gossiping = true;
    this.cinema(true, "gossip");
    const shown = new Set();
    const rounds =[...new Set(events.map((e) => e.round ?? 1))];
    for (const r of rounds) {
      if (this.skip) break;
      const evs = events.filter((e) => (e.round ?? 1) === r && this.npcs.get(e.asker) && this.npcs.get(e.responder));
      emit("music", "gossip");
      await this.wideShot();
      onRound?.(r, rounds.length);
      await Promise.all(evs.map(async (e, i) => {
        await sleep(this, i * 250);
        const b = this.npcs.get(e.responder);
        await this.walkTo(e.asker, b.sprite.x + (b.sprite.x > W / 2 ? -16 : 16), b.sprite.y + 2, 60, 5000);
      }));
      for (const e of evs) {
        if (this.skip) break;
        this.face(e.asker, e.responder); this.face(e.responder, e.asker);
        await this.closeOn([e.asker, e.responder]);
        emit("music", "close");
        if (this.skip) break;
        this.bubble(e.asker, e.question, 1900);
        await sleep(this, 1600);
        if (this.skip) break;
        const reply = e.status === "abstained" ? "I'm not sure." : e.reply;
        this.bubble(e.responder, reply, 2600, hideStatus ? "plain" : e.status);
        await sleep(this, 900);
        await this.sendWord(e.responder, e.asker, hideStatus ? "neutral" : e.status);
        shown.add(e); onEvent?.(e);
        if (e.clash && !this.skip) { emit("sfx", "clash"); this.bubble(e.asker, "?!", 1400); this.cameras.main.shake(260, 0.004); }
        await sleep(this, 900);
      }
    }
    for (const e of events) if (!shown.has(e)) onEvent?.(e); // skipped ones still reach the feed
    this.skip = false;
    this.clearFx();
    this.clearBubbles();
    this.cinema(false);
    this.gossiping = false;
    await this.wideShot(600);
    await Promise.all([...this.npcs.keys()].map((id) => this.walkTo(id, this.npcs.get(id).home.x, this.npcs.get(id).home.y, 70, 4000)));
    if (this.mode === "play") this.placeVillagers("inside");
  }

  skipScripted() {
    this.skip = true;
    this.clearFx();
    this.clearBubbles();
    for (const n of this.actors.values()) if (n.scripted) { n.sprite.setPosition(n.scripted.x, n.scripted.y); }
  }

  // Rumour mode: tint each villager by spread state; null clears.
  setRumour(spread) {
    for (const [id, n] of this.npcs) {
      const st = spread?.[id];
      if (!st) { n.sprite.clearTint(); n.ring.setVisible(false); continue; }
      n.sprite.setTint(RUMOUR_TINT[st]);
      n.ring.setVisible(st !== "plain").setTint(RUMOUR_RING[st]);
    }
  }

  setRumourOne(id, st) {
    const n = this.npcs.get(id);
    if (!n) return;
    n.sprite.setTint(RUMOUR_TINT[st]);
    n.ring.setVisible(st !== "plain").setTint(RUMOUR_RING[st]).setScale(1.8);
    this.tweens.add({ targets: n.ring, scale: 1, duration: 400, ease: "Back.easeOut" });
  }

  // Planted rumour, animated. The API gives only who holds the rumour after each round, so each new
  // holder hears it from the nearest villager who already had it (a red teller if the hearer turns red).
  // A traveller whispers it first; each round's first hand-over is shown close up, the rest fly in a wide shot.
  async playRumour(rounds, { origin, text, onRound } = {}) {
    const run = ++this.rumourRun;
    const live = () => run === this.rumourRun;
    const short = text.length > 60 ? `${text.slice(0, 57)}…` : text;
    const bare = short.replace(/[.!?]$/, "");
    let prev = Object.fromEntries([...this.npcs.keys()].map((id) => [id, "plain"]));
    this.setRumour(prev);
    this.cinema(true, "rumour");
    emit("music-level", 0);
    const o = this.npcs.get(origin);
    if (o) {
      await this.closeOn([origin]);
      if (!live()) return;
      this.bubble(origin, "A traveller passing through whispered something…", 2200);
      await sleep(this, 700);
      await this.sendWord(null, origin, "neutral", { from: { x: o.sprite.x + 120, y: o.sprite.y - 50 } });
      if (!live()) return;
    }
    const tell = (h) => h.state === "red" ? `Did you hear? ${short}` : `A traveller claimed ${bare}. I have no record of it.`;
    const hear = (h) => h.state === "red" ? `${bare}!` : "Hm. No record of that.";
    const tone = (st) => st === "red" ? "unsupported" : "abstained";
    for (const [k, round] of rounds.entries()) {
      if (!live()) return;
      const cur = round.spread;
      const changed = Object.keys(cur).filter((id) => cur[id] !== prev[id] && this.npcs.get(id));
      const hops = changed.map((id) => ({ to: id, from: this.nearestHolder(id, prev, cur[id]), state: cur[id] }));
      emit("music-level", k + 1);
      onRound?.(round.round, "start");
      for (const h of hops.filter((h) => !h.from)) this.setRumourOne(h.to, h.state); // the origin on round 1
      const first = hops.find((h) => h.from);
      if (first) {
        // close on the teller, ride along with the word, land on the hearer
        await this.closeOn([first.from]);
        if (!live()) return;
        this.face(first.from, first.to); this.face(first.to, first.from);
        this.bubble(first.from, tell(first), 2400, tone(first.state));
        await sleep(this, 1300);
        await this.sendWord(first.from, first.to, first.state, { follow: true });
        if (!live()) return;
        await this.closeOn([first.to], 400);
        if (!live()) return;
        this.setRumourOne(first.to, first.state);
        this.bubble(first.to, hear(first), 1800, tone(first.state));
        await sleep(this, 1500);
        if (!live()) return;
      }
      const rest = hops.filter((h) => h.from && h !== first);
      await this.wideShot(800);
      if (!live()) return;
      await Promise.all(rest.map(async (h, i) => {
        await sleep(this, i * 220);
        if (!live()) return;
        await this.sendWord(h.from, h.to, h.state);
        if (live()) this.setRumourOne(h.to, h.state);
      }));
      if (!live()) return;
      this.setRumour(cur);
      onRound?.(round.round, "end");
      prev = cur;
      await sleep(this, 900);
    }
    if (live()) this.cinema(false);
  }

  stopRumour() {
    this.rumourRun++;
    this.clearFx();
    this.clearBubbles();
    this.cinema(false);
  }

  nearestHolder(id, spread, want) {
    const b = this.npcs.get(id);
    const holders = [...this.npcs.values()].filter((n) => n.id !== id && spread[n.id] && spread[n.id] !== "plain");
    const pool = want === "red" && holders.some((n) => spread[n.id] === "red") ? holders.filter((n) => spread[n.id] === "red") : holders;
    const d = (n) => Phaser.Math.Distance.Between(n.sprite.x, n.sprite.y, b.sprite.x, b.sprite.y);
    pool.sort((p, q) => d(p) - d(q));
    return pool[0]?.id ?? null;
  }

  focusOn(id) {
    const n = this.npcs.get(id);
    if (!n) return;
    this.cameras.main.pan(n.sprite.x, n.sprite.y - 10, 700, "Sine.easeInOut");
  }
}
