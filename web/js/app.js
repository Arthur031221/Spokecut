// Boot, views and wiring. The other modules know nothing about each other; this file connects them.

import { detect } from "./api.js";
import { LOCALES, apply, initLocale, installLink, onLocale, setLocale, t, locale } from "./i18n.js";
import { CaptionPanel, Cleanup, ExportPanel } from "./panels.js";
import { Player, clock } from "./player.js";
import { Store } from "./store.js";
import { Transcript } from "./transcript.js";
import { TxOptions } from "./txoptions.js";
import { outputDuration } from "./timeline.js";
import { Waveform } from "./waveform.js";

const $ = (id) => document.getElementById(id);
const VIEWS = ["empty", "processing", "editor"];
const SAVE_DELAY = 400;

const store = new Store();
const txOptions = new TxOptions();
let api;
let current = null; // { id, name }
let saveTimer = 0;
let saving = Promise.resolve();
let dirty = false;

function show(view) {
  for (const v of VIEWS) $(v).hidden = v !== view;
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 4000);
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("spokecut.theme", theme);
  wave.draw();
}

/* Saving: edits are written a moment after the last change, and always before an export. */
function setSaveState(key) { $("save-state").dataset.key = key; $("save-state").textContent = key ? t(key) : ""; }

function scheduleSave() {
  dirty = true;
  setSaveState("save.saving");
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flush, SAVE_DELAY);
}

function flush() {
  clearTimeout(saveTimer);
  if (!dirty || !current) return saving;
  dirty = false;
  const body = store.state;
  saving = saving
    .then(() => api.putState(current.id, body))
    .then(() => { if (!dirty) setSaveState("save.saved"); })
    .catch((err) => { dirty = true; setSaveState("save.failed"); toast(t("err.save", { message: err.message })); });
  return saving;
}

/* Elements and modules */
const player = new Player(
  { video: $("video"), play: $("play"), speed: $("speed"), clock: $("clock"), captionLayer: $("caption-layer"), audioOnly: $("audio-only") },
  store,
  {
    onTime(time, index) {
      wave.setTime(time);
      transcript.setNow(index, follow);
    },
    onPlayState(playing) {
      $("icon-play").hidden = playing;
      $("icon-pause").hidden = !playing;
      $("play").setAttribute("aria-label", t(playing ? "player.pause" : "player.play"));
    },
  },
);
const wave = new Waveform($("wave"), store, (time) => player.seek(time));
const transcript = new Transcript($("transcript"), store, player);
transcript.bindBar($("sel-cut"), $("sel-extend"));
const cleanup = new Cleanup(store, transcript, player);
const captionPanel = new CaptionPanel(store);
let exportPanel;
let follow = true;

store.subscribe((_state, reason) => {
  if (reason === "load") return;
  transcript.paint();
  paint();
  scheduleSave();
});

function paint() {
  cleanup.paint();
  captionPanel.paint();
  exportPanel?.paint();
  wave.setCuts(player.plan?.cuts ?? []);
  summary();
  $("undo").disabled = !store.canUndo;
  $("redo").disabled = !store.canRedo;
}

function summary() {
  if (!player.plan) return;
  const total = store.project.media.duration;
  const edited = outputDuration(player.plan.keeps);
  $("sum-original").textContent = clock(total);
  $("sum-edited").textContent = clock(edited);
  $("sum-removed").textContent = clock(total - edited);
}

/* Opening a project */
function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function openProject(id) {
  show("processing");
  $("proc-error").hidden = true;
  $("proc-back").hidden = true;
  let info = await api.get(id);
  while (info.status === "analyzing" || info.status === "new") {
    const job = info.job;
    const pct = job ? Math.round(job.progress * 100) : 0;
    $("proc-title").textContent = t("proc.title", { name: info.name });
    $("proc-stage").textContent = job ? t(`stage.${job.stage}`, { pct }) : t("stage.queued");
    $("proc-bar").style.width = `${pct}%`;
    await sleep(700);
    info = await api.get(id);
  }
  if (info.status === "error") {
    $("proc-title").textContent = info.name;
    $("proc-error").textContent = t("err.analyze", { message: info.error });
    $("proc-error").hidden = false;
    $("proc-back").hidden = false;
    return;
  }
  current = { id: info.id, name: info.name };
  store.load(info.project);
  player.load(api.mediaUrl(id), info.project.media.hasVideo);
  transcript.build();
  cleanup.build();
  if (exportPanel) { exportPanel.id = id; exportPanel.build(); }
  player.refresh();
  paint();
  $("transcript").scrollTop = 0;
  show("editor");
  history.replaceState(null, "", api.mode === "server" ? `#p=${id}` : location.hash);
  setSaveState("");
  document.title = `${info.name} - Spokecut`;
}

