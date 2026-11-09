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
