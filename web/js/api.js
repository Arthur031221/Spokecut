// The editor talks to one of two back ends: the local Spokecut server, or a static demo bundled with the page.
// Both return the same project shape, so the rest of the app does not care which one it has.

import { chunkWords, keptWords, maxCharsFor, toSrt, toVtt } from "./captions.js";
import { plan } from "./timeline.js";

/** Convert the sidecar JSON ({t, s, e, p} words) into the shape the editor uses. */
export function normalize(raw) {
  return {
    ...raw,
    words: raw.words.map((w) => ({ text: w.t, start: w.s, end: w.e, prob: w.p })),
    state: {
      deleted: raw.state.deleted ?? [],
      cutGaps: raw.state.cutGaps ?? [],
      edits: raw.state.edits ?? {},
      pause: raw.state.pause,
      caption: raw.state.caption,
    },
  };
}

class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function request(url, options = {}) {
  const res = await fetch(url, { credentials: "same-origin", ...options });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* body is not JSON */ }
    throw new HttpError(res.status, detail);
  }
  return res;
}

const json = (body) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export function serverApi(info) {
  return {
    mode: "server",
    info,
    list: async () => (await request("/api/projects")).json(),
    open: async (path) => (await request("/api/open", json({ path }))).json(),
    get: async (id) => {
      const body = await (await request(`/api/projects/${id}`)).json();
      if (body.project) body.project = normalize(body.project);
      return body;
    },
    putState: (id, state, keepalive = false) =>
      request(`/api/projects/${id}/state`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state), keepalive }),
    mediaUrl: (id) => `/api/projects/${id}/media`,
    exportUrl: (id, fmt) => `/api/projects/${id}/export/${fmt}`,
    render: async (id, encoder = "auto") => (await request(`/api/projects/${id}/render`, json({ encoder }))).json(),
    job: async (id) => (await request(`/api/jobs/${id}`)).json(),
    jobFileUrl: (id) => `/api/jobs/${id}/file`,
    upload(file, onProgress) {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `/api/upload?name=${encodeURIComponent(file.name)}`);
        xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
        xhr.onload = () => {
          if (xhr.status < 300) return resolve(JSON.parse(xhr.responseText));
          let detail = xhr.statusText;
          try { detail = JSON.parse(xhr.responseText).detail ?? detail; } catch { /* not JSON */ }
          reject(new HttpError(xhr.status, detail));
        };
        xhr.onerror = () => reject(new HttpError(0, "network"));
        xhr.send(file);
      });
    },
  };
}

const DEMO_KEY = "spokecut.demo.state";

/** The static GitHub Pages build: one bundled clip, edits kept in localStorage, text exports made in the browser. */
export function demoApi(base = new URL("../demo/", import.meta.url)) {
  const url = (name) => new URL(name, base).href;
  let project = null;
  return {
    mode: "demo",
    info: { formats: ["srt", "vtt", "json"] },
    list: async () => [],
    get: async () => {
      const raw = await (await request(url("project.json"))).json();
      project = normalize(raw);
      try {
        const saved = JSON.parse(localStorage.getItem(DEMO_KEY));
        if (saved && saved.deleted) project.state = saved;
      } catch { /* a corrupt entry is ignored */ }
      return { id: "demo", name: project.media.file, status: "ready", project, job: null };
    },
    putState: async (_id, state) => { localStorage.setItem(DEMO_KEY, JSON.stringify(state)); },
    resetState: () => localStorage.removeItem(DEMO_KEY),
    mediaUrl: () => url(project.media.proxy || project.media.file),
    textExport(fmt, proj, state) {
      const { segs } = plan(proj, state);
      const chunks = chunkWords(keptWords(proj.words, state, segs), proj.language, maxCharsFor(proj.media.width, proj.media.height));
      const stem = proj.media.file.replace(/\.[^.]+$/, "");
      if (fmt === "srt") return { name: `${stem}.spokecut.srt`, mime: "application/x-subrip", text: toSrt(chunks) };
      if (fmt === "vtt") return { name: `${stem}.spokecut.vtt`, mime: "text/vtt", text: toVtt(chunks) };
      const cuts = plan(proj, state).keeps.map(([start, end]) => ({ start, end }));
      return { name: `${stem}.spokecut.cuts.json`, mime: "application/json", text: JSON.stringify({ source: proj.media.file, keeps: cuts }, null, 2) };
    },
  };
}

/** Decide which back end to use. A page opened as `?demo`, or published as the static demo, gets the demo without probing for an API. */
export async function detect() {
  if (new URLSearchParams(location.search).has("demo")) return demoApi();
  if (document.querySelector('meta[name="spokecut-mode"]')?.content === "demo") return demoApi();
  try {
    const res = await fetch("/api/health", { credentials: "same-origin" });
    if (res.ok && (res.headers.get("content-type") || "").includes("json")) return serverApi(await res.json());
  } catch { /* no server on this origin */ }
  return demoApi();
}
