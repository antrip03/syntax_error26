# The Archive

Syntax Error 2026 hackathon, Local LLM Track, Problem Statement 3 (grounded answers, fewer hallucinations).

A browser murder-mystery where every villager is the same small LLM (Qwen3-1.7B) reading different private documents. We fine-tune it (SFT, then GRPO with programmatic rewards) to state only facts from its own documents, cite the sentence, and abstain when the answer is missing. A deterministic checker colours every claim.

See `AGENT_BRIEF.md` for the full spec.

## Layout

- `archive/` Python package: world generator, checker, tasks, rewards, toolkit adapters, training, eval, NPC engine, API.
- `configs/` YAML configs for every run.
- `game/` front end (Vite).
- `docs/` `TOOLKIT_USAGE.md`, `ENV_NOTES.md`, `PROGRESS.md`.

## Setup (P2 and P3, laptop)

Work on the **`archive` branch** (`main` still holds an older, abandoned project).

```
git clone -b archive https://github.com/antrip03/syntax_error26.git archive
cd archive
```

**Python 3.11** (pinned in `.python-version`; 3.12 also works for the CPU code). Use [uv](https://docs.astral.sh/uv/):

```
uv venv --python 3.11
source .venv/bin/activate            # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"           # pydantic 2.14, fastapi, httpx, pyyaml, pytest, hypothesis
uv pip install -e ".[dev,tokenizer]" # P2 only: adds transformers for the prompt token-count test
pytest -q
```

Without uv: `python3.11 -m venv .venv && pip install -e ".[dev]"`.

Library versions are pinned in `pyproject.toml` to match the GPU server. If you need a new dependency, add it there with an exact version and tell P1.

**What runs where**

| Who | Code | Needs a GPU? |
| --- | --- | --- |
| P2 | `archive/{schemas.py, world/, verifiers/, tasks/, rewards/, eval/metrics.py, npc/detective_bot.py}` | No. Pure Python, standard library + pydantic. Do not import torch/transformers in these modules. |
| P3 | `game/` (Vite + TypeScript, Node 20+) and `archive/serve/api.py` | No. Calls SGLang over HTTP. |
| P1 | `archive/adapters/`, `archive/train/`, `archive/eval/run_eval.py` | Yes, on the A6000 server. Versions and commands in `docs/ENV_NOTES.md`. |

**Interfaces P1 calls** (please keep these signatures; see `TASKS_P1.md`):

```python
archive.world.casegen.generate_case(seed: int, difficulty: str = "normal") -> Case
archive.tasks.prompt.build_messages(case, villager_id, question, heard=[]) -> list[dict]
archive.tasks.gold.gold_reply(task) -> str
archive.verifiers.checker.check(reply: str, ctx) -> CheckResult
archive.verifiers.checker.context_for(case, villager_id, heard=[]) -> VillagerContext
archive.rewards.combine.reward(reply, task, case, bundle="full") -> dict   # {"total": float, ...parts}
archive.eval.metrics.compute(records: list[dict]) -> dict
archive.npc.detective_bot.play(case, ask_fn) -> dict
```

## Running the stub API (P3, for game development)

```
uvicorn archive.serve.api:app --reload --port 8000
```

Every route from `AGENT_BRIEF.md` section 12.3 returns canned data from the Elsie case. CORS allows `http://localhost:5173`. `GET /health` returns `{"ok": true, "stub": true}`.

## Server (P1)

Qwen3-1.7B, SGLang 0.5.9, torch 2.9.1+cu128, AlignTune (TRL backend), CuratorKIT, AuditKIT on one RTX A6000 (driver 535 / CUDA 12.2). Full details in `docs/ENV_NOTES.md`; what each toolkit does in `docs/TOOLKIT_USAGE.md`.

## Results

To be filled in from `artifacts/results/summary.md`.
