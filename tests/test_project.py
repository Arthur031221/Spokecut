import json

import pytest
from conftest import make_project

from spokecut.project import EditState, Project, load_project, save_project, sidecar_path


def test_round_trip_keeps_everything(tmp_path):
    p = make_project()
    p.state = EditState(deleted=[3, 1], cut_gaps=[9], edits={0: "Thus"})
    p.suggestions = [{"kind": "filler", "words": [1], "text": "um", "default": True}]
    path = tmp_path / "talk.mp4.spokecut.json"
    save_project(p, path)
    back = load_project(path)
    assert back.to_json() == p.to_json()
    assert back.state.deleted == [3, 1] or sorted(back.state.deleted) == [1, 3]
    assert back.state.edits == {0: "Thus"}


def test_state_json_is_sorted_and_deduplicated():
    s = EditState(deleted=[5, 1, 5], cut_gaps=[9, 9]).to_json()
    assert s["deleted"] == [1, 5] and s["cutGaps"] == [9]


def test_missing_state_gets_defaults():
    s = EditState.from_json(None)
    assert s.pause["keep"] == 0.25 and s.caption["style"] == "highlight"


def test_partial_state_is_filled_in():
    s = EditState.from_json({"pause": {"keep": 0.5}, "caption": {"style": "pop"}})
    assert s.pause == {"threshold": 0.7, "keep": 0.5}
    assert s.caption["style"] == "pop" and s.caption["accent"] == "#FFB224"


def test_unknown_version_is_rejected():
    d = make_project().to_json()
    d["version"] = 99
    with pytest.raises(ValueError, match="version"):
        Project.from_json(d)


def test_snap_count_is_checked():
    d = make_project().to_json()
    d["snaps"] = d["snaps"][:-1]
    with pytest.raises(ValueError, match="snaps"):
        Project.from_json(d)


def test_sidecar_sits_next_to_the_video(tmp_path):
    assert sidecar_path(tmp_path / "talk.mp4") == tmp_path / "talk.mp4.spokecut.json"


def test_saved_file_is_plain_json(tmp_path):
    save_project(make_project(), tmp_path / "p.json")
    assert json.loads((tmp_path / "p.json").read_text())["version"] == 1


def test_word_text_prefers_the_edit():
    p = make_project()
    p.state.edits[0] = " Thus "
    assert p.word_text(0) == "Thus" and p.word_text(1) == "um"
