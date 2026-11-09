import sys

import numpy as np

from spokecut import transcribe as tr
from spokecut.project import Word


def test_sanitize_orders_and_widens_words():
    out = tr.sanitize([Word("a", 1.0, 1.0), Word("b", 0.5, 0.6), Word("  ", 2, 3)], 10.0)
    assert [w.text for w in out] == ["a", "b"]
    assert out[1].start >= out[0].start
    assert all(w.end - w.start >= 0.02 - 1e-9 for w in out)


def test_sanitize_trims_overlap_and_clamps_to_duration():
    out = tr.sanitize([Word("a", 0.0, 1.0), Word("b", 0.8, 5.0)], 2.0)
    assert out[0].end <= out[1].start + 1e-9
    assert out[1].end == 2.0


def test_trim_to_voice_pulls_a_stretched_edge_back():
    energy = np.concatenate([np.full(50, 0.3), np.full(100, 0.0005)]).astype(np.float32)
    energy[energy < 0.001] = 0.0005
    w = tr.trim_to_voice([Word("hi", 0.0, 1.4)], energy)[0]
    assert w.end < 0.7


def test_trim_to_voice_leaves_short_signals_alone():
    words = [Word("hi", 0.0, 0.2)]
    assert tr.trim_to_voice(words, np.zeros(5, dtype=np.float32))[0].end == 0.2


def test_verbatim_tags_become_words():
    out = tr._split_tags("so[UM]yes", 0.0, 1.0, 0.9)
    assert [w.text for w in out] == ["so", "um", "yes"]
    assert out[0].start == 0.0 and abs(out[-1].end - 1.0) < 1e-9


def test_default_model_depends_on_the_device():
    assert tr.default_model(True) == "large-v3-turbo"
    assert tr.default_model(False) == "small"


def test_cuda_needs_cublas_not_just_a_device(monkeypatch):
    import types

    fake = types.SimpleNamespace(get_cuda_device_count=lambda: 1)
    monkeypatch.setitem(sys.modules, "ctranslate2", fake)
    monkeypatch.setattr(tr, "preload_cuda_libs", lambda: None)
    monkeypatch.setattr(sys, "platform", "linux")

    def no_cublas(name):
        raise OSError(name)

    monkeypatch.setattr(tr.ctypes, "CDLL", no_cublas)
    ok, why = tr.cuda_status()
    assert not ok and "spokecut[cuda]" in why
    monkeypatch.setattr(tr.ctypes, "CDLL", lambda name: None)
    assert tr.cuda_status() == (True, "")
