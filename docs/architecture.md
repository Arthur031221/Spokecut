# Architecture

Spokecut has two halves that meet at one JSON file next to your video.

```
video.mp4
   |
   +-> ffmpeg decode (16 kHz mono) -> faster-whisper (word timestamps)
   |                                      |
   |        energy grid -> snap points    +-> cleaner: fillers, repeats
   |                                      |
   |                      video.mp4.spokecut.json  {words, snaps, suggestions, peaks, state}
   |                                      |
browser <- static web/ + /api/* <---------+
   edit = change `state` only: deleted words, cut pauses, word fixes, caption style
   |
   +-> timeline.plan(state) -> kept ranges -> ffmpeg filter graph -> MP4
                                           -> SRT, VTT, ASS, EDL, FCPXML, OTIO, JSON
```

The source video is never written to. An edit is a small `state` object, and every output is computed from the words plus that state.

## Python (`src/spokecut`)

| Module | Role |
| --- | --- |
| `audio.py` | ffprobe and ffmpeg helpers: probe, decode to float32 mono, waveform peaks, the browser proxy for codecs a browser cannot play |
| `transcribe.py` | faster-whisper with word timestamps, CUDA when there is a GPU. Trims word edges to where there is sound, because Whisper stretches a word over the silence after it |
| `snap.py` | a 10 ms RMS energy grid and the quietest point between each pair of words. A cut placed there lands in silence |
| `cleaner.py` | fillers per language, loose phrases such as "you know", and immediate repeats |
| `timeline.py` | state to cut ranges to kept ranges, snapped to frames, plus the source to output time map |
| `captions.py`, `ass.py` | group kept words into caption chunks and write SRT, VTT and ASS with the five styles |
| `export.py`, `exporting.py`, `timecode.py` | EDL, FCPXML, OTIO and the cut list. One entry point shared by the CLI and the server |
| `render.py` | builds the ffmpeg filter script and runs it. NVENC when it opens, else x264 |
| `project.py` | the project file and the edit state, with validation of anything the browser sends |
| `workspace.py`, `jobs.py` | the open projects, and one worker thread so GPU memory stays predictable |
| `server.py` | Starlette app: JSON API, the media file with range support, uploads with a size cap, static files, the local-only guard |
| `cli.py` | `edit`, `transcribe`, `clean`, `export`, `doctor` |

### The render

The kept ranges become a `filter_complex` script. Each range is a `trim` and `atrim` pair on its own branch of a `split`, and `concat` joins them. Video cuts are frame exact: the ranges are rounded to frame numbers before the trim. Every audio piece gets a 15 ms fade in and out so a join doesn't click (see [benchmarks](benchmarks.md)). Captions are drawn last by libass from a generated ASS file.

### The timeline in two languages

The editor has to show the edited duration, skip cuts during playback and draw captions while you type, so `timeline.py` and `captions.py` exist twice, once in Python and once in `web/js`. They must agree. `scripts/make_golden.py` writes fixtures to `tests/golden`, and both `tests/test_golden.py` and `tests/js/golden.test.mjs` check their side against the same files.

## Browser (`web`)

Plain ES modules and CSS. There's no bundler and no framework, so the folder is also the GitHub Pages site.

| File | Role |
| --- | --- |
| `js/api.js` | two back ends with one interface: `serverApi` talks to `/api`, `demoApi` keeps state in local storage and exports text formats in the page |
| `js/store.js` | the edit state with undo and redo. Edits within one second of each other on the same target merge into one step |
| `js/transcript.js` | the word list: selection, keyboard, inline edit, pause chips |
| `js/player.js` | cut skipping playback driven by `requestAnimationFrame`, and the caption preview |
| `js/waveform.js` | peaks, cut shading, playhead |
| `js/panels.js` | the cleanup, caption and export panels |
| `js/i18n.js`, `locales/*.json` | nine languages, one key set. `tests/js/i18n.test.mjs` fails when the keys or placeholders differ |
| `js/app.js` | wiring, saving (400 ms debounce, flushed before an export) and the project picker |

`detect()` picks the demo back end when the URL has `?demo` or when there's no API, which is the case on GitHub Pages.

## Server and safety

The server binds to `127.0.0.1`. Every `/api` request except `/api/health` needs the random token, and the Host and Origin headers must be local. The browser sends only the edit state, and `validate_state` rejects anything out of range before it's saved. Paths from the browser are opened only through `/api/open` and the upload endpoint, which stores files under a hash named folder with a cleaned file name.

## Tests

| Suite | What it covers |
| --- | --- |
| `pytest -m "not slow and not e2e"` | timeline, cleaner, captions, exports with OTIO read back, render with ffmpeg, server API, CLI, golden fixtures |
| `node --test tests/js/*.test.mjs` | the JavaScript timeline and captions against the golden fixtures, the locales |
| `pytest -m e2e` | a real browser on the demo page and on a real server: cut skipping, undo, captions, language switch, exports, an MP4 render |
| `pytest -m slow` | real Whisper (`tiny.en`) on the demo clip through to an MP4 |
