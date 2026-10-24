# The Audit at Tickerville: finance port of the game (branch `finance-ui`)

This branch re-skins the walkable pixel-art game for our FinSeries-RLVR project. **The detective story is gone; the engine, art
and UI are the teammate's untouched.** The villagers are now **desks**: each desk is one of our model stages (untrained base model,
SFT recipes, GRPO). All desks answer the same audit question about the same return series. Every line a desk writes
(`S3: ret(34,43) = 396`) is recomputed by the deterministic verifier, which becomes the badge:

| Original game | Finance port |
| --- | --- |
| villager reads private documents | desk shows its working on a return series (the tape) |
| claim badge (supported / unsupported) + source quote | green / red badge + "Verifier recompute: ret(34,43) = 412" quote, cited tape rows |
| contradiction board | link two lines from different desks that disagree on the same step |
| evening gossip | peer review: desks compare notes, clash hints |
| accuse the killer + motive | flag the desk with the wrong figure + pin a line showing the true final figure |
| Base vs Grounded village | floor with the untrained baseline vs trained desks only |

All data is **real model output** (`data/cases.json`, built by `scripts/build_game_cases.py` from our evaluation runs); the in-browser
mock replays it through the same routes the original API used, so no backend is needed. The models analyse the series they are given;
nothing in the game predicts the market.

Rebuild the cases when new runs finish (adds GRPO desks):
```
python scripts/build_game_cases.py --tasks artifacts/tasks/val.jsonl --desk base=PATH --desk sftchunk=PATH --desk r3chunk=PATH ... --out game/data/cases.json
python scripts/build_game_replays.py
node game/test/mock_smoke.mjs        # plays every case end to end through the mock (solvable on easy and hard)
```

---- original README below ----

# The Killing at Vaudville: game front end (The Archive)

A walkable pixel-art Vaudville (Phaser 4.2 + Arcade Physics) with DOM overlays for questioning,
the notebook, the contradiction board and accusations. There is **no build step**: plain ES modules,
with Phaser loaded from jsDelivr. All art is drawn procedurally at boot (`js/art.js`), so there are
no image assets.

## Run

```
python3 -m http.server 5173 -d game          # from the repo root; open http://localhost:5173
```

The game calls the FastAPI backend at `http://localhost:8000` (set in `config.js`, or override with
`?api=https://...`). If `/health` doesn't answer within 2.5 s, it falls back to an **in-browser mock**
(`js/mock.js`) that mirrors the stub's routes and shapes, so the game is always playable. The title
screen shows which backend is active.

```
source scripts/env.sh serve && python -m uvicorn archive.serve.api:app --port 8000   # stub / real API
```

URL flags: `?offline=1` forces the mock, `?backend=api` forces the API, `?debug` draws physics bodies.
Over SSH: `ssh -L 5173:localhost:5173 -L 8000:localhost:8000 user@server`.

## Plugging in the LLM side

Nothing in the UI changes. The backend has to keep the section 12.3 contract that `archive/serve/api.py`
already serves:

| Route | Fields the game reads |
| --- | --- |
| `POST /case` | `case_id, briefing, villagers[{id,name,role,persona}], evidence[{id,title,sentences[{id,text}]}], evidence_claims[claim], limits{questions_per_day,days,strikes,verifies_per_day,badges}, state{day,questions_left,strikes_left,verifies_left,seed}`; optional `victim{id,name}`, `scene` |
| `POST /ask` | `speech[]` (the `#` lines), `abstained`, `claims[claim]`, `questions_left` |
| `POST /verify` | `status`, `verifies_left`, optional `reason` |
| `POST /pin` | `ok`, `pinned[]`, `reason` |
| `POST /link` | `confirmed`, `reason` |
| `POST /day/end` | `events[{round?,asker,responder,question,reply,status,heard_id?,clash?}]`, `hints[]`, `day`, `game_over`, `state` |
| `POST /accuse` | `correct`, `score`, `confirmed_links`, `motive_ok`, `strikes_left`, `reveal{killer,motive,contradictions[]}` (once over) |
| `POST /rumour` | `rounds[{round, spread{villager_id: red\|amber\|plain}}]`, `repeated_as_fact` |
| `GET /replay/{id}` | a transcript (format below) |

