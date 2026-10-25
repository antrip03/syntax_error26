const TTS = () => (new URLSearchParams(location.search).get("tts") || window.ARCHIVE_CONFIG?.ttsUrl || "http://localhost:8001").replace(/\/$/, "");
const KEY = "vaudeville-voice";

let on = (() => { try { return localStorage.getItem(KEY) !== "off"; } catch { return true; } })();
let current = null, token = 0, downUntil = 0;

export const voiceOn = () => on;
export function setVoice(v) {
  on = v;
  try { localStorage.setItem(KEY, v ? "on" : "off"); } catch {  }
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
    if (mine !== token) return;
    current = new Audio(URL.createObjectURL(blob));
    await current.play();
  } catch (e) {
    if (mine !== token) return;
    if (e?.name !== "NotAllowedError") downUntil = Date.now() + 60000;
    browserVoice(text);
  }
}
