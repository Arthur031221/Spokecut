import json
import shutil
import subprocess

import pytest

from spokecut.project import sidecar_path

pytestmark = pytest.mark.e2e


def sign_in(page, url):
    page.goto(f"{url}/?t=e2e-token")
    page.wait_for_selector("#empty:not([hidden])", timeout=15000)


def seconds(text: str) -> int:
    parts = [int(p) for p in text.split(":")]
    return sum(p * 60**i for i, p in enumerate(reversed(parts)))


def test_without_the_token_the_page_explains_where_to_get_it(page, server_url):
    page.goto(server_url)
    page.wait_for_selector("#empty:not([hidden])", timeout=15000)
    assert "Open the link that Spokecut printed" in page.inner_text("#empty-error")


def test_upload_edit_and_the_edit_lands_in_the_sidecar(page, server_url, clip, tmp_path):
    sign_in(page, server_url)
    page.set_input_files("#file-input", str(clip))
    page.wait_for_selector("#editor:not([hidden])", timeout=60000)
    assert page.locator(".w").count() > 200
    assert page.locator("#project-picker").is_hidden()

    page.click("#pause-apply")
    page.locator('.w[data-i="4"]').click()
    page.keyboard.press("Delete")
    page.wait_for_function("document.getElementById('save-state').textContent === 'Saved'")

    uploaded = next((tmp_path / "uploads").rglob("talk.mp4"))
    state = json.loads(sidecar_path(uploaded).read_text())["state"]
    assert 4 in state["deleted"]
    assert len(state["cutGaps"]) == 10

    page.reload()
    page.wait_for_selector("#editor:not([hidden])", timeout=15000)
    assert page.locator(".w.del").count() == 1
    assert page.inner_text("#pause-apply") == "Restore 10 pauses"
    assert page.problems == []


def test_uploading_the_same_file_twice_opens_one_project(page, server_url, clip):
    sign_in(page, server_url)
    for _ in range(2):
        page.set_input_files("#file-input", str(clip))
        page.wait_for_selector("#editor:not([hidden])", timeout=60000)
    assert page.evaluate("fetch('/api/projects').then(r => r.json()).then(l => l.length)") == 1


def test_every_export_format_downloads_from_the_ui(page, server_url, clip, tmp_path):
    sign_in(page, server_url)
    page.set_input_files("#file-input", str(clip))
    page.wait_for_selector("#editor:not([hidden])", timeout=60000)
    page.click("#pause-apply")
    page.click("#tab-export")
    names = {}
    for fmt in ("srt", "vtt", "ass", "edl", "fcpxml", "otio", "json"):
        with page.expect_download() as download:
            page.click(f'li[data-fmt="{fmt}"] button')
        names[fmt] = download.value.suggested_filename
        path = tmp_path / names[fmt]
        download.value.save_as(path)
        assert path.stat().st_size > 100, fmt
    assert names["json"].endswith(".cuts.json")
    assert names["fcpxml"].endswith(".spokecut.fcpxml")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")
def test_render_from_the_ui_matches_the_duration_on_screen(page, server_url, clip, tmp_path):
    sign_in(page, server_url)
    page.set_input_files("#file-input", str(clip))
    page.wait_for_selector("#editor:not([hidden])", timeout=60000)
    page.click("#pause-apply")
    page.click('[data-kind="filler"] .main')
    expected = seconds(page.inner_text("#sum-edited"))
    page.click("#tab-export")
    with page.expect_download(timeout=180000) as download:
        page.click('li[data-fmt="mp4"] button')
    out = tmp_path / "out.mp4"
    download.value.save_as(out)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    assert abs(float(probe.stdout) - expected) <= 1.0
    assert page.inner_text("#render-text").startswith("Done")


def test_options_chosen_before_the_upload_reach_the_transcriber(page, server_url, clip, analysis_calls):
    sign_in(page, server_url)
    page.click("#empty summary")
    page.select_option("#empty-options .tx-language", "ja")
    page.select_option("#empty-options .tx-model", "medium")
    page.check("#empty-options .tx-verbatim")
    page.set_input_files("#file-input", str(clip))
    page.wait_for_selector("#editor:not([hidden])", timeout=60000)
    assert analysis_calls == [{"video": "talk.mp4", "model": "medium", "language": "ja", "verbatim": True}]
    assert page.problems == []


def test_transcribe_again_from_the_editor_with_other_options(page, server_url, clip, analysis_calls):
    sign_in(page, server_url)
    page.set_input_files("#file-input", str(clip))
    page.wait_for_selector("#editor:not([hidden])", timeout=60000)
    page.locator('.w[data-i="4"]').click()
    page.keyboard.press("Delete")
    page.wait_for_function("document.getElementById('save-state').textContent === 'Saved'")

    page.click("#retx summary")
    page.select_option("#retx-options .tx-language", "de")
    page.click("#retx-start")
    page.wait_for_function("document.querySelectorAll('#retx-start:not([disabled])').length === 1")
    page.wait_for_selector("#editor:not([hidden])", timeout=30000)
    assert len(analysis_calls) == 2
    assert analysis_calls[1]["language"] == "de" and analysis_calls[1]["verbatim"] is False
    # The choice follows to the next page load, and the empty screen shows the same one.
    page.reload()
    page.wait_for_selector("#editor:not([hidden])", timeout=15000)
    assert page.input_value("#empty-options .tx-language") == "de"
    assert page.problems == []


def test_a_failed_transcription_says_why_and_goes_back(page, server_url, clip, tmp_path):
    broken = tmp_path / "broken.mp4"
    shutil.copy(clip, broken)
    sign_in(page, server_url)
    page.set_input_files("#file-input", str(broken))
    page.wait_for_selector("#proc-error:not([hidden])", timeout=30000)
    assert "the model could not be loaded" in page.inner_text("#proc-error")
    page.click("#proc-back")
    page.wait_for_selector("#empty:not([hidden])")


def test_a_missing_file_is_explained_not_called_not_found(page, server_url, tmp_path):
    sign_in(page, server_url)
    page.fill("#path-input", str(tmp_path / "gone.mp4"))
    page.click("#path-form button")
    page.wait_for_selector("#empty-error:not([hidden])")
    assert "no such file" in page.inner_text("#empty-error")
