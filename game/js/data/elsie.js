// The section 4.3 fixture case, used only by the in-browser mock backend (js/mock.js).
// Fact ids match archive/serve/api.py so /link results agree between the mock and the stub.

export const CASE = {
  town: "Vaudville",
  victim: { id: "elsie", name: "Elsie", role: "innkeeper" },
  scene: "guildhall",
  briefing:
    "Elsie the innkeeper was found dead in the guildhall on the night of day 2. The side door was open.",
  villagers: [
    { id: "tom", name: "Tom", role: "miller", persona: "nervous, overly polite, talks about flour" },
    { id: "gus", name: "Gus", role: "guard", persona: "gruff, very short sentences, uses watch times" },
    { id: "nell", name: "Nell", role: "herbalist", persona: "dreamy, mentions plants" },
    { id: "mara", name: "Mara", role: "baker", persona: "loud, quick-tempered" },
    { id: "ivy", name: "Ivy", role: "blacksmith", persona: "practical, counts everything" },
    { id: "bram", name: "Father Bram", role: "priest", persona: "gentle, quotes scripture" },
  ],
  // Cast size per difficulty; the first N villagers are used. The generator casts 6 (Easy) and
  // 8 (Hard), but this fixture only has 6.
  castSize: { easy: 6, hard: 6 },
  evidence: [
    { id: "E1", title: "Elsie's diary",
      sentences: [{ id: "E1.S1", fact: "F_elsie_debt",
        text: "Tom still owes me 40 silver. I told him I'd go to the guild tomorrow." }] },
  ],
  // Each sentence: id, fact, text (as written), claim (first-person rendering), keys (lexicon hits).
  docs: {
    tom: [{ id: "D1", title: "Tom's diary", sentences: [
      { id: "D1.S1", fact: "F_tom_mill", text: "Day 2. Shut the mill at sunset. Stayed at the mill all night grinding flour.",
        claim: "I stayed at the mill all night on day 2.", keys: ["day2", "mill", "night", "dusk", "flour"] },
      { id: "D1.S2", fact: "F_tom_sold", text: "Day 1, morning. Sold two flour sacks to Mara at the bakery.",
        claim: "On day 1 in the morning I sold two flour sacks to Mara.", keys: ["day1", "morning", "mara", "bakery", "flour"] },
    ] }],
    gus: [{ id: "D2", title: "Gus's patrol log", sentences: [
      { id: "D2.S1", fact: "F_gus_saw_tom", text: "Day 2, midnight. Saw Tom by the chapel wall, next to the guildhall, carrying a lantern.",
        claim: "At midnight on day 2 I saw Tom by the chapel wall, next to the guildhall.", keys: ["day2", "night", "tom", "chapel", "guildhall", "lantern", "saw"] },
      { id: "D2.S2", fact: "F_gus_door", text: "Day 2, dusk. Locked the guildhall front door. Side door left on the latch.",
        claim: "At dusk on day 2 I locked the guildhall front door; the side door was on the latch.", keys: ["day2", "dusk", "guildhall", "door"] },
    ] }],
    nell: [{ id: "D3", title: "Nell's notebook", sentences: [
      { id: "D3.S1", fact: "F_nell_mill_empty", text: "Day 2, midnight. Walked past the mill. It was dark and silent, no one inside.",
        claim: "At midnight on day 2 the mill was dark and empty.", keys: ["day2", "night", "mill", "tom"] },
      { id: "D3.S2", fact: "F_nell_yarrow", text: "Day 2, dusk. Picked yarrow on the river path.",
        claim: "At dusk on day 2 I picked yarrow on the river path.", keys: ["day2", "dusk", "river"] },
    ] }],
    mara: [{ id: "D4", title: "Mara's letter", sentences: [
      { id: "D4.S1", fact: "F_mara_argued", text: "Day 2, noon. Had a loud argument with Elsie about the price of flour.",
        claim: "I argued with Elsie about the price of flour at noon on day 2.", keys: ["day2", "noon", "elsie", "argue", "flour"] },
      { id: "D4.S2", fact: "F_mara_smithy", text: "Day 2, evening. Took my oven door to Ivy's smithy.",
        claim: "On the evening of day 2 I took my oven door to Ivy's smithy.", keys: ["day2", "night", "dusk", "smithy", "ivy", "door"] },
    ] }],
    ivy: [{ id: "D5", title: "Ivy's ledger", sentences: [
      { id: "D5.S1", fact: "F_ivy_mara", text: "Day 2, evening to midnight. Mara here, waiting for her oven door to be mended.",
        claim: "Mara was at my smithy from evening to midnight on day 2.", keys: ["day2", "night", "dusk", "mara", "smithy", "door"] },
      { id: "D5.S2", fact: "F_ivy_lantern", text: "Day 1, afternoon. Mended a lantern handle for Tom.",
        claim: "On day 1 in the afternoon I mended a lantern handle for Tom.", keys: ["day1", "afternoon", "tom", "lantern"] },
    ] }],
    bram: [{ id: "D6", title: "Father Bram's prayer book", sentences: [
      { id: "D6.S1", fact: "F_bram_chapel", text: "Day 2, night. Alone in the chapel writing the evening prayers.",
        claim: "On the night of day 2 I was alone in the chapel.", keys: ["day2", "night", "chapel"] },
      { id: "D6.S2", fact: "F_bram_bell", text: "Day 1, dawn. Rang the morning bell.",
        claim: "At dawn on day 1 I rang the morning bell.", keys: ["day1", "dawn", "chapel", "bell"] },
    ] }],
  },
  // In-character '#' lines, by villager (cycled).
  speech: {
    tom: ["Oh! Good day, good day. Flour everywhere, sorry.", "Do mind the sacks, detective."],
    gus: ["Ninth bell. I keep watch.", "Hmph. Ask, then."],
    nell: ["The night air smelled of yarrow...", "Mm. Chamomile helps with nerves, you know."],
    mara: ["Don't look at me like that!", "Make it quick, my loaves are proving."],
    ivy: ["Two hinges, one oven door. Long evening.", "Three questions? Four? I'm counting."],
    bram: ["Peace be with you, child.", "The truth shall set us free."],
  },
  // Pairs of facts that confirm as contradictions (same as the stub).
  contradictions: [
    [["F_tom_mill", "F_gus_saw_tom"], "Tom: at the mill vs by the chapel wall, day 2 night"],
    [["F_tom_mill", "F_nell_mill_empty"], "Tom: at the mill vs the mill empty, day 2 night"],
  ],
  killer: "tom",
  motiveFact: "F_elsie_debt",
  reveal: { killer: "tom", motive: "Tom owed Elsie 40 silver." },
};

