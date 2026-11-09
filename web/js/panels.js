// The three side panels: cleanup (above the transcript), captions and export.

import { t } from "./i18n.js";
import { toggleDeleted } from "./store.js";
import { findMatches } from "./find.js";
import { findPauses } from "./timeline.js";

const $ = (id) => document.getElementById(id);
const KINDS = ["filler", "repeat", "loose"];

/** Suggestions grouped by kind, each with the word indices it covers. */
function grouped(project) {
  const out = Object.fromEntries(KINDS.map((k) => [k, []]));
  for (const hit of project.suggestions) out[hit.kind]?.push(hit.words);
  return out;
}

export class Cleanup {
  constructor(store, transcript, player) {
    this.store = store;
    this.transcript = transcript;
    this.player = player;
    this.steps = {};
    $("pause-threshold").addEventListener("input", (e) => {
      store.change((s) => { s.pause.threshold = Number(e.target.value); }, "pause");
    });
    $("pause-keep").addEventListener("input", (e) => {
      store.change((s) => { s.pause.keep = Number(e.target.value); }, "keep");
    });
    $("pause-apply").addEventListener("click", () => this.togglePauses());
    this.hits = [];
    const input = $("find-input");
    input.addEventListener("input", () => this.paintFind());
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); this.stepFind(e.shiftKey ? -1 : 1); }
      else if (e.key === "Escape") { e.stopPropagation(); this.clearFind(); transcript.root.focus({ preventScroll: true }); }
    });
    $("find-next").addEventListener("click", () => this.stepFind(1));
    $("find-prev").addEventListener("click", () => this.stepFind(-1));
    $("find-cut").addEventListener("click", () => {
      const words = this.hits.flat();
      store.change((s) => toggleDeleted(s, words));
    });
  }

  focusFind() {
    const input = $("find-input");
    input.focus();
    input.select();
  }

  clearFind() {
    $("find-input").value = "";
    this.paintFind();
  }

  /** Mark the matches in the transcript and fill the Cut button. Runs on every change, since a fixed word can add or remove a match. */
  paintFind() {
    const query = $("find-input").value;
    const { project, state } = this.store;
    this.hits = project && query.trim() ? findMatches(project.words, state, query) : [];
    this.transcript.setHits(this.hits);
    const found = this.hits.length > 0;
    $("find-hits").hidden = !found;
    $("find-none").hidden = found || !query.trim();
    if (!found) return;
    const gone = new Set(state.deleted);
    const all = this.hits.flat().every((i) => gone.has(i));
    const cut = $("find-cut");
    cut.setAttribute("aria-pressed", String(all));
    cut.textContent = t(all ? "find.restore" : "find.cut", { n: this.hits.length });
    for (const id of ["find-prev", "find-next"]) {
      const b = $(id);
      b.title = t(id === "find-next" ? "clean.next" : "clean.prev");
      b.setAttribute("aria-label", b.title);
    }
  }

  /** Move to the next match after the cursor, or the one before it, and wrap around at the ends. */
  stepFind(dir) {
    if (this.hits.length) this.goTo(this.hits.map((run) => run[0]), dir);
  }

  pauses() {
    return findPauses(this.store.project.words, this.store.state.pause.threshold);
  }

  togglePauses() {
    const gaps = this.pauses();
    this.store.change((s) => {
      const set = new Set(s.cutGaps);
      const all = gaps.every((g) => set.has(g));
      for (const g of gaps) all ? set.delete(g) : set.add(g);
      s.cutGaps = [...set].sort((a, b) => a - b);
    });
  }

  build() {
    const box = $("clean-kinds");
    box.textContent = "";
    this.groups = grouped(this.store.project);
    this.steps = {};
    for (const kind of KINDS) {
      if (!this.groups[kind].length) continue;
      const wrap = document.createElement("div");
      wrap.className = "kind";
      wrap.dataset.kind = kind;
      const main = document.createElement("button");
      main.type = "button";
      main.className = "main";
      main.addEventListener("click", () => {
        const words = this.groups[kind].flat();
        this.store.change((s) => toggleDeleted(s, words));
      });
      const prev = this.stepButton("‹", kind, -1);
      const next = this.stepButton("›", kind, 1);
      wrap.append(main, prev, next);
      box.append(wrap);
    }
    const note = $("clean-note");
    const none = KINDS.every((k) => !this.groups[k].length);
    note.hidden = !none;
    note.textContent = none ? t("clean.none") : "";
  }

  stepButton(label, kind, dir) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "step";
    b.textContent = label;
    b.addEventListener("click", () => this.step(kind, dir));
    return b;
  }

  step(kind, dir) {
    this.goTo(this.groups[kind].map((w) => w[0]), dir);
  }

  goTo(firsts, dir) {
    const here = this.transcript.cursor;
    const target = dir > 0 ? firsts.find((i) => i > here) ?? firsts[0] : [...firsts].reverse().find((i) => i < here) ?? firsts.at(-1);
    this.transcript.moveTo(target);
    this.player.seek(this.store.project.words[target].start);
  }

  paint() {
    const { state } = this.store;
    const deleted = new Set(state.deleted);
    for (const wrap of $("clean-kinds").children) {
      const kind = wrap.dataset.kind;
      const hits = this.groups[kind];
      const on = hits.flat().every((i) => deleted.has(i));
      const main = wrap.querySelector(".main");
      main.setAttribute("aria-pressed", String(on));
      main.textContent = t(`clean.${kind}`, { n: hits.length });
      wrap.querySelectorAll(".step").forEach((b, k) => { b.title = t(k ? "clean.next" : "clean.prev"); b.setAttribute("aria-label", b.title); });
    }
    this.paintFind();
    const { threshold, keep } = state.pause;
    $("pause-threshold").value = threshold;
    $("pause-keep").value = keep;
    $("pause-threshold-out").textContent = `${threshold.toFixed(1)}s`;
    $("pause-keep-out").textContent = `${Number(keep).toFixed(2)}s`;
    const gaps = this.pauses();
    const set = new Set(state.cutGaps);
    const applied = gaps.length > 0 && gaps.every((g) => set.has(g));
    const button = $("pause-apply");
    button.disabled = gaps.length === 0;
    button.textContent = t(applied ? "clean.restorePauses" : "clean.cutPauses", { n: gaps.length });
  }
}

