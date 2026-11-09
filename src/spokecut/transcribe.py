"""Speech to words with timings, using faster-whisper on CUDA when there is a GPU."""

from __future__ import annotations

import ctypes
import functools
import glob
import os
import sys
from collections.abc import Callable

import numpy as np

from .cleaner import split_verbatim_tags
from .project import Word
from .snap import GRID, SAMPLE_RATE, energy_grid

VERBATIM_MODEL = "nyrahealth/faster_CrisperWhisper"
VERBATIM_LICENSE = "CC BY-NC 4.0 (non-commercial use only)"
# Whisper drops ums unless it is shown some. Helps a little, never fully.
DISFLUENCY_PROMPT = "Umm, let me think like, hmm... Okay, here's what I'm, like, thinking. Uh, so, you know, yeah."


def preload_cuda_libs() -> None:
    """Load cuBLAS and cuDNN from the pip wheels (spokecut[cuda]) so CTranslate2 finds them without LD_LIBRARY_PATH."""
    if not sys.platform.startswith("linux"):
        return
    for site in sys.path:
        for pattern in ("nvidia/cublas/lib/libcublas.so.*", "nvidia/cudnn/lib/libcudnn.so.*"):
            for lib in sorted(glob.glob(os.path.join(site, pattern))):
                try:
                    ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass


def cuda_status() -> tuple[bool, str]:
    """Whether CTranslate2 can use the GPU, and if not, why. A driver alone is not enough: it also needs cuBLAS."""
    preload_cuda_libs()
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() == 0:
            return False, "no CUDA device"
    except Exception:
        return False, "no CUDA device"
    if sys.platform.startswith("linux"):
        try:
            ctypes.CDLL("libcublas.so.12")
        except OSError:
            return False, "GPU found but cuBLAS is missing, reinstall with the spokecut[cuda] extra (docs/install.md)"
    return True, ""


def has_cuda() -> bool:
    return cuda_status()[0]


def default_model(cuda: bool) -> str:
    return "large-v3-turbo" if cuda else "small"


@functools.lru_cache(maxsize=1)
def load_model(name: str, device: str = "auto"):
    from faster_whisper import WhisperModel

    preload_cuda_libs()
    cuda = has_cuda() if device == "auto" else device == "cuda"
    return WhisperModel(name, device="cuda" if cuda else "cpu", compute_type="float16" if cuda else "int8")


def _split_tags(text: str, start: float, end: float, prob: float) -> list[Word]:
    parts = split_verbatim_tags(text.strip())
    weights = [max(2, len(p)) for p in parts]
    total, pos, out = sum(weights), start, []
    for part, wt in zip(parts, weights, strict=True):
        nxt = pos + (end - start) * wt / total
        out.append(Word(part, float(pos), float(nxt), float(prob)))
        pos = nxt
    return out


def sanitize(words: list[Word], duration: float) -> list[Word]:
    """Whisper timestamps can overlap or collapse. Make them ordered with every word at least 20 ms long."""
    out: list[Word] = []
    for w in words:
        if not w.text.strip():
            continue
        start = min(max(w.start, out[-1].start if out else 0.0), duration)
        end = min(max(w.end, start + 0.02), duration)
        if out and start < out[-1].end:
            out[-1].end = max(out[-1].start + 0.02, start)
        out.append(Word(w.text.strip(), start, end, w.prob))
    return out


def trim_to_voice(words: list[Word], energy: np.ndarray, factor: float = 2.5) -> list[Word]:
    """Whisper stretches words across the silence that follows them. Pull word edges in to where there is sound."""
    if len(energy) < 10 or not words:
        return words
    threshold = max(float(np.percentile(energy, 10)) * factor, 1e-4)
    for w in words:
        a, b = int(w.start / GRID), min(len(energy), int(np.ceil(w.end / GRID)))
        lo, hi = a, b
        while hi - 1 > lo + 2 and energy[hi - 1] < threshold:
            hi -= 1
        while lo + 1 < hi - 2 and energy[lo] < threshold:
            lo += 1
        w.start, w.end = max(w.start, lo * GRID), min(w.end, hi * GRID)
    return words


def transcribe(
    samples: np.ndarray,
    model_name: str,
    language: str | None = None,
    device: str = "auto",
    verbatim: bool = False,
    progress: Callable[[float], None] | None = None,
) -> tuple[list[Word], str]:
    model = load_model(VERBATIM_MODEL if verbatim else model_name, device)
    duration = len(samples) / SAMPLE_RATE
    segments, info = model.transcribe(
        samples,
        language=language,
        word_timestamps=True,
        condition_on_previous_text=False,
        initial_prompt=None if verbatim else DISFLUENCY_PROMPT,
        vad_filter=False,
    )
    words: list[Word] = []
    for seg in segments:
        for w in seg.words or []:
            words.extend(_split_tags(w.word, w.start, w.end, w.probability))
        if progress and duration:
            progress(min(1.0, seg.end / duration))
    energy = energy_grid(samples)
    return trim_to_voice(sanitize(words, duration), energy), info.language
