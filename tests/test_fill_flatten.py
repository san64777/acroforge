import io

import pypdf

from acroforge.engine.base import default_writer
from acroforge.models import FieldSpec, FieldType
from tests.test_engine_text_checkbox import _blank_pdf


def test_fill_sets_text_value_roundtrip():
    w = default_writer()
    built = w.create_fields(
        _blank_pdf(),
        [FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 700, 300, 718), name="full_name")],
    )
    filled = w.fill(built, {"full_name": "Asha Rao"})
    f = pypdf.PdfReader(io.BytesIO(filled)).get_fields() or {}
    assert f["full_name"]["/V"] == "Asha Rao"


def test_flatten_removes_widgets_but_keeps_content():
    w = default_writer()
    built = w.create_fields(
        _blank_pdf(),
        [FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 700, 300, 718), name="x")],
    )
    filled = w.fill(built, {"x": "BAKED"})
    flat = w.flatten(filled)
    r = pypdf.PdfReader(io.BytesIO(flat))
    assert not (r.get_fields() or {})
    annots = r.pages[0].get("/Annots") or []
    widgets = [a for a in annots if a.get_object().get("/Subtype") == "/Widget"]
    assert widgets == []
