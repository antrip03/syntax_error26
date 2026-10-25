// Vaudville layout, in tiles. Buildings face south; doors are at the bottom centre.

export const MAP = {
  cols: 48,
  rows: 34,
  river: { y: 1, h: 3 },
  bridge: [22, 4],
  plaza: [17, 16, 14, 8],
  roads: [
    [0, 4, 48, 2], // river path
    [22, 4, 4, 28], // north-south high street
    [2, 12, 44, 3], // upper lane
    [2, 24, 44, 2], // lower lane
    [2, 31, 44, 2], // south lane
  ],
  gardens: [[18, 7, 3, 3], [41, 13, 3, 2], [11, 26, 2, 3]],
  pond: [26, 26, 4, 3],
  buildings: [
    { id: "mill", kind: "mill", label: "Mill", x: 3, y: 6, w: 7, h: 5 },
    { id: "river", kind: "cottage", label: "Herb cottage", x: 13, y: 6, w: 5, h: 4 },
    { id: "guildhall", kind: "guildhall", label: "Guildhall", x: 28, y: 5, w: 7, h: 6 },
    { id: "chapel", kind: "chapel", label: "Chapel", x: 35, y: 5, w: 8, h: 6 },
    { id: "inn", kind: "inn", label: "The Drowsy Goose Inn", x: 3, y: 17, w: 8, h: 6 },
    { id: "bakery", kind: "bakery", label: "Bakery", x: 11, y: 17, w: 6, h: 5 },
    { id: "smithy", kind: "smithy", label: "Smithy", x: 35, y: 17, w: 7, h: 5 },
    { id: "house1", kind: "house", label: "", x: 4, y: 26, w: 5, h: 4 },
    { id: "house2", kind: "house2", label: "", x: 13, y: 26, w: 5, h: 4 },
    { id: "house3", kind: "house", label: "", x: 30, y: 26, w: 5, h: 4 },
    { id: "house4", kind: "house2", label: "", x: 38, y: 26, w: 6, h: 4 },
  ],
  trees: [[1, 7], [11, 8], [20, 10], [44, 7], [45, 10], [1, 15], [1, 20], [46, 18], [45, 22], [19, 28],
    [10, 29], [36, 29], [46, 29], [1, 28], [33, 15], [12, 15], [43, 15]],
  bushes: [[9, 11], [26, 11], [27, 22], [16, 22], [34, 23], [42, 23], [3, 30], [44, 30]],
  stalls: [[18, 17, "stall_a"], [28, 17, "stall_b"], [18, 21, "stall_c"]],
  well: [24, 20],
  lamps: [[21, 13], [27, 13], [21, 25], [27, 25], [12, 13], [36, 13], [12, 25], [36, 25]],
  crates: [[10, 10], [33, 21], [17, 15]],
  haystacks: [[0, 9], [1, 10]],
  barrels: [[2, 20], [2, 21], [43, 21]],
  carts: [[31, 21]],
  signs: [[26, 15]],
  fences: [[17, 10, 4], [40, 15, 4], [10, 23, 1]],
  scene: { place: "guildhall", tx: 28.6, ty: 10.4 }, // the open side door
};

// Where each role lives (an anchor in pixels is computed by the scene).
export const ROLE_HOME = {
  miller: "mill", guard: "guildhall", herbalist: "river", baker: "bakery", blacksmith: "smithy",
  priest: "chapel", innkeeper: "inn",
};
export const FALLBACK_HOMES = ["inn", "house1", "house2", "house3", "house4", "plaza"];

// ---------- interiors ----------
// Rooms sit in the same world, below the village. Coordinates are tiles inside the room; the top two
// rows are wall. Furniture: [kind, x, y, w, h, solid]. `station` is where a resident villager stands.

