# Progress

## P1 — M0 smoke tests (2026-10-24, T+~1.5h)
- Works on GPU 2 (Slurm job 2943): SGLang 0.5.9 serving Qwen3-0.6B with per-request LoRA; AlignTune SFT (20 steps, 9.5 s) and GRPO (5 steps, 14 s) via the TRL backend with a custom reward; SFT adapter served by SGLang produces our exact reply format.
- CuratorKIT pipeline (gold gate + pass-rate gate sampling through SGLang) and AuditKIT eval (api: backend + custom scorers + per-villager chat adapter) both run end to end on 0.6B.
- Fixes needed: torch repinned to 2.9.1+cu128 (driver 535); AlignTune custom rewards are per-sample; thinking must be disabled via `chat_template_kwargs`.
- Next: stub API (done) handed to P3; wait for P2's schemas/checker/prompt builder; write sglang_client, sft.py, grpo.py, run_eval.py against them; 1.7B timing run.
- Risk: untrained 0.6B almost never uses our format, so pass-rate band [0.2, 0.8] may drop most answerable tasks; re-check with 1.7B and the real prompt.

## P1 — pipeline scripts (2026-10-24, T+~2.5h)
- Written and dry-run end to end on 0.6B with stand-in data: `archive/train/{curate,sft,grpo}.py`, `archive/eval/run_eval.py`, `archive/adapters/{sglang_client,aligntune_adapter}.py`, `archive/interfaces.py`, configs for each stage.
- GRPO: starts from the R1 adapter (weights loaded into AlignTune's fresh LoRA), one reward function per part so every part is logged, abstain and reward-hacking guards, `--resume` from the latest checkpoint.
- GRPO timing on 1.7B: 9.7 s/step at crunch settings, so 100 steps is ~15-75 min depending on reply length.
- Known: on untrained models answerable tasks score pass rate 0, so the 0.2-0.8 band drops them; SFT reads gold_ok.jsonl by default. Abstain-heavy SFT data made the dry R1 abstain on everything: check val accuracy, not just parse/support, before GRPO.
- Next: swap in P2's modules when they land (no code change; interfaces.py switches automatically), run real curation + SFT on 1.7B.

## P2 — world, checker, data, rewards, metrics, bot, rumour (2026-10-25, branch `p2-core`)
- Done and pushed: schemas + Elsie fixture, lexicon, strict parser, checker, contradiction check, prompts, casegen +
  renderer + personas + solver, task generator + gold, rewards + metrics, detective bot, planted rumour, gossip engine.
  `interfaces.MODE` is "p2" once all of these are present. 1388 tests pass (6 of P1's devstub-only tests skip).
- Data: `python -m archive.tasks.generate --config configs/data.yaml` -> 240 cases, 3309 tasks (train 1678, val 278,
  test_id 558, test_adv 237, test_game 558), half easy / half hard, the brief's type mix exactly. Every gold reply
  passes the checker (checked on 1.4M candidate gold replies over 1600 extra cases too).

Decisions taken with the team (brief ambiguities or changes), so nobody re-opens them by accident:
- Modes: only `easy` (6 villagers, 3 witnesses at or near the scene, 1 red herring, 3 days) and `hard` (8 villagers,
  2 witnesses seen by role "the miller", a heard-noise clue, 2 red herrings, 2 secrets, liar killer, 2 days).
  Every job is a different person. Contradictions come only from sightings and empty places.
- Sequence budget: max_seq_len 1536, prompt budget 1280 tokens (tested with the Qwen3 tokenizer).
- Prompt: 19 numbered rules incl. strict format rules, a marked format-only example, empty HEARD prints "(none)",
  rule 3 "say so" = state what the documents really say (cited) or abstain.
- Parser: strict (any stray line in <answer> = unparsed); not stricter than that ('#' lines may appear anywhere).
- Checker (order bad_cite, pronoun, vacuous, entity_mismatch, fact_mismatch, no_attribution):
  names not pronouns (new reason `pronoun`); one fact per claim (a time span counts as one); every cite must hold
  the fact; negation words must also be in the cited line; crime/judgement words must be in the line; saw/owes
  direction (passive too); door states and amounts; "my" is not "me"; hearsay needs "<name> told me / said";
  a repeated unsupported rumour with attribution is green with no facts; flavour words (in no fact) may be quoted;
  guess words ("probably") stay green; garbage (markup, glued words) is `vacuous`; names match in any case
  (accepted trade-off: the plant "ivy" reads as the person Ivy).
- Gold: no '#' lines; hearsay quotes the teller (`Gus said: "I saw ..."`); times copied from the line; false
  premises corrected from the line when possible, else abstain; hearsay_plus_own includes witnesses hearing the
  killer's alibi.
- Rewards: a correct abstain scores support 1 and cite 1 (total 1.00); a wrong abstain -0.05 (explainer D).
  Token count from the caller when given, else an estimate; with max_completion_len 192 the length term never
  fires in GRPO.
- Metrics: citation precision is exact (cases or reward parts) or None; gates: parse >= 95%, support >= 90% (val),
  abstain <= 60% (training mix; test_adv is abstain-heavy by design), >= 200 items per headline cell.
- Bot: adds "What did you see or hear on the night of the murder?" so empty-place witnesses are heard; no guess on
  a true tie; liar mode: nobody contradicted -> most red claims (caught, not solved).
- Hard: the liar killer never reads its documents, so the alibi must reach the player as gossip hearsay (P3).
