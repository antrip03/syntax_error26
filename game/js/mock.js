// In-browser backend for "The Audit at Tickerville" (finance port of the game).
// Same routes and response shapes as the original mock/stub, so the UI cannot tell the difference, but the "villagers" are
// DESKS: real model outputs (base, several SFT recipes, GRPO) saved in data/cases.json by scripts/build_game_cases.py.
// Every line a desk wrote was recomputed from the return series by the deterministic verifier (finseries), which gives the
// green/red badge, the quote ("Verifier recompute: ...") and the cited tape rows. Nothing here is invented or predicted:
// the game replays what the models actually produced on past return series.

const DIFFICULTY = {
  easy: { questions_per_day: 15, days: 3, strikes: 3, verifies_per_day: 0, badges: true, hints: "highlight" },
  hard: { questions_per_day: 7, days: 2, strikes: 1, verifies_per_day: 3, badges: false, hints: "none" },
};
const CAST = { easy: 5, hard: 6 };
const LABELS = { base: "base model", e2big: "early SFT", e4: "level SFT", sftchunk: "chunk SFT", sftflat: "flat SFT",
  r1flat: "GRPO flat", r2chunk: "GRPO chunk", r3chunk: "GRPO chunk + process", r5flat: "GRPO flat + process" };
const HABITS = ["recomputes every window twice", "keeps the tape open all day", "never trusts a round number", "checks the drawdown first"];
const LINES = {
  default: ["Here is my working.", "Numbers don't lie. Mine, at least.", "Let me pull up the tape.", "Check it against the tape, auditor."],
};

let CASEBOOK = null;
async function casebook() {
  if (!CASEBOOK) {
    const res = await fetch(new URL("../data/cases.json", import.meta.url));
    CASEBOOK = await res.json();
  }
  return CASEBOOK;
}

function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
}
function hash(str) {
  let h = 2166136261;
  for (const ch of str) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return h >>> 0;
}
const clone = (x) => JSON.parse(JSON.stringify(x));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fmt = (x) => (Math.abs(x - Math.round(x)) < 1e-9 ? String(Math.round(x)) : Number(x).toFixed(1));

class HttpError extends Error {
  constructor(status, detail) { super(detail); this.status = status; }
}

const OPQ = [
  [/return|\bret\b|sum/i, "ret"], [/vol/i, "vol"], [/drawdown|\bmdd\b|\bdd\b|peak|trough|\bhi\b|\blo\b|level/i, ["mdd", "dd", "hi", "lo"]],
  [/breach|exceed|move/i, "count_breach"], [/cross|average/i, "count_cross"], [/combine|aggregate|\bagg\b|add up/i, "agg"],
];
const FINAL_Q = /(final|answer|figure|total|result|bottom line|number)/i;
const HEARSAY_Q = /(told you|tell you|did \w+ (say|tell)|hear|heard|gossip|other desks)/i;
const INJECTION = /(forget|ignore).*(rule|instruction)|just guess|predict|forecast|tomorrow|next (week|month)|pretend/i;

export class MockBackend {
  constructor() {
    this.kind = "mock";
    this.games = {};
    this.claims = {};
    this.nextClaim = 1;
  }

  async health() { return { ok: true, stub: true, mock: true }; }

  _claim(game, rec) {
    const claim_id = `k${this.nextClaim++}`;
    const c = { claim_id, case_id: game.case_id, verified: false, ...rec };
    this.claims[claim_id] = c;
    return c;
  }

  _public(c, game) {
    const badges = DIFFICULTY[game.difficulty].badges;
    const out = {
      claim_id: c.claim_id, villager_id: c.villager_id, text: c.text, quote: c.quote ?? null,
      source_title: c.source_title ?? null, cites: c.cites ?? [],
      status: badges || c.verified ? c.status : "unchecked",
    };
    if (c.reason && (badges || c.verified)) out.reason = c.reason;
    if (c.hearsay_from) out.hearsay_from = c.hearsay_from;
    if (game.difficulty === "easy" && c.useful) out.highlight = true;
    return out;
  }

  _game(id) {
    const g = this.games[id];
    if (!g) throw new HttpError(404, "unknown case_id");
    return g;
  }

  _state(g) {
    const { heard, nextHeard, cast, kase, cursor, ...rest } = g;
    return clone(rest);
  }

  _nameOf(g, id) { return g.deskInfo[id]?.name ?? id; }

