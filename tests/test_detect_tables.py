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


def _shrink_pdf() -> bytes:
    """A single cell with a label at the TOP and empty space below it.

    Target cell: x 100..500, y 620..660 (bottom-up, 40pt tall). A short 8pt
    filler row below (612..620) gives pdfplumber a detectable table grid; the
    filler is too short to pass the cell-size filter. Label "First Name" is drawn
    near the top of the target cell, leaving the writable area below empty.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.setLineWidth(1)
    c.rect(100, 620, 400, 40)  # target cell: x 100..500, y 620..660
    c.line(100, 612, 500, 612)  # short filler row below -> makes a 2-row grid
    c.line(100, 620, 100, 612)
    c.line(500, 620, 500, 612)
    c.setFont("Helvetica", 9)
    c.drawString(110, 650, "First Name")  # near the TOP edge (y=660)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_find_table_cells_shrinks_below_top_label():
    """The field rect must sit BELOW the label line, not on top of it."""
    with pdfplumber.open(io.BytesIO(_shrink_pdf())) as pdf:
        page = pdf.pages[0]
        height = float(page.height)
        results = find_table_cells(page)
    assert results, "expected at least one field"
    # Locate the label's bottom-up y-band by reading the word's coords.
    with pdfplumber.open(io.BytesIO(_shrink_pdf())) as pdf:
        words = pdf.pages[0].extract_words()
    label = next(w for w in words if "First" in w["text"] or "Name" in w["text"])
    label_y0_bottomup = height - float(label["bottom"])  # lower edge of label, bottom-up
    # Every resulting field's top edge (y1) must be at/below the label's bottom.
    for cand, _label in results:
        assert cand.rect[3] <= label_y0_bottomup + 1.0, (
            f"field top {cand.rect[3]} should be below label bottom {label_y0_bottomup}"
        )


def _split_pdf() -> bytes:
    """A single wide cell with three well-separated labels on one line.

    Target cell: x 100..520, y 620..660 (40pt tall). A short filler row below
    makes the grid detectable without itself passing the size filter.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.setLineWidth(1)
    c.rect(100, 620, 420, 40)  # target cell: x 100..520, y 620..660
    c.line(100, 612, 520, 612)  # short filler row -> detectable grid
    c.line(100, 620, 100, 612)
    c.line(520, 620, 520, 612)
    c.setFont("Helvetica", 9)
    # Multi-word label groups: small intra-group gaps, large inter-group gaps -
    # the typical credentialing-form "LAST NAME   FIRST NAME   MIDDLE INITIAL" row.
    c.drawString(110, 650, "LAST NAME")
    c.drawString(320, 650, "FIRST NAME")
    c.drawString(460, 650, "MIDDLE INITIAL")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_find_table_cells_splits_multi_label_cell():
    """A wide cell with three separated labels yields three fields."""
    with pdfplumber.open(io.BytesIO(_split_pdf())) as pdf:
        results = find_table_cells(pdf.pages[0])
    assert len(results) == 3, f"expected 3 split fields, got {len(results)}"
    by_left = sorted(results, key=lambda r: r[0].rect[0])
    slugs = [label for _cand, label in by_left]
    assert "last_name" in slugs[0]
    assert "first" in slugs[1]
    assert "middle" in slugs[2]
    # x-ranges must be left / center / right and non-overlapping in order.
    lefts = [c.rect[0] for c, _ in by_left]
    assert lefts[0] < lefts[1] < lefts[2]


def _header_pdf() -> bytes:
    """A full-width cell with a single large bold heading and no value.

    Body-size (9pt) filler text is drawn elsewhere on the page so the page body
    font size is small; the 16pt bold heading is then clearly larger than body,
    triggering the header-skip rule. A short filler row makes the grid detectable.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.setLineWidth(1)
    # Full-width header cell: x 10..602 (> 0.8 * 612), y 620..660.
    c.rect(10, 620, 592, 40)
    c.line(10, 612, 602, 612)  # short filler row -> detectable grid
    c.line(10, 620, 10, 612)
    c.line(602, 620, 602, 612)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20, 632, "Section I")
    # Body-size text elsewhere establishes a small page body font size.
    c.setFont("Helvetica", 9)
    for i in range(40):
        c.drawString(40, 100 + i * 5, "body filler text line content here")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_find_table_cells_skips_section_header():
    """A large bold full-width heading cell produces 0 fields."""
    with pdfplumber.open(io.BytesIO(_header_pdf())) as pdf:
        results = find_table_cells(pdf.pages[0])
    assert results == [], f"expected no fields for a header cell, got {results}"
