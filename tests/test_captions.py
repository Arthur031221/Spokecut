from conftest import make_project

from spokecut import ass, captions
from spokecut import timeline as tl
from spokecut.captions import CapWord
from spokecut.project import DEFAULT_CAPTION, EditState


def words(*items):
    return [CapWord(t, s, e) for t, s, e in items]


def test_chunks_break_on_sentence_end():
    out = captions.chunk_words(words(("Hi.", 0, 0.3), ("Then", 0.4, 0.7), ("go", 0.8, 1.0)), "en")
    assert [c.text() for c in out] == ["Hi.", "Then go"]


def test_chunks_break_on_long_gap():
    out = captions.chunk_words(words(("a", 0, 0.3), ("b", 2.0, 2.3)), "en")
    assert len(out) == 2


def test_chunks_respect_the_word_limit():
    items = [(f"w{i}", i * 0.3, i * 0.3 + 0.2) for i in range(15)]
    out = captions.chunk_words(words(*items), "en", max_chars=200, max_words=5)
    assert [len(c.words) for c in out] == [5, 5, 5]


def test_chunks_respect_the_character_limit():
    items = [("abcdefgh", i * 0.3, i * 0.3 + 0.2) for i in range(6)]
    out = captions.chunk_words(words(*items), "en", max_chars=20)
    assert all(len(c.text()) <= 20 for c in out)


def test_cjk_chunks_join_without_spaces():
    out = captions.chunk_words(words(("你好", 0, 0.3), ("世界", 0.4, 0.7)), "zh")
    assert out[0].text() == "你好世界"


def test_srt_and_vtt_timestamps():
    out = captions.chunk_words(words(("Hi", 3661.5, 3662.25)), "en")
    assert "01:01:01,500 --> 01:01:02,250" in captions.to_srt(out)
    assert captions.to_vtt(out).startswith("WEBVTT")
    assert "01:01:01.500 --> 01:01:02.250" in captions.to_vtt(out)


def test_kept_words_skip_deleted_and_move_to_output_time():
    p = make_project()
    p.state = EditState(deleted=[1, 2])
    keeps, segs = tl.plan(p)
    kept = captions.kept_words(p, segs)
    assert len(kept) == len(p.words) - 2
    assert kept[0].text == "So"
    assert kept[1].start < p.words[3].start


def test_edited_text_replaces_the_word():
    p = make_project()
    p.state = EditState(edits={0: "Thus"})
    _, segs = tl.plan(p)
    assert captions.kept_words(p, segs)[0].text == "Thus"


def test_emptied_edit_removes_the_word():
    p = make_project()
    p.state = EditState(edits={0: "  "})
    _, segs = tl.plan(p)
    assert len(captions.kept_words(p, segs)) == len(p.words) - 1


def test_ass_has_every_style_and_valid_colours():
    chunks = captions.chunk_words(words(("Hello", 0, 0.4), ("there", 0.5, 0.9)), "en")
    for style in ass.STYLES:
        text = ass.build_ass(chunks, 1280, 720, {**DEFAULT_CAPTION, "style": style})
        assert "[Events]" in text and "Dialogue:" in text
    assert ass.ass_color("#FFB224") == "&H0024B2FF"
