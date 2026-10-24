# P1 tasks: GPU pipeline, toolkits, training, evaluation (owner of the A6000)

You (or your coding agent) own everything that runs on the GPU. Read `AGENT_BRIEF.md` first; this file is your personal task list and timeline. **Section 0 of `AGENT_BRIEF.md` (crunch mode) overrides the rest of that file.**

Team:
- **P1** (you) works on the A6000 over SSH.
- **P2** is available now and owns the world generator, checker, data, rewards and metrics. Their task list is `TASKS_P2.md`.
- **P3** arrives at T+3 and owns the game UI and backend.

You also cover P3's first job: a stub API that is ready when P3 arrives.

T = the moment you start. Deadline: 9 o'clock tomorrow. Times below are targets; if a step overruns, cut per section 0 of the brief.

---

## Interfaces you depend on (P2 provides them; do not reimplement)

```python
# archive/schemas.py                     Case, Villager, Document, Fact, Task, HeardItem, CheckResult (pydantic)
# archive/world/casegen.py               generate_case(seed: int, difficulty: str = "normal") -> Case
# archive/tasks/prompt.py                build_messages(case, villager_id, question, heard=[]) -> list[dict]  # chat messages, system + user
# archive/tasks/generate.py              python -m archive.tasks.generate --config configs/data.yaml
#                                        -> data_prepared/{cases,tasks}_{train,val,test_id,test_adv,test_game}.jsonl
# archive/tasks/gold.py                  gold_reply(task) -> str
# archive/verifiers/checker.py           check(reply: str, ctx: VillagerContext) -> CheckResult
#                                        context_for(case, villager_id, heard=[]) -> VillagerContext
# archive/rewards/combine.py             reward(reply: str, task: Task, case: Case, bundle: str = "full") -> dict  # {"total": float, parts...}
# archive/eval/metrics.py                compute(records: list[dict]) -> dict
# archive/npc/detective_bot.py           play(case, ask_fn) -> dict   # ask_fn(villager_id, question) -> reply str
```

- P2 pushes `schemas.py` and a hand-written fixture case (`tests/fixtures/case_elsie.json`) within about 30 minutes.
- Until real tasks arrive (about T+5), test your scripts on tasks P2 generates from the fixture, or on a tiny early generator run.

---

## T+0 to T+0.5: repo (shared with P2 and P3)

1. Create a GitHub repo `archive` and invite P2 and P3.
2. Push the skeleton from section 14 of the brief:
   - folders with `__init__.py` files;
   - `pyproject.toml` (Python 3.11, package `archive`);
   - `.gitignore` covering `data_raw/ data_prepared/ artifacts/ *.safetensors .venv/`;
   - empty `docs/{TOOLKIT_USAGE,ENV_NOTES,PROGRESS}.md`;
   - `configs/`.
3. Tell P2 the repo is up.

## T+0 to T+2: server and smoke tests (run long installs/downloads in tmux; do the repo step while they run)

1. `ssh` to the server and check:
   - `nvidia-smi` (is the card free? which driver/CUDA version?);
   - free disk space (need about 40 GB);
   - Python version.
2. Create the environment:
   - `uv venv` with Python 3.11;
   - install a PyTorch build matching the driver;
   - install SGLang following https://docs.sglang.io/ for that CUDA version.
3. Download `Qwen/Qwen3-0.6B` and `Qwen/Qwen3-1.7B` with `huggingface-cli download` in the background.
4. **SGLang smoke test.**
   - Launch Qwen3-0.6B in tmux.
   - Call the OpenAI-compatible endpoint with one chat request, with thinking off (`enable_thinking=False` via `chat_template_kwargs`; verify the field name in the docs).
5. **LoRA smoke test.**
   - Make a dummy LoRA adapter for 0.6B with PEFT (random init, rank 16, saved with `save_pretrained`).
   - Relaunch SGLang with LoRA enabled and the adapter registered as `grounded`.
   - Send one request with the adapter and one without.
   - Record the exact flags and the request field that selects the adapter.
6. **AlignTune smoke test (time-box 1 hour).**
   - Install it and read its docs and source for the SFT and GRPO entry points.
   - Key question: **can you pass custom Python reward functions to GRPO?**
   - Run 5 GRPO steps on 0.6B with a dummy reward (for example `len(completion) < 200`), bf16.
   - If blocked after 1 hour, run the same 5 steps with TRL `GRPOTrainer`. Keep AlignTune for SFT and config handling, and write down why.
7. Write `docs/ENV_NOTES.md`: versions, working commands, flags that failed.

**Done when:**
- SGLang answers on 0.6B, with and without the adapter.
- 5 GRPO steps finish without OOM.
- `ENV_NOTES.md` is pushed.

## T+2 to T+3: the other toolkits, and the stub API for P3

1. **CuratorKIT:**
   - Install it and run its smallest example (pointing at your SGLang server if it needs a model).
   - Find out how to add **our verifier as a custom step or filter**, and how to run a **pass-rate filter** (sample N replies per task, keep tasks whose pass rate is in a band).