export const ROOMS = {
  bakery: { title: "Bakery", w: 14, h: 10, crime: [2, 5.5], floor: "wood", wall: "#e8c9a0", trim: "#9a5a3a", station: [6.5, 3.8],
    furniture: [["oven", 1, 2, 2, 2, 1], ["oven", 11, 2, 2, 2, 1], ["shelf_bread", 4, 2, 6, 1, 1], ["counter", 2, 4, 8, 1, 1],
      ["sacks", 1, 7, 2, 2, 1], ["table", 9, 7, 3, 1, 1], ["stool", 9, 8, 1, 1, 0], ["stool", 11, 8, 1, 1, 0], ["rug", 5, 6, 3, 2, 0], ["plant", 12, 5, 1, 1, 1]] },
  inn: { title: "The Drowsy Goose Inn", w: 16, h: 11, crime: [3, 5], floor: "wood", wall: "#c9a27a", trim: "#6a3a2a", station: [4, 3.6],
    furniture: [["barrels", 1, 2, 2, 2, 1], ["shelf_bottles", 3, 2, 4, 1, 1], ["counter", 2, 4, 6, 1, 1], ["fireplace", 12, 2, 3, 2, 1],
      ["table", 9, 5, 2, 1, 1], ["table", 12, 5, 2, 1, 1], ["table", 9, 8, 2, 1, 1], ["table", 12, 8, 2, 1, 1],
      ["stool", 8, 5, 1, 1, 0], ["stool", 14, 5, 1, 1, 0], ["stool", 8, 8, 1, 1, 0], ["stool", 14, 8, 1, 1, 0], ["rug", 3, 7, 4, 2, 0]] },
  guildhall: { title: "Guildhall", w: 16, h: 10, floor: "stone", wall: "#a8a090", trim: "#4a3a2a", station: [12.5, 7],
    furniture: [["banner", 3, 0, 1, 2, 0], ["banner", 12, 0, 1, 2, 0], ["shelf_books", 6, 2, 4, 1, 1], ["longtable", 4, 4, 8, 1, 1],
      ["chair", 5, 3, 1, 1, 0], ["chair", 8, 3, 1, 1, 0], ["chair", 10, 3, 1, 1, 0], ["sidedoor", 0, 5, 1, 2, 0], ["rug", 7, 7, 3, 2, 0]], crime: [2, 6] },
  chapel: { title: "Chapel", w: 14, h: 11, crime: [10.5, 8.6], floor: "stone", wall: "#d6d0c4", trim: "#5a5a68", station: [7, 3.4],
    furniture: [["glass", 3, 0, 1, 2, 0], ["glass", 10, 0, 1, 2, 0], ["altar", 5, 2, 4, 1, 1], ["candle", 4, 2, 1, 1, 0], ["candle", 9, 2, 1, 1, 0],
      ["pew", 2, 5, 4, 1, 1], ["pew", 8, 5, 4, 1, 1], ["pew", 2, 7, 4, 1, 1], ["pew", 8, 7, 4, 1, 1], ["runner", 6, 4, 2, 6, 0]] },
  smithy: { title: "Smithy", w: 14, h: 10, crime: [3.5, 7.6], floor: "dirt", wall: "#8a7a6a", trim: "#3a3028", station: [5.5, 6.6],
    furniture: [["forge", 1, 2, 3, 2, 1], ["rack", 9, 2, 4, 1, 1], ["anvil", 5, 5, 2, 1, 1], ["barrel", 12, 7, 1, 1, 1], ["coal", 1, 7, 2, 2, 1], ["bench", 8, 7, 3, 1, 1]] },
  mill: { title: "Mill", w: 14, h: 10, crime: [2, 4], floor: "wood", wall: "#d8c4a0", trim: "#6b4a30", station: [7, 7.2],
    furniture: [["gears", 2, 0, 3, 2, 0], ["grindstone", 5, 2, 4, 3, 1], ["sacks", 1, 6, 2, 2, 1], ["sacks", 11, 6, 2, 2, 1], ["sacks", 11, 3, 2, 1, 1], ["rug", 6, 7, 2, 1, 0]] },
  river: { title: "Herb cottage", w: 12, h: 9, crime: [1.5, 4], floor: "wood", wall: "#d8d0a8", trim: "#5a6a3a", station: [4, 5.4],
    furniture: [["herbs", 1, 0, 4, 2, 0], ["shelf_jars", 1, 2, 4, 1, 1], ["shelf_jars", 7, 2, 4, 1, 1], ["cauldron", 5, 4, 2, 2, 1], ["table", 8, 5, 2, 1, 1], ["plant", 1, 6, 1, 1, 1], ["plant", 10, 7, 1, 1, 1], ["rug", 4, 6, 3, 2, 0]] },
};

