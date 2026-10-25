
import { MockBackend } from "./mock.js";

class HttpBackend {
  constructor(base) {
    this.kind = "api";
    this.base = base.replace(/\/$/, "");
  }

  async _req(method, path, body) {
    const res = await fetch(this.base + path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  health() { return this._req("GET", "/health"); }
  newCase(body) { return this._req("POST", "/case", body); }
  ask(body) { return this._req("POST", "/ask", body); }
  verify(body) { return this._req("POST", "/verify", body); }
  pin(body) { return this._req("POST", "/pin", body); }
  link(body) { return this._req("POST", "/link", body); }
  dayEnd(body) { return this._req("POST", "/day/end", body); }
  accuse(body) { return this._req("POST", "/accuse", body); }
  rumour(body) { return this._req("POST", "/rumour", body); }
  state(caseId) { return this._req("GET", `/state/${encodeURIComponent(caseId)}`); }
  replay(id) { return this._req("GET", `/replay/${encodeURIComponent(id)}`); }
}

function settings() {
  const cfg = window.ARCHIVE_CONFIG || {};
  const params = new URLSearchParams(location.search);
  return {
    apiUrl: params.get("api") || cfg.apiUrl || "http://localhost:8000",
    backend: params.has("offline") ? "mock" : params.get("backend") || cfg.backend || "auto",
  };
}

export let api = new MockBackend();

export async function connect() {
  const { apiUrl, backend } = settings();
  if (backend === "mock") return (api = new MockBackend());
  const http = new HttpBackend(apiUrl);
  if (backend === "api") return (api = http);
  try {
    await Promise.race([http.health(), new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), 2500))]);
    api = http;
  } catch {
    api = new MockBackend();
  }
  return api;
}

export function backendLabel() {
  return api.kind === "api" ? `Live API · ${api.base}` : "Offline mock";
}
