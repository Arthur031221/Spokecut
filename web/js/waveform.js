// The waveform overview: peaks from the project file, cut regions in coral, a playhead, click and drag to seek.

export class Waveform {
  constructor(canvas, store, onSeek) {
    this.canvas = canvas;
    this.store = store;
    this.onSeek = onSeek;
    this.time = 0;
    this.cuts = [];
    this.columns = null;
    this.width = 0;
    this.height = 0;
    this.scale = 1;
    const seekFrom = (e) => {
      const r = canvas.getBoundingClientRect();
      const frac = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
      onSeek(frac * store.project.media.duration);
    };
    canvas.addEventListener("pointerdown", (e) => {
      canvas.setPointerCapture(e.pointerId);
      seekFrom(e);
      canvas.onpointermove = seekFrom;
    });
    const release = () => { canvas.onpointermove = null; };
    canvas.addEventListener("pointerup", release);
    canvas.addEventListener("pointercancel", release);
    new ResizeObserver(() => this.resize()).observe(canvas);
  }

  resize() {
    const r = this.canvas.getBoundingClientRect();
    this.scale = window.devicePixelRatio || 1;
    this.width = Math.round(r.width * this.scale);
    this.height = Math.round(r.height * this.scale);
    this.canvas.width = this.width;
    this.canvas.height = this.height;
    this.columns = null;
    this.draw();
  }

  /** Reduce the peaks to one value per pixel column. Only redone when the width or the project changes. */
  buildColumns() {
    const { peaks, media } = this.store.project;
    const data = peaks?.data ?? [];
    this.columns = new Float32Array(this.width);
    if (!data.length || !this.width) return;
    const perColumn = data.length / this.width;
    for (let x = 0; x < this.width; x++) {
      const from = Math.floor(x * perColumn);
      const to = Math.max(from + 1, Math.floor((x + 1) * perColumn));
      let top = 0;
      for (let i = from; i < to && i < data.length; i++) top = Math.max(top, data[i]);
      this.columns[x] = top / 100;
    }
    this.duration = media.duration;
  }

  setCuts(cuts) { this.cuts = cuts; this.draw(); }

  setTime(t) { this.time = t; this.draw(); }

  reset() { this.columns = null; this.draw(); }

  draw() {
    const ctx = this.canvas.getContext("2d");
    if (!ctx || !this.store.project || !this.width) return;
    if (!this.columns) this.buildColumns();
    const css = getComputedStyle(document.documentElement);
    const accent = css.getPropertyValue("--accent").trim();
    const cut = css.getPropertyValue("--cut").trim();
    const muted = css.getPropertyValue("--muted").trim();
    const { duration } = this.store.project.media;
    const px = (t) => (t / duration) * this.width;
    const mid = this.height / 2;
    ctx.clearRect(0, 0, this.width, this.height);
    ctx.fillStyle = accent;
    ctx.globalAlpha = 0.9;
    for (let x = 0; x < this.width; x++) {
      const h = Math.max(1, this.columns[x] * (this.height - 8));
      ctx.fillRect(x, mid - h / 2, 1, h);
    }
    ctx.globalAlpha = 1;
    for (const [a, b] of this.cuts) {
      ctx.fillStyle = cut;
      ctx.globalAlpha = 0.28;
      ctx.fillRect(px(a), 0, Math.max(1, px(b) - px(a)), this.height);
      ctx.globalAlpha = 1;
      ctx.fillRect(px(a), 0, this.scale, this.height);
    }
    ctx.fillStyle = muted;
    ctx.globalAlpha = 0.4;
    ctx.fillRect(0, mid, this.width, 1);
    ctx.globalAlpha = 1;
    ctx.fillStyle = css.getPropertyValue("--text").trim();
    ctx.fillRect(Math.round(px(this.time)), 0, 2 * this.scale, this.height);
  }
}
