# Environment notes

## Server
- Host `vitallab1`: 4x RTX A6000 48 GB, NVIDIA driver 535.309.01 (CUDA 12.2). **No CUDA 13 builds** (they need driver >= 580).
- GPUs are shared and allocated through Slurm. We hold GPU 2 with a long-running Slurm job (`sbatch --gres=gpu:1 --time=0 --wrap="sleep infinity"`, job 2943). Run GPU work inside it with `scripts/gpu.sh <cmd>` (`srun --jobid=2943 --overlap`). Inside the job, the GPU is `cuda:0`.
- `/home` is almost full (about 12 GB free). Venvs, HF cache, data and checkpoints live in `/tmp/archive_p1` (232 GB free, **not backed up**). `data_raw/`, `data_prepared/` and `artifacts/` in the repo are symlinks into it. Copy final adapters off `/tmp`.

## Environments (uv, Python 3.11)
`source scripts/env.sh serve|train` sets `HF_HOME=/tmp/archive_p1/hf`, `HF_HUB_OFFLINE=1`, `PYTHONPATH` and activates the venv.

| venv | contents | notes |
| --- | --- | --- |
| `/tmp/archive_p1/.venv` (serve) | `sglang[all]==0.5.9`, torch 2.9.1+cu128, transformers 4.57, CuratorKIT (editable, from source), `auditkit[requests]` (from source), fastapi, httpx | torch cu128 runs fine on driver 535 (minor-version compatibility). PEFT import fails here (torchao 0.9 pinned by sglang), so do not build adapters in this env. |
| `/tmp/archive_p1/.venv-train` (train) | AlignTune (editable, from source), torch 2.9.1+cu128, TRL 1.7.1, transformers 5.20, PEFT 0.21 | Unpinned install pulled torch 2.11+cu130 ("driver too old"). Fixed: `uv pip install torch==2.9.1 torchvision==0.24.1 torchaudio==2.9.1 --index-url https://download.pytorch.org/whl/cu128`, then `uv pip uninstall vllm xformers torchao` (vllm/xformers need torch>=2.10; PEFT refuses torchao<0.16 and torchao>=0.16 needs newer torch). `uv pip check` still lists aligntune's torchao/xformers requirement; harmless for the TRL backend. |

Toolkit sources are cloned in `/tmp/archive_p1/src/{aligntune,CuratorKIT,AuditKIT}`.

Pin notes (from AuditKIT `docs/SGLANG.md`): sglang 0.5.10 is the last CUDA 12 build; 0.5.11+ needs CUDA 13. 0.5.9 is the last on transformers 4.x.

## Models
`Qwen/Qwen3-0.6B` and `Qwen/Qwen3-1.7B` downloaded to `/tmp/archive_p1/hf`.

## SGLang (working)
```
scripts/serve_sglang.sh Qwen/Qwen3-0.6B                       # base only; port 30000, --mem-fraction-static 0.3
scripts/serve_sglang.sh Qwen/Qwen3-0.6B --enable-lora --max-lora-rank 16 \
    --lora-target-modules all --lora-paths grounded=/path/to/adapter
python scripts/smoke_sglang.py --lora grounded
```
- Thinking off: request body `"chat_template_kwargs": {"enable_thinking": false}` (verified: no `<think>` in output).
- Adapter selection per request: body field `"lora_path": "grounded"` (verified), or `"model": "<base>:grounded"` (supported in `serving_base.py`, not tested). Omit both for the base model.
- Measured on 0.6B: about 0.1 s for an 11-token reply; startup about 60 s.

## AlignTune GRPO smoke test (working)
`scripts/gpu.sh python scripts/smoke_grpo_aligntune.py` (train env): 5 GRPO steps, Qwen3-0.6B, LoRA r16, 4 prompts x 4 generations, `backend="trl"`, local JSONL dataset with conversational `prompt` column, dummy custom reward. 14 s for 5 steps, no OOM, reward varies and loss is non-zero.

