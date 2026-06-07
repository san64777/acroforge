import io

import pytest
from reportlab.pdfgen import canvas

from acroforge.detect.manifest import detect_manifest
from acroforge.models import FieldType, FormManifest, ScannedPDFError


def _form_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.drawString(100, 702, "Name")
    c.line(140, 700, 360, 700)
    c.rect(100, 660, 12, 12)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_detect_manifest_finds_text_and_checkbox():
    m = detect_manifest(_form_pdf())
    assert isinstance(m, FormManifest)
    kinds = {f.type for f in m.fields}
    assert FieldType.TEXT in kinds and FieldType.CHECKBOX in kinds
    assert all(0.0 < f.confidence < 1.0 for f in m.fields)
    assert all(f.name for f in m.fields)


def test_detect_manifest_text_field_named_from_label():
    m = detect_manifest(_form_pdf())
    text_fields = [f for f in m.fields if f.type == FieldType.TEXT]
    # the underline is to the right of the "Name" label on the same row → name should derive from it
    assert any(f.name == "name" for f in text_fields)


def test_detect_manifest_refuses_scanned():
    with pytest.raises(ScannedPDFError):
        detect_manifest("tests/fixtures/scanned_sample.pdf")
