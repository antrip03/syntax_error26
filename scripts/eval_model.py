"""Serve a (merged) model with SGLang and evaluate one scaffold on one task split. Hardware-agnostic (Kaggle / Modal).
usage: python scripts/eval_model.py --model PATH --arm chunk --variant e1 --tasks-dir DIR --split val --out DIR"""
import argparse
import json
import sys

sys.path.insert(0, ".")
from finseries.adapters.sglang_client import SGLangClient  # noqa: E402
from finseries.eval import run_eval  # noqa: E402
from finseries.serve import sglang_server  # noqa: E402
from finseries.tasks.generate import read_jsonl  # noqa: E402

VARIANTS = {"base": {}, "e1": {"prompt_style": "indexed"}, "e2": {"prompt_style": "indexed", "trace_style": "scratch"},
            "e3": {"prompt_style": "index5", "trace_style": "scratch"}, "e4": {"trace_style": "scratch"}, "e5": {"trace_style": "scratch2"}}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--variant", default="base")
    ap.add_argument("--tasks-dir", required=True)
    ap.add_argument("--split", default="val")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--max-tokens", type=int, default=1500)
    ap.add_argument("--flags", default="--dtype bfloat16 --attention-backend triton --sampling-backend pytorch --mem-fraction-static 0.85")
    ap.add_argument("--python", default="python")
    a = ap.parse_args()
    tasks = read_jsonl(f"{a.tasks_dir}/{a.split}.jsonl")[:a.limit]
    with sglang_server.server(a.model, gpu=0, flags=a.flags, log="/tmp/sglang_server.log", python=a.python, stub=None) as url:
        _, m = run_eval.run(tasks, a.arm, SGLangClient(url, concurrency=128), a.out, max_tokens=a.max_tokens,
                            scaffold_kwargs=VARIANTS[a.variant])
    o = m["overall"]
    print(f"EVAL {a.arm}/{a.variant}/{a.split}: acc={o['accuracy']:.3f} parse={o['parse_rate']:.3f} "
          f"stepvalid={o['step_validity']:.3f} tok={o['mean_tokens']:.0f}")
    print("BY_OP", json.dumps({k: [v["n"], round(v["valid"], 3)] for k, v in list(m["by_op"].items())[:12]}))
    print("BY_FAMILY", json.dumps({k: [round(v["accuracy"], 3), round(v["step_validity"], 3)] for k, v in m["by_family"].items()}))
