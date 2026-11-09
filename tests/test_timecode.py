from fractions import Fraction

import pytest

from spokecut import timecode as tc


@pytest.mark.parametrize(
    ("fps", "exact"),
    [
        (23.976, Fraction(24000, 1001)),
        (29.97, Fraction(30000, 1001)),
        (30.0, Fraction(30)),
        (59.94, Fraction(60000, 1001)),
    ],
)
def test_exact_fps_snaps_broadcast_rates(fps, exact):
    assert tc.exact_fps(fps) == exact


def test_exact_fps_falls_back_to_milliseconds():
    assert tc.exact_fps(12.5) == Fraction(25, 2)


def test_non_drop_timecode():
    assert tc.timecode(0, Fraction(30)) == "00:00:00:00"
    assert tc.timecode(30 * 3661 + 7, Fraction(30)) == "01:01:01:07"


def test_drop_frame_skips_frame_numbers_each_minute():
    fps = Fraction(30000, 1001)
    assert tc.timecode(1799, fps) == "00:00:59;29"
    assert tc.timecode(1800, fps) == "00:01:00;02"


def test_drop_frame_keeps_every_tenth_minute():
    fps = Fraction(30000, 1001)
    assert tc.timecode(17982, fps) == "00:10:00;00"


def test_drop_frame_one_hour():
    fps = Fraction(30000, 1001)
    assert tc.timecode(tc.hour_frames(fps), fps) == "01:00:00;00"


def test_hour_frames_non_drop():
    assert tc.hour_frames(Fraction(25)) == 90000


def test_rational_reduces():
    assert tc.rational(30, Fraction(30)) == "1s"
    assert tc.rational(1, Fraction(30000, 1001)) == "1001/30000s"
    assert tc.rational(3, Fraction(24)) == "1/8s"


def test_to_frames_rounds_to_nearest():
    assert tc.to_frames(1.0, Fraction(30000, 1001)) == 30
    assert tc.to_frames(0.0167, Fraction(30)) == 1
