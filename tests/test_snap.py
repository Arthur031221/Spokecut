import numpy as np
from conftest import make_project

from spokecut import snap
from spokecut.project import Word


def signal(rate=16000, seconds=3.0, voiced=((0.2, 0.9), (1.4, 2.2))):
    t = np.arange(int(rate * seconds)) / rate
    x = 0.001 * np.random.default_rng(1).standard_normal(len(t))
    for a, b in voiced:
        m = (t >= a) & (t < b)
        x[m] += 0.3 * np.sin(2 * np.pi * 220 * t[m])
    return x.astype(np.float32)


def test_energy_grid_is_one_value_per_10ms():
    assert len(snap.energy_grid(np.zeros(16000, dtype=np.float32))) == 100


def test_energy_grid_of_nothing():
    assert len(snap.energy_grid(np.zeros(10, dtype=np.float32))) == 1


def test_quiet_point_lands_in_the_silence_between_two_sounds():
    e = snap.energy_grid(signal())
    t = snap.quiet_point(e, 0.9, 1.4)
    assert 0.9 <= t <= 1.4


def test_quiet_point_avoids_a_loud_stretch_inside_the_window():
    e = snap.energy_grid(signal())
    t = snap.quiet_point(e, 0.5, 1.6)
    assert not (0.5 < t < 0.88) and not (1.42 < t < 1.6)


def test_snap_points_has_one_more_entry_than_words():
    words = [Word("a", 0.2, 0.9), Word("b", 1.4, 2.2)]
    pts = snap.snap_points(words, snap.energy_grid(signal()), 3.0)
    assert len(pts) == 3
    assert pts[0] < 0.2 and 0.9 <= pts[1] <= 1.4 and pts[2] >= 2.2


def test_snap_points_for_touching_words_search_the_halo():
    words = [Word("a", 0.2, 0.9), Word("b", 0.9, 1.4)]
    pts = snap.snap_points(words, snap.energy_grid(signal()), 3.0)
    assert 0.85 <= pts[1] <= 0.95


def test_snap_points_without_words():
    assert snap.snap_points([], np.zeros(10), 1.0) == [0.0]


def test_fixture_snaps_are_valid_for_the_timeline():
    p = make_project()
    assert len(p.snaps) == len(p.words) + 1
    assert p.snaps == sorted(p.snaps)
