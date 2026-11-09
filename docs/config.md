# Configuration

Spokecut has no config file. Everything is a flag, and your edits live in the project file next to each video.

## `spokecut edit`

| Flag | Default | Meaning |
| --- | --- | --- |
| `--host` | `127.0.0.1` | bind address |
| `--port` | `8765` | port. If it is taken, for example by another Spokecut, the next free one up to 20 higher is used and the printed link shows it |
| `--no-open` | off | do not open a browser tab |
| `--model` | `large-v3-turbo` on a GPU, `small` on a CPU | Whisper model name or a path |
| `--language` | detect | spoken language code, such as `en` or `zh` |
| `--device` | `auto` | `auto`, `cuda` or `cpu` |
| `--verbatim` | off | use CrisperWhisper, which keeps ums and uhs. Non-commercial license |

The server prints a link with a random token in it. Opening the link sets a cookie, and every request to `/api` except `/api/health` needs that cookie or an `X-Spokecut-Token` header. The server also rejects any request whose Host or Origin isn't local, which blocks DNS rebinding and uploads from other websites. If you pass another `--host`, that address is accepted as a Host too. There's no login, so only do that on a network you trust, or use an SSH tunnel. `--host 0.0.0.0` is refused because Spokecut can read and write your files.

Browser uploads go under `$XDG_DATA_HOME/spokecut/uploads` (`~/.local/share/spokecut/uploads` by default), in a folder named after a hash of the file. Drop the same file twice under the same name and it's kept once. The limit is 8 GiB.

## `spokecut transcribe`, `clean` and `export`

`transcribe` takes `--model`, `--language`, `--device` and `--verbatim`, same as `edit`.

| Flag | Command | Meaning |
| --- | --- | --- |
| `-o`, `--output` | clean, export | output file. `clean` takes it with one input only |
| `--format` | clean | `mp4` (default), `srt`, `vtt`, `ass`, `edl`, `fcpxml`, `otio`, `json` |
| `--format` | export | the same list, required |
| `--pauses SECONDS` | clean | shorten pauses at least this long |
| `--keep SECONDS` | clean | silence left in a shortened pause, 0.25 by default |
| `--no-fillers`, `--no-repeats` | clean | skip that kind of cut |
| `--loose` | clean | also cut phrases like "you know", which are sometimes real words |
| `--captions STYLE` | clean | burn in captions: `highlight`, `karaoke`, `pop`, `lowerthird`, `plain` |
| `--encoder` | clean, export | `auto`, `nvenc` or `x264` |
| `--retranscribe` | clean | ignore an existing project file |

## The project file

`<video>.spokecut.json` is plain JSON. `words` holds every word as `{t, s, e, p}` (text, start, end, confidence). `state` holds what you changed: the deleted word indexes, the cut pauses, edited words, the pause threshold and the caption style. Delete the file to start over. The video itself is never modified.

## Environment

| Variable | Meaning |
| --- | --- |
| `XDG_DATA_HOME` | base folder for uploads, `~/.local/share` by default |
| `SPOKECUT_BROWSER_CHANNEL` | for the test suite: run the browser tests in an installed `chrome` instead of the bundled Chromium |

## Language of the interface

The editor picks the language from your browser and remembers a manual choice in local storage. The list is at the top right. Available: English, Traditional Chinese, Simplified Chinese, Japanese, Korean, Spanish, French, German and Portuguese (Brazil).
