"""Villager voices: Kokoro-82M text-to-speech, served locally on our GPU (tts env).

scripts/serve_tts.sh                      # port 8001 (TTS_PORT), GPU via scripts/gpu.sh
POST /tts   {text, villager_id?, role?, persona?, gender?, voice?, speed?}  -> audio/wav (24 kHz mono)
GET  /voices                                                                -> fixture voices + pools
GET  /health

Voice choice, in order: `voice` if given; the fixed voice for a known villager id; otherwise a stable pick from
the pool for `gender` (f/m), hashed on villager_id, so the same villager always sounds the same. Speed comes from
`speed`, else from persona words (nervous -> faster, gentle -> slower). Citations ([D1.S2], [H3]), tags and
"CLAIM:" prefixes are stripped before speaking, so the game can pass the reply text as is.
"""
import hashlib
import io
import re
from collections import OrderedDict

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

REPO = "hexgrad/Kokoro-82M"
SR = 24000
MAX_CHARS = 600

# Elsie fixture cast; generated cases fall back to the pools.
VILLAGER_VOICES = {
    "tom": "am_puck", "gus": "bm_george", "nell": "bf_isabella", "mara": "af_bella", "ivy": "bf_emma",
    "bram": "bm_fable", "elsie": "af_heart",
}
POOLS = {
    "f": ["af_heart", "af_bella", "af_nicole", "af_sarah", "af_aoede", "af_kore", "bf_emma", "bf_isabella", "bf_alice", "bf_lily"],
    "m": ["am_michael", "am_puck", "am_fenrir", "am_eric", "am_liam", "am_onyx", "bm_george", "bm_fable", "bm_lewis", "bm_daniel"],
}
NARRATOR = "bm_lewis"
# Gender of every name in the village name pool (archive/world/lexicon.py THEMES), so a generated villager gets a
# voice that fits the name. Villager ids are their lowercase first names.
FEMALE = {"nell", "mara", "ivy", "elsie", "wren", "agnes", "maud", "bess", "tilda", "alba", "morwen", "orla", "tamsin",
          "vera", "yara", "ada", "dora", "flora", "hattie", "ines", "lettie", "nora", "greta", "brenna", "delphine"}
MALE = {"tom", "gus", "bram", "hollis", "edwin", "osric", "cedric", "rowan", "fenn", "hugh", "jory", "ned", "piers",
        "silas", "ulric", "bertram", "clem", "ezra", "giles", "jasper", "milo", "otto", "perrin", "aldous", "corin"}
PACE = [(("nervous", "anxious", "quick", "loud", "excited", "kid"), 1.1),
        (("gentle", "dreamy", "slow", "old", "elder", "calm", "scripture"), 0.88),
        (("gruff", "short sentences"), 0.95)]


class TTSRequest(BaseModel):
    text: str
    villager_id: str | None = None
    role: str | None = None
    persona: str | None = None
    gender: str | None = None
    voice: str | None = None
    speed: float | None = None


def clean(text: str) -> str:
    t = re.sub(r"\[(?:[A-Z]\d+(?:\.S\d+)?(?:,\s*)?)+\]", "", text)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"(?m)^\s*(CLAIM|SAY)\s*:\s*", "", t)
    t = re.sub(r"(?m)^\s*#\s*", "", t)
    t = re.sub(r"\*[^*]*\*", "", t)  # stage directions like *hic*
    return re.sub(r"\s+", " ", t).strip()[:MAX_CHARS]


def pick_voice(r: TTSRequest) -> str:
    if r.voice:
        return r.voice
    if r.villager_id in VILLAGER_VOICES:
        return VILLAGER_VOICES[r.villager_id]
    if not r.villager_id:
        return NARRATOR
    h = int(hashlib.md5(r.villager_id.encode()).hexdigest(), 16)
    g = (r.gender or "").lower()[:1]
    if g not in POOLS:
        key = r.villager_id.lower().split("_")[0]
        g = "f" if key in FEMALE else "m" if key in MALE else ""
    pool = POOLS[g] if g in POOLS else POOLS["f"] + POOLS["m"]
    return pool[h % len(pool)]


def pick_speed(r: TTSRequest) -> float:
    if r.speed:
        return max(0.5, min(2.0, r.speed))
    p = f"{r.persona or ''} {r.role or ''}".lower()
    for words, s in PACE:
        if any(w in p for w in words):
            return s
    return 1.0


class Voices:
    def __init__(self, device: str):
        from kokoro import KModel, KPipeline
        self.model = KModel(repo_id=REPO).to(device).eval()
        # 'a' = American voices (a*), 'b' = British (b*); both share one model
        self.pipes = {lang: KPipeline(lang_code=lang, repo_id=REPO, model=self.model) for lang in "ab"}
        self.cache: OrderedDict = OrderedDict()

    def wav(self, text: str, voice: str, speed: float) -> bytes:
        k = (text, voice, speed)
        if k in self.cache:
            self.cache.move_to_end(k)
            return self.cache[k]
        pipe = self.pipes.get(voice[0])
        if pipe is None:
            raise HTTPException(400, f"unsupported voice {voice!r}; use an a*/b* English voice")
        with torch.inference_mode():
            parts = [r.audio.cpu().numpy() for r in pipe(text, voice=voice, speed=speed) if r.audio is not None]
        audio = np.concatenate(parts) if parts else np.zeros(SR // 10, dtype=np.float32)
        buf = io.BytesIO()
        sf.write(buf, audio, SR, format="WAV", subtype="PCM_16")
        out = buf.getvalue()
        self.cache[k] = out
        if len(self.cache) > 500:
            self.cache.popitem(last=False)
        return out


app = FastAPI(title="Archive TTS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["X-Voice", "X-Speed"])
_voices: Voices | None = None


@app.on_event("startup")
def _load():
    global _voices
    _voices = Voices("cuda" if torch.cuda.is_available() else "cpu")
    _voices.wav("Hello.", NARRATOR, 1.0)  # warm up


@app.get("/health")
def health():
    return {"ok": _voices is not None, "device": str(_voices.model.device) if _voices else None}


@app.get("/voices")
def voices():
    return {"villagers": VILLAGER_VOICES, "pools": POOLS, "narrator": NARRATOR}


@app.post("/tts")
def tts(r: TTSRequest):
    text = clean(r.text)
    if not text:
        raise HTTPException(400, "nothing to say after cleaning")
    voice, speed = pick_voice(r), pick_speed(r)
    return Response(_voices.wav(text, voice, speed), media_type="audio/wav",
                    headers={"X-Voice": voice, "X-Speed": str(speed), "Cache-Control": "max-age=86400"})
