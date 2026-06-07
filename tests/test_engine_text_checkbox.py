import io

import pypdf

from acroforge.engine.base import Writer, default_writer
from acroforge.models import FieldSpec, FieldType


def test_default_writer_satisfies_protocol():
    w = default_writer()
    assert isinstance(w, Writer)
    for meth in ("create_fields", "fill", "flatten"):
        assert callable(getattr(w, meth))


def _blank_pdf(w=612, h=792) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.drawString(72, 72, "base")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_create_text_and_checkbox_registers_fields():
    w = default_writer()
    fields = [
        FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 700, 300, 718), name="full_name"),
        FieldSpec(type=FieldType.CHECKBOX, page=0, rect=(100, 670, 114, 684), name="agree"),
    ]
    out = w.create_fields(_blank_pdf(), fields)
    r = pypdf.PdfReader(io.BytesIO(out))
    f = r.get_fields() or {}
    assert "full_name" in f and "agree" in f


def test_created_fields_have_appearance_streams():
    w = default_writer()
    out = w.create_fields(
        _blank_pdf(), [FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 700, 300, 718), name="x")]
    )
    r = pypdf.PdfReader(io.BytesIO(out))
    annots = r.pages[0]["/Annots"]
    widget = [a.get_object() for a in annots if a.get_object().get("/T") == "x"][0]
    assert "/AP" in widget
