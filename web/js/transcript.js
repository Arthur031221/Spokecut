// The transcript: one span per word, a chip for each pause, selection, keyboard editing.

import { t } from "./i18n.js";
import { toggleDeleted, toggleGap, setEdit } from "./store.js";
import { wordText } from "./timeline.js";

const MIN_CHIP = 0.3; // pauses shorter than this get no chip

export class Transcript {
  /** @param {HTMLElement} root @param {import("./store.js").Store} store @param {{seek(t:number):void, toggle():void}} player */
  constructor(root, store, player) {
    this.root = root;
    this.store = store;
    this.player = player;
    this.cursor = 0;
    this.anchor = 0;
    this.dragging = false;
    this.spans = [];
    this.chips = new Map();
    this.now = -1;
    this.suggested = new Set();
    this.hitRuns = [];
    this.hitWords = new Set();
    this.extendNext = false;
    root.addEventListener("mousedown", (e) => this.onDown(e));
    root.addEventListener("mouseover", (e) => this.onOver(e));
    window.addEventListener("mouseup", () => this.onUp());
    root.addEventListener("keydown", (e) => this.onKey(e));
    root.addEventListener("dblclick", (e) => {
      const i = this.indexOf(e.target);
      if (i >= 0) this.edit(i);
    });
    root.addEventListener("click", (e) => {
      const chip = e.target.closest(".gap");
      if (chip) store.change((s) => toggleGap(s, Number(chip.dataset.gap)));
    });
  }

  get words() { return this.store.project.words; }

  /** Wire the Cut button and the touch friendly Select range toggle that sit above the transcript. */
  bindBar(cut, extend) {
    this.bar = { cut, extend };
    cut.addEventListener("click", () => {
      this.store.change((s) => toggleDeleted(s, this.selection()));
      this.root.focus({ preventScroll: true });
    });
    extend.addEventListener("click", () => {
      this.extendNext = !this.extendNext;
      this.paintBar();
    });
  }

  paintBar() {
    if (!this.bar) return;
    this.bar.cut.disabled = !this.words.length;
    if (!this.words.length) return;
    const gone = new Set(this.store.state.deleted);
    const sel = this.selection();
    const n = sel.length;
    this.bar.cut.textContent = t(sel.every((i) => gone.has(i)) ? "tx.restore" : "tx.cut", { n });
    this.bar.extend.setAttribute("aria-pressed", String(this.extendNext));
  }

  indexOf(el) {
    const span = el.closest?.(".w");
    return span ? Number(span.dataset.i) : -1;
  }

  /** Rebuild the DOM. Only needed when the words change; edits and deletions are applied by paint(). */
  build() {
    const { words } = this.store.project;
    this.root.textContent = "";
    this.spans = [];
    this.chips.clear();
    this.suggested = new Set(this.store.project.suggestions.flatMap((s) => s.words));
    this.hitRuns = [];
    this.hitWords = new Set();
    const frag = document.createDocumentFragment();
    words.forEach((w, i) => {
      if (i > 0) {
        const gap = w.start - words[i - 1].end;
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "gap";
        chip.dataset.gap = String(i);
        chip.tabIndex = -1;
        chip.hidden = gap < MIN_CHIP;
        chip.textContent = `${gap.toFixed(1)}s`;
        chip.title = t("tx.gapTitle");
        this.chips.set(i, chip);
        frag.append(chip);
      }
      const span = document.createElement("span");
      span.className = "w";
      span.dataset.i = String(i);
      frag.append(span);
      frag.append(document.createTextNode(" "));
      this.spans.push(span);
    });
    this.root.append(frag);
    this.cursor = this.anchor = 0;
    this.paint();
  }

  /** Highlight the words of the find matches. The match the cursor is in gets a stronger mark. */
  setHits(runs) {
    this.hitRuns = runs;
    this.hitWords = new Set(runs.flat());
    this.paintHits();
  }

  paintHits() {
    const here = this.hitRuns.find((run) => run.includes(this.cursor)) ?? [];
    this.spans.forEach((span, i) => {
      span.classList.toggle("hit", this.hitWords.has(i));
      span.classList.toggle("hit-now", here.includes(i));
    });
  }

  /** Apply deletion, edit and suggestion classes to the existing spans. */
  paint() {
    const { state } = this.store;
    const { words } = this.store.project;
    const deleted = new Set(state.deleted);
    const [lo, hi] = this.range();
    this.spans.forEach((span, i) => {
      const text = wordText(words, state, i);
      if (span.firstChild?.nodeType === 3 && span.textContent !== text) span.textContent = text;
      else if (!span.firstChild) span.textContent = text;
      span.classList.toggle("del", deleted.has(i));
      span.classList.toggle("edited", i in state.edits);
      span.classList.toggle("sug", this.suggested.has(i) && !deleted.has(i));
      span.classList.toggle("sel", i >= lo && i <= hi);
      span.classList.toggle("cursor", i === this.cursor);
    });
    if (this.hitWords.size) this.paintHits();
    this.paintBar();
    const gaps = new Set(state.cutGaps);
    for (const [g, chip] of this.chips) {
      chip.classList.toggle("cut", gaps.has(g));
      chip.setAttribute("aria-pressed", String(gaps.has(g)));
    }
  }

