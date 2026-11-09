// Find a word or phrase in the transcript. Pure functions, so the matching is testable without a browser.

import { wordText } from "./timeline.js";

/** Lower case with everything but letters and digits removed, so "Basically," matches "basically". */
export function normalize(text) {
  return text.toLowerCase().normalize("NFKC").replace(/[^\p{L}\p{N}]+/gu, "");
}

/**
 * Runs of word indices that spell `query`. A match starts at the start of a word and ends at the end of one, and
 * spaces and punctuation in the query are ignored, so "so far" finds the two words and "你好" finds two single
 * character words. Matches never overlap. The text is the edited text, so a fixed caption word is found by its fix.
 */
export function findMatches(words, state, query) {
  const needle = normalize(query);
  if (!needle) return [];
  let flat = "";
  const owner = [];
  words.forEach((_, i) => {
    const piece = normalize(wordText(words, state, i));
    flat += piece;
    for (let k = 0; k < piece.length; k++) owner.push(i);
  });
  const runs = [];
  let from = 0;
  for (;;) {
    const at = flat.indexOf(needle, from);
    if (at < 0) break;
    const last = at + needle.length - 1;
    const startsWord = at === 0 || owner[at] !== owner[at - 1];
    const endsWord = last === flat.length - 1 || owner[last] !== owner[last + 1];
    if (startsWord && endsWord) {
      runs.push(Array.from({ length: owner[last] - owner[at] + 1 }, (_, k) => owner[at] + k));
      from = at + needle.length;
    } else {
      from = at + 1;
    }
  }
  return runs;
}
