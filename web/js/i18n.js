// Tiny i18n layer: JSON locale files, English fallback, data-i18n attributes in the HTML.

export const LOCALES = [
  ["en", "English"], ["zh-TW", "繁體中文"], ["zh-CN", "简体中文"], ["ja", "日本語"], ["ko", "한국어"],
  ["es", "Español"], ["fr", "Français"], ["de", "Deutsch"], ["pt-BR", "Português (Brasil)"],
];

let messages = {};
let fallback = {};
let current = "en";
const listeners = new Set();

export function onLocale(fn) { listeners.add(fn); }

/** Pick the best supported locale for a list of BCP 47 tags. */
export function pickLocale(tags) {
  const codes = LOCALES.map(([code]) => code);
  for (const tag of tags) {
    const exact = codes.find((c) => c.toLowerCase() === tag.toLowerCase());
    if (exact) return exact;
    const lang = tag.toLowerCase().split("-")[0];
    if (lang === "zh") return /tw|hk|mo|hant/i.test(tag) ? "zh-TW" : "zh-CN";
    if (lang === "pt") return "pt-BR";
    const base = codes.find((c) => c.toLowerCase() === lang);
    if (base) return base;
  }
  return "en";
}

export function format(template, vars = {}) {
  return template.replace(/\{(\w+)\}/g, (_, key) => (key in vars ? String(vars[key]) : `{${key}}`));
}

export function t(key, vars) {
  const template = messages[key] ?? fallback[key] ?? key;
  return format(template, vars);
}

export function locale() { return current; }

async function load(code) {
  const res = await fetch(new URL(`../locales/${code}.json`, import.meta.url));
  if (!res.ok) throw new Error(`missing locale ${code}`);
  return res.json();
}

export async function setLocale(code) {
  if (!Object.keys(fallback).length) fallback = await load("en");
  messages = code === "en" ? fallback : await load(code);
  current = code;
  document.documentElement.lang = code;
  apply(document);
  for (const fn of listeners) fn(code);
  localStorage.setItem("spokecut.lang", code);
}

/** Translate every marked element under root. Elements whose text is built by code are refreshed by their own module. */
export function apply(root) {
  for (const el of root.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of root.querySelectorAll("[data-i18n-title]")) {
    const text = t(el.dataset.i18nTitle);
    el.title = text;
    el.setAttribute("aria-label", text);
  }
  for (const el of root.querySelectorAll("[data-i18n-placeholder]")) el.placeholder = t(el.dataset.i18nPlaceholder);
  for (const el of root.querySelectorAll("[data-i18n-aria]")) el.setAttribute("aria-label", t(el.dataset.i18nAria));
}

export async function initLocale() {
  const saved = localStorage.getItem("spokecut.lang");
  const wanted = new URLSearchParams(location.search).get("lang");
  const code = [wanted, saved].find((c) => c && LOCALES.some(([l]) => l === c)) || pickLocale(navigator.languages || ["en"]);
  await setLocale(code);
  return code;
}

const INSTALL_URL = "https://github.com/Arthur031221/Spokecut#install";

/** The demo cannot transcribe or render, so it points at the install steps. */
export function installLink() {
  const a = document.createElement("a");
  a.href = INSTALL_URL;
  a.rel = "noopener";
  a.textContent = t("demo.install");
  return a;
}
