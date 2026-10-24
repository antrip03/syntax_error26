// Ambient cast for the title screen only (the playable desks come from data/cases.json via js/mock.js).
export const CASE = {
  town: "Tickerville",
  victim: { id: "ledger", name: "the audit file", role: "ledger" },
  villagers: [
    { id: "barry", name: "Barry Base", role: "miller", persona: "untrained zero-shot model" },
    { id: "edie", name: "Edie Early", role: "herbalist", persona: "first SFT recipe" },
    { id: "eli", name: "Eli Levels", role: "guard", persona: "running-level SFT" },
    { id: "chen", name: "Chen Chunk", role: "baker", persona: "chunk-summary scaffold" },
    { id: "fiona", name: "Fiona Flat", role: "blacksmith", persona: "five-day window scaffold" },
    { id: "rhea", name: "Rhea Reward", role: "priest", persona: "GRPO with the verifier as reward" },
  ],
};