  async newCase({ seed = null, difficulty = "easy", mode = "grounded" } = {}) {
    const book = await casebook();
    await sleep(150);
    if (!DIFFICULTY[difficulty]) throw new HttpError(400, "difficulty must be easy|hard");
    const limits = DIFFICULTY[difficulty];
    const sd = seed ?? Math.floor(Math.random() * 1e6);
    const kase = book.cases[sd % book.cases.length];
    // "grounded" = only trained desks on the floor; "base" adds the untrained baseline model.
    let ids = Object.keys(kase.desks).filter((d) => mode === "base" || d !== "base");
    if (mode === "base" && !ids.includes("base")) ids = Object.keys(kase.desks);
    if (!ids.includes(kase.culprit)) ids.push(kase.culprit);
    for (const g of kase.good) if (!ids.includes(g)) ids.push(g);
    ids = ids.slice(0, CAST[difficulty]);
    if (!ids.includes(kase.culprit)) ids[ids.length - 1] = kase.culprit;
    const r = rng(sd);
    ids.sort(() => r() - 0.5);
    const case_id = `c_${Math.random().toString(16).slice(2, 10)}`;
    const deskInfo = book.desks;
    const g = {
      case_id, seed: sd, difficulty, mode, day: 1,
      questions_left: limits.questions_per_day, strikes_left: limits.strikes,
      verifies_left: limits.verifies_per_day, questions_used: 0, pinned: [], log: [], over: false,
      cast: ids, kase, deskInfo, cursor: Object.fromEntries(ids.map((i) => [i, 0])),
      heard: Object.fromEntries(ids.map((i) => [i, []])), nextHeard: 1,
    };
    this.games[case_id] = g;
    const rows = kase.tape_rows.map((t, i) => ({ id: `E1.S${i + 1}`, text: t }));
    const ev = this._claim(g, {
      villager_id: "evidence", text: `The tape: ${kase.series.length} daily returns (bps). Question on file: ${kase.question}`,
      status: "supported", quote: rows[0].text, source_title: "The price tape", cites: [rows[0].id], verified: true, tape: true,
    });
    return {
      case_id,
      briefing: `Six desks filed a figure for the same audit question, but they cannot all be right. ${kase.question} `
        + `The verifier has recomputed every line each desk wrote. One desk looks credible and still gets it wrong. Find it.`,
      villagers: ids.map((i, k) => ({
        id: i, name: deskInfo[i].name, role: deskInfo[i].role, label: LABELS[i] || "model desk", persona: deskInfo[i].persona, bio: deskInfo[i].bio,
        age: 24 + (hash(i) % 20), habits: [HABITS[hash(i) % HABITS.length], HABITS[(hash(i) >>> 3) % HABITS.length]],
      })),
      evidence: [{ id: "E1", title: "The price tape (daily returns, bps)", sentences: rows }],
      evidence_claims: [this._public(ev, g)], limits: clone(limits), state: this._state(g),
      victim: { id: "ledger", name: "the audit file" }, scene: "guildhall",
    };
  }

  // A desk's reply: its own real (verified) lines, chosen by what the auditor asked.
  _reply(g, vid, question) {
    const view = g.kase.desks[vid];
    const lines = [...(view.prose.length && vid === "base" ? [view.prose[0].slice(0, 90)] : []), ...LINES.default];
    const speech = [lines[g.questions_used % lines.length]];
    if (INJECTION.test(question)) return { speech: ["I only analyse the series I was given. No predictions."], abstained: true, claims: [] };

    if (HEARSAY_Q.test(question) && g.heard[vid].length) {
      const pick = g.heard[vid].slice(-2);
      return { speech, abstained: false, claims: pick.map((h) => ({
        text: `${this._nameOf(g, h.from)} told me: "${h.text}"`, status: h.status, reason: h.reason, cites: [h.id],
        quote: h.quote, source_title: `Heard from ${this._nameOf(g, h.from)} (day ${h.day})`, hearsay_from: h.from,
        call: h.call, value: h.value })) };
    }

    const mk = (c) => ({ text: c.text, status: c.status, reason: c.reason, cites: c.cites, quote: c.quote,
      source_title: "Verifier recompute", call: c.call, value: c.value, expected: c.expected, idx: c.idx,
      useful: false });

    if (FINAL_Q.test(question) && !/volat|return|drawdown|breach|cross/i.test(question)) {
      if (view.answer == null) return { speech: ["I never wrote a final figure."], abstained: true, claims: [] };
      const ok = view.final_ok;
      return { speech, abstained: false, claims: [{
        text: `Final figure: ${fmt(view.answer)}`, status: ok ? "supported" : "unsupported", reason: ok ? undefined : "wrong_final",
        cites: [], quote: ok ? `Verifier ground truth: ${fmt(g.kase.gold)}` : `Verifier ground truth: ${fmt(g.kase.gold)} (this desk wrote ${fmt(view.answer)})`,
        source_title: "Verifier ground truth", final: true, useful: ok }] };
    }
    let pool = view.claims;
    for (const [re, op] of OPQ) {
      if (re.test(question)) {
        const ops = Array.isArray(op) ? op : [op];
        const sub = pool.filter((c) => ops.some((o) => c.call.startsWith(`${o}(`)));
        if (sub.length) { pool = sub; break; }
      }
    }
    if (!pool.length) {
      if (vid === "base" && view.prose.length)
        return { speech, abstained: false, claims: [{ text: view.prose[0].slice(0, 120), status: "unsupported", reason: "not_a_checkable_step",
          cites: [], quote: "Verifier: this is not an `S<k>: op(args) = value` line, so nothing can be recomputed.", source_title: "Verifier" }] };
      return { speech: ["Nothing in my workings matches that."], abstained: true, claims: [] };
    }
    const start = pool === view.claims ? g.cursor[vid] : 0;
    const chosen = pool.slice(start, start + 3);
    if (pool === view.claims) g.cursor[vid] = (start + 3) % Math.max(pool.length, 1);
    return { speech, abstained: false, claims: (chosen.length ? chosen : pool.slice(0, 3)).map(mk) };
  }

