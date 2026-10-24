# Results summary (greedy decoding; AuditKit-scored; item counts per cell shown)

| run | scaffold | split | n | final accuracy [95% CI] | step validity | format | mean tokens |
|---|---|---|---|---|---|---|---|
| SFT chunk (e5) | chunk | val | 300 | 0.243 [0.197, 0.290] | 0.680 | 1.000 | 379 |
| SFT chunk (e5) | chunk | test_period | 200 | 0.260 [0.200, 0.320] | 0.674 | 1.000 | 384 |
| SFT chunk (e5) | chunk | test_len | 60 | 0.017 [0.000, 0.050] | 0.273 | 0.967 | 866 |
| SFT flat (e5) | flat | val | 300 | 0.317 [0.267, 0.373] | 0.846 | 1.000 | 500 |
| SFT flat (e5) | flat | test_period | 200 | 0.320 [0.255, 0.380] | 0.823 | 1.000 | 504 |
| SFT flat (e5) | flat | test_len | 60 | 0.000 [0.000, 0.000] | 0.532 | 0.800 | 1550 |

## Length generalisation (accuracy on test_len minus accuracy on val)

| run | val | test_len | drop |
|---|---|---|---|
| SFT chunk (e5) | 0.243 | 0.017 | -0.227 |
| SFT flat (e5) | 0.317 | 0.000 | -0.317 |

## Token efficiency

| run | split | accuracy per 1k tokens | tokens-vs-length slope |
|---|---|---|---|
| SFT chunk (e5) | val | 0.642 | -0.17 |
| SFT chunk (e5) | test_period | 0.678 | 0.25 |
| SFT chunk (e5) | test_len | 0.019 | 2.29 |
| SFT flat (e5) | val | 0.633 | 0.83 |
| SFT flat (e5) | test_period | 0.635 | 0.47 |
| SFT flat (e5) | test_len | 0.000 | 3.91 |

## Accuracy by family (val)

| run | compositional | event_count | regime_conditional | running_drawdown | windowed_stats |
|---|---|---|---|---|---|
| SFT chunk (e5) | 0.083 | 0.533 | 0.000 | 0.217 | 0.383 |
| SFT flat (e5) | 0.100 | 0.467 | 0.050 | 0.683 | 0.283 |

## Per-operation step validity (val)

| run | agg | count_breach | count_cross | dd | hi | lo | mdd | ret | vol |
|---|---|---|---|---|---|---|---|---|---|
| SFT chunk (e5) | 0.76 | 0.91 | 0.47 | nan | 0.47 | 0.51 | 0.42 | 0.70 | 0.98 |
| SFT flat (e5) | 0.84 | 0.97 | 0.60 | 0.76 | nan | nan | nan | 0.88 | 0.98 |
