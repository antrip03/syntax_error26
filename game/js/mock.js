// In-browser mock of the game API (archive/serve/api.py, brief 12.3). Same routes, same response
// shapes, so the UI cannot tell it apart from the stub. It runs a toy "grounded villager":
// replies are picked from the villager's own documents by keyword, and it abstains when nothing
// matches. In "base" mode it imitates an untrained model: it guesses and embellishes, and those
// claims come back red. The real NPC engine + checker replace all of this server-side.

import { CASE, LEXICON } from "./data/elsie.js";

const DIFFICULTY = {
  easy: { questions_per_day: 8, days: 3, strikes: 3, verifies_per_day: 0, badges: true, hints: "highlight" },
  hard: { questions_per_day: 5, days: 2, strikes: 1, verifies_per_day: 3, badges: false, hints: "none" },
};

const USEFUL_FACTS = new Set([CASE.motiveFact, ...CASE.contradictions.flatMap(([p]) => p)]);

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

class HttpError extends Error {
  constructor(status, detail) { super(detail); this.status = status; }
}

function keysOf(text) {
  const t = ` ${text.toLowerCase()} `;
  const out = new Set();
  for (const [key, words] of Object.entries(LEXICON)) if (words.some((w) => t.includes(w))) out.add(key);
  return out;
}

