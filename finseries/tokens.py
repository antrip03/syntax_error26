"""Token counting: the real Qwen tokenizer when available (FINSERIES_TOKENIZER), else a calibrated approximation."""
import os
import re

_tok = None
_tried = False
_APPROX = re.compile(r"\d|[A-Za-z]+|[^\sA-Za-z\d]|\n")


def _load():
    global _tok, _tried
    if _tried:
        return _tok
    _tried = True
    if os.environ.get("FINSERIES_APPROX_TOKENS"):
        return None
    try:
        from transformers import AutoTokenizer
        name = os.environ.get("FINSERIES_TOKENIZER", "Qwen/Qwen2.5-0.5B-Instruct")
        _tok = AutoTokenizer.from_pretrained(name, local_files_only=True)
    except Exception:
        _tok = None
    return _tok


def approx_tokens(text):
    return len(_APPROX.findall(text))


def count_tokens(text, exact=True):
    tok = _load() if exact else None
    return len(tok(text)["input_ids"]) if tok is not None else approx_tokens(text)
