import re

import pytest

pytestmark = pytest.mark.e2e


def open_demo(page, url):
    page.goto(url)
    page.wait_for_selector("#editor:not([hidden])", timeout=30000)


def seconds(text: str) -> int:
    parts = [int(p) for p in text.split(":")]
    return sum(p * 60**i for i, p in enumerate(reversed(parts)))


def word(page, i):
    return page.locator(f'.w[data-i="{i}"]')


def test_demo_loads_the_clip_and_the_transcript_without_errors(page, demo_url, demo_project):
    open_demo(page, demo_url)
    assert page.locator(".w").count() == len(demo_project["words"])
    assert seconds(page.inner_text("#sum-original")) == round(demo_project["media"]["duration"])
    assert page.inner_text("#sum-removed") == "0:00"
    assert page.locator("#demo-banner").is_visible()
    assert page.locator("#open-file").is_hidden()
    assert page.locator("#caption-layer .cap").count() == 1
    assert page.problems == []


def test_deleting_words_shortens_the_edit_and_undo_redo_restore_it(page, demo_url):
    open_demo(page, demo_url)
    word(page, 10).click()
    word(page, 20).click(modifiers=["Shift"])
    page.keyboard.press("Delete")
    assert page.locator(".w.del").count() == 11
    assert seconds(page.inner_text("#sum-removed")) >= 2
    page.click("#undo")
    assert page.locator(".w.del").count() == 0
    assert page.inner_text("#sum-removed") == "0:00"
    page.click("#redo")
    assert page.locator(".w.del").count() == 11
    page.keyboard.press("Delete")
    assert page.locator(".w.del").count() == 0, "Delete on deleted words brings them back"


def test_cut_pauses_and_fillers_buttons_toggle(page, demo_url):
    open_demo(page, demo_url)
    assert page.inner_text("#pause-apply") == "Cut 10 pauses"
    page.click("#pause-apply")
    assert page.inner_text("#pause-apply") == "Restore 10 pauses"
    assert page.locator(".gap.cut").count() == 10
    page.click('[data-kind="filler"] .main')
    assert page.get_attribute('[data-kind="filler"] .main', "aria-pressed") == "true"
    removed = seconds(page.inner_text("#sum-removed"))
    assert removed >= 7
    page.click("#pause-apply")
    assert page.locator(".gap.cut").count() == 0


def test_edits_survive_a_reload_in_demo_mode(page, demo_url):
    open_demo(page, demo_url)
    page.click("#pause-apply")
    page.wait_for_function("document.getElementById('save-state').textContent === 'Saved'")
    page.reload()
    page.wait_for_selector("#editor:not([hidden])")
    assert page.inner_text("#pause-apply") == "Restore 10 pauses"


def test_playback_jumps_over_a_cut(page, demo_url):
    open_demo(page, demo_url)
    page.evaluate("document.getElementById('video').muted = true")
    bounds = page.evaluate("""() => { const s = [...document.querySelectorAll('.w')]; return s.length; }""")
    assert bounds > 100
    word(page, 30).click()
    word(page, 45).click(modifiers=["Shift"])
    page.keyboard.press("Delete")
    cut = page.evaluate(
        """async () => {
            const res = await (await fetch('demo/project.json')).json();
            return [res.words[30].s, res.words[45].e];
        }"""
    )
    page.evaluate(
        """([from]) => {
            const v = document.getElementById('video');
            window.__seen = [];
            v.currentTime = from;
            setInterval(() => window.__seen.push(v.currentTime), 15);
        }""",
        [cut[0] - 0.8],
    )
    page.wait_for_function("document.getElementById('video').readyState >= 3")
    page.click("#play")
    page.wait_for_function(
        "([to]) => document.getElementById('video').currentTime > to", arg=[cut[1] + 0.4], timeout=20000
    )
    page.click("#play")
    inside = page.evaluate("([a, b]) => window.__seen.filter(t => t > a + 0.15 && t < b - 0.15).length", cut)
    assert inside == 0, "the playhead must never sit inside the cut"


def test_fixing_a_caption_word_changes_the_srt(page, demo_url, tmp_path):
    open_demo(page, demo_url)
    word(page, 3).click()
    page.keyboard.press("Enter")
    page.fill(".w-edit", "ZEBRA")
    page.keyboard.press("Enter")
    assert page.inner_text('.w[data-i="3"]') == "ZEBRA"
    assert "edited" in page.get_attribute('.w[data-i="3"]', "class")
    page.click("#tab-export")
    with page.expect_download() as download:
        page.click('li[data-fmt="srt"] button')
    path = tmp_path / download.value.suggested_filename
    download.value.save_as(path)
    text = path.read_text()
    assert "ZEBRA" in text
    assert re.search(r"^1\n00:00:00,\d{3} --> ", text)
    assert path.name.endswith(".spokecut.srt")


