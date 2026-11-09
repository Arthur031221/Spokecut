# Benchmarks

Numbers on this page come from the commands shown, run with `bench/bench.py`. Nothing here is a vendor figure.

Hardware: NVIDIA GeForce RTX 5090 (driver 610.43.02), AMD Ryzen 5 7500F with 3 threads available to the CPU runs,
ffmpeg 6.1, Python 3.12, faster-whisper with CTranslate2 (float16 on the GPU, int8 on the CPU).

Test video: the first 300 seconds of the CC BY-SA 3.0 interview "Ward Cunningham, Inventor of the Wiki" on Wikimedia
Commons, scaled to 960x540 at 30 fps (see `web/demo/NOTICE`). One person talking to a camera.

## File to finished video

`python bench/bench.py pipeline talk.mp4 --device cuda`

This is the whole job from a cold process: probe, decode, transcribe with `large-v3-turbo`, find quiet points,
mark pauses of 0.7 s and longer plus fillers and repeats, then render an MP4 with burned in captions. The model is
already on disk. The run is not warmed up, because a person using the app pays for the model load too.

| Device | Transcribe | Render | Whole job | Speed |
| --- | --- | --- | --- | --- |
| RTX 5090, `large-v3-turbo`, NVENC | 4.1 to 4.4 s | 10.2 to 10.5 s | 14.7 to 15.1 s (4 runs, mean 15.0 s) | 20.0x realtime |
| Ryzen 5 7500F, `small`, x264 | 33.3 s | 27.3 s | 61.1 s (1 run) | 4.9x realtime |

On the GPU the render is the larger half. The 300 second source becomes 272.7 s after cleanup.

## Transcription alone

`python bench/bench.py transcribe talk.mp4 --model large-v3-turbo --device cuda --runs 3`

The model is loaded once, one pass is run and discarded as a warm-up, and the table shows the best of the timed
passes. The CPU rows are a single timed pass after the warm-up.

| Model | Device | Time for 300 s of audio | Speed |
| --- | --- | --- | --- |
| `large-v3-turbo` | RTX 5090 | 2.19 s (best of 3) | 136.8x realtime |
| `large-v3` | RTX 5090 | 6.25 s (best of 3) | 48.0x realtime |
| `small` | RTX 5090 | 2.82 s (best of 3) | 106.6x realtime |
| `tiny.en` | RTX 5090 | 1.74 s (best of 3) | 172.2x realtime |
| `small` | Ryzen 5 7500F | 32.76 s (1 run) | 9.2x realtime |
| `tiny.en` | Ryzen 5 7500F | 5.52 s (1 run) | 54.3x realtime |

Speed alone does not say which model is better. On this card `large-v3-turbo` was faster than `small`, so the GPU
default costs nothing in time against the smaller model.

## Clicks at the joins

A cut leaves a step in the waveform where two pieces of audio meet, and that step is heard as a click. Spokecut
fades each kept piece in and out over 15 ms. `python bench/bench.py joins talk.mp4` renders the same 37 joins
(pauses of 0.7 s and longer, cut) with and without the fade, and measures the largest change between two
neighbouring samples within one sample of each join.

| Fade | Median step at a join | Worst step at a join | Joins above 10x the median step of the whole file |
| --- | --- | --- | --- |
| none | 0.00293 | 0.06509 | 3 of 37 |
| 15 ms | 0.00003 | 0.00046 | 0 of 37 |

Samples are floats between -1 and 1. This counts steps in the signal, and I did not run a listening test. The
cuts are also placed on the quietest point between two words, so most of them are quiet even without a fade.

## What these numbers do not say

- One speaker, clean audio, one language. Noisy rooms, crosstalk and music slow nothing down but lower accuracy.
- The edit on a different clip depends on how much that person pauses. The demo clip loses 10 percent.
- NVENC speed depends on the card. A card without NVENC falls back to x264 and takes the CPU path for the render.
- The output files can be larger than the source. The render is a re-encode at constant quality (`-cq 21` on NVENC,
  `-crf 19` on x264) with the captions drawn into the picture. The quality is high on purpose, because the file is
  usually uploaded and encoded again. I have not measured quality against the source.
