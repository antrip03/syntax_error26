
export const bus = new EventTarget();
export const emit = (type, detail) => bus.dispatchEvent(new CustomEvent(type, { detail }));
export const on = (type, fn) => bus.addEventListener(type, (e) => fn(e.detail));

export const store = {
  settings: { difficulty: "easy", mode: "grounded", seed: "" },
  game: null, 
};

export function newGame(caseResp, settings) {
  store.game = {
    caseId: caseResp.case_id,
    settings: { ...settings },
    briefing: caseResp.briefing,
    villagers: caseResp.villagers,
    evidence: caseResp.evidence,
    limits: caseResp.limits,
    victim: caseResp.victim || { id: "victim", name: "the victim" },
    scene: caseResp.scene || "guildhall",
    scenePlace: caseResp.scene_place || (caseResp.briefing?.match(/found dead in the ([a-z ]+?) on/) || [])[1] || caseResp.scene || "guildhall",
    state: caseResp.state,
    claims: Object.fromEntries((caseResp.evidence_claims || []).map((c) => [c.claim_id, c])),
    evidenceClaimIds: (caseResp.evidence_claims || []).map((c) => c.claim_id),
    pinned: [],
    links: [], 
    chats: {}, 
    gossip: [], 
    over: false,
    result: null,
  };
  emit("game", store.game);
  return store.game;
}

export function villager(id) {
  return store.game?.villagers.find((v) => v.id === id);
}

export function nameOf(id) {
  if (id === "evidence") return "Evidence";
  if (store.game?.victim?.id === id) return store.game.victim.name;
  return villager(id)?.name ?? id;
}