async function openPath(path) {
  const info = await api.open(path, txOptions.request());
  await refreshProjects(info.id);
  await openProject(info.id);
}

async function uploadFile(file) {
  show("processing");
  $("proc-error").hidden = true;
  $("proc-back").hidden = true;
  $("proc-title").textContent = t("proc.uploading", { name: file.name });
  $("proc-stage").textContent = "";
  try {
    const info = await api.upload(file, (f) => {
      $("proc-bar").style.width = `${Math.round(f * 100)}%`;
      $("proc-stage").textContent = `${Math.round(f * 100)}%`;
    }, txOptions.request());
    await refreshProjects(info.id);
    await openProject(info.id);
  } catch (err) {
    show("empty");
    fail(t("err.upload", { message: err.message }));
  }
}

function fail(message) {
  const el = $("empty-error");
  el.textContent = message;
  el.hidden = !message;
}

async function refreshProjects(selected) {
  if (api.mode !== "server") return;
  const list = await api.list();
  const select = $("project-select");
  select.replaceChildren(...list.map((p) => Object.assign(document.createElement("option"), { value: p.id, textContent: p.name })));
  if (selected) select.value = selected;
  $("project-picker").hidden = list.length < 2;
}

/** Transcribe the open video again with the options in the panel. A failure leaves the old transcript and edit as they were. */
async function retranscribe() {
  if (!current) return;
  const { id } = current;
  $("retx-start").disabled = true;
  try {
    await flush();
    const job = await api.analyze(id, txOptions.request());
    let info = await api.get(id);
    while (info.status === "analyzing" || info.job?.id === job.id && ["queued", "running"].includes(info.job.status)) {
      show("processing");
      $("proc-error").hidden = true;
      $("proc-back").hidden = true;
      const pct = Math.round((info.job?.progress ?? 0) * 100);
      $("proc-title").textContent = t("proc.title", { name: info.name });
      $("proc-stage").textContent = info.job ? t(`stage.${info.job.stage}`, { pct }) : t("stage.queued");
      $("proc-bar").style.width = `${pct}%`;
      await sleep(700);
      info = await api.get(id);
    }
    if (info.job?.id === job.id && info.job.status === "error") toast(t("redo.failed", { message: info.job.error }));
    $("retx").open = false;
    await openProject(id);
  } catch (err) {
    toast(t("redo.failed", { message: err.message }));
    show("editor");
  } finally {
    $("retx-start").disabled = false;
  }
}

function pickFile() { $("file-input").click(); }

function wireEmpty() {
  const drop = $("drop");
  $("empty-pick").addEventListener("click", pickFile);
  $("open-file").addEventListener("click", pickFile);
  $("file-input").addEventListener("change", (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (file) uploadFile(file);
  });
  $("path-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const path = $("path-input").value.trim();
    if (!path) return;
    fail("");
    try { await openPath(path); } catch (err) { show("empty"); fail(t("err.open", { message: err.message })); }
  });
  for (const type of ["dragenter", "dragover"]) {
    window.addEventListener(type, (e) => { e.preventDefault(); drop.classList.add("over"); });
  }
  for (const type of ["dragleave", "drop"]) {
    window.addEventListener(type, (e) => { e.preventDefault(); drop.classList.remove("over"); });
  }
  window.addEventListener("drop", (e) => {
    const file = e.dataTransfer?.files?.[0];
    if (file && api.mode === "server") uploadFile(file);
  });
  $("project-select").addEventListener("change", (e) => openProject(e.target.value));
  $("proc-back").addEventListener("click", () => show("empty"));
  $("retx-start").addEventListener("click", retranscribe);
}

