// The edit state with undo and redo. Every change goes through change(), so the UI has one place to listen.

const LIMIT = 200;

export class Store {
  constructor() {
    this.project = null;
    this.state = null;
    this.past = [];
    this.future = [];
    this.lastKey = null;
    this.lastAt = 0;
    this.listeners = new Set();
  }

  load(project) {
    this.project = project;
    this.state = structuredClone(project.state);
    this.past = [];
    this.future = [];
    this.lastKey = null;
    this.emit("load");
  }

  subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }

  emit(reason) { for (const fn of this.listeners) fn(this.state, reason); }

  /**
   * Apply `fn` to a copy of the state. Changes that share a `key` within a second (a slider drag, typing)
   * become one undo step.
   */
  change(fn, key = null) {
    const next = structuredClone(this.state);
    fn(next);
    if (JSON.stringify(next) === JSON.stringify(this.state)) return;
    const now = performance.now();
    const merge = key !== null && key === this.lastKey && now - this.lastAt < 1000;
    if (!merge) {
      this.past.push(this.state);
      if (this.past.length > LIMIT) this.past.shift();
    }
    this.lastKey = key;
    this.lastAt = now;
    this.future = [];
    this.state = next;
    this.emit("change");
  }

  undo() {
    if (!this.past.length) return;
    this.future.push(this.state);
    this.state = this.past.pop();
    this.lastKey = null;
    this.emit("undo");
  }

  redo() {
    if (!this.future.length) return;
    this.past.push(this.state);
    this.state = this.future.pop();
    this.lastKey = null;
    this.emit("redo");
  }

  get canUndo() { return this.past.length > 0; }
  get canRedo() { return this.future.length > 0; }
}

/** Mark or unmark words. If every word in `indices` is already deleted they come back, otherwise they all go. */
export function toggleDeleted(state, indices) {
  const set = new Set(state.deleted);
  const allGone = indices.every((i) => set.has(i));
  for (const i of indices) allGone ? set.delete(i) : set.add(i);
  state.deleted = [...set].sort((a, b) => a - b);
}

export function toggleGap(state, gap) {
  const set = new Set(state.cutGaps);
  set.has(gap) ? set.delete(gap) : set.add(gap);
  state.cutGaps = [...set].sort((a, b) => a - b);
}

export function setEdit(state, index, text, original) {
  const clean = text.trim();
  if (!clean || clean === original.trim()) delete state.edits[index];
  else state.edits[index] = clean;
}