`claim` = `{claim_id, villager_id, text, status: supported|unsupported|abstained|unchecked, quote, source_title, cites[], reason?, hearsay_from?, highlight?}`.
`highlight` is the Easy-mode "useful claim" hint, and `hearsay_from` labels a claim citing an `H` id.
Villager roles pick each villager's home building (`js/map.js` `ROLE_HOME`); unknown roles get a house.

## What's in it

- **Case flow:** morning briefing → walk and question (quick-asks or free text) → badges with quoted source lines → pin green claims → contradiction board (select two, Check) → evening gossip (villagers walk to each other and talk; feed + clash hints) → accuse (suspect + confirmed links + motive) → results.
- **Difficulty:** Easy and Hard. Limits come from the backend's `limits`. On Hard, badges are hidden and claims show a Verify button.
- **Base vs Grounded:** chosen on the title screen. The results screen replays the same seed with the other village and shows a side-by-side grounding table.
- **Planted rumour:** whisper a rumour to one villager, run 5 rounds (Base, Grounded or both). Villagers are tinted red/amber on the map, with a per-round grid.
- **Replay:** `replays/index.json` lists bundled transcripts, and any saved transcript file can be opened. It runs with no server.
- **Interiors:** the mill, herb cottage, guildhall (with the chalk outline to inspect), chapel, inn, bakery and smithy can be entered. Press `E` at the door or walk into it, and walk out through the doormat. A case villager whose home is that building is inside while you visit, and houses are locked. Rooms are defined in `js/map.js` `ROOMS`.
- **Villagers on the move:** each case villager is in exactly one place: inside any building or at an outdoor spot (`OUTDOOR_SPOTS` in `js/map.js`). Spots are re-rolled each morning (seeded by case and day), and one or two villagers move on every minute or so. They walk if you can see them. Building signs show who is inside.
- **Journal (`J`):** a profile page per villager with portrait, role, age, personality, habits, bio, live location, claim tally, pinned claims and your own remarks (saved per case in `localStorage`). Age, habits and bio are generated flavour (`js/profiles.js`) unless the backend sends `age`, `habits` and `bio` on the villager.
- **Interviews:** a battle-screen-style encounter over a snapshot of the current location. Ask (type a question or pick a suggestion), Notes, Leave. Claims are shown one at a time with badge, source and Pin/Verify.
- **Townsfolk and animals** (`EXTRAS`, `ANIMALS`, `SMALL_TALK` in `js/map.js`): vendors, guards, patrons, customers, a kid, chickens, cats and a duck. Their chat is canned flavour text. They never call the backend, cost no questions, and the game says so the first time you chat.
- **Day clock:** cosmetic. It runs from 08:00 to 19:00 (about 9 minutes, plus 20 minutes per question) and drives the lighting from morning warmth to a sunset glow with lamps. At sunset the End day button pulses. Nothing is forced.
- **Recording:** Menu → *Save transcript* (or the results screen) downloads the session in replay format. Record real R0/R3 games this way and drop them into `replays/`.

The two bundled replays are **illustrative**: they were written by hand from the section 4.3 fixture,
not produced by a model, and they say so in their `source` field. Replace them with recorded runs before the demo.

## Files

`js/main.js` boot · `js/api.js` backend selection + HTTP client · `js/mock.js` offline backend ·
`js/VillageScene.js` Phaser scene · `js/art.js` procedural pixel art · `js/map.js` village layout ·
`js/store.js` state + event bus · `js/ui/` DOM screens (`play.js` case flow, `menus.js` title/rumour/replay,
`claims.js` badges, `dom.js` helpers + modal stack).

Deploy: the folder is static, so point Vercel at `game/` with no build command, and set `apiUrl` in `config.js`.
