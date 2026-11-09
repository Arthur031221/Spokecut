// Caption chunking for the live preview and the in-browser SRT and VTT downloads.
// This repeats src/spokecut/captions.py. tests/js/captions.test.mjs checks both against tests/golden.

import { EPS, toOutput, wordText } from "./timeline.js";

const SENTENCE_END = ["。", "！", "？", ".", "!", "?", "…"];
const CLAUSE_END = ["，", "、", ",", ";", ":", "；", "："];
const NO_SPACE = new Set(["zh", "ja", "ko"]);

const endsWith = (text, marks) => marks.some((m) => text.endsWith(m));

function segAt(segs, t) {
  return segs.find((s) => s.srcStart - EPS <= t && t <= s.srcEnd + EPS);
}

/** Words that survive the edit, moved onto the output timeline. Each is { text, start, end, index }. */
export function keptWords(words, state, segs) {
  const deleted = new Set(state.deleted);
  const out = [];
  words.forEach((w, i) => {
    if (deleted.has(i)) return;
    const mid = (w.start + w.end) / 2;
    const seg = segAt(segs, mid);
    if (!seg) return;
    const start = toOutput(segs, Math.max(w.start, seg.srcStart));
    const end = toOutput(segs, Math.min(w.end, seg.srcEnd));
    const text = wordText(words, state, i);
    if (text) out.push({ text, start, end: Math.max(end, start + 0.04), index: i });
  });
  return out;
}

export function chunkWords(words, language, maxChars = 32, maxWords = 7, maxGap = 0.8) {
  const sep = NO_SPACE.has(language) ? "" : " ";
  const chunks = [];
  let cur = [];
  const flush = () => { chunks.push({ words: cur, sep }); cur = []; };
  for (const w of words) {
    if (cur.length) {
      const length = [...cur, w].map((x) => x.text).join(sep).length;
      const gap = w.start - cur[cur.length - 1].end;
      const full = cur.length >= maxWords || length > maxChars;
      const last = cur[cur.length - 1].text;
      if (gap > maxGap || full || endsWith(last, SENTENCE_END)) flush();
      else if (endsWith(last, CLAUSE_END) && length > maxChars * 0.6) flush();
    }
    cur.push(w);
  }
  if (cur.length) chunks.push({ words: cur, sep });
  return chunks.map((c) => ({ ...c, start: c.words[0].start, end: c.words[c.words.length - 1].end, text: c.words.map((x) => x.text).join(c.sep) }));
}

export function maxCharsFor(width, height) {
  return height > width ? 20 : 34;
}

function stamp(t, comma) {
  let ms = Math.round(t * 1000);
  const h = Math.floor(ms / 3600000); ms -= h * 3600000;
  const m = Math.floor(ms / 60000); ms -= m * 60000;
  const s = Math.floor(ms / 1000); ms -= s * 1000;
  const p = (n, w = 2) => String(n).padStart(w, "0");
  return `${p(h)}:${p(m)}:${p(s)}${comma ? "," : "."}${p(ms, 3)}`;
}

export function toSrt(chunks) {
  return chunks.map((c, n) => `${n + 1}\n${stamp(c.start, true)} --> ${stamp(c.end, true)}\n${c.text}\n`).join("\n");
}

export function toVtt(chunks) {
  return ["WEBVTT\n", ...chunks.map((c) => `${stamp(c.start, false)} --> ${stamp(c.end, false)}\n${c.text}\n`)].join("\n");
}
