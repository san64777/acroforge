"""Detection must tolerate malformed pdfplumber geometry from real-world PDFs."""

from acroforge.detect.geometry import find_boxes, find_underlines, _vertical_segments


class _FakePage:
    def __init__(self, lines=None, edges=None, rects=None):
        self.lines = lines or []
        self.edges = edges or []
        self.rects = rects or []


def test_find_underlines_skips_objects_missing_coords():
    page = _FakePage(
        lines=[{"x0": 100, "x1": 300, "y0": 700, "y1": 700}],  # valid underline
        edges=[{"orientation": "v"}],                            # missing y0/y1
        rects=[{"x0": 0}],                                       # missing keys
    )
    cands = find_underlines(page)            # must not raise
    assert len(cands) == 1                    # valid underline still found


def test_vertical_segments_skips_objects_missing_coords():
    page = _FakePage(edges=[{"orientation": "v"}], rects=[{"x0": 1}], lines=[{}])
    assert _vertical_segments(page) == []     # no crash, nothing usable


def test_find_boxes_skips_objects_missing_coords():
    page = _FakePage(rects=[{"x0": 1}, {"x0": 100, "x1": 112, "y0": 700, "y1": 712}])
    cands = find_boxes(page)                  # must not raise
    assert len(cands) == 1                     # the valid 12x12 box
