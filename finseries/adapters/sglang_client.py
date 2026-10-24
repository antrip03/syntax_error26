"""Thin client for SGLang's OpenAI-compatible endpoint: batched, threaded, seeded. All generation for eval,
curation pass-rate sampling and self-consistency goes through here."""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


@dataclass
class Gen:
    text: str
    n_tokens: int
    finish: str          # stop | length | error:...


class SGLangClient:
    def __init__(self, base_url="http://127.0.0.1:30000", model="default", concurrency=64, timeout=600):
        self.base, self.model, self.concurrency, self.timeout = base_url.rstrip("/"), model, concurrency, timeout

    def _one(self, system, user, temperature, max_tokens, seed, retries=3):
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        body = {"model": self.model, "temperature": temperature, "max_tokens": max_tokens, "seed": seed, "messages": msgs}
        req = urllib.request.Request(f"{self.base}/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        err = ""
        for k in range(retries):
            try:
                r = json.loads(urllib.request.urlopen(req, timeout=self.timeout).read())
                ch = r["choices"][0]
                return Gen(ch["message"]["content"] or "", int(r["usage"]["completion_tokens"]), ch.get("finish_reason") or "stop")
            except Exception as e:  # noqa: BLE001
                err = repr(e)
                time.sleep(2 * (k + 1))
        return Gen("", 0, "error:" + err[:80])

    def generate(self, system, prompts, n=1, temperature=0.0, max_tokens=1024, seed=0):
        """-> list (per prompt) of list (n) of Gen. Greedy when temperature == 0 (use n=1)."""
        jobs = [(i, j) for i in range(len(prompts)) for j in range(n)]
        with ThreadPoolExecutor(self.concurrency) as ex:
            res = list(ex.map(lambda ij: self._one(system, prompts[ij[0]], temperature, max_tokens, seed + ij[1] + 1000 * ij[0]), jobs))
        out = [[None] * n for _ in prompts]
        for (i, j), g in zip(jobs, res):
            out[i][j] = g
        return out
