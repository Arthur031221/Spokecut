import json
from pathlib import Path

import pytest
from conftest import make_project, needs_ffmpeg

from spokecut import cli
from spokecut.project import Media, save_project, sidecar_path


def prepared(video: Path, duration=3.0) -> None:
    project = make_project(duration=duration)
    project.words = project.words[:6]
    project.snaps = project.snaps[:6] + [duration]
    project.media = Media(video.name, duration, 30.0, 320, 240, True)
    from spokecut.cleaner import suggestions

    project.suggestions = suggestions(project.words, "en")
    save_project(project, sidecar_path(video))


def test_no_arguments_means_edit():
    parsed = cli.build_parser().parse_args(["edit"])
    assert parsed.command == "edit" and parsed.port == cli.DEFAULT_PORT


def test_missing_file_is_reported(capsys):
    assert cli.main(["clean", "/nope/missing.mp4"]) == 2
    assert "no such file" in capsys.readouterr().err


def test_doctor_runs(capsys):
    code = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "ffmpeg" in out and "model" in out and code in (0, 1)


def test_edit_refuses_to_listen_on_every_interface(capsys):
    assert cli.main(["edit", "--host", "0.0.0.0", "--no-open"]) == 2
    assert "Bind to one address" in capsys.readouterr().err


def test_bare_path_opens_the_editor(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "cmd_edit", lambda args: seen.update(files=args.files) or 0)
    assert cli.main(["talk.mp4"]) == 0 and seen["files"] == ["talk.mp4"]
    assert cli.main(["--port", "9000"]) == 0


@needs_ffmpeg
def test_clean_writes_srt_beside_the_video(tone_video, tmp_path, capsys):
    video = tmp_path / "talk.mp4"
    video.write_bytes(tone_video.read_bytes())
    prepared(video)
    assert cli.main(["clean", str(video), "--format", "srt"]) == 0
    assert (tmp_path / "talk.spokecut.srt").is_file()
    assert "removed" in capsys.readouterr().out
    saved = json.loads(sidecar_path(video).read_text())["state"]
    assert 1 in saved["deleted"]  # the "um" the cleaner found


@needs_ffmpeg
def test_clean_renders_a_shorter_video(tone_video, tmp_path):
    video = tmp_path / "talk.mp4"
    video.write_bytes(tone_video.read_bytes())
    prepared(video)
    out = tmp_path / "out.mp4"
    assert cli.main(["clean", str(video), "-o", str(out), "--encoder", "x264"]) == 0
    assert out.stat().st_size > 1000


@needs_ffmpeg
def test_export_needs_a_project_file(tone_video, capsys):
    assert cli.main(["export", str(tone_video), "--format", "edl"]) == 2
    assert "spokecut transcribe" in capsys.readouterr().err


@needs_ffmpeg
@pytest.mark.parametrize("fmt", ["edl", "fcpxml", "otio", "json", "vtt", "ass"])
def test_export_formats(tone_video, tmp_path, fmt):
    video = tmp_path / "talk.mp4"
    video.write_bytes(tone_video.read_bytes())
    prepared(video)
    assert cli.main(["export", str(video), "--format", fmt]) == 0


@needs_ffmpeg
def test_render_keeps_a_caption_file_exported_earlier(tone_video, tmp_path):
    video = tmp_path / "talk.mp4"
    video.write_bytes(tone_video.read_bytes())
    prepared(video)
    assert cli.main(["export", str(video), "--format", "ass"]) == 0
    ass = tmp_path / "talk.spokecut.ass"
    text = ass.read_text()
    assert cli.main(["clean", str(video), "--captions", "plain", "--encoder", "x264"]) == 0
    assert ass.read_text() == text


@needs_ffmpeg
def test_output_cannot_be_the_source_video(tone_video, tmp_path, capsys):
    video = tmp_path / "talk.mp4"
    video.write_bytes(tone_video.read_bytes())
    prepared(video)
    before = video.read_bytes()
    assert cli.main(["clean", str(video), "-o", str(video)]) == 1
    assert "source video" in capsys.readouterr().err
    assert video.read_bytes() == before


@needs_ffmpeg
def test_clean_without_captions_does_not_turn_burn_in_off_for_later(tone_video, tmp_path):
    video = tmp_path / "talk.mp4"
    video.write_bytes(tone_video.read_bytes())
    prepared(video)
    assert cli.main(["clean", str(video), "--format", "srt"]) == 0
    assert json.loads(sidecar_path(video).read_text())["state"]["caption"]["burn"] is True


def test_keep_must_be_in_range(capsys):
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["clean", "x.mp4", "--keep", "-1"])