function wireControls() {
  const back = (fn) => () => { fn(); $("transcript").focus({ preventScroll: true }); };
  $("undo").addEventListener("click", back(() => store.undo()));
  $("redo").addEventListener("click", back(() => store.redo()));
  $("theme-toggle").addEventListener("click", () => setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light"));
  const toggle = (id, on) => {
    const el = $(id);
    el.addEventListener("click", () => {
      const next = el.getAttribute("aria-pressed") !== "true";
      el.setAttribute("aria-pressed", String(next));
      on(next);
    });
  };
  toggle("skip", (on) => player.setSkip(on));
  toggle("follow", (on) => { follow = on; });

  const tabs = [...document.querySelectorAll('[role="tab"]')];
  for (const tab of tabs) tab.addEventListener("click", () => selectTab(tab));

  window.addEventListener("keydown", (e) => {
    if (!current) return;
    const typing = e.target.matches?.("input, select, textarea");
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === "z" && !typing) { e.preventDefault(); e.shiftKey ? store.redo() : store.undo(); }
    else if (mod && e.key.toLowerCase() === "y" && !typing) { e.preventDefault(); store.redo(); }
    else if (mod && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "f") { e.preventDefault(); showTranscriptTab(); cleanup.focusFind(); }
    else if (e.key === "/" && !mod && !typing && !e.target.isContentEditable) { e.preventDefault(); showTranscriptTab(); cleanup.focusFind(); }
    else if (e.key === " " && !typing && e.target.tagName !== "BUTTON" && e.target !== $("transcript")) { e.preventDefault(); player.toggle(); }
  });
  window.addEventListener("pagehide", () => { if (dirty && current) api.putState(current.id, store.state, true); });
}

function selectTab(tab) {
  for (const other of document.querySelectorAll('[role="tab"]')) {
    const active = other === tab;
    other.setAttribute("aria-selected", String(active));
    $(other.getAttribute("aria-controls")).hidden = !active;
  }
}

function showTranscriptTab() { selectTab($("tab-transcript")); }

function fillLanguages() {
  const select = $("lang-select");
  select.replaceChildren(...LOCALES.map(([code, name]) => Object.assign(document.createElement("option"), { value: code, textContent: name })));
  select.value = locale();
  select.addEventListener("change", () => setLocale(select.value));
}

function retranslate() {
  $("lang-select").value = locale();
  txOptions.paint();
  if (store.project) { paint(); cleanup.build(); cleanup.paint(); transcript.paint(); }
  exportPanel?.paint();
  const key = $("save-state").dataset.key;
  if (key) setSaveState(key);
  const demo = $("demo-banner");
  if (api?.mode === "demo") demo.replaceChildren(t("demo.banner"), " ", installLink());
  $("play").setAttribute("aria-label", t($("video").paused ? "player.play" : "player.pause"));
}

async function main() {
  const saved = localStorage.getItem("spokecut.theme");
  document.documentElement.dataset.theme = saved || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  await initLocale();
  fillLanguages();
  onLocale(retranslate);
  wireEmpty();
  wireControls();
  api = await detect();
  exportPanel = new ExportPanel(store, api, flush, toast);
  if (api.mode === "server") {
    txOptions.mount($("empty-options"), $("tx-fields"));
    txOptions.mount($("retx-options"), $("tx-fields"));
    $("retx").hidden = false;
  } else {
    document.querySelector("#empty .options").hidden = true;
  }
  retranslate();
  apply(document);

  if (api.mode === "demo") {
    $("demo-banner").hidden = false;
    $("open-file").hidden = true;
    await openProject("demo");
    return;
  }
  if (!api.info.authorized) {
    show("empty");
    fail(t("err.auth"));
    return;
  }
  if (!api.info.ffmpeg) toast(t("err.ffmpeg"));
  const projects = await api.list();
  const wanted = new URLSearchParams(location.hash.slice(1)).get("p");
  const first = projects.find((p) => p.id === wanted) ?? projects[0];
  await refreshProjects(first?.id);
  if (first) await openProject(first.id);
  else show("empty");
}

main().catch((err) => {
  console.error(err);
  show("empty");
  fail(String(err.message || err));
});
