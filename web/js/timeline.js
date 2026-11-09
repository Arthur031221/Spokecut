// Edit state to cut ranges, kept ranges and the source to output time map.
// This repeats src/spokecut/timeline.py. tests/js/timeline.test.mjs checks both against tests/golden/timeline.json.

export const EPS = 1e-6;

/** Python's round(): halves go to the even neighbour, so frame snapping agrees with the exporter. */
export function pyRound(x) {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

export function pauseCut(prevEnd, nextStart, keep) {
  if (nextStart - prevEnd <= keep + EPS) return null;
  const half = keep / 2;
  return [prevEnd + half, nextStart - half];
}

/** Gap indices g (between word g-1 and word g) whose silence lasts at least `threshold` seconds. */
export function findPauses(words, threshold) {
  const out = [];
  for (let g = 1; g < words.length; g++) {
    if (words[g].start - words[g - 1].end >= threshold - EPS) out.push(g);
  }
  return out;
}

export function merge(ranges) {
  const out = [];
  const sorted = [...ranges].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  for (const [s, e] of sorted) {
    if (e - s <= EPS) continue;
    const last = out[out.length - 1];
    if (last && s <= last[1] + EPS) last[1] = Math.max(last[1], e);
    else out.push([s, e]);
  }
  return out;
}

export function cutRanges(words, snaps, deleted, cutGaps, keep, duration) {
  const n = words.length;
  const ranges = [];
  const marked = [...new Set(deleted)].filter((i) => i >= 0 && i < n).sort((a, b) => a - b);
  let i = 0;
  while (i < marked.length) {
    let j = i;
    while (j + 1 < marked.length && marked[j + 1] === marked[j] + 1) j++;
    const first = marked[i];
    const last = marked[j];
    ranges.push([first === 0 ? 0 : snaps[first], last === n - 1 ? duration : snaps[last + 1]]);
    i = j + 1;
  }
  for (const g of [...new Set(cutGaps)].sort((a, b) => a - b)) {
    if (g >= 1 && g < n) {
      const cut = pauseCut(words[g - 1].end, words[g].start, keep);
      if (cut) ranges.push(cut);
    }
  }
  return merge(ranges.map(([s, e]) => [Math.max(0, s), Math.min(duration, e)]));
}

export function snapToFrames(ranges, fps) {
  if (fps <= 0) return ranges;
  const out = [];
  for (const [s, e] of ranges) {
    const fs = pyRound(s * fps);
    const fe = pyRound(e * fps);
    if (fe > fs) out.push([fs / fps, fe / fps]);
  }
  return merge(out);
}

export function keepRanges(cuts, duration, fps = 0) {
  let keeps = [];
  let pos = 0;
  for (const [s, e] of cuts) {
    if (s - pos > EPS) keeps.push([pos, s]);
    pos = Math.max(pos, e);
  }
  if (duration - pos > EPS) keeps.push([pos, duration]);
  if (fps > 0) keeps = keeps.filter(([s, e]) => pyRound(e * fps) > pyRound(s * fps));
  return keeps;
}

export function segments(keeps) {
  const out = [];
  let pos = 0;
  for (const [s, e] of keeps) {
    out.push({ srcStart: s, srcEnd: e, outStart: pos, outEnd: pos + (e - s) });
    pos += e - s;
  }
  return out;
}

export function outputDuration(keeps) {
  return keeps.reduce((sum, [s, e]) => sum + (e - s), 0);
}

/** Output time of source time `t`, or null when `t` was cut. */
export function toOutput(segs, t) {
  for (const seg of segs) {
    if (seg.srcStart - EPS <= t && t <= seg.srcEnd + EPS) {
      return seg.outStart + (Math.min(Math.max(t, seg.srcStart), seg.srcEnd) - seg.srcStart);
    }
  }
  return null;
}

/** Source time at output time `t`. */
export function toSource(segs, t) {
  for (const seg of segs) {
    if (t <= seg.outEnd + EPS) return seg.srcStart + Math.max(0, t - seg.outStart);
  }
  return segs.length ? segs[segs.length - 1].srcEnd : 0;
}

/** Frame-snapped keep ranges and segments for a project and edit state. */
export function plan(project, state) {
  const { media, words, snaps } = project;
  const fps = media.hasVideo ? media.fps : 0;
  let cuts = cutRanges(words, snaps, state.deleted, state.cutGaps, Number(state.pause.keep), media.duration);
  cuts = snapToFrames(cuts, fps);
  const keeps = keepRanges(cuts, media.duration, fps);
  return { cuts, keeps, segs: segments(keeps) };
}

export function wordText(words, state, i) {
  const edited = state.edits[i];
  return (edited !== undefined ? edited : words[i].text).trim();
}
