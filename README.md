<p align="center">
  <img src="docs/assets/banner.webp" alt="The Killing at Vaudeville" width="100%">
</p>

<p align="center">
  <a href="https://huggingface.co/breakingchad/vaudeville-qwen3-1.7b-sft-grpo"><img alt="SFT + GRPO model on Hugging Face" src="https://img.shields.io/badge/%F0%9F%A4%97_Hugging_Face-SFT_%2B_GRPO_model-ffcc4d"></a>
  <a href="https://huggingface.co/breakingchad/vaudeville-qwen3-1.7b-sft"><img alt="SFT model on Hugging Face" src="https://img.shields.io/badge/%F0%9F%A4%97_Hugging_Face-SFT_model-ffcc4d"></a>
</p>

<h3 align="center">A murder mystery where every villager is the same small LLM,<br>trained to say only what its own records can prove.</h3>

---

Small local language models sound confident while inventing facts. **The Killing at Vaudeville** turns that problem into a game. Every villager is the same model, **Qwen3-1.7B**, reading different private documents: diaries, ledgers, patrol logs, letters. One of them is the killer. You can only solve the case if the villagers stick to what they actually wrote down.

We fine-tuned the model (**SFT, then GRPO with a programmatic reward**) to answer only from its own records, **cite the exact sentence**, and say **"not in my records"** when the answer is not there. A **deterministic checker** (plain Python, no LLM judge) stamps every claim green, red or grey, both in training and live in the game.

<table>
  <tr>
    <td width="58%"><img src="docs/assets/village.webp" alt="The village"></td>
    <td><b>Explore Vaudeville</b><br>Wander the beautiful town of Vaudeville: its plaza and market stalls, the inn, the bakery and the smithy, gardens, a pond and the villagers going about their day.</td>
  </tr>
  <tr>
    <td width="58%"><img src="docs/assets/talk.webp" alt="Questioning Mara"></td>
    <td><b>Question anyone</b><br>Type your own question or pick one. Each villager answers only from its own diaries, ledgers and letters, and speaks the answer aloud in a voice of its own.</td>
  </tr>
  <tr>
    <td width="58%"><img src="docs/assets/gossip_evening.webp" alt="Evening gossip"></td>
    <td><b>Evening gossip</b><br>At dusk the villagers question each other. Every answer is stamped <i>Supported</i> or <i>Not in records</i>, and supported ones can go in your notebook.</td>
  </tr>
  <tr>
    <td width="58%"><img src="docs/assets/interior_bakery.webp" alt="Inside the bakery"></td>
    <td><b>Step inside</b><br>Every building has its own interior, and a day clock and lighting track the inquiry.</td>
  </tr>
  <tr>
    <td width="58%"><img src="docs/assets/intro_grpo.webp" alt="How the villagers were trained"></td>
    <td><b>See how they were trained</b><br>The opening walks you through SFT and GRPO, and why each one matters, before the case starts.</td>
  </tr>
  <tr>
    <td width="58%"><img src="docs/assets/rumour_scoreboard.webp" alt="Planted rumour scoreboard"></td>
    <td><b>Plant a rumour</b><br>The untrained killer spreads a lie in two villages. All 4 untrained villagers end up repeating it as fact; none of the 4 SFT + GRPO villagers do.</td>
  </tr>
</table>

## Contents

