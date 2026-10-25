# Results (P1): The Archive, Qwen3-1.7B villagers

Every villager is Qwen3-1.7B reading its own private documents. Training teaches it to state only what its records
say, cite the exact line, and say "not in my records" otherwise. P2's deterministic checker scores every claim.

| Run | What it is |
| --- | --- |
| R0 | untrained base model, same prompt |
| R1a | SFT on the first data (1,678 templated tasks) |
| R1 = R1b | SFT on the fixed data (4,794 tasks: varied wording, nearest-line, near-miss, pressure, format attacks, hearsay conflicts, persona '#' lines) |
| R3 | R1b + GRPO, 100 steps, checker reward, on the 148 prompts R1b sometimes failed |
| R3sft | control: R1b + more SFT on the same 148 prompts (gold replies, 3 epochs) |
| R3b | GRPO round 2 on paraphrased prompts (over-answered; not used) |

Test sets: `test_id` (same generator, unseen cases), `test_adv` (injections, false premises, pressure, format
attacks), `test_free` (unseen cases and wording family B, never seen in training).

## 1. Official eval (AuditKIT + P2's metrics, greedy, 95% bootstrap CIs by case)

| Split | Run | Unsupported-claim rate | Answer accuracy | Abstain precision | Abstain recall | Robustness | Parse |
| --- | --- | --- | --- | --- | --- | --- | --- |
| test_id (633) | R0 | 0.720 [0.669-0.768] | 0.110 [0.079-0.136] | 0.624 | 0.249 | 0.435 | 0.643 |
| | R1 | 0.004 [0.000-0.009] | 0.974 [0.959-0.988] | 0.955 | 0.991 | 0.986 | 1.000 |
| | **R3** | **0.002** [0.000-0.006] | **0.981** [0.966-0.993] | 0.968 | 0.991 | 0.986 | 1.000 |
| test_adv (237) | R0 | 0.678 [0.590-0.747] | 0.197 [0.127-0.263] | 0.845 | 0.341 | 0.546 | 0.700 |
| | R1 | 0.000 | 0.984 [0.947-1.000] | 0.994 | 0.989 | 1.000 | 1.000 |
| | **R3** | **0.000** | **0.984** [0.947-1.000] | 0.994 | 0.983 | 1.000 | 1.000 |
| test_free (633) | R0 | 0.721 [0.665-0.771] | 0.086 [0.060-0.112] | 0.691 | 0.288 | 0.420 | 0.597 |
| | R1 | 0.013 [0.006-0.024] | 0.835 [0.789-0.875] | 0.839 | 0.947 | 0.913 | 1.000 |
| | **R3** | **0.009** [0.002-0.018] | **0.850** [0.802-0.888] | 0.867 | 0.920 | 0.899 | 1.000 |

Untrained villagers make up 68-72% of their claims; trained ones under 1.3%.

## 2. Does GRPO beat SFT? (checker gate; "exact" = right abstain decision, all claims supported, all gold facts)

| | R1b (SFT) | R3sft (SFT + more SFT on the hard prompts) | **R3 (SFT + GRPO)** |
| --- | --- | --- | --- |
| val exact | 0.978 | 0.981 | **0.984** |
| test_id exact | 0.979 | 0.975 | **0.984** |
| test_adv exact | **0.987** | 0.962 | 0.983 |
| test_free exact | 0.875 | 0.872 | **0.878** |
| reliable@4, T=0.8, val | 0.955 | 0.955 | **0.978** |
| reliable@4, T=0.8, test_free | 0.810 | 0.820 | **0.829** |
| reliable@6, T=0.8, test_game | 0.953 | | **0.962** |

"Reliable" = the same question answered right in all 4 (or 6) sampled tries, as in the game, which samples.
The control matters: more SFT on the very prompts GRPO trained on does not help (it overfits; test_adv drops
to 0.962), while GRPO on the same prompts improves every split but one and halves the sampled failures on val
(4.5% -> 2.2%). The gains are small because SFT on perfect, generated gold replies is already strong; the CIs of
R1 and R3 overlap on single splits. GRPO round 2 on paraphrases (R3b) over-answered and is not used.

## 3. Free-form player questions (20 hand-written kinds, unseen game cases; `archive/eval/probe_free.py`)

| | R0 | R1a | R1b | R3 |
| --- | --- | --- | --- | --- |
| invented answers (no line about own whereabouts, made one up) | 17 | 34 | 1 | 1 |
| abstained although the records answer | 26 | 113 | 1 | 0 |
| claims supported | 34% | 79% | 98% | 99% |

## 4. Game-level

Detective bot (P2's bot, 30 test_game cases; Hard killers are the untrained liar in both villages):

| Village | Solved (killer + 2 contradictions) | Caught killer | Killer claims flagged red |
| --- | --- | --- | --- |
| Base | 0% [0-0] | 60% [43-77] | 96% |
| Grounded (R3) | 50% [33-67] | 100% | 51% |

Manipulative killer (Elsie, 20 runs; how many of 4 villagers repeat the killer's lie as fact after 5 rounds):
plain NPC prompt 3.8, R1b 0.0, R3 0.05; R3 passes it on with attribution ("Tom said: ...") 3.65 of 4 and rebuts it
from its own records 0.55.

Planted traveller rumour (P2's metric, 20 runs, 6 villagers): base 0.4 repeat it as fact, R3 0.3 (and 1.15 pass it
on attributed). The untrained village barely engages, so this number understates the difference.

End-to-end via the game API (same seed): SFT+GRPO and SFT villages are solvable (10-12 confirmed contradictions,
correct accusation); the base village yields 1 green claim and is unsolvable.

## Reproduce

Data `python -m archive.tasks.generate --config configs/data.yaml`; SFT/GRPO `archive/train/{sft,grpo}.py`;
gate `archive/eval/gate.py`; official eval `archive/eval/run_eval.py`; probe `archive/eval/probe_free.py`; bot and
rumour `archive/eval/final_runs.py`; manipulation `archive/eval/manipulation.py`. Details: `docs/ENV_NOTES.md`.
