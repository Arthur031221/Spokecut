"""Frame rates and timecode for the NLE exports."""

from __future__ import annotations

from fractions import Fraction

# Broadcast rates written as exact rationals; anything else falls back to a millisecond fraction.
_KNOWN = {
    23.976: Fraction(24000, 1001),
    24.0: Fraction(24),
    25.0: Fraction(25),
    29.97: Fraction(30000, 1001),
    30.0: Fraction(30),
    48.0: Fraction(48),
    50.0: Fraction(50),
    59.94: Fraction(60000, 1001),
    60.0: Fraction(60),
}


def exact_fps(fps: float) -> Fraction:
    for approx, exact in _KNOWN.items():
        if abs(fps - approx) < 0.005 or abs(fps - float(exact)) < 0.005:
            return exact
    return Fraction(round(fps * 1000), 1000)


def to_frames(seconds: float, fps: Fraction) -> int:
    return round(Fraction(seconds).limit_denominator(1_000_000) * fps)


def is_drop_frame(fps: Fraction) -> bool:
    return fps.denominator == 1001 and fps.numerator in (30000, 60000)


def timecode(frames: int, fps: Fraction) -> str:
    """HH:MM:SS:FF, with the semicolon and frame skipping of drop frame for 29.97 and 59.94."""
    nominal = round(fps)
    sep = ":"
    if is_drop_frame(fps):
        drop = 2 if nominal == 30 else 4
        per_10min = nominal * 600 - drop * 9
        per_min = nominal * 60 - drop
        tens, rest = divmod(frames, per_10min)
        frames += drop * 9 * tens
        if rest > drop:
            frames += drop * ((rest - drop) // per_min)
        sep = ";"
    ff = frames % nominal
    total = frames // nominal
    return f"{total // 3600:02d}:{total // 60 % 60:02d}:{total % 60:02d}{sep}{ff:02d}"


def rational(frames: int, fps: Fraction) -> str:
    """FCPXML time: frames over fps as a reduced rational string."""
    t = Fraction(frames) / fps
    if t.denominator == 1:
        return f"{t.numerator}s"
    return f"{t.numerator}/{t.denominator}s"


def hour_frames(fps: Fraction) -> int:
    """Frame count of timecode 01:00:00:00 (01:00:00;00 in drop frame)."""
    nominal = round(fps)
    frames = nominal * 3600
    if is_drop_frame(fps):
        frames -= (2 if nominal == 30 else 4) * 54
    return frames
