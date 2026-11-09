# Spokecut

Edit talking video by editing its transcript. Delete a word and it's gone from the video. It runs on your own machine and costs nothing.

[![CI](https://img.shields.io/github/actions/workflow/status/Arthur031221/Spokecut/ci.yml?branch=main&style=flat-square&color=2dd4bf&label=CI)](https://github.com/Arthur031221/Spokecut/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2dd4bf?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-2dd4bf?style=flat-square)](docs/install.md)

[Live demo](https://arthur031221.github.io/Spokecut/) | [Install](docs/install.md) | [Usage](docs/usage.md) | [Config](docs/config.md) | [Architecture](docs/architecture.md) | [Benchmarks](docs/benchmarks.md)

English | [Traditional Chinese](README.zh-TW.md) | [Simplified Chinese](README.zh-CN.md) | [Japanese](README.ja.md) | [Korean](README.ko.md) | [Spanish](README.es.md) | [French](README.fr.md) | [German](README.de.md) | [Portuguese (Brazil)](README.pt-BR.md)

![Spokecut: cut the pauses and fillers, find a word and cut every match, delete a sentence, play the edit with the cuts skipped, restyle the captions](assets/demo.gif)

A 5 minute talking video gets transcribed, cleaned up and rendered with burned in captions in 15.0 s on an RTX 5090, 20.0x realtime. That's the whole job from a cold process (`python bench/bench.py pipeline talk.mp4`, mean of 4 runs, 14.7 to 15.1 s, `large-v3-turbo` and NVENC). On a Ryzen 5 7500F with 3 threads, `small` and x264, the same video takes 61.1 s.

Your video never leaves your machine. I'd rather tell you Whisper hides most of your ums than pretend the filler button finds them all.

## Before and after

The numbers are from the 80 second demo clip, which is also the live demo, transcribed with `large-v3`, unless a row says otherwise.

| What you want | By hand in a timeline editor | Spokecut |
| --- | --- | --- |
| Cut 10 pauses longer than 0.7 s | Find each one by ear, split, ripple delete, ten times | One click, or `--pauses 0.7 --no-fillers --no-repeats --model large-v3`. 80.3 s becomes 73.4 s |
| Remove an "uh" and a repeated word | Scrub until you hear it | Click the word and press Delete, or use the Fillers and Repeats buttons |
| Cut a whole sentence | Hunt for its start and end on the waveform | Select the words and press Delete. Cuts snap to the quietest point between words |
| Avoid a click where two pieces meet | Add a crossfade at every cut | Every join has a 15 ms fade. On the 300 second benchmark clip, 3 of 37 joins stepped above 10x the typical sample change without the fade and none did with it |
| Get captions | Transcribe somewhere else, import an SRT, retime it after every cut | Captions follow the edit. Five styles burned in, or SRT, VTT and ASS |
| Take the edit to another editor | Rebuild it by hand | EDL, FCPXML and OTIO of the kept ranges |
| Result on the demo clip | | 80.3 s to 72.1 s, 8.2 s removed, one command: `spokecut clean talk.mp4 --pauses 0.7 --captions highlight --model large-v3` |

## Install

It's not on PyPI yet, so install from GitHub. You also need Python 3.10 or newer and ffmpeg.

<details>
<summary>Linux (NVIDIA GPU or CPU)</summary>

```sh
sudo apt install ffmpeg pipx
pipx install "spokecut[cuda] @ git+https://github.com/Arthur031221/Spokecut"
spokecut doctor
```

Leave out `[cuda]` for a CPU only install. The render uses NVENC when ffmpeg can open it and x264 when it can't.

</details>

<details>
<summary>macOS (Apple Silicon or Intel)</summary>

```sh
brew install ffmpeg pipx
pipx install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

Transcription runs on the CPU and the render uses x264. I haven't run Spokecut on a Mac.

</details>

<details>
<summary>Windows</summary>

```powershell
winget install Gyan.FFmpeg
pip install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

I haven't run Spokecut on Windows. The CI job covers Linux only.

</details>

The first transcription downloads the Whisper model, about 1.6 GB for `large-v3-turbo` and 464 MB for `small`. After that nothing needs the network.

## Use

```sh
spokecut talk.mp4
```

This opens the editor in your browser. Click a word and press Delete to cut it, drag to cut a phrase, click a gray chip to cut a pause, and press Enter on a word to fix a caption. Press Ctrl+F to find a word or phrase and cut every match at once. Playback skips what you cut. The edit is saved next to the video as `talk.mp4.spokecut.json`, and the video itself is never changed. Language, model and the ums-and-uhs option are under Transcription options, and Transcribe again redoes a video whose language was detected wrong.

You don't need a browser for the common case:

```sh
spokecut clean talk.mp4 --pauses 0.7 --captions highlight
spokecut clean *.mp4 --pauses 0.7
spokecut export talk.mp4 --format fcpxml
```

See [usage](docs/usage.md) for the keyboard shortcuts and every format, and [config](docs/config.md) for the flags.

## Fillers, honestly

Stock Whisper drops most ums and uhs from its transcript, so the filler button has little to find. On the demo clip `large-v3` kept 2 fillers. `--verbatim` switches to CrisperWhisper, which keeps them, and it found 4 on the same clip. It's licensed CC BY-NC 4.0, so non-commercial use only. Pauses and immediate repeats work with every model.

## What it does not do

- One speaker per file. It doesn't separate voices.
- It cuts and captions. There's no multitrack timeline, no screen recording and no voice cloning.
- I read the EDL, FCPXML and OTIO files back through the OpenTimelineIO adapters in the tests. I haven't imported them into Resolve or Premiere, and the OTIO has a video track only.
- The live demo can't transcribe your own video or render an MP4. Those need the Python side.
- Caption fonts come from your system. I checked burned in Chinese with Noto CJK installed. Without a font for your language the text won't draw correctly.

## How it works

Spokecut decodes the audio, runs faster-whisper for word timestamps, and finds the quietest point between each pair of words so a cut lands in silence. Your edit is a small state object of deleted words, cut pauses and caption settings. Every output is computed from the words and that state, and the render becomes one ffmpeg filter graph with frame exact trims. The editor is plain ES modules with no build step, in nine languages. The [architecture](docs/architecture.md) page has the details and the [benchmarks](docs/benchmarks.md) page has the method behind each number.

## Contributing

Bug reports with a short video that reproduces the problem help most. See [CONTRIBUTING](CONTRIBUTING.md).

## License

MIT, see [LICENSE](LICENSE). The demo clip is an excerpt of "Ward Cunningham, Inventor of the Wiki" by Vgrigas, CC BY-SA 3.0, see [web/demo/NOTICE](web/demo/NOTICE).

Assisted by Claude/Codex.
