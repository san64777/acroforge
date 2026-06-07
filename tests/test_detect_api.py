import io
import pypdf
from reportlab.pdfgen import canvas
import acroforge as af


def _form_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.drawString(100, 702, "Name")
    c.line(140, 700, 360, 700)
    c.rect(100, 660, 12, 12)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_detect_returns_manifest():
    m = af.detect(_form_pdf())
    assert len(m.fields) >= 2


def test_make_fillable_produces_real_fields():
    out = af.make_fillable(_form_pdf())
    flds = pypdf.PdfReader(io.BytesIO(out)).get_fields() or {}
    assert len(flds) >= 2
