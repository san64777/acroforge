"""Detection must degrade gracefully: skip a scanned/bad page, complete the rest."""

import io
import pathlib
import warnings

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

import acroforge as af

FIX = pathlib.Path(__file__).parent / "fixtures"


def _vector_page() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.drawString(72, 700, "Name:")
    c.line(120, 698, 400, 698)
    c.showPage()
    c.save()
    return buf.getvalue()


def _mixed_pdf() -> bytes:
    # page 0: vector underline, page 1: real scanned (image-only) fixture, page 2: vector
    scanned = (FIX / "scanned_sample.pdf").read_bytes()
    w = PdfWriter()
    w.append(PdfReader(io.BytesIO(_vector_page())))
    w.append(PdfReader(io.BytesIO(scanned)))
    w.append(PdfReader(io.BytesIO(_vector_page())))
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def test_detect_skips_scanned_page_and_continues():
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        manifest = af.detect(_mixed_pdf())
    pages = {f.page for f in manifest.fields}
    assert 0 in pages and 2 in pages          # vector pages were detected
    assert 1 not in pages                      # the image-only page was skipped
    assert any("image-only" in str(w.message) for w in rec)


def test_make_fillable_does_not_refuse_mixed_doc():
    out = af.make_fillable(_mixed_pdf())       # used to raise ScannedPDFError
    assert isinstance(out, bytes) and out[:5] == b"%PDF-"


def test_detect_all_scanned_still_refuses():
    with pytest.raises(af.ScannedPDFError):
        af.detect((FIX / "scanned_sample.pdf").read_bytes())