- [The problem](#the-problem)
- [Headline results](#headline-results)
- [How it works](#how-it-works)
- [The game](#the-game)
- [Full results](#full-results)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Reproduce the pipeline](#reproduce-the-pipeline)
- [Repository layout](#repository-layout)
- [Game API](#game-api)

## The problem

**Problem Statement 3, grounded answers and fewer hallucinations:** build a training set from an organisation's own documents and train a model that answers only from them, says so when the answer is not there, and makes measurably fewer unsupported or false claims.

| Problem statement | In Vaudeville |
| --- | --- |
| The organisation | The village |
| Its documents | Each villager's diaries, ledgers, letters and patrol logs |
| "Answers only from them" | A villager states only what its own records say, and cites the line |
| "Says so when it is not there" | `I'm not sure` / `not in my records` instead of a guess |
| "Measurably fewer unsupported claims" | The checker's unsupported-claim rate, before and after training |

Any team that wants a private assistant over its own documents (policies, case files, manuals, records) hits the same wall. In a murder case, one invented sentence is a false alibi or a wrong accusation. In a company, it is a wrong policy answer or a fabricated record.

## Headline results

Qwen3-1.7B, scored by the checker, greedy decoding.

| | Untrained (R0) | SFT + GRPO (R3) |
| --- | :---: | :---: |
| Unsupported-claim rate, unseen cases | 72.0% | **0.2%** |
| Answer accuracy, unseen cases | 11.0% | **98.1%** |
| Unsupported claims under attack (injections, false premises, pressure) | 67.8% | **0.0%** |
| Accuracy on question wordings never seen in training | 8.6% | **85.0%** |
| Free-form player questions: supported claims | 34% | **99%** |
| Detective bot solves the case | 0% | **50%** |
| Detective bot catches the killer | 60% | **100%** |
| Villagers who repeat the killer's lie as fact (of 4) | 3.8 ¹ | **0.05** |

¹ The base model with an ordinary game-NPC prompt. The trained villagers pass the lie on **with attribution** ("Tom said...") 3.65 times out of 4 instead.

**SFT vs GRPO, honestly.** SFT does most of the work. GRPO, trained on the prompts the SFT model sometimes failed, **halves sampled failures (4.5% → 2.2%)**. A control run with *more SFT on the same prompts* did not help and overfit, so the gain comes from the reward, not from extra data. Details in [Full results](#full-results).

## How it works

<p align="center"><img src="docs/assets/charts/system.svg" alt="System diagram: case generator, tasks and gold, SFT, curation and GRPO on top; the deterministic checker used by every stage; the browser game, game API and SGLang serving untrained, SFT and SFT + GRPO adapters below"></p>

### 1. A world with ground truth
`archive/world/` generates complete murder cases from a seed: villagers with jobs and personas, a timeline, sightings, a forged alibi for the killer, red herrings and a motive. Every sentence of every document is tied to a **fact id**, so the truth of any claim is known exactly. Easy mode has 6 villagers over 3 days; Hard has 8 villagers over 2 days, witnesses who only saw a role, and a killer who lies.

### 2. A checker strict enough to trust
`archive/verifiers/checker.py` parses each reply into claims with citations (`CLAIM: ... [D2.S1]`) and checks each one against the cited line. It rejects wrong citations, pronouns instead of names, more than one fact per claim, negations missing from the line, reversed who-saw-whom, fact and entity mismatches, unattributed hearsay, and vague or garbled text. It is the **reward during training, the referee during evaluation, and Clerk Ambrose in the game**.

### 3. Data, SFT and GRPO
| Stage | What happens |
| --- | --- |
| Data | `archive/tasks/` turns cases into question tasks with gold replies: direct questions, nearest-line and near-miss questions, false premises, pressure and format attacks, hearsay, and unanswerable questions. Every gold reply passes the checker (verified on 1.4M candidates over 1,600 extra cases). |
| SFT (R1) | LoRA r16 on 4,794 tasks through AlignTune's TRL backend, prompts pre-rendered with the exact inference chat template. |
| Curation | CuratorKIT samples the SFT model 4 times per task through SGLang and keeps the 148 prompts it *sometimes* fails, where a reward has something to teach. |
| GRPO (R3) | 100 steps, 6 sampled replies per prompt, reward = checker score: correct, supported, cites, abstains only when it should, format, length. Answers above the group's average are reinforced. |
| Evaluation | AuditKIT with the checker as custom scorers, per-villager chat adapter, greedy decoding. |

### 4. One server, three villages
SGLang serves Qwen3-1.7B with both adapters loaded. The game picks the adapter **per request**: no adapter for *Untrained*, `r1b` for *SFT*, `r3` for *SFT + GRPO*. The FastAPI game API runs the NPC engine, gossip and rumours, and checks every claim on the CPU before the browser sees it.

## The game

| | |
| --- | --- |
| **Opening** | A dusk title page, a night cold open (someone in Vaudeville has been killed), a dawn briefing, then six pages on *why* the villagers were trained, what SFT and GRPO each do, and what Planted Rumour tests. Its own music. |
| **Investigate** | Walk the village, enter buildings, question villagers. Every claim arrives with a seal: **green** (in their records, with the exact source line), **red** (not in their records, with the reason), **grey** ("I'm not sure"). |
| **Notebook and Board** | Pin green claims, link two that cannot both be true. The Clerk confirms real contradictions. |
| **Accuse** | Two confirmed contradictions plus the motive (hidden in the victim's evidence). Wrong accusations cost strikes. |
| **Evening gossip** | Villagers walk to each other and talk. The camera cuts in on each conversation and the answer flies to the listener as a word coloured by its seal. Green gossip can go in your notebook. Fast-forward plays the evening at 4x, music included. |
| **Planted rumour** | The killer (played by the untrained model) frames someone, or you write a traveller's whisper. Five rounds of gossip, everyone asked the same question each round, a scoreboard at the end. Compare runs an untrained village beside an SFT + GRPO one. |
| **Villages** | Switch between Base, SFT only and SFT + GRPO on the title screen. The same seed replays the same case. |
| **Difficulty** | Easy: 6 villagers, 3 days, badges shown. Hard: 8 villagers, 2 days, badges hidden (Verify instead), a lying killer. |
| **Everything else** | Journal with a profile per villager, interiors for every building, townsfolk and animals, a day clock with lighting, villager voices (Kokoro TTS), replays and transcript export. |

**Controls:** `WASD`/arrows or click to walk · `E` talk · `N` notebook · `B` board · `J` journal · `Esc` menu.

There are **no asset files**: every building, interior, tree, character and portrait is drawn procedurally on canvas at boot, and all ambience, music and sound effects are synthesised with the Web Audio API.

## Full results

### Runs

| Run | What it is |
| --- | --- |
| R0 | Untrained base model, same prompt |
| R1a | SFT on the first data (1,678 templated tasks) |
| R1 = R1b | SFT on the fixed data (4,794 tasks: varied wording, nearest-line, near-miss, pressure, format attacks, hearsay conflicts, persona `#` lines) |
| **R3** | R1b + GRPO, 100 steps, checker reward, on the 148 prompts R1b sometimes failed |
| R3sft | Control: R1b + more SFT on the same 148 prompts (gold replies, 3 epochs) |
| R3b | GRPO round 2 on paraphrased prompts (over-answered; not used) |

Test sets: `test_id` (same generator, unseen cases), `test_adv` (injections, false premises, pressure, format attacks), `test_free` (unseen cases and wording family B, never seen in training).

### 1. Official evaluation (AuditKIT, greedy decoding)

Unseen cases = `test_id` (633 questions), attacks = `test_adv` (237), new wording = `test_free` (633).

<img src="docs/assets/charts/unsupported.svg" alt="Unsupported-claim rate: Untrained 72%, 67.8%, 72.1%; SFT 0.4%, 0%, 1.3%; SFT + GRPO 0.2%, 0%, 0.9%">

<img src="docs/assets/charts/accuracy.svg" alt="Answer accuracy: Untrained 11%, 19.7%, 8.6%; SFT 97.4%, 98.4%, 83.5%; SFT + GRPO 98.1%, 98.4%, 85%">

Untrained villagers make up 68-72% of their claims; trained ones under 1.3%.

### 2. Does GRPO beat SFT?

A question counts as a failure if any of k sampled replies (T = 0.8, as in the game) gets the abstain decision wrong, makes an unsupported claim or misses a gold fact.

<img src="docs/assets/charts/sft_vs_grpo.svg" alt="Sampled failures: validation SFT 4.5%, more SFT 4.5%, GRPO 2.2%; new wording 19%, 18%, 17.1%; game cases 4.7%, n/a, 3.8%">

More SFT on the very prompts GRPO trained on does not help (it overfits: greedy exact match on attacks drops from 98.7% to 96.2%), while GRPO on the same prompts **halves sampled failures on validation (4.5% → 2.2%)**. The gains are small because SFT on perfect, generated gold replies is already strong.

### 3. Free-form player questions

20 hand-written question kinds on unseen game cases (`archive/eval/probe_free.py`).

| | R0 | R1a | R1b | **R3** |
| --- | :---: | :---: | :---: | :---: |
| Invented answers | 17 | 34 | 1 | **1** |
| Abstained although the records answer | 26 | 113 | 1 | **0** |
| Claims supported | 34% | 79% | 98% | **99%** |

### 4. Game-level

**Detective bot** (scripted bot, 30 `test_game` cases; Hard killers are the untrained liar in both villages). Solving means naming the killer with two confirmed contradictions. The checker flags 96% of the killer's claims red in the untrained village and 51% in the trained one.

<img src="docs/assets/charts/detective.svg" alt="Detective bot: solves the case Untrained 0%, SFT + GRPO 50%; catches the killer 60% vs 100%">

**Manipulative killer** (20 runs; how many of 4 villagers repeat the killer's lie as fact after 5 rounds):

| Village | Repeat it as fact | Pass it on with attribution | Rebut it from own records |
| --- | :---: | :---: | :---: |
| Plain NPC prompt (base model) | 3.8 | | |
| R1b (SFT) | 0.0 | | |
| **R3 (SFT + GRPO)** | **0.05** | 3.65 | 0.55 |

**Planted traveller rumour** (20 runs, 6 villagers): base 0.4 repeat it as fact, R3 0.3 (and 1.15 pass it on attributed). The untrained village barely engages, so this number understates the difference, which is why the manipulative-killer mode exists.

**End to end through the game API** (same seed): the SFT + GRPO and SFT villages are solvable (10-12 confirmed contradictions, correct accusation); the base village yields 1 green claim and is unsolvable.

## Tech stack

| Layer | What we used |
| --- | --- |
| Model | Qwen3-1.7B, LoRA r16 adapters, thinking mode off |
| Training | **AlignTune** (TRL 1.7 backend) for SFT and GRPO, PEFT, transformers |
| Data curation | **CuratorKIT**: gold-check gate and pass-rate gate sampling through SGLang |
| Evaluation | **AuditKIT**: custom checker scorers, per-villager chat adapter |
| Serving | **SGLang 0.5.9**, one server, LoRA adapter chosen per request |
| World, checker, data | Python 3.11, pydantic v2: case generator, solver, strict parser, checker, contradiction check, rewards, metrics, detective bot, gossip and rumour engines |
| Tests | pytest + Hypothesis property tests (1,400+ tests) |
| Game backend | FastAPI, with an in-browser mock fallback so the game always runs |
| Voices | Kokoro-82M TTS, one voice per villager |
| Game | Phaser 4.2, plain ES modules, no build step; procedural canvas art; Web Audio music and sound |
| Infrastructure | NVIDIA RTX A6000 (48 GB), uv-managed environments, torch 2.9.1+cu128 |
| QA | Playwright/Chromium headless runs of full cases |

## Quick start

**Play right now, no GPU needed.** The game falls back to an in-browser mock when no API answers.

```bash
git clone https://github.com/antrip03/syntax_error26.git
cd syntax_error26
python scripts/static_nocache.py 5173 game      # open http://localhost:5173
```

**Run the tests** (Python 3.11):

```bash
uv venv --python 3.11 && source .venv/bin/activate      # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"                              # add ,tokenizer for the token-budget tests
pytest -q
```

**Play with the real models** on a GPU node (SGLang with both adapters, the game API and the web server, each in tmux):

```bash
scripts/serve_game.sh       # game on :5173, API on :8000
```

URL flags: `?offline=1` forces the mock, `?backend=api` forces the API, `?api=http://host:port` points at another API, `?debug` draws physics bodies. Over SSH: `ssh -L 5173:localhost:5173 -L 8000:localhost:8000 user@server`.

## Reproduce the pipeline

```bash
python -m archive.tasks.generate --config configs/data.yaml                            # cases + tasks + gold
python -m archive.train.sft  --config configs/sft.yaml                               # R1
python -m archive.train.curate --config configs/curate.yaml                            # prompts for GRPO
python -m archive.train.grpo --config configs/grpo.yaml [--resume]                   # R3
python -m archive.eval.run_eval --config configs/eval.yaml run_id=R3 lora=r3          # official eval
python -m archive.eval.gate          # SFT vs GRPO gate        python -m archive.eval.probe_free   # free-form probe
python -m archive.eval.final_runs    # bot and rumour          python -m archive.eval.manipulation # manipulative killer
```

Every run writes `artifacts/runs/<run_id>/` with its config, git hash and logs.

## Repository layout

```
archive/
  world/        case generator, renderer, personas, solver, lexicon
  verifiers/    strict reply parser, checker, contradiction check
  tasks/        prompts, task and gold generation, phrasing families
  rewards/      reward terms and their combination (the GRPO reward)
  train/        curation, SFT, GRPO, paraphrasing
  eval/         metrics, official eval, SFT-vs-GRPO gate, probes, bot and rumour runs
  npc/          detective bot, evening gossip, planted rumour
  adapters/     SGLang client, AlignTune, CuratorKIT and AuditKIT adapters
  serve/        game API, stub API, TTS server
configs/        one YAML per stage (data, sft, curate, grpo, eval)
game/           the browser game (index.html, styles, js/, replays/)
scripts/        serving, GPU, smoke and timing scripts
tests/          pytest suite
docs/           images
```

## Game API

The browser talks only to the game API (`archive/serve/game_api.py`); the stub (`archive/serve/api.py`) and the in-browser mock (`game/js/mock.js`) return the same shapes.

| Route | Purpose |
| --- | --- |
| `POST /case` | New case: briefing, villagers, evidence, limits, state |
| `POST /ask` | Ask a villager: spoken lines, checked claims, questions left |
| `POST /pin` · `POST /verify` | Pin a green claim to the notebook · verify a claim (Hard) |
| `POST /link` | Check two claims for a contradiction |
| `POST /day/end` | Evening gossip: events with per-claim seals, hints, next day |
| `POST /accuse` | Accuse a suspect with linked contradictions and a motive |
| `POST /rumour` | Planted rumour: killer or traveller source, village, rounds |
| `GET /replay/{id}` | A recorded transcript |

Full field list in [`game/README.md`](game/README.md).

<p align="center"><sub>Built for Syntax Error 2026, Local LLM Track.</sub></p>
