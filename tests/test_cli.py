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


def test_listen_skips_a_port_that_is_taken():
    import socket

    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        port = taken.getsockname()[1]
        sock = cli.listen("127.0.0.1", port)
        try:
            assert sock.getsockname()[1] != port
        finally:
            sock.close()


def test_listen_gives_up_when_nothing_is_free():
    import socket

    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        with pytest.raises(OSError, match="no free port"):
            cli.listen("127.0.0.1", taken.getsockname()[1], tries=1)


def test_second_editor_serves_on_the_port_it_got(monkeypatch, capsys):
    import socket

    import uvicorn

    served = {}
    monkeypatch.setattr(uvicorn.Server, "run", lambda self, sockets=None: served.update(sockets=sockets))
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        port = taken.getsockname()[1]
        assert cli.main(["edit", "--port", str(port), "--no-open"]) == 0
        got = served["sockets"][0]
        try:
            assert got.getsockname()[1] != port
        finally:
            got.close()
    assert f"Port {port} is in use" in capsys.readouterr().err


@needs_ffmpeg
def test_clean_takes_several_files_and_keeps_going_after_a_failure(tone_video, tmp_path, capsys):
    a, c = tmp_path / "a.mp4", tmp_path / "c.mp4"
    for video in (a, c):
        video.write_bytes(tone_video.read_bytes())
        prepared(video)
    missing = tmp_path / "b.mp4"
    code = cli.main(["clean", str(a), str(missing), str(c), "--format", "srt"])
    err = capsys.readouterr().err
    assert code == 2 and "2 of 3 files cleaned, 1 failed" in err
    assert (tmp_path / "a.spokecut.srt").is_file() and (tmp_path / "c.spokecut.srt").is_file()


def test_clean_refuses_one_output_name_for_several_files(capsys):
    assert cli.main(["clean", "a.mp4", "b.mp4", "-o", "x.mp4"]) == 2
    assert "one input" in capsys.readouterr().err


def test_listen_near_the_top_of_the_port_range_fails_cleanly():
    with pytest.raises(OSError, match="no free port"):
        cli.listen("127.0.0.1", 70000)


def test_allowed_hosts_include_the_bracketed_ipv6_form():
    assert cli.allowed_hosts("127.0.0.1") == frozenset()
    assert cli.allowed_hosts("192.168.1.20") == frozenset({"192.168.1.20"})
    assert cli.allowed_hosts("2001:db8::5") == frozenset({"2001:db8::5", "[2001:db8::5]"})