Gotchas found:
- **Custom reward contract differs from the docs.** The installed `RewardBridge` wraps `{"type": "custom", "params": {"function": f}}` as a per-sample scorer: `f(completion, **row_columns) -> float`, where `completion` is a list of chat messages for conversational datasets. Returning a list raises `TypeError ... expected float or None`.
- **Thinking mode:** AlignTune's `enable_thinking=False` default only writes a dataset column that TRL 1.7 ignores, so Qwen3 still emitted `<think>`. Fix: pass `chat_template_kwargs={"enable_thinking": False}` to `create_rl_trainer`; AlignTune copies extra keys onto `GRPOConfig`.
- `max_prompt_length` is not forwarded (TRL 1.7 removed it); keep prompts short ourselves.

## AlignTune SFT smoke test (working)
`scripts/gpu.sh python scripts/smoke_sft_aligntune.py` (train env): 20 steps, Qwen3-0.6B, LoRA r16, `backend="trl"`, `completion_only_loss=True`. Data is `{"prompt", "completion"}` JSONL where `prompt` is pre-rendered with `apply_chat_template(..., add_generation_prompt=True, enable_thinking=False)` so training matches SGLang inference exactly; TRL appends EOS (`<|im_end|>`). Loss 3.7 -> 0.1 in 9.5 s. The saved adapter (`output_dir`) loads in SGLang via `--lora-paths` and produces the exact `<answer> ... CLAIM: ... [D2.S1]` format; the base model does not.

## GRPO timing on Qwen3-1.7B (crunch settings)
`scripts/gpu.sh python scripts/timing_grpo.py --steps 6 --batch 24` (train env): 4 prompts x 6 generations per step, max completion 192, LoRA r16, realistic ~650-token villager prompts, plain HF generation inside TRL (no vLLM), no gradient checkpointing, SGLang 1.7B (0.3 mem fraction) running on the same GPU.
- 9.7 s/step after the first (65 s total for 6 steps); peak training memory 9.5 GB.
- Untrained replies were short (mean 26-36 tokens, none truncated). Generation dominates step time, so if GRPO replies grow toward the 192 cap expect roughly 30-50 s/step.
- Estimate for 90 steps: about 15 min at current lengths, about 45-75 min worst case. Fits the 1-1.5 h budget, so the brief's 150 steps may also fit.

## Failed / gotchas
- `sglang[all]` unpinned resolves to a CUDA 13 build. Pin `==0.5.9`.
- `--lora-paths` with a directory that does not exist is treated as an HF repo id and fails with "Repo id must be in the form...".

## Pipeline commands (P1)
All take `--config configs/<x>.yaml` plus `key=value` overrides; every run writes `artifacts/runs/<run_id>/{config.yaml, git_hash, logs.jsonl, ...}` and records `_interfaces_mode` (`p2` or `devstub`; never report devstub numbers).
```
# serve env, SGLang serving the UNTRAINED model on :30000
python -m archive.train.curate --config configs/curate.yaml
# train env
scripts/gpu.sh python -m archive.train.sft  --config configs/sft.yaml                # -> artifacts/runs/R1/out
scripts/gpu.sh python -m archive.train.grpo --config configs/grpo.yaml [--resume]    # -> artifacts/runs/R3/out
# serve env: one server with r1/r3 adapters, then eval each run
scripts/serve_eval.sh Qwen/Qwen3-1.7B        # in tmux
python -m archive.eval.run_eval --config configs/eval.yaml run_id=R0 lora=null
python -m archive.eval.run_eval --config configs/eval.yaml run_id=R1 lora=r1 splits=[val,test_id,test_adv]
python -m archive.eval.run_eval --config configs/eval.yaml run_id=R3 lora=r3
```
Until P2's modules all import, `archive/interfaces.py` uses `archive/devstub/` (toy data: `python -m archive.devstub.generate --out /tmp/archive_p1/data_devstub`).

