import io

import pypdf

from acroforge.engine.base import default_writer
from acroforge.models import FieldSpec, FieldType
from tests.test_engine_text_checkbox import _blank_pdf


def test_radio_group_registers_single_named_field():
    fields = [
        FieldSpec(type=FieldType.RADIO, page=0, rect=(100, 700, 114, 714), name="sex", export_value="M"),
        FieldSpec(type=FieldType.RADIO, page=0, rect=(140, 700, 154, 714), name="sex", export_value="F"),
    ]
    out = default_writer().create_fields(_blank_pdf(), fields)
    r = pypdf.PdfReader(io.BytesIO(out))
    f = r.get_fields() or {}
    assert "sex" in f
    # both radio widgets should be present on the page as Btn widgets
    annots = [a.get_object() for a in r.pages[0]["/Annots"]]
    btn_widgets = [
        a
        for a in annots
        if a.get("/FT") == "/Btn" or (a.get("/Parent") and a.get("/Subtype") == "/Widget")
    ]
    assert len(btn_widgets) >= 2
