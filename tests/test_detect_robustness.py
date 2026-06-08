"""Detection must tolerate malformed pdfplumber geometry from real-world PDFs."""

from acroforge.detect.geometry import find_boxes, find_underlines, _vertical_segments


class _FakePage:
    def __init__(self, lines=None, edges=None, rects=None, width=612, height=792):
        self.lines = lines or []
        self.edges = edges or []
        self.rects = rects or []
        self.width = width
        self.height = height


def test_find_underlines_skips_objects_missing_coords():
    page = _FakePage(
        lines=[{"x0": 100, "x1": 300, "y0": 700, "y1": 700}],  # valid underline
        edges=[{"orientation": "v"}],                            # missing y0/y1
        rects=[{"x0": 0}],                                       # missing keys
    )
    cands = find_underlines(page)            # must not raise
    assert len(cands) == 1                    # valid underline still found


def test_find_underlines_rejects_full_width_separator():
    # a near-full-width horizontal rule is a decorative separator, not a field
    page = _FakePage(lines=[{"x0": 10, "x1": 600, "y0": 400, "y1": 400}])  # ~96% of 612pt
    assert find_underlines(page) == []


def test_find_underlines_rejects_margin_rule():
    # a rule in the top page margin is a header separator, not a field
    page = _FakePage(lines=[{"x0": 100, "x1": 300, "y0": 785, "y1": 785}])  # top 4% of 792pt
    assert find_underlines(page) == []


def test_find_underlines_dedups_near_coincident_lines():
    # a line plus its near-coincident edge (same field drawn twice) -> one candidate
    page = _FakePage(
        lines=[{"x0": 100, "x1": 300, "y0": 400, "y1": 400}],
        edges=[{"orientation": "h", "x0": 100, "x1": 300, "y0": 401, "y1": 401}],
    )
    assert len(find_underlines(page)) == 1


def test_vertical_segments_skips_objects_missing_coords():
    page = _FakePage(edges=[{"orientation": "v"}], rects=[{"x0": 1}], lines=[{}])
    assert _vertical_segments(page) == []     # no crash, nothing usable


def test_find_boxes_skips_objects_missing_coords():
    page = _FakePage(rects=[{"x0": 1}, {"x0": 100, "x1": 112, "y0": 700, "y1": 712}])
    cands = find_boxes(page)                  # must not raise
    assert len(cands) == 1                     # the valid 12x12 box


def test_find_glyph_checkboxes_detects_ballot_glyphs():
    from acroforge.detect.geometry import find_glyph_checkboxes

    page = _FakePage()
    page.chars = [
        {"text": "☐", "x0": 100, "x1": 110, "y0": 700, "y1": 710},
        {"text": "☑", "x0": 140, "x1": 150, "y0": 700, "y1": 710},
        {"text": "A", "x0": 160, "x1": 170, "y0": 700, "y1": 710},  # not a checkbox
    ]
    cands = find_glyph_checkboxes(page)
    assert len(cands) == 2
    assert all(c.kind == "checkbox" for c in cands)
