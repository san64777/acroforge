import io

import pdfplumber
from reportlab.pdfgen import canvas

from acroforge.detect.geometry import Candidate, find_underlines


def _pdf_with_underlines() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.setLineWidth(1)
    c.line(100, 700, 300, 700)
    c.line(100, 660, 250, 660)
    c.drawString(100, 600, "ignore short")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_find_underlines_returns_text_candidates_above_each_line():
    with pdfplumber.open(io.BytesIO(_pdf_with_underlines())) as pdf:
        cands = find_underlines(pdf.pages[0])
    assert len(cands) == 2
    assert all(isinstance(c, Candidate) and c.kind == "text" for c in cands)
    xs = sorted(round(c.rect[0]) for c in cands)
    assert xs == [100, 100]
    assert all(c.rect[3] > c.rect[1] for c in cands)
    assert all(0.0 < c.confidence <= 1.0 for c in cands)


def _pdf_with_boxes() -> bytes:
    import io

    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.rect(100, 700, 12, 12)
    c.rect(140, 700, 12, 12)
    c.rect(100, 500, 300, 80)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_find_boxes_returns_small_square_checkbox_candidates():
    import io

    import pdfplumber

    from acroforge.detect.geometry import find_boxes

    with pdfplumber.open(io.BytesIO(_pdf_with_boxes())) as pdf:
        cands = find_boxes(pdf.pages[0])
    assert len(cands) == 2
    assert all(c.kind == "checkbox" for c in cands)
    assert all(8 <= (c.rect[2] - c.rect[0]) <= 20 for c in cands)


def _pdf_with_table_and_underline() -> bytes:
    import io

    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.rect(100, 600, 200, 20)        # a closed box (cell): top/bottom edges bounded by L/R verticals
    c.line(100, 700, 300, 700)       # a bare underline with OPEN ends
    c.showPage()
    c.save()
    return buf.getvalue()


def test_find_underlines_skips_box_edges_keeps_bare_underline():
    import io

    import pdfplumber

    from acroforge.detect.geometry import find_underlines

    with pdfplumber.open(io.BytesIO(_pdf_with_table_and_underline())) as pdf:
        cands = find_underlines(pdf.pages[0])
    ys = sorted(round(c.rect[1]) for c in cands)
    assert ys == [700]    # box top/bottom edges filtered; bare underline survives