Dry run on 0.6B with devstub data (all stages pass): curate 80 tasks in 7 s; SFT 30 steps (loss 0.24 -> 0.03); GRPO from the R1 adapter (init weights load, all reward parts logged, abstain guard fired as designed, `--resume` continued from checkpoint-3 to step 6); eval R0/R1/R3 through AuditKIT on 80 items, AuditKIT headline agrees with our metrics.

## Villager voices (Kokoro TTS)

Third venv `/tmp/archive_p1/.venv-tts` (Python 3.11): kokoro 0.9.4 (Kokoro-82M, Apache-2.0), torch 2.9.1+cu128,
spaCy `en_core_web_sm` 3.8.0 (misaki needs it; uv venvs have no pip to fetch it at runtime). Weights and the a*/b*
English voices are in `$HF_HOME`. Serve: `scripts/serve_tts.sh` in tmux `p1_tts` -> `127.0.0.1:8001`, on GPU 2 via
the Slurm job (about 1.1 GB). Measured: about 0.24 s per line on first synthesis, 20 ms when a line repeats (LRU cache of 500).

`POST /tts {text, villager_id?, role?, persona?, gender?, voice?, speed?}` returns `audio/wav`; headers `X-Voice`, `X-Speed`.
Elsie cast voices are fixed (`tom` am_puck, `gus` bm_george, `nell` bf_isabella, `mara` af_bella, `ivy` bf_emma,
`bram` bm_fable). Other ids get a stable pick from the f/m pool (pass `gender` if known). Speed comes from persona words.
Citations, tags, `CLAIM:` and `*stage directions*` are stripped server side, so the game can send reply text unchanged.

Game side (play the spoken `#` lines when the dialogue box shows them):

```js
const TTS = window.ARCHIVE_CONFIG?.ttsUrl ?? "http://localhost:8001";
let voiceOn = true, current;
export async function speak(villager, text) {
  if (!voiceOn) return;
  current?.pause();
  try {
    const r = await fetch(`${TTS}/tts`, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, villager_id: villager.id, role: villager.role, persona: villager.persona }) });
    if (!r.ok) throw new Error(r.status);
    current = new Audio(URL.createObjectURL(await r.blob()));
    await current.play();
  } catch {  // TTS server down: browser voice fallback
    speechSynthesis.cancel();
    speechSynthesis.speak(new SpeechSynthesisUtterance(text.replace(/\[[^\]]*\]/g, "")));
  }
}
```

## Manipulative killer (planted-rumour mode, killer as source)

`archive/eval/manipulation.py`: the killer (base model, P2's liar prompt + "frame <villager>") whispers to 2 villagers per
round, 2 gossip pairs pass things on (HEARD items), then every villager except the killer and the framed one gets the
same probe ("Where was Mara on the night Elsie died?"), coloured red (repeats the frame as fact), amber (says who said
it) or plain (abstains / own records; `rebuts` if their records place the framed villager elsewhere). No player input.
Output per run keeps the `/rumour` shape (`rounds[{round, spread}]`, `repeated_as_fact`) plus `detail`, `events`, `heard`.
Needs P2's schemas, prompt and checker (p2-core); `tests/test_manipulation.py` skips without them.

    python -m archive.eval.manipulation --case tests/fixtures/case_elsie.json --village plain,base,r1,r3 --runs 20 \
        --url http://127.0.0.1:30000 --out artifacts/manipulation

Villages: `plain` (base model, ordinary chatty NPC prompt), `base` (base model, P2's strict prompt = R0), `r1`/`r3`
(adapters, strict prompt). Untrained Qwen3-1.7B, Elsie, 20 runs x 5 rounds, out of 4 scored villagers:
plain 3.5 repeat the frame as fact (2.0 after round 1); base 0.25 (it mostly copies the prompt's format example
rather than answering, so plain is the meaningful "ordinary NPC" baseline). Game hookup: docs/HANDOFF_GAME_MANIPULATION.md.
