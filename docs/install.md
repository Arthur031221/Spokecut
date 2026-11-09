# Install

Spokecut needs Python 3.10 or newer and ffmpeg on your PATH.

```sh
pipx install git+https://github.com/Arthur031221/Spokecut
spokecut doctor
```

pipx (or `uv tool install`, which takes the same argument) puts Spokecut in its own environment. Recent Debian, Ubuntu and Homebrew Pythons refuse a plain `pip install` into the system Python with an `externally-managed-environment` error, and pipx avoids that. If `spokecut` is not found afterwards, run `pipx ensurepath` and open a new terminal. On Windows plain `pip install` works.

`spokecut doctor` prints where it found ffmpeg, whether CUDA and NVENC work, and which model it will use. If it says `cuda no`, everything still runs on the CPU, just slower (see [benchmarks](benchmarks.md)).

The first transcription downloads the Whisper model from Hugging Face: about 1.6 GB for `large-v3-turbo` on a GPU, about 480 MB for `small` on a CPU. After that you don't need the network.

## ffmpeg

| System | Command |
| --- | --- |
| macOS | `brew install ffmpeg` |
| Debian, Ubuntu | `sudo apt install ffmpeg` |
| Windows | `winget install Gyan.FFmpeg` |

Drawing captions takes `libass`. Most distribution packages and the Gyan build have it.

## GPU

On Linux or Windows with an NVIDIA card, pipx can install the CUDA libraries CTranslate2 needs:

```sh
pipx install "spokecut[cuda] @ git+https://github.com/Arthur031221/Spokecut"
```

Spokecut finds them inside the Python environment, so there's no need to set `LD_LIBRARY_PATH`. To force a device, pass `--device cpu` or `--device cuda`. The render uses NVENC if ffmpeg can open it, and x264 if not.

## From source

```sh
git clone https://github.com/Arthur031221/Spokecut
cd Spokecut
pip install -e ".[dev]"
```

## Try it without installing

The [live demo](https://arthur031221.github.io/Spokecut/) runs the same editor in your browser on a bundled CC BY-SA 3.0 clip. You can edit, undo, caption and download SRT, VTT and JSON. It can't transcribe your own files or render an MP4, since that needs the Python side.
