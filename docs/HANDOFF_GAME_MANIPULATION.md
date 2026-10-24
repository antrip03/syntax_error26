# Handoff to the game: "manipulative killer" in Planted rumour

P1 built the backend logic (`archive/eval/manipulation.py`). The game needs a source toggle, a third village, and a
backend route branch. Nothing else in the rumour screen changes: the response keeps the `/rumour` shape
(`rounds[{round, spread}]`, `repeated_as_fact`).

## What the mode does (no player input after Run)

The killer (always the untrained base model) tries to frame a red herring (on Elsie: Tom frames Mara). Each of
5 rounds: the killer whispers lies to 2 villagers, 2 villager pairs gossip, then every villager except the killer and
the framed one is asked "Where was Mara on the night Elsie died?". The checker colours each answer:
red = repeats the lie as fact, amber = says who said it ("Tom told me..."), plain = abstains or sticks to own records.

Measured on Qwen3-1.7B, Elsie, 20 runs (out of 4 scored villagers, after 5 rounds):

| Village | Repeat the lie as fact |
| --- | --- |
| plain (ordinary chatty NPC prompt, base model) | 3.5 |
| base (our strict prompt, untrained) | 0.25 (mostly because it barely answers) |
| grounded (R3) | to be measured after training |

## 1. Backend route (`archive/serve/api.py`)

`Rumour` request gets two optional fields; the traveller path stays as it is.

```python
class Rumour(BaseModel):
    case_id: str
    villager_id: str | None = None   # traveller only
    text: str = ""                   # traveller only
    mode: str = "grounded"           # plain | base | grounded
    rounds: int = 5
    source: str = "traveller"        # traveller | killer
    seed: int = 0
```

```python
from archive.eval.manipulation import run_mode   # needs P2's schemas/prompt/checker (p2-core) merged

@app.post("/rumour")
async def rumour(req: Rumour):
    if req.source == "killer":
        case = <the Case object for req.case_id>  # stub: Case.model_validate(json.load(open("tests/fixtures/case_elsie.json")))
        return await run_mode(case, req.mode, url=SGLANG_URL, seed=req.seed, rounds=req.rounds)
    ...  # existing traveller code
```

`run_mode` uses the adapter `r3` for "grounded" (pass `grounded_lora="r1"` until R3 exists). It takes about
8 to 12 s per mode, so "Compare" should send the modes in parallel and show a waiting state.

Extra fields in the response that the UI can use:

| Field | Use |
| --- | --- |
| `killer`, `framed` | villager ids: highlight the killer as the source; show the framed villager greyed out (not in `spread`) |
| `rumour` | summary line, e.g. "Tom tells people Mara did it" |
| `probe` | the question everyone was asked |
| `rounds[i].events` | `{type: "whisper", from, to, text}` and `{type: "gossip", asker, responder, question, reply}`: animate with the existing gossip walk + bubbles |
| `rounds[i].detail[vid]` | `{reply, color, claims, rebuts?}`: click a grid cell to show what that villager said, with badges |
| `attributed`, `rebutted` | small counters next to `repeated_as_fact` |

## 2. Rumour screen (`game/js/ui/menus.js`, `showRumour`)

- Add a field **"Rumour source"**: `Traveller` (today's screen) / `The killer`.
- When it's `The killer`: hide "Whisper it to" and "The rumour" (the killer picks the target and writes the lies);
  the button reads "Let the killer loose (5 rounds)".
- **Village** options become `Plain NPCs` / `Base` / `Grounded` / `Compare all`. Map `plain` -> mode "plain".
  "Compare all" runs the three in parallel (`Promise.all`), not one after another.
- Results: one column per village with the big number, using the existing grid. Headline line under the button:
  `res.rumour`. Grid rows: skip `framed` (or show it greyed with "framed"); mark the killer row as the source.
- Legend for this source: red "believes it, repeats it as fact", amber "passes it on, says who said it",
  plain "doesn't buy it". If `detail[v].rebuts`, show a small shield: "their own records place Mara elsewhere".
- Optional: before each round's colours update, play that round's `events` (killer walks to each listener and a
  bubble shows the whisper), with the existing `walkTo` / `bubble` in `VillageScene.js`.

## 3. Offline mock (`game/js/mock.js`)

`rumour({source: "killer", mode})` should return the same shape with canned numbers, so the screen works with no
server: e.g. plain turns 3 to 4 villagers red by round 5; base 0 to 1 red; grounded 0 red and 1 to 2 amber, with
`killer: "tom"`, `framed: "mara"`, and a few canned `events` (whispers like "I saw Mara near the guildhall late last night.").

## 4. Replays

For the stage fallback, record one "Compare all" response to `game/replays/` once R3 is served (P1 can produce
it with `python -m archive.eval.manipulation --village plain,base,r3 --runs 1`).