const STYLE_SAMPLE = { highlight: "Hello <b>world</b>", karaoke: "<b>Hello</b> world", pop: "Hello <b>world</b>", lowerthird: "Hello world", plain: "Hello world" };

export class CaptionPanel {
  constructor(store) {
    this.store = store;
    const fieldset = $("cap-styles");
    for (const style of Object.keys(STYLE_SAMPLE)) {
      const card = document.createElement("label");
      card.className = "style-card";
      card.innerHTML = `<input type="radio" name="cap-style" value="${style}"><span class="sample"></span><small data-style="${style}"></small>`;
      card.querySelector(".sample").innerHTML = STYLE_SAMPLE[style].replace("<b>", '<b style="color: var(--sug)">');
      card.querySelector("input").addEventListener("change", () => store.change((s) => { s.caption.style = style; }));
      fieldset.append(card);
    }
    const bind = (id, key, read) => $(id).addEventListener("input", (e) => store.change((s) => { s.caption[key] = read(e.target); }, `cap-${key}`));
    bind("cap-position", "position", (el) => el.value);
    bind("cap-size", "size", (el) => Number(el.value));
    bind("cap-color", "color", (el) => el.value.toUpperCase());
    bind("cap-accent", "accent", (el) => el.value.toUpperCase());
    bind("cap-upper", "uppercase", (el) => el.checked);
    bind("cap-burn", "burn", (el) => el.checked);
  }

