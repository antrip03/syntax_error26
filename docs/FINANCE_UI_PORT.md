# Finance port of the game (branch `finance-ui`)

Created from `archive`; `archive`, `main` and `p2-core` are untouched.

Changed: `game/js/mock.js` (new finance backend with the same routes/shapes), `game/js/data/market.js` (replaces `elsie.js`),
`game/data/cases.json` (real model outputs), UI strings in `menus.js`, `play.js`, `claims.js`, `encounter.js`, `map.js`, `index.html`,
`game/replays/*` (recorded from real outputs), `game/test/mock_smoke.mjs`.
Added: `finseries/` (our verifier, copied from `main`), `scripts/build_game_cases.py`, `scripts/build_game_replays.py`, `scripts/reskin_finance.py`
(the exact text replacements applied, asserting each match).
Unchanged: Phaser scenes, art, audio, camera, store, API client (`api.js`) and the route contract.