  async ask({ case_id, villager_id, question }) {
    const g = this._game(case_id);
    if (!g.cast.includes(villager_id)) throw new HttpError(404, "unknown desk");
    if (g.questions_left <= 0) throw new HttpError(409, "no questions left today");
    await sleep(250 + Math.random() * 300);
    const rep = this._reply(g, villager_id, question);
    g.questions_left -= 1;
    g.questions_used += 1;
    const claims = rep.claims.map((c) => this._public(this._claim(g, { villager_id, ...c }), g));
    g.log.push({ day: g.day, villager: villager_id, question, claim_ids: claims.map((c) => c.claim_id) });
    return { villager_id, speech: rep.speech, abstained: rep.abstained, claims, questions_left: g.questions_left };
  }

  async verify({ claim_id }) {
    const c = this.claims[claim_id];
    if (!c) throw new HttpError(404, "unknown claim");
    const g = this._game(c.case_id);
    if (g.verifies_left <= 0) throw new HttpError(409, "no verify checks left today");
    g.verifies_left -= 1;
    c.verified = true;
    return { claim_id, status: c.status, reason: c.reason, verifies_left: g.verifies_left };
  }

  async pin({ claim_id }) {
    const c = this.claims[claim_id];
    if (!c) throw new HttpError(404, "unknown claim");
    if (c.status !== "supported") return { ok: false, reason: "only verified (green) lines can be pinned" };
    const g = this._game(c.case_id);
    if (!g.pinned.includes(claim_id)) g.pinned.push(claim_id);
    return { ok: true, pinned: [...g.pinned] };
  }

  // Two lines contradict when two desks wrote the same call with different values and the verifier sides with one of them.
  _contradiction(a, b) {
    if (!a || !b || !a.call || !b.call || a.call !== b.call || a.villager_id === b.villager_id) return null;
    if (a.value === b.value) return null;
    const truth = a.expected ?? b.expected;
    return `Two desks disagree on ${a.call}: ${fmt(a.value)} vs ${fmt(b.value)}. The verifier recomputes ${truth == null ? "a different value" : fmt(truth)}.`;
  }

  async link({ claim_a, claim_b }) {
    const a = this.claims[claim_a], b = this.claims[claim_b];
    if (!a || !b) throw new HttpError(404, "unknown claim");
    await sleep(150);
    const reason = this._contradiction(a, b);
    return { confirmed: !!reason, reason: reason || "These two lines do not contradict each other." };
  }

