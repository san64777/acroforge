from acroforge.detect.geometry import Candidate
from acroforge.detect.grouping import group_checkboxes


def test_adjacent_checkboxes_group_into_one_set():
    cands = [
        Candidate("checkbox", (100, 700, 112, 712), 0.5),
        Candidate("checkbox", (130, 700, 142, 712), 0.5),
        Candidate("checkbox", (100, 500, 112, 512), 0.5),
    ]
    groups = group_checkboxes(cands)
    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 2]


def test_single_checkbox_is_its_own_group():
    cands = [Candidate("checkbox", (100, 700, 112, 712), 0.5)]
    assert [len(g) for g in group_checkboxes(cands)] == [1]


def test_far_apart_same_row_checkboxes_do_not_group():
    cands = [
        Candidate("checkbox", (100, 700, 112, 712), 0.5),
        Candidate("checkbox", (400, 700, 412, 712), 0.5),  # same row but big horizontal gap
    ]
    assert sorted(len(g) for g in group_checkboxes(cands)) == [1, 1]
