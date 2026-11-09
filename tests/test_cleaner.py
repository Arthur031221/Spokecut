from conftest import make_project

from spokecut import cleaner
from spokecut.project import Word


def w(*texts):
    return [Word(t, i * 0.4, i * 0.4 + 0.3) for i, t in enumerate(texts)]


def test_normalize_strips_punctuation_and_case():
    assert cleaner.normalize("Um,") == "um"
    assert cleaner.normalize("Don’t.") == "don't"


def test_fillers_in_english():
    hits = cleaner.find_fillers(w("So", "um", "yes", "uh,"), "en")
    assert [h["words"] for h in hits] == [[1], [3]]
    assert all(h["default"] for h in hits)


def test_unknown_language_still_finds_verbatim_tags():
    assert cleaner.find_fillers(w("um", "hello"), "xx")[0]["words"] == [0]


def test_loose_phrases_are_not_on_by_default():
    hits = cleaner.find_fillers(w("you", "know", "it"), "en", loose=True)
    assert hits[0]["kind"] == "loose" and hits[0]["default"] is False and hits[0]["words"] == [0, 1]


def test_loose_does_not_overlap_a_filler():
    hits = cleaner.find_fillers(w("sort", "um", "of"), "en", loose=True)
    assert [h["kind"] for h in hits] == ["filler"]


def test_repeat_flags_the_first_take():
    hits = cleaner.find_repeats(w("I", "want", "to", "to", "go"), "en")
    assert [h["words"] for h in hits] == [[2]]


def test_repeat_ignores_numbers_and_long_gaps():
    words = [Word("7", 0, 0.3), Word("7", 0.4, 0.7), Word("no", 1, 1.3), Word("no", 3, 3.3)]
    assert cleaner.find_repeats(words, "en") == []


def test_repeat_is_off_for_languages_without_spaces():
    assert cleaner.find_repeats(w("好", "好"), "zh") == []


def test_verbatim_tags_are_split_from_punctuation():
    assert cleaner.split_verbatim_tags(",[UH]the") == ["uh", "the"]
    parts = cleaner.split_verbatim_tags("so[UM]yes")
    assert parts == ["so", "um", "yes"]


def test_plain_text_is_not_split():
    assert cleaner.split_verbatim_tags("hello") == ["hello"]


def test_suggestions_are_sorted_by_position():
    p = make_project()
    hits = cleaner.suggestions(p.words, "en")
    assert [h["words"][0] for h in hits] == sorted(h["words"][0] for h in hits)
    assert {h["kind"] for h in hits} >= {"filler", "repeat"}


def test_apply_cleanup_marks_defaults_only():
    p = make_project()
    p.suggestions = cleaner.suggestions(p.words, "en")
    state = cleaner.apply_cleanup(p, pause=0.7)
    assert 1 in state.deleted and 5 in state.deleted
    assert state.cut_gaps == [9, 17]
    assert state.pause["threshold"] == 0.7


def test_apply_cleanup_is_idempotent():
    p = make_project()
    p.suggestions = cleaner.suggestions(p.words, "en")
    a = list(cleaner.apply_cleanup(p, pause=0.7).deleted)
    b = list(cleaner.apply_cleanup(p, pause=0.7).deleted)
    assert a == b
