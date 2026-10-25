import { hash } from "./art.js";

const HABITS = {
  miller: ["up before dawn to open the sluice", "counts flour sacks twice", "hums while the stones turn"],
  guard: ["walks the same patrol route every night", "keeps a tidy patrol log", "drinks his tea black and cold"],
  herbalist: ["gathers yarrow at dusk", "presses flowers in her notebook", "talks to her plants"],
  baker: ["fires the ovens at four bells", "argues prices at the market", "saves the burnt loaves for the birds"],
  blacksmith: ["keeps a ledger of every job", "never lets the forge go cold", "tests every hinge three times"],
  priest: ["rings the morning bell", "writes the evening prayers by candle", "visits the sick on market day"],
  innkeeper: ["knows everyone's tab", "polishes the same glass when thinking", "hears all the gossip"],
};
const GENERIC = ["takes long walks by the river", "never misses market day", "keeps to themselves after dark", "writes everything down"];
const BIO = {
  miller: "Runs the mill by the river. Polite to a fault, and nervous when money comes up.",
  guard: "Keeps the night watch around the guildhall and the chapel. Few words, sharp eyes.",
  herbalist: "Grows remedies in the cottage garden and wanders the paths at odd hours.",
  baker: "Her bakery feeds half the village. Quick to anger, quicker to forgive.",
  blacksmith: "Mends everything from oven doors to lanterns, and keeps careful accounts.",
  priest: "Has tended Vaudeville's chapel for twenty years. Gentle, and hard to rattle.",
  innkeeper: "Runs the inn and hears every rumour in the village.",
};

export function profileFor(v) {
  const r = hash(v.id);
  const role = (v.role || "").toLowerCase();
  const pool = HABITS[role] || GENERIC;
  const habits = v.habits || [pool[r % pool.length], pool[(r >>> 3) % pool.length], GENERIC[(r >>> 6) % GENERIC.length]]
    .filter((x, i, a) => a.indexOf(x) === i);
  return {
    age: v.age ?? 24 + (r % 45),
    habits,
    bio: v.bio || BIO[role] || `A ${v.role || "villager"} of Vaudeville.`,
    flavour: !(v.age && v.habits && v.bio),
  };
}
