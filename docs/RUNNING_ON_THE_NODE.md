# Running The Archive on the GPU node (vitallab1)

How the pieces connect, what is already running, and how a teammate with their own account on the node can play,
record, or develop against the real Qwen models without breaking anything.

## How it fits together

```
 browser (your laptop)
   │  ssh tunnel
   ▼
 game page  :5180   static files from game/            (scripts/static_nocache.py)
   │  fetch()
   ▼
 game API   :8010   archive/serve/game_api.py           cases, /ask, /day/end, /link, /accuse, /rumour
   │  OpenAI-style HTTP
   ▼
 SGLang     :30000  Qwen/Qwen3-1.7B + LoRA adapters     r1b = SFT, r3 = SFT + GRPO, (base = adapter off)
                    on GPU 2, held by Slurm job 2943
 voices     :8001   archive/serve/tts.py (Kokoro)       optional
```

The browser only ever talks to the game API (and to voices). The game API calls SGLang, choosing the adapter per
request: Untrained = no adapter, SFT = `r1b`, SFT + GRPO = `r3`. P2's checker scores every claim in the game API,
on the CPU.

## What is already running (owner: aryan_s2)

| tmux session | what | port |
| --- | --- | --- |
| `p1_sglang` | SGLang, Qwen3-1.7B + adapters `r1b`, `r3`, `r3sft` | 127.0.0.1:30000 |
| `p1_game` | game API (real models) | 0.0.0.0:8010 |
| `p1_web` | game page, no-cache | 0.0.0.0:5180 |
| `p1_tts` | villager voices | 127.0.0.1:8001 |

Ports :8000 and :5173 belong to an old stub with canned answers. Don't use them.
Health checks from the node: `curl localhost:8010/health` (should say `"stub": false`), `curl localhost:30000/health`.

Please **don't** stop these sessions, and don't start GPU jobs on GPU 2: it is held by aryan's Slurm job and only
that account can run on it. Ask aryan to restart anything that goes down (commands at the end).

## Option A: just play or record the demo (no clone needed)

On your laptop:
```bash
ssh -L 5180:localhost:5180 -L 8010:localhost:8010 -L 8001:localhost:8001 <you>@192.168.104.71
```
Open **http://localhost:5180/?api=http://localhost:8010**. The title screen should say "Live API". If the page
hangs after an update, hard reload (Cmd+Shift+R).

Demo: seed **4010**, Easy, then **Planted rumour** → "The killer (untrained, manipulating)" → **Compare** →
**Spread it in both villages** (about 4.5 minutes; Skip ▸▸ shortens it). For the case itself: ask Mara, Vera and
Ezra "Where were you on the night of the murder?", add the green claims to the notebook, link two on the Board,
then accuse Mara with "Mara owes me 70 silver."

## Option B: work on the game or the game API, using the shared model

Clone into **your own home** (aryan's checkout is private and in use):
```bash
git clone https://github.com/antrip03/syntax_error26.git ~/syntax_error26
cd ~/syntax_error26 && git checkout main     # or: archive
curl -LsSf https://astral.sh/uv/install.sh | sh          # if you don't have uv
uv venv -p 3.11 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"                                 # pydantic, fastapi, httpx, uvicorn, pytest (no GPU libs)
python -m pytest -q tests                                  # sanity check (about 1 minute)
```

**Front end only** (game/ files). Serve your copy on your own port and point it at the shared API:
```bash
python3 scripts/static_nocache.py 5190 game
# laptop: ssh -L 5190:localhost:5190 -L 8010:localhost:8010 -L 8001:localhost:8001 <you>@192.168.104.71
# open   http://localhost:5190/?api=http://localhost:8010&tts=http://localhost:8001
```

**Game API too** (archive/ files). Run your own API on your own port, against the shared SGLang:
```bash
SGLANG_URL=http://127.0.0.1:30000 ARCHIVE_STATE=$HOME/archive_game_state.pkl \
  python -m uvicorn archive.serve.game_api:app --host 0.0.0.0 --port 8020
# open http://localhost:5190/?api=http://localhost:8020   (tunnel 8020 as well)
```
- `ARCHIVE_STATE` must be a file you can write (the default lives in aryan's /tmp folder).
- Optional settings:
  - `ARCHIVE_GROUNDED` (default `r3`) and `ARCHIVE_SFT` (default `r1b`) pick the adapters;
  - `ARCHIVE_TEMPERATURE` (default `0.7`);
  - `ARCHIVE_DIARY_SUSPECTS=1` lists the red herrings' motives in the victim's diary too.
- Restart your uvicorn after Python changes. Open games survive restarts.

**Git:** work on a branch, push it, and merge into `main` after a quick check:
`git checkout -b my-change` … `git push origin my-change`.

## Option C: your own model server (only if the shared one is down and aryan isn't around)

You need your own GPU and environment; the adapters and model cache are readable:
```bash
sbatch --gres=gpu:1 --time=0 --wrap="sleep infinity"      # note the job id; check: squeue -u $USER
uv venv -p 3.11 ~/sgl && source ~/sgl/bin/activate
uv pip install "sglang[all]==0.5.9" --extra-index-url https://download.pytorch.org/whl/cu128
export HF_HOME=/tmp/archive_p1/hf HF_HUB_OFFLINE=1
srun --jobid=<your job> --overlap python -m sglang.launch_server --model-path Qwen/Qwen3-1.7B \
  --host 127.0.0.1 --port 30100 --mem-fraction-static 0.3 --enable-lora --max-lora-rank 16 --lora-target-modules all \
  --lora-paths r1b=/tmp/archive_p1/artifacts/runs/R1b/out r3=/tmp/archive_p1/artifacts/runs/R3/out
```
Then run your game API with `SGLANG_URL=http://127.0.0.1:30100`. Keep at most 3 adapters registered: SGLang 0.5.9
crashed with "illegal memory access" when more were registered.

/tmp is not backed up. Copies of the adapters are in aryan's `~/archive_p1_backup/` (R1b, R3, R3sft), and
should also be uploaded somewhere shared before the node is wiped.

## Restarting (aryan_s2)

```bash
cd ~/rl/archive
scripts/serve_game.sh                       # starts any missing p1_sglang / p1_game / p1_web
GAME_PORT=8010 WEB_PORT=5180 scripts/serve_game.sh      # the ports used above
tmux new-session -d -s p1_tts "scripts/serve_tts.sh"    # voices
```
`scripts/serve_game.sh` serves `r1b` and `r3` only. To kill and restart one piece: `tmux kill-session -t p1_game`,
then run the script again.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Answers like "Don't look at me like that!" | You're on the stub (:8000). Use :8010. |
| Page stuck on the loading screen | Stale cached files. Hard reload; use the :5180/:5190 no-cache server. |
| "This case is no longer on the server" | Start a new case from the menu. |
| Every request fails, `curl localhost:30000/health` fails | SGLang died. aryan restarts `p1_sglang` (or use Option C). |
| Voice is the browser's robot voice | TTS on :8001 isn't reachable. Tunnel 8001 or ignore it. |
