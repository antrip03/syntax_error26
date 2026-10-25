# Game front end: handoff for the LLM integration

`game/` is the browser game "The Killing at Vaudeville" (P3). It is finished as a front end and
currently runs against either the FastAPI stub (`archive/serve/api.py`) or its own in-browser mock.
**To plug the LLM in, change only the server.** If the server keeps the response shapes below, no
game file needs editing.

## Run

```
python3 -m http.server 5173 -d game                                   # from repo root -> http://localhost:5173
source scripts/env.sh serve && python -m uvicorn archive.serve.api:app --port 8000   # API (stub today)
python archive/serve/tts.py                                           # optional villager voices on :8001
```

- No build step and no Node. Plain ES modules, with Phaser 4.2.0 loaded from jsDelivr. All art and sound are generated in code, so there are no asset files.
- Backend choice: on boot the game calls `GET {apiUrl}/health` (2.5 s timeout). If it answers, every call goes to the API; otherwise it falls back to `js/mock.js`. The title screen shows which one is active.
- URL flags: `?api=http://host:port`, `?offline=1` (force the mock), `?backend=api` (force the API, no fallback), `?tts=http://host:port`, `?debug` (physics boxes).
- CORS: the API must allow the game's origin (the stub already sets permissive CORS middleware).

## The integration contract (what the server must return)

All calls go through `js/api.js` (`HttpBackend`). JSON in, JSON out. Errors are non-2xx with
`{"detail": "message"}`, and the game shows `detail` as a toast.

| Call (sent by) | Request body | Response fields the game reads |
| --- | --- | --- |
| `GET /health` (`api.js`) | none | any 200 |
| `POST /case` (`ui/play.js`, `ui/menus.js`) | `{seed: int\|null, difficulty: "easy"\|"hard", mode: "grounded"\|"base"}` | `case_id, briefing, villagers[{id,name,role,persona}], evidence[{id,title,sentences[{id,text}]}], evidence_claims[claim], limits{questions_per_day,days,strikes,verifies_per_day,badges}, state{day,questions_left,strikes_left,verifies_left,seed}`. Optional: `victim{id,name,role}`, `scene` (a building key, default `"guildhall"`), and per villager `age`, `habits[]`, `bio` (otherwise the journal generates flavour). |
| `POST /ask` (`ui/play.js` `ask()`) | `{case_id, villager_id, question}` | `speech[]` (in-character lines, a leading `#` is stripped), `abstained: bool`, `claims[claim]`, `questions_left` |
| `POST /pin` | `{claim_id}` | `ok`, `pinned[]`, `reason` (shown when `ok` is false) |
| `POST /verify` (Hard only) | `{claim_id}` | `status`, `verifies_left`, optional `reason` |
| `POST /link` (board) | `{claim_a, claim_b}` | `confirmed: bool`, `reason` (a short contradiction label, reused in the accuse screen) |
| `POST /day/end` | `{case_id}` | `events[{round?, asker, responder, question, reply, status, heard_id?, clash?}]`, `hints[]`, `day`, `game_over`, `state{...}` |
| `POST /accuse` | `{case_id, villager_id, links:[[claim_a,claim_b],...], motive_claim: claim_id\|null}` | `correct`, `score`, `confirmed_links`, `motive_ok`, `strikes_left`, and once the game is over `reveal{killer, motive, contradictions[]}` |
| `POST /rumour` (title → Planted rumour) | `{case_id, source: "killer"\|"traveller", village: "plain"\|"sft"\|"grounded", rounds: 5, seed, start?, about?, text?}` | `source_id, framed, text, label, probe, rounds[{round, events[], spread{}, detail{}}], n_villagers, repeated_as_fact, attributed, rebutted` |
| `GET /replay/{id}` | none | a transcript (see Replays) |

**`claim` object**, used everywhere:
`{claim_id, villager_id, text, status, quote, source_title, cites[], reason?, hearsay_from?, highlight?}`

- `status`: `supported` (green), `unsupported` (red), `abstained` (grey) or `unchecked` (Hard mode, until Verify is used).
- `reason` keys the game has wording for: `ok, bad_cite, vacuous, entity_mismatch, fact_mismatch, no_attribution` (`js/ui/claims.js` `REASON`). Unknown keys fall back to "not backed by their records".
- `quote` and `source_title` are shown as the cited source line. `cites` that start with `H` (or a set `hearsay_from`) are labelled as hearsay ("X told me").
- `highlight: true` adds the Easy-mode "★ useful" tag.
- Only `supported` claims can be pinned, and only pinned claims are offered on the board.

**Villager ids and roles drive the map.** `role` picks the home building (`js/map.js` `ROLE_HOME`:
baker→bakery, miller→mill, guard→guildhall, priest→chapel, blacksmith→smithy, herbalist→herb
cottage (scene key `river`), innkeeper→inn). Other roles fall back to the inn, the houses or the
plaza (`FALLBACK_HOMES`). There are 10 outdoor spots, so 8 villagers fit. The title screen promises
Easy = 6 villagers and Hard = 8. Valid `scene` keys are the `ROOMS` keys in `js/map.js` (`mill`,
`river`, `guildhall`, `chapel`, `inn`, `bakery`, `smithy`).

## Where the LLM actually lands