  paint() {
    const c = this.store.state.caption;
    for (const input of document.querySelectorAll('input[name="cap-style"]')) input.checked = input.value === c.style;
    for (const small of document.querySelectorAll("#cap-styles small")) small.textContent = t(`cap.${small.dataset.style}`);
    $("cap-position").value = c.position;
    $("cap-size").value = c.size;
    $("cap-color").value = c.color.toLowerCase();
    $("cap-accent").value = c.accent.toLowerCase();
    $("cap-upper").checked = c.uppercase;
    $("cap-burn").checked = c.burn;
  }
}

const ROWS = [
  ["mp4", "export.mp4", true],
  ["srt", "export.srt", false],
  ["vtt", "export.vtt", false],
  ["ass", "export.ass", false],
  ["edl", "export.edl", false],
  ["fcpxml", "export.fcpxml", false],
  ["otio", "export.otio", false],
  ["json", "export.json", false],
];

export class ExportPanel {
  constructor(store, api, flush, toast) {
    this.store = store;
    this.api = api;
    this.flush = flush;
    this.toast = toast;
    this.rendering = false;
  }

  build() {
    const list = $("export-list");
    list.textContent = "";
    const formats = this.api.info.formats ?? [];
    for (const [fmt, key] of ROWS) {
      if (!formats.includes(fmt)) continue;
      const li = document.createElement("li");
      li.dataset.fmt = fmt;
      li.innerHTML = "<div><strong></strong><span></span></div>";
      const button = document.createElement("button");
      button.type = "button";
      button.className = fmt === "mp4" ? "btn primary" : "btn";
      button.addEventListener("click", () => (fmt === "mp4" ? this.render() : this.download(fmt)));
      li.append(button);
      list.append(li);
    }
    if (this.api.mode === "demo") {
      const li = document.createElement("li");
      li.innerHTML = "<div><strong></strong><span></span></div>";
      li.dataset.fmt = "demo";
      list.append(li);
    }
    this.paint();
  }

  paint() {
    for (const li of $("export-list").children) {
      const fmt = li.dataset.fmt;
      const [title, hint] = li.querySelectorAll("strong, span");
      if (fmt === "demo") { title.textContent = t("export.demoTitle"); hint.textContent = t("export.demoBody"); continue; }
      title.textContent = t(`export.${fmt}.title`);
      hint.textContent = t(`export.${fmt}.hint`);
      const button = li.querySelector("button");
      button.textContent = t(fmt === "mp4" ? "export.render" : "export.download");
      if (fmt === "mp4") button.disabled = this.rendering;
    }
  }

  async download(fmt) {
    try {
      if (this.api.mode === "demo") {
        const file = this.api.textExport(fmt, this.store.project, this.store.state);
        const url = URL.createObjectURL(new Blob([file.text], { type: file.mime }));
        this.save(url, file.name);
        setTimeout(() => URL.revokeObjectURL(url), 10000);
      } else {
        await this.flush();
        this.save(this.api.exportUrl(this.id, fmt), "");
      }
    } catch (err) {
      this.toast(t("err.export", { message: err.message }));
    }
  }

  save(url, name) {
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.append(a);
    a.click();
    a.remove();
  }

  async render() {
    const box = $("render-box");
    const bar = $("render-bar");
    const text = $("render-text");
    this.rendering = true;
    this.paint();
    box.hidden = false;
    bar.style.width = "0";
    text.textContent = t("export.rendering", { pct: 0 });
    try {
      await this.flush();
      let job = await this.api.render(this.id);
      while (job.status === "queued" || job.status === "running") {
        bar.style.width = `${Math.round(job.progress * 100)}%`;
        text.textContent = t("export.rendering", { pct: Math.round(job.progress * 100) });
        await new Promise((r) => setTimeout(r, 500));
        job = await this.api.job(job.id);
      }
      if (job.status !== "done") throw new Error(job.error || "render failed");
      bar.style.width = "100%";
      text.textContent = t("export.done");
      this.save(this.api.jobFileUrl(job.id), "");
    } catch (err) {
      text.textContent = t("err.export", { message: err.message });
    } finally {
      this.rendering = false;
      this.paint();
    }
  }
}
