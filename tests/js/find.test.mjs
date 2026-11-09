import assert from "node:assert/strict";
import test from "node:test";

import { findMatches, normalize } from "../../web/js/find.js";

const words = (...texts) => texts.map((text, i) => ({ text: ` ${text}`, start: i, end: i + 0.5 }));
const none = { edits: {} };

test("normalize drops case, punctuation and spaces", () => {
  assert.equal(normalize(" Basically, "), "basically");
  assert.equal(normalize("don't"), "dont");
  assert.equal(normalize("..."), "");
});

test("finds every whole word, ignoring case and punctuation", () => {
  const w = words("So", "I", "said,", "so.", "Something", "so");
  assert.deepEqual(findMatches(w, none, "so"), [[0], [3], [5]]);
});

test("a match never starts or ends inside a word", () => {
  const w = words("basically", "basic", "a", "basics");
  assert.deepEqual(findMatches(w, none, "basic"), [[1]]);
  assert.deepEqual(findMatches(w, none, "sic"), []);
});

test("a phrase matches across words and ignores spacing in the query", () => {
  const w = words("so", "far", "so", "good", "so", "far");
  assert.deepEqual(findMatches(w, none, "so far"), [[0, 1], [4, 5]]);
  assert.deepEqual(findMatches(w, none, "  SO   far "), [[0, 1], [4, 5]]);
});

test("characters of a language without spaces match across single character words", () => {
  const w = words("我", "覺", "得", "你", "好", "你", "好");
  assert.deepEqual(findMatches(w, none, "你好"), [[3, 4], [5, 6]]);
  assert.deepEqual(findMatches(w, none, "覺得"), [[1, 2]]);
});

test("matches do not overlap", () => {
  const w = words("a", "a", "a");
  assert.deepEqual(findMatches(w, none, "a a"), [[0, 1]]);
});

test("an edited word is found by its fix", () => {
  const w = words("kubernetes", "is", "hard");
  assert.deepEqual(findMatches(w, { edits: { 0: " Kubernetes" } }, "kubernetes"), [[0]]);
  assert.deepEqual(findMatches(w, { edits: { 0: " k8s" } }, "kubernetes"), []);
});

test("an empty or punctuation only query finds nothing", () => {
  const w = words("a", "b");
  assert.deepEqual(findMatches(w, none, ""), []);
  assert.deepEqual(findMatches(w, none, " ?! "), []);
});

test("words that are only punctuation are skipped", () => {
  const w = words("so", "-", "far");
  assert.deepEqual(findMatches(w, none, "so far"), [[0, 1, 2]]);
});