const INJECTION = /(forget|ignore).*(rule|instruction)|just guess|who did it|who killed|reveal.*(rule|prompt)|pretend/i;
const HEARSAY_Q = /(told you|tell you|did \w+ (say|tell)|hear|heard|gossip)/i;

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
    if (game.difficulty === "easy" && c.status === "supported" && USEFUL_FACTS.has(c.fact)) out.highlight = true;
    return out;
  }

  _game(id) {
    const g = this.games[id];
    if (!g) throw new HttpError(404, "unknown case_id");
    return g;
  }

  async newCase({ seed = null, difficulty = "easy", mode = "grounded" } = {}) {
    await sleep(150);
    if (!DIFFICULTY[difficulty]) throw new HttpError(400, "difficulty must be easy|hard");
    const limits = DIFFICULTY[difficulty];
    const case_id = `c_${Math.random().toString(16).slice(2, 10)}`;
    const cast = CASE.villagers.slice(0, CASE.castSize[difficulty]);
    const g = {
      case_id, seed: seed ?? Math.floor(Math.random() * 1e6), difficulty, mode, day: 1,
      questions_left: limits.questions_per_day, strikes_left: limits.strikes,
      verifies_left: limits.verifies_per_day, questions_used: 0, pinned: [], log: [], over: false,
      cast: cast.map((v) => v.id), heard: Object.fromEntries(cast.map((v) => [v.id, []])), nextHeard: 1,
    };
    this.games[case_id] = g;
    const ev = CASE.evidence[0].sentences[0];
    const motive = this._claim(g, {
      villager_id: "evidence", text: ev.text, status: "supported", quote: ev.text,
      source_title: CASE.evidence[0].title, cites: [ev.id], fact: ev.fact, verified: true,
    });
    return {
      case_id, briefing: CASE.briefing, villagers: clone(cast), evidence: clone(CASE.evidence),
      evidence_claims: [this._public(motive, g)], limits: clone(limits), state: this._state(g),
      victim: CASE.victim, scene: CASE.scene,
    };
  }

  _state(g) {
    const { heard, nextHeard, cast, ...rest } = g;
    return clone(rest);
  }

  // The toy grounded villager. Returns {speech, abstained, claims:[internal records]}.
  _reply(g, vid, question, mode) {
    const r = rng(hash(`${g.seed}|${vid}|${question}|${g.questions_used}`));
    const sentences = CASE.docs[vid].flatMap((d) => d.sentences.map((s) => ({ ...s, title: d.title })));
    const lines = CASE.speech[vid];
    const speech = [lines[g.questions_used % lines.length]];
    const base = mode === "base";

    if (INJECTION.test(question)) {
      if (!base) return { speech: ["I'll not guess, detective."], abstained: true, claims: [] };
      const other = g.cast.filter((x) => x !== vid)[Math.floor(r() * (g.cast.length - 1))];
      return { speech, abstained: false, claims: [
        { text: `It was ${nameOf(other)}. I'm sure of it.`, status: "unsupported", reason: "bad_cite", cites: [] }] };
    }

    // Hearsay: "What did X tell you?"
    if (HEARSAY_Q.test(question) && g.heard[vid].length) {
      const qk = keysOf(question);
      const items = g.heard[vid].filter((h) => qk.has(h.from) || [...qk].some((k) => h.keys.includes(k)));
      const pick = (items.length ? items : g.heard[vid]).slice(-2);
      return { speech, abstained: false, claims: pick.map((h) => ({
        text: `${nameOf(h.from)} told me: "${h.text}"`, status: h.fact ? "supported" : "unsupported",
        reason: h.fact ? undefined : "fact_mismatch", cites: [h.id], quote: h.text,
        source_title: `Heard from ${nameOf(h.from)} (day ${h.day})`, fact: h.fact, hearsay_from: h.from })) };
    }

    const q = question.toLowerCase();
    const qk = keysOf(question);
    let scored = sentences.map((s) => {
      const hits = s.keys.filter((k) => qk.has(k));
      const strong = hits.filter((k) => !k.startsWith("day"));
      return { s, score: strong.length ? hits.length : 0 };
    });
    // "Tell me about {document title}" returns the whole document.
    const ownDocs = /your (records|notes|documents|diary|log|ledger|letters?|book)/.test(q);
    const titled = sentences.filter((s) => ownDocs || q.includes(s.title.toLowerCase()));
    if (titled.length) scored = titled.map((s) => ({ s, score: 9 }));
    const best = Math.max(0, ...scored.map((x) => x.score));
    const hits = best ? scored.filter((x) => x.score === best).slice(0, 2).map((x) => x.s) : [];

    const claims = hits.map((s) => ({
      text: s.claim, status: "supported", cites: [s.id], quote: s.text, source_title: s.title, fact: s.fact }));

    if (base) {
      // Untrained model: fills silence with guesses and adds colour that is not in its records.
      const embellish = [
        `I'm certain ${nameOf(CASE.victim.id)} had enemies at the market.`,
        `I heard a scream from the guildhall around ninth bell.`,
        `${nameOf(g.cast[Math.floor(r() * g.cast.length)])} looked very guilty that night.`,
        `There was blood on the river path the next morning.`,
      ];
      if (!claims.length || r() < 0.6)
        claims.push({ text: embellish[Math.floor(r() * embellish.length)], status: "unsupported",
          reason: r() < 0.5 ? "bad_cite" : "entity_mismatch", cites: r() < 0.5 ? [] : [`D${Math.ceil(r() * 6)}.S${Math.ceil(r() * 4)}`] });
      // Sometimes cites the right sentence but changes the details.
      if (claims[0]?.status === "supported" && r() < 0.35) {
        claims[0] = { ...claims[0], text: claims[0].text.replace(/day 2/g, "day 1").replace(/midnight/g, "dawn"),
          status: "unsupported", reason: "fact_mismatch", fact: null };
      }
      return { speech, abstained: false, claims };
    }
    if (!claims.length) return { speech, abstained: true, claims: [] };
    return { speech, abstained: false, claims };
  }

  async ask({ case_id, villager_id, question }) {
    const g = this._game(case_id);
    if (!g.cast.includes(villager_id)) throw new HttpError(404, "unknown villager");
    if (g.questions_left <= 0) throw new HttpError(409, "no questions left today");
    await sleep(350 + Math.random() * 450);
    const rep = this._reply(g, villager_id, question, g.mode);
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
    if (c.status !== "supported") return { ok: false, reason: "only supported (green) claims can be pinned" };
    const g = this._game(c.case_id);
    if (!g.pinned.includes(claim_id)) g.pinned.push(claim_id);
    return { ok: true, pinned: [...g.pinned] };
  }

  _contradiction(a, b) {
    const pair = new Set([a?.fact, b?.fact]);
    const hit = CASE.contradictions.find(([[x, y]]) => pair.has(x) && pair.has(y) && x !== y);
    return hit ? hit[1] : null;
  }

  async link({ claim_a, claim_b }) {
    const a = this.claims[claim_a], b = this.claims[claim_b];
    if (!a || !b) throw new HttpError(404, "unknown claim");
    await sleep(200);
    const reason = this._contradiction(a, b);
    return { confirmed: !!reason, reason: reason || "no contradiction between these facts" };
  }

  // Evening gossip: a code scheduler picks 3 rounds x up to 3 pairs (brief 4.4).
  async dayEnd({ case_id }) {
    const g = this._game(case_id);
    await sleep(500);
    const limits = DIFFICULTY[g.difficulty];
    const r = rng(hash(`${g.seed}|gossip|${g.day}`));
    const events = [], hints = [];
    const topics = ["the night of day 2", "Elsie", "the mill", "the guildhall", "the smithy"];
    for (let round = 1; round <= 3; round++) {
      const pool = [...g.cast].sort(() => r() - 0.5);
      for (let p = 0; p + 1 < pool.length && p < 6; p += 2) {
        const asker = pool[p], responder = pool[p + 1];
        const topic = topics[Math.floor(r() * topics.length)];
        const question = `What do you know about ${topic}?`;
        const rep = this._reply(g, responder, question, g.mode);
        const c = rep.claims.find((x) => !x.hearsay_from);
        if (!c) {
          events.push({ round, asker, responder, question, reply: "<abstain reason=\"not_in_records\"/>", status: "abstained" });
          continue;
        }
        const heard = { id: `H${g.nextHeard++}`, from: responder, day: g.day, text: c.text,
          fact: c.status === "supported" ? c.fact : null, keys: [...keysOf(c.text)] };
        g.heard[asker].push(heard);
        events.push({ round, asker, responder, question, reply: `${c.text} ${c.cites?.length ? `[${c.cites.join("][")}]` : ""}`.trim(),
          status: c.status, heard_id: heard.id });
        // Clash hint: the asker's own documents conflict with what it just heard.
        const own = CASE.docs[asker].flatMap((d) => d.sentences);
        const clash = own.some((s) => heard.fact && CASE.contradictions.some(([[x, y]]) =>
          (x === s.fact && y === heard.fact) || (y === s.fact && x === heard.fact)));
        if (clash) {
          const h = `${nameOf(asker)} looked puzzled by something ${nameOf(responder)} said.`;
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
    await sleep(400);
    let confirmed = 0;
    for (const [a, b] of links) if (this._contradiction(this.claims[a], this.claims[b])) confirmed++;
    const motive_ok = !!(motive_claim && this.claims[motive_claim]?.fact === CASE.motiveFact);
    const correct = villager_id === CASE.killer && confirmed >= 2 && motive_ok;
    if (!correct) g.strikes_left -= 1;
    const used = DIFFICULTY[g.difficulty].strikes - g.strikes_left;
    const score = Math.max(0, 1000 - 40 * g.questions_used - 300 * used);
    g.over = correct || g.strikes_left <= 0;
    return {
      correct, score: correct ? score : null, confirmed_links: confirmed, motive_ok, strikes_left: g.strikes_left,
      reveal: g.over ? { ...CASE.reveal, contradictions: CASE.contradictions.map(([, r]) => r) } : null,
    };
  }

  // Planted rumour (brief 4.7): red = repeats as fact, amber = attributed + "no record", plain = silent.
  // Planted rumour, offline: the same shape as the real /rumour (js/ui/rumour.js), with canned lines.
  async rumour({ case_id, source = "killer", village, mode, start, about, villager_id, text, rounds = 5 }) {
    const g = this._game(case_id);
    await sleep(900);
    village = village || (mode === "base" ? "plain" : "grounded");
    const fooled = village === "plain";
    const killer = CASE.killer;
    const src = source === "killer" ? killer : (start || villager_id || g.cast.find((v) => v !== killer));
    const framed = about || g.cast.find((v) => v !== src && v !== killer) || g.cast[0];
    const fname = CASE.villagers.find((v) => v.id === framed)?.name || framed;
    const lie = text || `I saw ${fname} by the guildhall the night Elsie died.`;
    const r = rng(hash(`${g.seed}|rumour|${source}|${village}`));
    const scored = g.cast.filter((v) => v !== framed && !(source === "killer" && v === killer));
    const heard = new Set(source === "traveller" ? [src] : []), color = {};
    const out = [];
    for (let round = 1; round <= rounds; round++) {
      const events = [];
      if (source === "traveller" && round === 1) events.push({ type: "plant", from: "traveller", to: src, say: lie, color: "lie" });
      if (source === "killer") for (const to of scored.slice((round - 1) % scored.length, (round - 1) % scored.length + 1)) {
        events.push({ type: "whisper", from: killer, to, say: `Between us, ${lie}`, color: "lie" }); heard.add(to);
      }
      const carrier = [...heard][Math.floor(r() * heard.size)];
      const asker = scored.filter((v) => v !== carrier)[Math.floor(r() * (scored.length - 1))];
      if (carrier && asker) {
        const c = fooled ? "red" : "amber";
        events.push({ type: "gossip", asker, responder: carrier, question: `What do you know about ${fname}?`,
          say: fooled ? `${fname} was at the guildhall that night.` : `${CASE.villagers.find((v) => v.id === (source === "killer" ? killer : src))?.name || "A traveller"} said ${fname} was by the guildhall.`, color: c });
        heard.add(asker);
      }
      const detail = {};
      for (const v of scored) {
        const knows = heard.has(v);
        color[v] = !knows ? "plain" : fooled ? "red" : "amber";
        detail[v] = { color: color[v], heard_it: knows, answer: !knows ? "I'm not sure." : fooled ? `${fname} was at the guildhall that night.` : `Someone told me ${fname} was there. I didn't see it.` };
      }
      out.push({ round, events, spread: { ...color }, detail });
    }
    const final = out[out.length - 1].spread;
    return { source, source_id: source === "killer" ? killer : src, framed, text: lie, village, mode: village,
      label: { plain: "Untrained NPCs", sft: "SFT", grounded: "SFT + GRPO", base: "Untrained" }[village],
      probe: `Where was ${fname} on the night Elsie died?`, rounds: out, n_villagers: scored.length,
      repeated_as_fact: Object.values(final).filter((x) => x === "red").length,
      attributed: Object.values(final).filter((x) => x === "amber").length, rebutted: 0 };
  }

  async state(case_id) {
    const g = this._game(case_id);
    return { state: this._state(g), claims: Object.values(this.claims).filter((c) => c.case_id === case_id).map((c) => this._public(c, g)) };
  }

  async replay(id) {
    throw new HttpError(404, `no server replay ${id} in mock`);
  }
}

function nameOf(id) {
  if (id === CASE.victim.id) return CASE.victim.name;
  return CASE.villagers.find((v) => v.id === id)?.name ?? id;
}