1. **`/ask`** is the core: NPC engine reply plus checker → `speech[]` and `claims[]` with statuses. The game shows speech lines one at a time in the interview box and speaks them (TTS), then shows each claim with its badge, quote and Pin/Verify buttons.
2. **`/day/end`**: villager-to-villager gossip. Each event is animated (the asker walks to the responder, with speech bubbles) and listed in the evening feed.
3. **`/rumour`**: the conversations, probe answers and scoreboard of Planted rumour (`js/ui/rumour.js`).
4. **`/case`**: the generated case (cast, evidence, briefing, victim, scene).
5. **`/link` and `/accuse`**: the contradiction check and the scoring.

Townsfolk (non-case NPCs) and animals use canned lines in `js/map.js` `SMALL_TALK` and never call the backend.

## File-by-file

| File | What it does |
| --- | --- |
| `index.html` | Page shell: Phaser CDN, `config.js`, `js/main.js`, and the DOM layers (`#game` canvas, `#hud`, `#title`, `#encounter`, `#modal-root`, `#toasts`, ...). |
| `config.js` | `window.ARCHIVE_CONFIG = {apiUrl, ttsUrl, backend}`. The one place to point at a deployed server. |
| `styles.css` | All UI styling (HUD, time bar, encounter screen, journal, modals, badges). |
| `README.md` | Player-facing overview and the same contract table. |
| `js/main.js` | Boot: `connect()` to the backend, load fonts, start Phaser with `VillageScene`, global keys. |
| `js/api.js` | `HttpBackend` (fetch wrapper, one method per route) and `connect()`, which picks the API or the mock. **The only network layer.** |
| `js/mock.js` | Offline stand-in for the API, with identical shapes. A keyword-grounded toy villager over `data/elsie.js`: base mode hallucinates red claims, plus hearsay, gossip with clash hints, rumour spread and accuse scoring. Delete or ignore it once the real server is up. |
| `js/data/elsie.js` | The Elsie fixture case (the section 4.3 brief) used only by the mock: villagers, docs with fact ids, contradictions, lexicon. |
| `js/store.js` | Shared state (`store.game`, built from the `/case` response by `newGame()`) and the event bus (`emit`/`on`) between the UI and the Phaser scene. |
| `js/VillageScene.js` | Phaser scene: village and interiors, player movement, case villagers (placed at seeded spots, moving every minute or so), townsfolk and animals, proximity/talk prompts, day clock and lighting, gossip animation, rumour tints, snapshots for the interview background. |
| `js/map.js` | Static world data: building layout, `ROLE_HOME`, interior `ROOMS`, townsfolk `EXTRAS`, `ANIMALS`, `SMALL_TALK`, `OUTDOOR_SPOTS`. |
| `js/art.js`, `js/art_extra.js` | Procedural pixel art: characters (look derived from role and id), buildings, ground, props, furniture, rooms, decor, animals, portraits. |
| `js/profiles.js` | Journal flavour (age, habits, bio) when the server doesn't send them. |
| `js/audio.js` | Web Audio synthesis: ambience per location, townsfolk grunts, footsteps, ducking during talks. |
| `js/voice.js` | `speak(villager, text)`: `POST {ttsUrl}/tts {text, villager_id, role, persona}` → WAV, falling back to the browser's speech voice. |
| `js/ui/play.js` | Case flow: `startCase` (calls `/case`), HUD, briefing, `ask()` (calls `/ask` and records the transcript), pin, verify, notebook, contradiction board (`/link`), end day (`/day/end` plus the gossip feed), accuse (`/accuse`), results screen (Base vs Grounded comparison), transcript download, pause menu. |
| `js/ui/encounter.js` | Pokémon-style interview screen: enlarged sprites over a snapshot of the location, typewriter text box, Ask (free text or suggestions), claims shown one at a time with badges and Pin/Verify. |
| `js/ui/claims.js` | Badge and claim-card rendering, plus the `STATUS` and `REASON` labels. |
| `js/ui/journal.js` | Per-villager profile: portrait, role, age, personality, habits, live location, claim tally, pinned claims, player remarks (saved in `localStorage`). |
| `js/ui/menus.js` | Title screen (difficulty Easy/Hard, Grounded/Base, seed), replay picker and player. Planted rumour lives in `js/ui/rumour.js`. |
| `js/ui/dom.js` | `h()` element helper, modal stack, toasts, confirm dialog, input blocker. |
| `replays/` | `index.json` plus two **hand-written illustrative** transcripts (labelled as such in `source`). Replace them with real recorded runs: Menu → Save transcript downloads the current game in this format. |

## Replays / transcripts

The format is the one `downloadTranscript()` in `ui/play.js` writes:
`{replay_id, title, mode, difficulty, source, briefing, villagers[], turns[{day, type: "ask"|"pin"|"verify"|"link"|"gossip"|"accuse", ...}]}`.
An `ask` turn stores `{villager_id, question, speech, abstained, claims[claim]}`. Recording one Base and
one Grounded run on the same seed gives the demo its side-by-side.

## Known gaps

- `GET /state/{case_id}` exists in `api.js` but the UI doesn't use it, since state comes back on each response.
- The mock's fixture has only 6 villagers, so offline Hard also uses 6. The real generator should send 8.
- The two bundled replays are illustrative, not model output.