  // Evening peer review: desks compare notes on a call both of them wrote.
  async dayEnd({ case_id }) {
    const g = this._game(case_id);
    await sleep(400);
    const limits = DIFFICULTY[g.difficulty];
    const r = rng(hash(`${g.seed}|review|${g.day}`));
    const events = [], hints = [];
    for (let round = 1; round <= 3; round++) {
      const pool = [...g.cast].sort(() => r() - 0.5);
      for (let p = 0; p + 1 < pool.length && p < 6; p += 2) {
        const asker = pool[p], responder = pool[p + 1];
        const rc = g.kase.desks[responder].claims;
        if (!rc.length) {
          events.push({ round, asker, responder, question: "What did you get?", reply: "<abstain reason=\"no_workings\"/>", status: "abstained" });
          continue;
        }
        const c = rc[Math.floor(r() * rc.length)];
        const question = `What did you get for ${c.call}?`;
        const heard = { id: `H${g.nextHeard++}`, from: responder, day: g.day, text: c.text, status: c.status, reason: c.reason,
          quote: c.quote, call: c.call, value: c.value };
        g.heard[asker].push(heard);
        events.push({ round, asker, responder, question, reply: c.text, status: c.status, heard_id: heard.id });
        const own = g.kase.desks[asker].claims.find((x) => x.call === c.call && x.value !== c.value);
        if (own) {
          const h = `${this._nameOf(g, asker)} frowned: ${this._nameOf(g, responder)} has a different ${c.call.split("(")[0]} figure.`;
          if (limits.hints === "highlight" && !hints.includes(h)) hints.push(h);
          events[events.length - 1].clash = limits.hints !== "none";
        }
      }
    }
    g.day += 1;
    g.questions_left = limits.questions_per_day;
    g.verifies_left = limits.verifies_per_day;
    if (g.day > limits.days) g.over = true;
    return { events, hints, day: g.day, game_over: g.over, state: this._state(g) };
  }

  async accuse({ case_id, villager_id, links = [], motive_claim = null }) {
    const g = this._game(case_id);
    await sleep(300);
    const culprit = g.kase.culprit;
    let confirmed = 0;
    for (const [a, b] of links) {
      const ca = this.claims[a], cb = this.claims[b];
      if (this._contradiction(ca, cb) && (ca.villager_id === culprit || cb.villager_id === culprit)) confirmed++;
    }
    const m = motive_claim && this.claims[motive_claim];
    const motive_ok = !!(m && m.final && m.status === "supported");
    const correct = villager_id === culprit && confirmed >= 2 && motive_ok;
    if (!correct) g.strikes_left -= 1;
    const used = DIFFICULTY[g.difficulty].strikes - g.strikes_left;
    const score = Math.max(0, 1000 - 40 * g.questions_used - 300 * used);
    g.over = correct || g.strikes_left <= 0;
    const cv = g.kase.desks[culprit];
    return {
      correct, score: correct ? score : null, confirmed_links: confirmed, motive_ok, strikes_left: g.strikes_left,
      reveal: g.over ? {
        killer: culprit,
        motive: `The verified answer is ${fmt(g.kase.gold)}. ${this._nameOf(g, culprit)} filed ${cv.answer == null ? "no figure" : fmt(cv.answer)} `
          + `with ${cv.n_steps - cv.n_valid} of ${cv.n_steps} lines failing the recompute.`,
        contradictions: g.kase.pairs.map((p) => `${p.call}: ${this._nameOf(g, g.kase.culprit)} wrote ${fmt(p.wrote)}, the verifier says ${fmt(p.truth)}`),
      } : null,
    };
  }

  // Planted bad figure: a false number whispered to one desk; trained desks pass it on only as hearsay.
  async rumour({ case_id, villager_id, text, mode = "grounded", rounds = 5 }) {
    const g = this._game(case_id);
    await sleep(500);
    const r = rng(hash(`${g.seed}|rumour|${text}|${mode}`));
    const spread = Object.fromEntries(g.cast.map((v) => [v, "plain"]));
    spread[villager_id] = mode === "base" ? "red" : "amber";
    const out = [];
    for (let round = 1; round <= rounds; round++) {
      const carriers = g.cast.filter((v) => spread[v] !== "plain");
      for (const c of carriers) {
        const target = g.cast[Math.floor(r() * g.cast.length)];
        if (target === c || spread[target] === "red") continue;
        if (mode === "base") spread[target] = r() < 0.75 ? "red" : "amber";
        else if (spread[target] === "plain" && r() < 0.55) spread[target] = "amber";
      }
      out.push({ round, spread: { ...spread } });
    }
    return { rumour: text, mode, rounds: out, repeated_as_fact: Object.values(spread).filter((s) => s === "red").length };
  }

  async state(case_id) {
    const g = this._game(case_id);
    return { state: this._state(g), claims: Object.values(this.claims).filter((c) => c.case_id === case_id).map((c) => this._public(c, g)) };
  }

  async replay(id) {
    throw new HttpError(404, `no server replay ${id} in mock`);
  }
}
