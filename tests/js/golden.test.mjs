import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { chunkWords, keptWords, toSrt, toVtt } from "../../web/js/captions.js";
import { findPauses, outputDuration, plan, pyRound, toOutput } from "../../web/js/timeline.js";

const golden = (name) => JSON.parse(readFileSync(new URL(`../golden/${name}.json`, import.meta.url), "utf8"));
const close = (a, b, msg) => assert.ok(Math.abs(a - b) < 1e-5, `${msg}: ${a} vs ${b}`);

test("pyRound rounds halves to even like Python", () => {
  assert.deepEqual([0.5, 1.5, 2.5, 3.5, -0.5, 2.4, 2.6].map(pyRound), [0, 2, 2, 4, 0, 2, 3]);
});

for (const c of golden("timeline")) {
  test(`timeline: ${c.name}`, () => {
    const project = {
      media: { duration: c.duration, fps: c.fps, hasVideo: c.fps > 0 },
      words: c.words.map(([text, start, end]) => ({ text, start, end })),
      snaps: c.snaps,
    };
    const state = { deleted: c.deleted, cutGaps: c.cutGaps, edits: Object.fromEntries(Object.entries(c.edits)), pause: { keep: c.keep } };
    const { keeps, segs } = plan(project, state);
    assert.equal(keeps.length, c.keeps.length, "number of keeps");
    keeps.forEach(([s, e], i) => { close(s, c.keeps[i][0], "keep start"); close(e, c.keeps[i][1], "keep end"); });
    close(outputDuration(keeps), c.outputDuration, "output duration");
    assert.deepEqual(findPauses(project.words, 0.7), c.pauses);
    for (const [t, expected] of c.probes) {
      const got = toOutput(segs, t);
      if (expected === null) assert.equal(got, null, `probe ${t}`);
      else close(got, expected, `probe ${t}`);
    }
    const kept = keptWords(project.words, state, segs);
    assert.equal(kept.length, c.kept.length, "kept word count");
    kept.forEach((w, i) => {
      assert.equal(w.text, c.kept[i][0]);
      close(w.start, c.kept[i][1], "kept start");
      close(w.end, c.kept[i][2], "kept end");
    });
  });
}

for (const c of golden("captions")) {
  test(`captions: ${c.name}`, () => {
    const words = c.words.map(([text, start, end]) => ({ text, start, end }));
    const chunks = chunkWords(words, c.language, c.maxChars, c.maxWords, c.maxGap);
    assert.deepEqual(chunks.map((k) => k.words.map((w) => w.text)), c.chunks);
    assert.deepEqual(chunks.map((k) => k.text), c.text);
  });
}

test("srt and vtt use the same timestamps as the exporter", () => {
  const chunks = chunkWords([{ text: "Hi", start: 3661.5, end: 3662.25 }], "en");
  assert.match(toSrt(chunks), /01:01:01,500 --> 01:01:02,250/);
  assert.ok(toVtt(chunks).startsWith("WEBVTT"));
  assert.match(toVtt(chunks), /01:01:01\.500 --> 01:01:02\.250/);
});
