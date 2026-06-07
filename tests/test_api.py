import io

import pypdf

import acroforge as af
from tests.test_engine_text_checkbox import _blank_pdf


def test_build_fill_flatten_via_public_api():
    fields = [af.FieldSpec(type=af.FieldType.TEXT, page=0, rect=(100, 700, 300, 718), name="name")]
    doc = af.build(_blank_pdf(), fields)
    doc = af.fill(doc, {"name": "Asha"})
    assert pypdf.PdfReader(io.BytesIO(doc)).get_fields()["name"]["/V"] == "Asha"
    flat = af.flatten(doc)
    assert not (pypdf.PdfReader(io.BytesIO(flat)).get_fields() or {})
