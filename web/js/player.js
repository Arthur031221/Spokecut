// Playback of the source video that jumps over the cuts, plus the live caption preview.

import { chunkWords, keptWords, maxCharsFor } from "./captions.js";
import { EPS, outputDuration, plan, toOutput } from "./timeline.js";

export function clock(seconds) {
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rest = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${rest}` : `${m}:${rest}`;
}

/** Index of the last word starting at or before t, or -1. Words are sorted by start. */
export function wordAt(words, t) {
  let lo = 0;
  let hi = words.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (words[mid].start <= t + EPS) { found = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return found;
}

export class Player {
  constructor(els, store, hooks) {
    this.els = els;
    this.store = store;
    this.hooks = hooks; // { onTime(t, wordIndex), onPlayState(playing) }
    this.skip = true;
    this.plan = null;
    this.chunks = [];
    this.capKey = "";
    this.raf = 0;
    const v = els.video;
    v.addEventListener("play", () => this.started());
    v.addEventListener("pause", () => this.stopped());
    v.addEventListener("ended", () => this.stopped());
    v.addEventListener("seeked", () => this.tick());
    v.addEventListener("loadedmetadata", () => this.tick());
    els.play.addEventListener("click", () => this.toggle());
    els.speed.addEventListener("change", () => { v.playbackRate = Number(els.speed.value); });
    store.subscribe(() => this.refresh());
  }

  get time() { return this.els.video.currentTime; }

  load(url, hasVideo) {
    this.els.video.src = url;
    this.els.video.load();
    this.els.audioOnly.hidden = hasVideo;
    this.els.video.style.visibility = hasVideo ? "visible" : "hidden";
    this.refresh();
  }

  /** Shape the preview like the video frame so the captions land where the render puts them. */
  fitFrame({ width, height }) {
    const wrap = this.els.video.parentElement;
    const ok = width > 0 && height > 0;
    wrap.style.setProperty("--ar", ok ? `${width} / ${height}` : "16 / 9");
    wrap.style.setProperty("--arn", ok ? String(width / height) : "1.778");
  }

  /** Recompute cuts and captions after the edit state changed. */
  refresh() {
    const { project, state } = this.store;
    if (!project) return;
    this.plan = plan(project, state);
    this.fitFrame(project.media);
    const kept = keptWords(project.words, state, this.plan.segs);
    this.chunks = chunkWords(kept, project.language, maxCharsFor(project.media.width, project.media.height));
    this.capKey = "";
    const c = state.caption;
    const layer = this.els.captionLayer;
    layer.dataset.style = c.style;
    layer.dataset.pos = c.position;
    layer.style.setProperty("--cap-size", `${c.size}cqh`);
    layer.style.setProperty("--cap-color", c.color);
    layer.style.setProperty("--cap-accent", c.accent);
    layer.hidden = !c.burn;
    this.tick();
  }

  toggle() {
    const v = this.els.video;
    if (v.paused) {
      if (this.cutAt(v.currentTime)) this.jumpOver(v.currentTime);
      v.play().catch(() => {});
    } else v.pause();
  }

  seek(t) {
    this.els.video.currentTime = Math.max(0, Math.min(t, this.store.project.media.duration));
  }

  setSkip(on) { this.skip = on; this.tick(); }

  cutAt(t) {
    return this.plan?.cuts.find(([a, b]) => a - EPS <= t && t < b - EPS);
  }

  jumpOver(t) {
    const cut = this.cutAt(t);
    if (!cut) return false;
    const duration = this.store.project.media.duration;
    if (cut[1] >= duration - 0.05) { this.els.video.pause(); this.seek(cut[0]); return true; }
    this.els.video.currentTime = cut[1];
    return true;
  }

  started() {
    this.hooks.onPlayState(true);
    const loop = () => {
      this.tick();
      if (!this.els.video.paused) this.raf = requestAnimationFrame(loop);
    };
    cancelAnimationFrame(this.raf);
    this.raf = requestAnimationFrame(loop);
  }

  stopped() {
    cancelAnimationFrame(this.raf);
    this.hooks.onPlayState(false);
    this.tick();
  }

  tick() {
    const { project } = this.store;
    if (!project || !this.plan) return;
    const v = this.els.video;
    let t = v.currentTime;
    if (this.skip && !v.paused && this.jumpOver(t)) t = v.currentTime;
    const { segs, keeps } = this.plan;
    const total = outputDuration(keeps);
    const shown = this.skip ? toOutput(segs, t) : t;
    this.els.clock.textContent = `${clock(shown)} / ${clock(this.skip ? total : project.media.duration)}`;
    const idx = wordAt(project.words, t);
    this.hooks.onTime(t, idx);
    this.paintCaption(toOutput(segs, t));
  }

  paintCaption(out) {
    const layer = this.els.captionLayer;
    const style = this.store.state.caption.style;
    const chunk = this.chunks.find((c) => c.start - EPS <= out && out <= c.end + 0.15);
    if (!chunk) {
      if (this.capKey !== "none") { layer.textContent = ""; this.capKey = "none"; }
      return;
    }
    let on = -1;
    chunk.words.forEach((w, i) => { if (w.start - EPS <= out) on = i; });
    const key = `${this.chunks.indexOf(chunk)}:${style === "plain" || style === "lowerthird" ? 0 : on}`;
    if (key === this.capKey) return;
    this.capKey = key;
    const upper = this.store.state.caption.uppercase;
    const box = document.createElement("div");
    box.className = "cap";
    chunk.words.forEach((w, i) => {
      const span = document.createElement("span");
      span.textContent = upper ? w.text.toUpperCase() : w.text;
      const lit = style === "karaoke" ? i <= on : style === "highlight" || style === "pop" ? i === on : false;
      if (lit) span.className = "on";
      box.append(span);
      if (chunk.sep && i < chunk.words.length - 1) box.append(chunk.sep);
    });
    layer.replaceChildren(box);
  }
}
