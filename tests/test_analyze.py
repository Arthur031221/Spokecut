import numpy as np

from spokecut import analyze, audio, transcribe
from spokecut.project import Media, Word


def test_the_model_is_loaded_in_its_own_stage_before_transcribing(tmp_path, monkeypatch):
    """The first run downloads the model there, so the editor must be able to say so instead of showing 0 percent."""
    video = tmp_path / "talk.mp4"
    video.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(
        audio, "probe", lambda p: (Media("talk.mp4", 2.0, 30.0, 320, 240, True), {"video": "h264", "audio": "aac"})
    )
    monkeypatch.setattr(audio, "decode_audio", lambda p: np.zeros(32000, dtype=np.float32))
    monkeypatch.setattr(transcribe, "load_model", lambda name, device="auto": calls.append(("load", name)))
    monkeypatch.setattr(
        transcribe,
        "transcribe",
        lambda *a, **k: calls.append(("transcribe", a[1])) or ([Word("hi", 0.1, 0.5, 0.9)], "en"),
    )
    stages = []
    analyze.analyze(video, model="base", device="cpu", progress=lambda stage, f: stages.append(stage))
    assert stages.index("model") < stages.index("transcribe")
    assert calls == [("load", "base"), ("transcribe", "base")]

    calls.clear()
    analyze.analyze(video, model="base", device="cpu", verbatim=True)
    assert calls[0] == ("load", transcribe.VERBATIM_MODEL)
