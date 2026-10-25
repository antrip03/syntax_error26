// Boot: pick the backend, wait for the pixel font, start Phaser, play the opening sequence, then the title screen.

import { connect } from "./api.js";
import "./audio.js"; // ambient sound, footsteps, small-talk sounds
import { VillageScene } from "./VillageScene.js";
import { on, store } from "./store.js";

on("cinema", (v) => document.body.classList.toggle("cinema", v)); // letterbox bars during gossip / rumour
import { $, modalOpen, topModalDismissable, closeModal } from "./ui/dom.js";
import { setScene, playKeys } from "./ui/play.js";
import { setMenuScene, showTitle } from "./ui/menus.js";
import { playOpening } from "./ui/cinematic.js";

async function boot() {
  await Promise.all([
    connect(),
    document.fonts.load('16px "Pixelify Sans"').catch(() => {}),
  ]);

  on("scene-ready", (scene) => {
    setScene(scene);
    setMenuScene(scene);
    window.__archive = { scene, store }; // console / test handle
    $("#boot").remove();
    showTitle();
    playOpening(); // animated intro, briefing and SFT/GRPO explainer on every boot; the title screen waits behind it
  });

  new Phaser.Game({
    type: Phaser.AUTO,
    parent: "game",
    backgroundColor: "#2b1d14",
    pixelArt: true,
    audio: { noAudio: true },
    scale: { mode: Phaser.Scale.RESIZE, width: window.innerWidth, height: window.innerHeight },
    physics: { default: "arcade", arcade: { gravity: { x: 0, y: 0 }, debug: new URLSearchParams(location.search).has("debug") } },
    scene: [VillageScene],
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modalOpen()) {
      if (topModalDismissable()) closeModal();
      e.preventDefault();
      return;
    }
    if (playKeys(e)) e.preventDefault();
  });
}

boot();
