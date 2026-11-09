"""Quiet points between words. A cut placed on one lands in silence instead of inside a sound."""

from __future__ import annotations

import numpy as np

SAMPLE_RATE = 16000
GRID = 0.01  # seconds per energy frame
LEAD = 0.5  # how far before the first word and after the last word a quiet point may sit
HALO = 0.04  # words touch in fast speech: search this far into the neighbouring words


def energy_grid(samples: np.ndarray, rate: int = SAMPLE_RATE) -> np.ndarray:
    """RMS energy per 10 ms frame."""
    hop = int(rate * GRID)
    usable = len(samples) // hop * hop
    if usable == 0:
        return np.zeros(1, dtype=np.float32)
    frames = samples[:usable].astype(np.float32).reshape(-1, hop)
    return np.sqrt((frames**2).mean(axis=1))


def quiet_point(energy: np.ndarray, lo: float, hi: float) -> float:
    """The centre of the quietest stretch of the energy grid between `lo` and `hi` seconds."""
    a = max(0, int(lo / GRID))
    b = min(len(energy), max(a + 1, int(np.ceil(hi / GRID))))
    window = energy[a:b]
    if len(window) == 0:
        return lo
    # Smooth over 30 ms so one lucky low frame in a noisy gap does not win.
    k = min(3, len(window))
    smooth = np.convolve(window, np.ones(k) / k, mode="same") if k > 1 else window
    floor = smooth.min()
    candidates = np.flatnonzero(smooth <= floor * 1.0001 + 1e-9)
    mid = candidates[len(candidates) // 2]
    return round((a + mid + 0.5) * GRID, 3)


def snap_points(words, energy: np.ndarray, duration: float) -> list[float]:
    """snaps[i] is the quiet point just before word i. snaps[len(words)] follows the last word."""
    if not words:
        return [0.0]
    points = []
    first = words[0].start
    points.append(quiet_point(energy, max(0.0, first - LEAD), first))
    for i in range(1, len(words)):
        lo, hi = words[i - 1].end, words[i].start
        if hi - lo < 2 * GRID:
            mid = (lo + hi) / 2
            lo, hi = max(0.0, mid - HALO), mid + HALO
        points.append(quiet_point(energy, lo, hi))
    last = words[-1].end
    points.append(quiet_point(energy, last, min(duration, last + LEAD)))
    return points
