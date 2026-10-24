// Runtime config. Override per deploy, or with URL params: ?api=https://... or ?offline=1
window.ARCHIVE_CONFIG = {
  apiUrl: "http://localhost:8000",
  ttsUrl: "http://localhost:8001", // villager voices (archive/serve/tts.py); browser voice if down
  // "auto": use the API if /health answers, else the in-browser mock. "api" | "mock" force one.
  backend: "auto",
};
