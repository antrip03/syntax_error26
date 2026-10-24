# P2 tasks: world generator, checker, training data, rewards, metrics

You (or your coding agent) own the core logic that everything else depends on. Read `AGENT_BRIEF.md` first, especially:
- section 0 (crunch mode, which overrides the rest);
- sections 4 to 9 (game rules, generator, schemas, prompts, task types, checker).

This file is your personal task list and timeline.

Team:
- **P1** owns the A6000: toolkits, training and evaluation. Their task list is `TASKS_P1.md`.
- **P2** (you) is available now.
- **P3** arrives at T+3 and owns the game UI and backend.

You also cover part of P3's early work: the hand-written fixture case and the prompt builder the game will use.

T = the moment you start. Deadline: 9 o'clock tomorrow. **Your most important handoff is the generated training data to P1 by about T+5.** Protect that date; cut anything else first.

No GPU is needed for any of your work. Everything is plain Python and pytest on your laptop.

---

## Interfaces you must provide (P1 and P3 code against these names; keep them stable)

```python
# archive/schemas.py                     Case, Villager, Document, Sentence, Fact, Task, HeardItem, ClaimResult, CheckResult (pydantic v2)
# archive/world/casegen.py               generate_case(seed: int, difficulty: str = "normal") -> Case
# archive/world/solver.py                solve(case, villager_ids=None) -> SolveResult  # killer guess + contradictions
# archive/tasks/prompt.py                build_messages(case, villager_id, question, heard=[]) -> list[dict]
#                                        build_asker_messages(case, villager_id, target_id, topic, heard=[]) -> list[dict]
# archive/tasks/generate.py              python -m archive.tasks.generate --config configs/data.yaml
#                                        -> data_prepared/{cases,tasks}_{train,val,test_id,test_adv,test_game}.jsonl + manifest.json
# archive/tasks/gold.py                  gold_reply(task) -> str
# archive/verifiers/checker.py           context_for(case, villager_id, heard=[]) -> VillagerContext
#                                        check(reply: str, ctx: VillagerContext) -> CheckResult
# archive/verifiers/contradiction.py     confirm(case, claim_a: ClaimResult, claim_b: ClaimResult) -> tuple[bool, str]
# archive/rewards/combine.py             reward(reply, task, case, bundle="full") -> dict   # {"total", "correct", "support", "cite", "abstain", "fmt", "length"}
# archive/eval/metrics.py                compute(records: list[dict]) -> dict              # brief section 11 metrics + bootstrap CIs
# archive/npc/detective_bot.py           play(case, ask_fn) -> dict
# archive/npc/rumour.py                  spread_metric(transcripts) -> dict
```

---

## T+0 to T+0.5: unblock P1 and P3 (push this first)

1. Pull the repo P1 creates. If it is not up yet, start locally and push when it is.
2. `archive/schemas.py`: all models from brief section 6. Include `Villager.persona` and `Villager.model` (`grounded` | `base`).
3. `tests/fixtures/case_elsie.json`: the hand-written example case from brief section 4.3. Include:
   - all facts with ids, documents with sentence ids (`D1.S1` ...) linked to facts;
   - persona per villager;
   - the solution;
   - the forged flag on Tom's alibi, and a withheld Tom document.
4. Push both and tell P1. P1 builds the stub API from this fixture, and P3 builds the UI on it.

## T+0.5 to T+2: lexicon, prompt builder, checker (the heart)

1. `archive/world/lexicon.py`:
   - names, places, items and sounds per theme;
   - time slots and synonyms ("sunset" -> dusk, "midnight"/"ninth bell" -> night);
   - number words.
2. `archive/tasks/prompt.py`:
   - villager system prompt exactly as brief section 7.2, persona included, thinking off in the template call;
   - asker prompt (7.3);
   - liar prompt (7.4).
   - Test that real token length is at most 1024 with the Qwen3 tokenizer (`transformers.AutoTokenizer`, CPU only).
3. `archive/verifiers/parse.py`:
   - `<answer>` block, `CLAIM:` lines with `[ID]` citations, `#` lines ignored;
   - exact `<abstain reason="not_in_records"/>`.