  range() {
    return [Math.min(this.anchor, this.cursor), Math.max(this.anchor, this.cursor)];
  }

  selection() {
    const [lo, hi] = this.range();
    return Array.from({ length: hi - lo + 1 }, (_, k) => lo + k);
  }

  moveTo(i, extend = false, reveal = true) {
    const last = this.words.length - 1;
    this.cursor = Math.max(0, Math.min(last, i));
    if (!extend) this.anchor = this.cursor;
    this.paint();
    if (reveal) this.reveal(this.cursor);
  }

  onDown(e) {
    if (e.button !== 0 || e.target.closest(".w-edit")) return;
    const i = this.indexOf(e.target);
    if (i < 0) return;
    this.root.focus({ preventScroll: true });
    if (e.shiftKey || this.extendNext) { this.extendNext = false; this.moveTo(i, true, false); }
    else { this.moveTo(i, false, false); this.dragging = true; this.moved = false; }
    e.preventDefault();
  }

  onOver(e) {
    if (!this.dragging) return;
    const i = this.indexOf(e.target);
    if (i >= 0 && i !== this.cursor) { this.moved = true; this.moveTo(i, true); }
  }

  onUp() {
    if (!this.dragging) return;
    this.dragging = false;
    if (!this.moved) this.player.seek(this.words[this.cursor].start);
  }

  onKey(e) {
    if (e.target.closest(".w-edit")) return;
    const mod = e.ctrlKey || e.metaKey;
    if (mod || e.altKey) return;
    switch (e.key) {
      case "ArrowRight": this.moveTo(this.cursor + 1, e.shiftKey); break;
      case "ArrowLeft": this.moveTo(this.cursor - 1, e.shiftKey); break;
      case "ArrowDown": this.moveTo(this.lineStep(1), e.shiftKey); break;
      case "ArrowUp": this.moveTo(this.lineStep(-1), e.shiftKey); break;
      case "Home": this.moveTo(0, e.shiftKey); break;
      case "End": this.moveTo(this.words.length - 1, e.shiftKey); break;
      case "Delete": case "Backspace": this.store.change((s) => toggleDeleted(s, this.selection())); break;
      case "Enter": this.edit(this.cursor); break;
      case "Escape": this.anchor = this.cursor; this.paint(); break;
      case " ": this.player.seek(this.words[this.cursor].start); this.player.toggle(); break;
      default: return;
    }
    e.preventDefault();
  }

  /** The word on the next or previous visual line nearest the cursor's column, found by position so it matches what the user sees. */
  lineStep(dir) {
    const rects = this.spans.map((span) => span.getBoundingClientRect());
    const here = rects[this.cursor];
    const sameLine = (r, ref) => Math.abs(r.top - ref.top) < here.height * 0.6;
    let i = this.cursor + dir;
    while (rects[i] && sameLine(rects[i], here)) i += dir;
    if (!rects[i]) return this.cursor;
    const line = rects[i];
    let best = i;
    for (let j = i; rects[j] && sameLine(rects[j], line); j += dir) {
      if (Math.abs(rects[j].left - here.left) < Math.abs(rects[best].left - here.left)) best = j;
    }
    return best;
  }

  edit(i) {
    const span = this.spans[i];
    const { words } = this.store.project;
    const input = document.createElement("input");
    input.className = "w-edit";
    input.value = wordText(words, this.store.state, i);
    input.size = Math.max(4, input.value.length + 1);
    input.setAttribute("aria-label", t("tx.editLabel"));
    span.textContent = "";
    span.append(input);
    input.focus();
    input.select();
    const finish = (commit) => {
      if (!input.isConnected) return;
      const value = input.value;
      input.remove();
      if (commit) this.store.change((s) => setEdit(s, i, value, words[i].text), `edit${i}`);
      this.paint();
      this.root.focus({ preventScroll: true });
    };
    input.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.key === "Enter") finish(true);
      else if (e.key === "Escape") finish(false);
    });
    input.addEventListener("blur", () => finish(true));
    input.addEventListener("input", () => { input.size = Math.max(4, input.value.length + 1); });
  }

  /** Mark the word being spoken. */
  setNow(i, follow) {
    if (i === this.now) return;
    this.spans[this.now]?.classList.remove("now");
    this.now = i;
    const span = this.spans[i];
    if (!span) return;
    span.classList.add("now");
    if (follow) this.reveal(i, true);
  }

  reveal(i, center = false) {
    const span = this.spans[i];
    if (!span) return;
    const box = this.root.getBoundingClientRect();
    const r = span.getBoundingClientRect();
    if (matchMedia("(max-width: 960px)").matches) { this.revealInPage(r, center); return; }
    if (r.top < box.top + 24 || r.bottom > box.bottom - 24) {
      this.root.scrollTop += r.top - box.top - (center ? box.height / 3 : 40);
    }
  }

  /** On a narrow screen the transcript grows with the page and the stage sticks above it, so scroll the window to a spot below the stage. */
  revealInPage(r, center) {
    const stage = document.querySelector(".stage")?.getBoundingClientRect().bottom ?? 0;
    const top = stage + 24;
    const bottom = window.innerHeight - 24;
    if (r.top < top || r.bottom > bottom) {
      window.scrollBy({ top: r.top - top - (center ? (bottom - top) / 3 : 0), behavior: "auto" });
    }
  }
}