// Background townsfolk: not part of the case, no LLM, just small talk (kind picks their lines).
// area: "village" (tile coords) or a room id (room tile coords).
export const EXTRAS = [
  { id: "x_vendor1", name: "Pell", voice: "m", role: "vendor", kind: "vendor", area: "village", at: [19, 19.2], wander: 6 },
  { id: "x_vendor2", name: "Odile", voice: "f", role: "vendor", kind: "vendor", area: "village", at: [29, 19.2], wander: 6 },
  { id: "x_walker1", name: "Hobb", voice: "m", role: "townsfolk", kind: "townsfolk", area: "village", at: [21, 22], wander: 60 },
  { id: "x_walker2", name: "Wren", voice: "f", role: "townsfolk", kind: "townsfolk", area: "village", at: [14, 13.5], wander: 70 },
  { id: "x_walker3", name: "Old Maud", voice: "f_old", role: "elder", kind: "elder", area: "village", at: [8, 24.8], wander: 30 },
  { id: "x_kid", name: "Pip", voice: "kid", role: "kid", kind: "kid", area: "village", at: [27, 23], wander: 80, speed: 46 },
  { id: "x_guard1", name: "Sergeant Holt", voice: "m", role: "watch", kind: "guard", area: "village", at: [31.5, 12.5], wander: 50 },
  { id: "x_guard2", name: "Watchman Rook", voice: "m", role: "watch", kind: "guard", area: "village", at: [24, 6], wander: 40 },
  { id: "x_fisher", name: "Tamsin", voice: "f", role: "townsfolk", kind: "fisher", area: "village", at: [9, 4.6], wander: 20 },
  { id: "x_cust1", name: "Bess", voice: "f", role: "townsfolk", kind: "customer", area: "bakery", at: [5, 6.4], wander: 14 },
  { id: "x_cust2", name: "Alder", voice: "m", role: "townsfolk", kind: "customer", area: "bakery", at: [9, 5.6], wander: 14 },
  { id: "x_barmaid", name: "Junie", voice: "f", role: "barmaid", kind: "barmaid", area: "inn", at: [5, 3.6], wander: 18 },
  { id: "x_patron1", name: "Brann", voice: "m", role: "townsfolk", kind: "patron", area: "inn", at: [10.5, 6.4], wander: 8 },
  { id: "x_patron2", name: "Cobb", voice: "m", role: "townsfolk", kind: "patron", area: "inn", at: [13, 9.4], wander: 8 },
  { id: "x_patron3", name: "Lise", voice: "f", role: "townsfolk", kind: "patron", area: "inn", at: [9.5, 9.4], wander: 8 },
  { id: "x_gguard1", name: "Guard Ash", voice: "m", role: "watch", kind: "guard", area: "guildhall", at: [2.5, 3.4], wander: 10 },
  { id: "x_gguard2", name: "Guard Fenn", voice: "m", role: "watch", kind: "guard", area: "guildhall", at: [14, 3.4], wander: 10 },
  { id: "x_clerk", name: "Clerk Ambrose", voice: "m_old", role: "townsfolk", kind: "clerk", area: "guildhall", at: [9, 6.6], wander: 20 },
  { id: "x_pray1", name: "Widow Hale", voice: "f_old", role: "elder", kind: "worshipper", area: "chapel", at: [3, 6.4], wander: 6 },
  { id: "x_pray2", name: "Tobin", voice: "m", role: "townsfolk", kind: "worshipper", area: "chapel", at: [10, 8.4], wander: 6 },
  { id: "x_appr", name: "Kit", voice: "m", role: "apprentice", kind: "apprentice", area: "smithy", at: [10, 5], wander: 16 },
  { id: "x_farm", name: "Garth", voice: "m", role: "townsfolk", kind: "farmhand", area: "mill", at: [3, 4], wander: 16 },
];