2. **AuditKIT:**
   - Install it and run its smallest example with SGLang as the backend.
   - Find out whether it accepts **custom evaluators/metrics**.
3. Write the `docs/TOOLKIT_USAGE.md` skeleton: one section per toolkit, covering what it can do for us, what it can't, and the planned fallback.
4. **Stub API for P3** (`archive/serve/api.py`, FastAPI):
   - Implement every route from brief section 12.3 with canned responses built from `tests/fixtures/case_elsie.json`.
   - `/ask` returns a fixed reply per villager with claims and statuses.
   - Add `uvicorn` run instructions to `README.md`, plus CORS for `http://localhost:5173`.
   - Push it. P3 builds the UI against it from T+3.

## T+3 to T+5: training and eval scripts (on 0.6B with tiny data)

1. `archive/adapters/sglang_client.py`:
   - batched async chat calls (httpx);
   - adapter selection;
   - temperature/seed policy (greedy for eval, T=0.9 for sampling);
   - retries.
2. `archive/adapters/aligntune_adapter.py` + `archive/train/sft.py`:
   - SFT from `tasks_train.jsonl`, using `build_messages` + `gold_reply`;
   - completion-only loss, thinking off;
   - config `configs/sft.yaml` (brief 10.2, crunch sizes: 800 examples, 1 epoch);
   - checkpoint and `--resume`.
3. `archive/train/grpo.py`:
   - GRPO through the adapter;
   - reward = P2's `reward(...)["total"]` wrapped as a TRL-style reward function that returns a list of floats;
   - log every reward part, length, KL, parse rate and abstain rate to JSONL every step;
   - config `configs/grpo.yaml` (brief 10.3, crunch: 80 to 100 steps, max completion 192).
4. `archive/eval/run_eval.py`:
   - for a run id and split, generate greedy replies via SGLang;
   - `check()` each reply;
   - write a record per item;
   - call P2's `compute()`;
   - write `artifacts/runs/<id>/metrics.json`;
   - wire AuditKIT around it (as runner or custom evaluator, whichever M0 showed works).
5. `archive/adapters/curatorkit_adapter.py`: the curation flow found in step T+2.
6. Dry-run everything on 0.6B with the fixture-based tiny dataset: 20 SFT steps, 5 GRPO steps, eval on 20 items.

## T+5 to T+6: real data -> curation -> SFT (R1)

1. Pull P2's generator and run `python -m archive.tasks.generate --config configs/data.yaml` (crunch sizes: 120/20/40 cases, about 2.5k tasks).
2. Curation through CuratorKIT:
   - verify every gold reply with the checker;
   - pass-rate filter with 4 samples per task from **untrained Qwen3-1.7B** via SGLang, keeping 0.2 to 0.8;
   - abstain-type tasks kept by quota.
   - Save the curated set + manifest.
3. Start **SFT on Qwen3-1.7B** (about 15 to 30 minutes) in tmux. Lower SGLang memory (`--mem-fraction-static 0.3`) if it stays up.

## T+6 to T+8: GRPO (R3) and early evals

1. **Start GRPO** from the R1 adapter in tmux.
2. Watch the logs every 15 minutes:
   - Stop if the abstain rate exceeds 60%, or the total rises while `correct` falls.
   - **Fallback:** if no upward trend by step about 60 to 80, stop GRPO and do rejection-sampling fine-tuning instead: sample 8 per task with R1, keep checker-verified correct replies, SFT again. Record it in `TOOLKIT_USAGE.md` and `PROGRESS.md`.
3. While GRPO runs, if memory allows, evaluate **R0** and **R1** on `test_id` and `test_adv`. Otherwise run them right after.

## T+8 to T+9.5: final evals and handoff to the game

1. Evaluate **R3** on `test_id` and `test_adv`.
2. Run the detective bot (P2's code): 30 cases x Base vs Grounded.
3. Run the rumour metric: 20 runs x 2 modes.
4. Write `artifacts/results/summary.md`:
   - a table of R0 / R1 / R3 with bootstrap 95% CIs;
   - unsupported-claim rate first.
5. Serve the final model for the game:
   - SGLang with Qwen3-1.7B + `grounded` = R3 adapter;
   - expose it to the backend (Cloudflare Tunnel with a secret header, per brief 12.0);
   - give P3 the URL and token.
6. Back up the R3 adapter: copy it off the server and to a GitHub release or Hugging Face (private).

## Overnight / morning

1. Finish `docs/TOOLKIT_USAGE.md` with exactly what each toolkit did, including any fallback.
2. With P3, record replay transcripts:
   - 3 full cases;
   - Base vs Grounded on the same seed;
   - one rumour run per mode.
3. Add the results section to `README.md` and help with the pitch numbers.
4. **3 hours before the deadline: freeze.** No more training runs.

## Rules for you

- Prototype every GPU job on 0.6B first.
- Never guess toolkit APIs or flags. Read the docs and installed source, and wrap them in `archive/adapters/`.
- Time-box every toolkit problem to 1 hour, then fallback + document.
- Commit every 2 hours. Write 5 lines in `docs/PROGRESS.md` after each step above.
- Report the real numbers, even if they are disappointing.