def test_demo_offers_only_the_formats_it_can_make_in_the_browser(page, demo_url):
    open_demo(page, demo_url)
    page.click("#tab-export")
    formats = page.eval_on_selector_all("#export-list li", "els => els.map(e => e.dataset.fmt)")
    assert formats == ["srt", "vtt", "json", "demo"]


def test_arrow_keys_move_the_cursor_and_escape_collapses_the_selection(page, demo_url):
    open_demo(page, demo_url)
    word(page, 5).click()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    assert "cursor" in page.get_attribute('.w[data-i="7"]', "class")
    page.keyboard.press("Shift+ArrowRight")
    assert page.locator(".w.sel").count() == 2
    page.keyboard.press("Escape")
    assert page.locator(".w.sel").count() == 1


def test_language_switch_translates_and_persists(page, demo_url):
    open_demo(page, demo_url)
    page.select_option("#lang-select", "zh-TW")
    page.wait_for_function("document.getElementById('tab-transcript').textContent === '逐字稿'")
    assert page.evaluate("document.documentElement.lang") == "zh-TW"
    assert page.inner_text("#pause-apply") == "剪掉 10 個停頓"
    page.reload()
    page.wait_for_selector("#editor:not([hidden])")
    assert page.inner_text("#tab-captions") == "字幕"


@pytest.mark.parametrize("code", ["zh-CN", "ja", "ko", "es", "fr", "de", "pt-BR"])
def test_every_language_loads_without_missing_keys(page, demo_url, code):
    open_demo(page, demo_url)
    page.select_option("#lang-select", code)
    page.wait_for_function("code => document.documentElement.lang === code", arg=code)
    text = page.inner_text("body")
    assert not re.search(r"\b(top|tab|clean|cap|export|tx|player|sum|empty|err|save|stage)\.\w+", text)


def test_theme_toggle_flips_and_remembers(page, demo_url):
    open_demo(page, demo_url)
    before = page.evaluate("document.documentElement.dataset.theme")
    page.click("#theme-toggle")
    after = page.evaluate("document.documentElement.dataset.theme")
    assert before != after
    page.reload()
    page.wait_for_selector("#editor:not([hidden])")
    assert page.evaluate("document.documentElement.dataset.theme") == after


def test_phone_width_keeps_the_video_visible(browser, demo_url):
    context = browser.new_context(viewport={"width": 390, "height": 800})
    page = context.new_page()
    open_demo(page, demo_url)
    box = page.locator("#video").bounding_box()
    assert box["width"] > 150 and box["height"] > 80
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    context.close()


def test_caption_style_changes_the_preview(page, demo_url):
    open_demo(page, demo_url)
    page.click("#tab-captions")
    page.locator('input[value="lowerthird"]').check(force=True)
    assert page.get_attribute("#caption-layer", "data-style") == "lowerthird"
    page.uncheck("#cap-burn")
    assert page.locator("#caption-layer").is_hidden()