4. `archive/verifiers/checker.py`: the 5 tests from brief section 9, in order:
   - format;
   - citation exists in visible ids (own non-withheld sentences + H ids);
   - lexicon entities subset of the source's;
   - fact slot match;
   - non-vacuous;
   - plus hearsay attribution and negation handling.
5. `archive/verifiers/contradiction.py`: map claims to facts (via H items for hearsay). Confirmed if same person, same day+slot, different places.
6. Tests (`tests/test_checker.py`), all on the fixture:
   - gold-style replies are 100% supported;
   - the 6 example GRPO answers in the explainer (A to F) get the expected statuses;
   - at least 30 hand-written hallucinations are red;
   - hearsay without attribution is red;
   - Tom-mill vs Gus-chapel contradiction confirms;
   - Mara vs Ivy does not.

## T+2 to T+3: case generator

1. `archive/world/casegen.py`: steps from brief section 5.2, seeded. `difficulty` drives the presets from brief section 4.5:
   - villagers 4/6/8;
   - witnesses;
   - red herrings;
   - secrets;
   - clue directness;
   - gossip noise flag.
2. `archive/world/render.py`: templates per relation per genre (diary, ledger, letter, patrol log, notebook, prayer book). Sentence ids, fact links. No paraphrase (cut in crunch mode).
3. Personas: a list of about 40 persona cards in `archive/tasks/personas.py`, sampled per villager.

## T+3 to T+5: solver, tasks, gold, splits -> HANDOFF to P1

1. `archive/world/solver.py`: the pass conditions from brief section 5.4. In `generate_case`, regenerate until the solver passes (cap retries; log failures).
2. `archive/tasks/generate.py`: all types from brief section 8 with the mix. Drop `hearsay_plus_own` if short on time.
   - For hearsay types, create synthetic HeardItems from other villagers' true sentences.
   - Splits are by case id.
   - Crunch sizes: 120 train / 20 val / 40 test_id cases, plus a `test_adv` set and 40 `test_game` cases, about 2.5k tasks.
   - Write the JSONL + `manifest.json` (counts per type and split).
3. `archive/tasks/gold.py`: gold reply per task. It must pass `check()` at 100%.
4. Tests:
   - 1000 random gold replies are 100% supported;
   - no case id crosses splits;
   - solver passes 100 seeds at each difficulty;
   - prompts within the token budget.
5. **Push and tell P1 the data command works.** P1 starts curation and SFT immediately.

## T+5 to T+7: rewards and metrics (P1 calls these during GRPO and eval)

1. `archive/rewards/`: one pure function per term plus `combine.py`, exactly as brief section 10.3 (`bundle="full"` and `"outcome"`). Unit-test each term on the A to F example answers.
2. `archive/eval/metrics.py`: every metric in brief section 11 from per-item records (`{task, case_id, reply, check_result, tokens}`), plus bootstrap 95% CIs resampled by case (1000 resamples).
3. Push by **T+6** at the latest. P1's GRPO starts around then.

## T+7 onward: bot, rumour metric, help P3

1. `archive/npc/detective_bot.py`: rule-based detective from brief section 11. It takes an `ask_fn` so it runs against any model. Test it on the fixture with a fake `ask_fn` that returns gold replies: it must name Tom.
2. `archive/npc/rumour.py`: insert a rumour HeardItem from "a traveller", run N gossip rounds through a provided `ask_fn`, and classify each villager each round:
   - repeats as fact: unattributed claim containing the rumour's key entities;
   - attributed;
   - silent.
   - Return per-round maps + the spread metric.
3. Help P3 with `archive/npc/` gossip scheduling (3 rounds x 3 pairs, topic choice per brief 4.4), using your checker and prompt builder.
4. Hand bot + rumour code to P1 for the final runs (about T+8).

## Rules for you

- Keep the interface names above stable; tell P1 and P3 before changing any.
- The checker must be deterministic and fast: no models, no network.
- Write tests as you go and run `pytest` before every push. Commit every 2 hours.
- If something in the brief is ambiguous, pick the simplest option, write it in a comment and in `docs/PROGRESS.md`, and keep moving.
- **3 hours before the deadline: freeze.** Only bug fixes after that.
