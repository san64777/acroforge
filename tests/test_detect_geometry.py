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