@pytest.fixture
def phone(browser):
    context = browser.new_context(viewport={"width": 390, "height": 780}, has_touch=True, is_mobile=True)
    page = context.new_page()
    page.problems = []
    page.on("pageerror", lambda e: page.problems.append(f"pageerror: {e}"))
    page.on("console", lambda m: page.problems.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
    yield page
    context.close()


def test_touch_user_can_cut_a_phrase_without_a_keyboard(phone, demo_url):
    open_demo(phone, demo_url)
    assert phone.locator("#sel-extend").is_visible()
    word(phone, 10).tap()
    assert phone.inner_text("#sel-cut") == "Cut selection (1)"
    phone.tap("#sel-extend")
    assert phone.get_attribute("#sel-extend", "aria-pressed") == "true"
    word(phone, 14).tap()
    assert phone.get_attribute("#sel-extend", "aria-pressed") == "false"
    assert phone.locator(".w.sel").count() == 5
    phone.tap("#sel-cut")
    assert phone.locator(".w.del").count() == 5
    assert phone.inner_text("#sel-cut") == "Restore selection (5)"
    phone.tap("#sel-cut")
    assert phone.locator(".w.del").count() == 0
    assert phone.problems == []


def test_touch_targets_are_big_enough(phone, demo_url):
    open_demo(phone, demo_url)
    small = phone.evaluate("""[...document.querySelectorAll('#clean-kinds button, #sel-cut, #sel-extend, #pause-apply')]
        .map((e) => e.getBoundingClientRect()).filter((r) => r.height < 40 || r.width < 36).length""")
    assert small == 0
    assert phone.evaluate("document.querySelector('#pause-threshold').getBoundingClientRect().height") >= 30


def test_follow_keeps_the_playing_word_below_the_sticky_video_on_a_phone(phone, demo_url, demo_project):
    open_demo(phone, demo_url)
    far = len(demo_project["words"]) - 5
    start = demo_project["words"][far]["s"]
    phone.evaluate("(t) => { const v = document.querySelector('video'); v.currentTime = t; v.play(); }", start)
    phone.wait_for_selector(".w.now")
    phone.wait_for_timeout(400)
    stage = phone.evaluate("document.querySelector('.stage').getBoundingClientRect().bottom")
    r = phone.evaluate(
        "(() => { const b = document.querySelector('.w.now').getBoundingClientRect(); return [b.top, b.bottom, innerHeight]; })()"  # noqa: E501
    )
    assert stage <= r[0] and r[1] <= r[2], (stage, r)


def test_published_demo_does_not_probe_for_an_api(browser, demo_url):
    context = browser.new_context()
    page = context.new_page()
    page.problems = []
    page.on("console", lambda m: page.problems.append(m.text) if m.type == "error" else None)
    asked = []
    page.on("request", lambda r: asked.append(r.url) if "/api/" in r.url else None)

    def mark(route):
        res = route.fetch()
        marker = '<meta name="spokecut-mode" content="demo">'
        body = res.text().replace('<meta charset="utf-8">', '<meta charset="utf-8">' + marker)
        route.fulfill(response=res, body=body)

    root = demo_url.split("?")[0]
    page.route(root, mark)
    open_demo(page, root)
    assert asked == []
    assert page.problems == []
    assert page.locator("#demo-banner").is_visible()
    context.close()


def count_word(demo_project, target):
    return sum(1 for w in demo_project["words"] if re.sub(r"[\W_]+", "", w["t"].lower()) == target)


def test_find_marks_every_match_and_cuts_them_all(page, demo_url, demo_project):
    open_demo(page, demo_url)
    n = count_word(demo_project, "about")
    assert n >= 5
    page.keyboard.press("Control+f")
    assert page.evaluate("document.activeElement.id") == "find-input"
    page.keyboard.type("About")
    assert page.locator(".w.hit").count() == n
    assert page.inner_text("#find-cut") == f"Cut {n}"
    page.keyboard.press("Enter")
    first = page.locator(".w.cursor").get_attribute("data-i")
    assert page.locator(".w.hit-now").get_attribute("data-i") == first
    page.keyboard.press("Enter")
    assert page.locator(".w.cursor").get_attribute("data-i") != first
    page.keyboard.press("Shift+Enter")
    assert page.locator(".w.cursor").get_attribute("data-i") == first
    page.click("#find-cut")
    assert page.locator(".w.del").count() == n
    assert page.inner_text("#find-cut") == f"Restore {n}"
    page.click("#undo")
    assert page.locator(".w.del").count() == 0
    assert page.inner_text("#find-cut") == f"Cut {n}"


def test_find_with_no_match_says_so_and_escape_clears_it(page, demo_url):
    open_demo(page, demo_url)
    page.keyboard.press("/")
    assert page.evaluate("document.activeElement.id") == "find-input"
    page.keyboard.type("zzzqq")
    assert page.locator("#find-none").is_visible()
    assert page.locator("#find-hits").is_hidden()
    page.keyboard.press("Escape")
    assert page.input_value("#find-input") == ""
    assert page.locator("#find-none").is_hidden()
    assert page.evaluate("document.activeElement.id") == "transcript"


def test_find_phrase_and_a_fixed_word_follow_the_edit(page, demo_url):
    open_demo(page, demo_url)
    page.fill("#find-input", "move around")
    assert page.locator(".w.hit").count() == 2
    page.fill("#find-input", "hypercard")
    before = page.locator(".w.hit").count()
    assert before >= 1
    page.locator(".w.hit").first.dblclick()
    page.keyboard.type("Stack")
    page.keyboard.press("Enter")
    assert page.locator(".w.hit").count() == before - 1
