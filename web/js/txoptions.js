// Language, model and verbatim choices for a new transcription. One set of values, shown wherever the page asks for them.

import { t } from "./i18n.js";

export const LANGUAGES = [
  ["en", "English"], ["zh", "中文"], ["ja", "日本語"], ["ko", "한국어"], ["es", "Español"], ["fr", "Français"],
  ["de", "Deutsch"], ["pt", "Português"], ["it", "Italiano"], ["nl", "Nederlands"], ["ru", "Русский"], ["uk", "Українська"],
  ["pl", "Polski"], ["tr", "Türkçe"], ["ar", "العربية"], ["hi", "हिन्दी"], ["id", "Indonesia"], ["vi", "Tiếng Việt"], ["th", "ไทย"],
];
// Sizes are what the first run downloads.
export const MODELS = [
  ["tiny", "75 MB"], ["base", "142 MB"], ["small", "464 MB"], ["medium", "1.5 GB"], ["large-v3-turbo", "1.6 GB"], ["large-v3", "3.1 GB"],
];

const KEY = "spokecut.transcribe";
const BLANK = { model: "", language: "", verbatim: false };

function restore() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    return {
      model: MODELS.some(([m]) => m === saved?.model) ? saved.model : "",
      language: LANGUAGES.some(([l]) => l === saved?.language) ? saved.language : "",
      verbatim: saved?.verbatim === true,
    };
  } catch {
    return { ...BLANK };
  }
}

export class TxOptions {
  constructor() {
    this.value = restore();
    this.views = [];
  }

  /** Fill `container` with the three fields, cloned from the page template, and keep them in step with every other copy. */
  mount(container, template) {
    const root = template.content.cloneNode(true);
    const view = {
      language: root.querySelector(".tx-language"),
      model: root.querySelector(".tx-model"),
      verbatim: root.querySelector(".tx-verbatim"),
    };
    view.language.addEventListener("change", () => this.set({ language: view.language.value }));
    view.model.addEventListener("change", () => this.set({ model: view.model.value }));
    view.verbatim.addEventListener("change", () => this.set({ verbatim: view.verbatim.checked }));
    container.append(root);
    this.views.push(view);
    this.paint();
  }

  set(patch) {
    this.value = { ...this.value, ...patch };
    try { localStorage.setItem(KEY, JSON.stringify(this.value)); } catch { /* private mode: the choice lasts until reload */ }
    this.paint();
  }

  /** Rebuild the option labels, which are translated, and show the current choice. */
  paint() {
    for (const view of this.views) {
      const option = (value, text) => Object.assign(document.createElement("option"), { value, textContent: text });
      view.language.replaceChildren(option("", t("opt.auto")), ...LANGUAGES.map(([code, name]) => option(code, name)));
      view.model.replaceChildren(option("", t("opt.modelDefault")), ...MODELS.map(([name, size]) => option(name, `${name} (${size})`)));
      view.language.value = this.value.language;
      view.model.value = this.value.model;
      view.verbatim.checked = this.value.verbatim;
    }
  }

  /** The request fields. Empty choices are left out so the server uses its own defaults. */
  request() {
    const { model, language, verbatim } = this.value;
    return { ...(model && { model }), ...(language && { language }), verbatim };
  }
}
