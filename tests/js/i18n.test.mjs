import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";

import { LOCALES, format, pickLocale } from "../../web/js/i18n.js";

const dir = new URL("../../web/locales/", import.meta.url);
const load = (code) => JSON.parse(readFileSync(new URL(`${code}.json`, dir), "utf8"));
const placeholders = (s) => (s.match(/\{\w+\}/g) || []).sort().join(",");
const en = load("en");

test("every listed locale has a file and every file is listed", () => {
  const files = readdirSync(dir).map((f) => f.replace(/\.json$/, "")).sort();
  assert.deepEqual(files, LOCALES.map(([c]) => c).sort());
});

for (const [code] of LOCALES.filter(([c]) => c !== "en")) {
  test(`${code} has exactly the English keys and placeholders`, () => {
    const messages = load(code);
    assert.deepEqual(Object.keys(messages).sort(), Object.keys(en).sort());
    for (const key of Object.keys(en)) {
      assert.equal(placeholders(messages[key]), placeholders(en[key]), `${code}:${key}`);
      assert.ok(messages[key].trim().length > 0, `${code}:${key} is empty`);
    }
  });
}

test("every key used by the HTML and the modules exists in English", () => {
  const sources = ["index.html", ...readdirSync(new URL("../../web/js/", import.meta.url)).map((f) => `js/${f}`)];
  const used = new Set();
  for (const file of sources) {
    const text = readFileSync(new URL(`../../web/${file}`, import.meta.url), "utf8");
    for (const m of text.matchAll(/data-i18n(?:-[a-z]+)?="([\w.]+)"/g)) used.add(m[1]);
    for (const m of text.matchAll(/\bt\(\s*"([\w.]+)"/g)) used.add(m[1]);
  }
  for (const key of used) assert.ok(key in en, `missing key ${key}`);
});

test("pickLocale maps browser tags to the nearest locale", () => {
  assert.equal(pickLocale(["zh-Hant-TW"]), "zh-TW");
  assert.equal(pickLocale(["zh-HK"]), "zh-TW");
  assert.equal(pickLocale(["zh"]), "zh-CN");
  assert.equal(pickLocale(["pt-PT"]), "pt-BR");
  assert.equal(pickLocale(["de-AT", "en"]), "de");
  assert.equal(pickLocale(["sv"]), "en");
});

test("format fills placeholders and leaves unknown ones visible", () => {
  assert.equal(format("Cut {n} pauses", { n: 3 }), "Cut 3 pauses");
  assert.equal(format("{a} and {b}", { a: 1 }), "1 and {b}");
});
