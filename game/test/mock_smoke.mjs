// Headless smoke test of the finance mock: plays a full solvable audit through the same routes the UI calls.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const _st = globalThis.setTimeout; globalThis.setTimeout = (f, ms, ...a) => _st(f, 0, ...a); // skip the UI latency
globalThis.fetch = async (u) => ({ json: async () => JSON.parse(readFileSync(fileURLToPath(u), "utf8")) });
const { MockBackend } = await import("../js/mock.js");
const book = JSON.parse(readFileSync(new URL("../data/cases.json", import.meta.url), "utf8"));
let solved = 0, tried = 0;
for (let seed = 0; seed < book.cases.length; seed++) {
  for (const difficulty of ["easy", "hard"]) {
    const api = new MockBackend();
    const c = await api.newCase({ seed, difficulty, mode: "base" });
    const kase = book.cases[seed % book.cases.length];
    const ids = c.villagers.map((v) => v.id);
    if (!ids.includes(kase.culprit)) throw new Error("culprit missing from cast");
    // interview every desk: work, final figure
    const claims = {};
    for (const id of ids) {
      for (const q of ["Show me your work.", "Show me your work.", "Show me your work.", "Show me your work.", "What is your final figure?"]) {
        let r;
        try { r = await api.ask({ case_id: c.case_id, villager_id: id, question: q }); }
        catch (e) { if (e.status !== 409) throw e; await api.dayEnd({ case_id: c.case_id }); r = await api.ask({ case_id: c.case_id, villager_id: id, question: q }); }
        for (const cl of r.claims) claims[cl.claim_id] = cl;
      }
    }
    if (difficulty === "hard") for (const k of Object.keys(claims).slice(0, 3)) await api.verify({ claim_id: k });
    // find final-figure claim that is supported -> motive; find 2 confirmed contradictions involving culprit
    const all = Object.values(api.claims).filter((x) => x.case_id === c.case_id);
    const motive = all.find((x) => x.final && x.status === "supported");
    const links = [];
    const bad = all.filter((x) => x.villager_id === kase.culprit && x.status === "unsupported" && x.call);
    for (const a of bad) for (const b of all) {
      const r = await api.link({ claim_a: a.claim_id, claim_b: b.claim_id });
      if (r.confirmed && !links.some(([x]) => api.claims[x].call === a.call)) { links.push([a.claim_id, b.claim_id]); break; }
    }
    const res = await api.accuse({ case_id: c.case_id, villager_id: kase.culprit, links, motive_claim: motive?.claim_id });
    tried++;
    if (res.correct) solved++;
    else console.log("unsolved", seed, difficulty, { links: links.length, motive: !!motive, res });
    const gos = await api.dayEnd({ case_id: c.case_id });
    if (!Array.isArray(gos.events)) throw new Error("dayEnd shape");
  }
}
console.log(`solvable: ${solved}/${tried}`);
