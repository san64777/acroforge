import io

import pdfplumber
from reportlab.pdfgen import canvas

from acroforge.detect.geometry import Candidate, find_table_cells


def _grid_pdf() -> bytes:
    """A 2x2 table: outer rect + one vertical + one horizontal divider, labeled cells."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.setLineWidth(1)
    c.rect(100, 600, 400, 100)  # outer box: x 100..500, y 600..700
    c.line(300, 600, 300, 700)  # vertical divider at x=300
    c.line(100, 650, 500, 650)  # horizontal divider at y=650
    c.setFont("Helvetica", 9)
    c.drawString(110, 680, "First Name")
    c.drawString(310, 680, "Last Name")
    c.drawString(110, 630, "City")
    c.drawString(310, 630, "Zip")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_find_table_cells_returns_text_candidates_for_each_cell():
    with pdfplumber.open(io.BytesIO(_grid_pdf())) as pdf:
        results = find_table_cells(pdf.pages[0])
    # >= 3 cells (a 2x2 grid yields ~4)
    assert len(results) >= 3
    for cand, label in results:
        assert isinstance(cand, Candidate)
        assert cand.kind == "text"
        # valid bottom-up rect
        assert cand.rect[2] > cand.rect[0]
        assert cand.rect[3] > cand.rect[1]
        assert 0.0 < cand.confidence <= 1.0
        assert isinstance(label, str)


def test_find_table_cells_derives_label_slug_from_cell_text():
    with pdfplumber.open(io.BytesIO(_grid_pdf())) as pdf:
        results = find_table_cells(pdf.pages[0])
    labels = {label for _cand, label in results}
    expected = {"first_name", "last_name", "city", "zip"}
    # at least one label derived from the cell text matches what we drew
    assert labels & expected
