# The Archive

Syntax Error 2026 hackathon, Local LLM Track, Problem Statement 3 (grounded answers, fewer hallucinations).

A browser murder-mystery where every villager is the same small LLM (Qwen3-1.7B) reading different private documents. We fine-tune it (SFT, then GRPO with programmatic rewards) to state only facts from its own documents, cite the sentence, and abstain when the answer is missing. A deterministic checker colours every claim.

See `AGENT_BRIEF.md` for the full spec.

## Layout

- `archive/` Python package: world generator, checker, tasks, rewards, toolkit adapters, training, eval, NPC engine, API.
- `configs/` YAML configs for every run.
- `game/` front end (Vite).
- `docs/` `TOOLKIT_USAGE.md`, `ENV_NOTES.md`, `PROGRESS.md`.

## Running the stub API (for game development)

```
pip install -e .
uvicorn archive.serve.api:app --reload --port 8000
```

CORS allows `http://localhost:5173`.

## Results

To be filled in from `artifacts/results/summary.md`.