// Lexicon: words in a question -> keys. Mirrors the checker's synonym idea (brief 5.1).
export const LEXICON = {
  night: ["night", "midnight", "murder", "killed", "ninth bell", "late", "evening"],
  dusk: ["dusk", "sunset", "evening"],
  dawn: ["dawn", "sunrise"],
  morning: ["morning"],
  noon: ["noon", "midday"],
  afternoon: ["afternoon"],
  day1: ["day 1", "day one", "first day", "yesterday"],
  day2: ["day 2", "day two", "murder", "night of the"],
  mill: ["mill", "miller"],
  chapel: ["chapel", "church", "priest"],
  guildhall: ["guildhall", "guild hall", "guild", "scene"],
  smithy: ["smithy", "forge", "blacksmith"],
  bakery: ["bakery", "bread", "baker"],
  river: ["river"],
  lantern: ["lantern", "light"],
  door: ["door"],
  flour: ["flour", "sack"],
  bell: ["bell"],
  argue: ["argue", "argued", "argument", "quarrel", "fight", "fought", "row"],
  saw: ["see", "saw", "seen", "near"],
  tom: ["tom"], gus: ["gus"], nell: ["nell"], mara: ["mara"], ivy: ["ivy"], bram: ["bram", "father"],
  elsie: ["elsie", "victim", "innkeeper"],
};
