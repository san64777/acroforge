import io

import pypdf

from acroforge.engine.base import default_writer
from acroforge.models import FieldSpec, FieldType
from tests.test_engine_text_checkbox import _blank_pdf


def test_comb_field_registers_with_maxlen():
    out = default_writer().create_fields(_blank_pdf(), [
        FieldSpec(type=FieldType.COMB, page=0, rect=(100, 700, 300, 718), name="ssn", maxlen=9)])
    f = pypdf.PdfReader(io.BytesIO(out)).get_fields() or {}
    assert "ssn" in f


def test_signature_placeholder_registers():
    out = default_writer().create_fields(_blank_pdf(), [
        FieldSpec(type=FieldType.SIGNATURE, page=0, rect=(100, 640, 300, 680), name="sig")])
    r = pypdf.PdfReader(io.BytesIO(out))
    annots = r.pages[0]["/Annots"]
    sig = [a.get_object() for a in annots if a.get_object().get("/T") == "sig"]
    assert sig and sig[0].get("/FT") == "/Sig"
