// Villager voices. POST {ttsUrl}/tts {text, villager_id, role, persona} -> audio/wav (Kokoro on our
// GPU, archive/serve/tts.py). If the voice server is down, the browser's own speech voice is used,
// and the server is retried after a minute. Citations and tags are stripped server side.

const TTS = () => (new URLSearchParams(location.search).get("tts") || window.ARCHIVE_CONFIG?.ttsUrl || "http://localhost:8001").replace(/\/$/, "");
const KEY = "vaudville-voice";

let on = (() => { try { return localStorage.getItem(KEY) !== "off"; } catch { return true; } })();
let current = null, token = 0, downUntil = 0;

export const voiceOn = () => on;
export function setVoice(v) {
  on = v;
  try { localStorage.setItem(KEY, v ? "on" : "off"); } catch { /* private mode */ }
  if (!v) stopVoice();
}

export function stopVoice() {
  token++;
  if (current) { current.pause(); URL.revokeObjectURL(current.src); current = null; }
  if (window.speechSynthesis) speechSynthesis.cancel();
}

function browserVoice(text) {
  if (!window.speechSynthesis) return;
  speechSynthesis.cancel();
  speechSynthesis.speak(new SpeechSynthesisUtterance(text.replace(/\[[^\]]*\]/g, "").replace(/<[^>]+>/g, "")));
}

// Speak one line as a villager. A newer call cancels an older one still loading or playing.
export async function speak(villager, text) {
  if (!on || !text?.trim()) return;
  stopVoice();
  const mine = token;
  if (Date.now() < downUntil) return browserVoice(text);
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 6000);
    const r = await fetch(`${TTS()}/tts`, {
      method: "POST", headers: { "content-type": "application/json" }, signal: ctl.signal,
      body: JSON.stringify({ text, villager_id: villager.id, role: villager.role, persona: villager.persona }),
    });
    clearTimeout(timer);
    if (!r.ok) throw new Error(`tts ${r.status}`);
    const blob = await r.blob();
    if (mine !== token) return; // something newer started meanwhile
    current = new Audio(URL.createObjectURL(blob));
    await current.play();
  } catch (e) {
    if (mine !== token) return;
    if (e?.name !== "NotAllowedError") downUntil = Date.now() + 60000;
    browserVoice(text);
  }
}