export const ANIMALS = [
  { id: "a_hen1", kind: "chicken", at: [1.5, 12] }, { id: "a_hen2", kind: "chicken", at: [2.5, 11.4] },
  { id: "a_hen3", kind: "chicken", at: [11, 11.2] }, { id: "a_cat", kind: "cat", at: [11.5, 23.3] },
  { id: "a_cat2", kind: "cat", at: [33.5, 11.7] }, { id: "a_duck", kind: "duck", at: [27.5, 28.6] },
];

export const SMALL_TALK = {
  vendor: ["Fresh apples! Two for a copper!", "Turnips fat as your fist, detective.", "Business is slow since the guildhall business."],
  townsfolk: ["Lovely morning for it, isn't it?", "Mind the cobbles, they're slick by the well.", "I keep my door bolted now, I'll tell you that."],
  elder: ["In my day we left our doors open.", "Vaudville's seen hard winters, but nothing like this.", "Speak to folk who wrote it down, dear. Memory is a liar."],
  kid: ["Are you a real detective?!", "I saw a frog THIS big at the pond!", "Bet you can't catch me!"],
  guard: ["Move along, citizen.", "Captain says keep the peace and keep your eyes open.", "Nobody touches the guildhall floor. Orders."],
  fisher: ["Nothing's biting today.", "River's high this week."],
  customer: ["The rye's still warm!", "I come for the honey buns, mostly.", "Shh, I'm deciding."],
  barmaid: ["What'll it be, love?", "Place feels empty without {victim}.", "Inn's open, same as ever. Someone has to."],
  patron: ["Another round!", "To {victim}.", "*hic* ...what was I saying?"],
  clerk: ["Terrible business. Mind how you go.", "Ink, paper, seals. That's the guild.",
    "I stamp what folk say against what they wrote. Green seal if it's in their records, red if it isn't.",
    "Grey? That's when they tell you it's not in their records. Honest enough.",
    "I taught the new ones, you know. Six tries a question, and I stamped the honest ones."],
  worshipper: ["Shh. I'm praying for {victim}.", "Peace be on this village."],
  apprentice: ["Master says never touch the forge bare-handed.", "Forty-two nails today. Forty-three."],
  farmhand: ["Mind the stone, it bites.", "Flour gets everywhere. Everywhere."],
  chicken: ["Bawk!", "Bok bok bok.", "*pecks at your boot*"],
  cat: ["Mrrp.", "*ignores you completely*", "Mew."],
  duck: ["Quack.", "*paddles away*"],
};

// Outdoor places a villager can be found (tiles). Labels read "outside, <label>".
export const OUTDOOR_SPOTS = [
  { id: "plaza", label: "in the market square", at: [23, 22.6] },
  { id: "well", label: "by the well", at: [26.5, 21.2] },
  { id: "riverpath", label: "on the river path", at: [12, 5.2] },
  { id: "bridge", label: "by the bridge", at: [27, 5.2] },
  { id: "pond", label: "by the pond", at: [25, 29.6] },
  { id: "chapelsteps", label: "on the chapel steps", at: [41.5, 12.4] },
  { id: "millyard", label: "in the mill yard", at: [3, 12.6] },
  { id: "smithyyard", label: "by the smithy yard", at: [43.5, 24.6] },
  { id: "southlane", label: "on the south lane", at: [33, 31.6] },
  { id: "herbgarden", label: "by the herb garden", at: [21.5, 11] },
];
