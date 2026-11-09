from conftest import make_project

from spokecut import timeline as tl
from spokecut.project import EditState


def test_pause_cut_leaves_keep_seconds():
    assert tl.pause_cut(1.0, 2.0, 0.25) == (1.125, 1.875)


def test_pause_cut_ignores_short_pause():
    assert tl.pause_cut(1.0, 1.2, 0.25) is None
    assert tl.pause_cut(1.0, 1.25, 0.25) is None


def test_find_pauses(project):
    gaps = tl.find_pauses(project.words, 0.7)
    assert gaps == [9, 17]


def test_merge_joins_touching_and_overlapping():
    assert tl.merge([(3, 4), (0, 1), (1, 2), (1.5, 2.5)]) == [(0, 2.5), (3, 4)]


def test_merge_drops_empty():
    assert tl.merge([(1, 1), (2, 2.0000001)]) == []


def test_deleted_run_cuts_between_snap_points(project):
    cuts = tl.cut_ranges(project.words, project.snaps, [3, 4], [], 0.25, project.media.duration)
    assert cuts == [(project.snaps[3], project.snaps[5])]


def test_deleting_first_word_cuts_from_zero(project):
    cuts = tl.cut_ranges(project.words, project.snaps, [0], [], 0.25, 20.0)
    assert cuts == [(0.0, project.snaps[1])]


def test_deleting_last_word_cuts_to_the_end(project):
    last = len(project.words) - 1
    cuts = tl.cut_ranges(project.words, project.snaps, [last], [], 0.25, 20.0)
    assert cuts == [(project.snaps[last], 20.0)]


def test_separate_runs_stay_separate(project):
    cuts = tl.cut_ranges(project.words, project.snaps, [2, 5], [], 0.25, 20.0)
    assert len(cuts) == 2


def test_out_of_range_indices_are_ignored(project):
    assert tl.cut_ranges(project.words, project.snaps, [-1, 999], [0, 999], 0.25, 20.0) == []


def test_cut_gap_and_deleted_word_merge(project):
    g = 9
    cuts = tl.cut_ranges(project.words, project.snaps, [g], [g], 0.25, 20.0)
    assert len(cuts) == 1


def test_snap_to_frames_rounds_to_frame_grid():
    out = tl.snap_to_frames([(0.51, 1.02)], 30)
    assert out == [(15 / 30, 31 / 30)]


def test_snap_to_frames_drops_sub_frame_ranges():
    assert tl.snap_to_frames([(1.0, 1.01)], 30) == []


def test_snap_to_frames_without_video_is_a_noop():
    assert tl.snap_to_frames([(0.51, 1.02)], 0) == [(0.51, 1.02)]


def test_keep_ranges_is_the_complement():
    assert tl.keep_ranges([(1, 2), (4, 5)], 6) == [(0, 1), (2, 4), (5, 6)]
    assert tl.keep_ranges([(0, 2)], 6) == [(2, 6)]
    assert tl.keep_ranges([(0, 6)], 6) == []


def test_segments_are_contiguous_on_the_output(project):
    keeps, segs = tl.plan(project, _with(project, deleted=[3, 4], cut_gaps=[9]))
    assert segs[0].out_start == 0
    for a, b in zip(segs, segs[1:], strict=False):
        assert abs(a.out_end - b.out_start) < 1e-9
    assert abs(tl.output_duration(keeps) - segs[-1].out_end) < 1e-9


def test_plan_output_is_shorter_by_the_cut_time(project):
    state = _with(project, deleted=[3, 4], cut_gaps=[9, 17])
    keeps, _ = tl.plan(project, state)
    assert tl.output_duration(keeps) < project.media.duration - 1.0


def test_to_output_maps_kept_time_and_hides_cut_time(project):
    keeps, segs = tl.plan(project, _with(project, deleted=[3, 4]))
    cut_mid = (project.snaps[3] + project.snaps[5]) / 2
    assert tl.to_output(segs, cut_mid) is None
    assert tl.to_output(segs, 0.1) == 0.1
    after = project.snaps[5] + 0.5
    assert abs(tl.to_output(segs, after) - (after - (project.snaps[5] - project.snaps[3]))) < 0.05


def test_audio_only_projects_are_not_frame_snapped():
    p = make_project(has_video=False)
    keeps, _ = tl.plan(p, _with(p, deleted=[3]))
    assert keeps[0][1] == p.snaps[3]


def _with(project, **kw):
    return EditState(**kw)
