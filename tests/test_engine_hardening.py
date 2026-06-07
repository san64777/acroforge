import inspect
import io

import pypdf
import pytest

import acroforge as af
from acroforge.engine.backends import reportlab_pypdf
from acroforge.models import FieldSpec, FieldType
from tests.test_engine_text_checkbox import _blank_pdf


# FIX A — fill() must raise on unknown field names
def test_fill_unknown_field_raises():
    built = af.build(
        _blank_pdf(),
        [FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 700, 300, 718), name="nm")],
    )
    with pytest.raises(ValueError, match="fields not found"):
        af.fill(built, {"ghost": "x"})


def test_fill_known_field_still_works():
    built = af.build(
        _blank_pdf(),
        [FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 700, 300, 718), name="nm")],
    )
    filled = af.fill(built, {"nm": "ok"})
    f = pypdf.PdfReader(io.BytesIO(filled)).get_fields() or {}
    assert f["nm"]["/V"] == "ok"


# FIX B — create_fields rejects out-of-range page index
def test_create_fields_out_of_range_page_raises():
    spec = FieldSpec(type=FieldType.TEXT, page=3, rect=(100, 700, 300, 718), name="oops")
    with pytest.raises(ValueError, match="oops"):
        af.build(_blank_pdf(), [spec])


# FIX C — empty fields list is a no-op (no /AcroForm)
def test_empty_fields_list_is_noop():
    out = af.build(_blank_pdf(), [])
    r = pypdf.PdfReader(io.BytesIO(out))
    assert "/AcroForm" not in r.trailer["/Root"]
    assert not (r.get_fields() or {})
    assert len(r.pages) == 1  # still opens


# FIX E — radio kid widgets must be registered as real indirect objects
def test_radio_kid_widgets_are_indirect_objects():
    fields = [
        FieldSpec(type=FieldType.RADIO, page=0, rect=(100, 700, 114, 714),
                  name="sex", export_value="M"),
        FieldSpec(type=FieldType.RADIO, page=0, rect=(140, 700, 154, 714),
                  name="sex", export_value="F"),
    ]
    out = af.build(_blank_pdf(), fields)
    r = pypdf.PdfReader(io.BytesIO(out))
    acro = r.trailer["/Root"]["/AcroForm"].get_object()
    parent = acro["/Fields"][0].get_object()
    kids = parent["/Kids"]
    annots = r.pages[0]["/Annots"]
    annot_ids = {(a.idnum, a.generation) for a in annots}
    assert len(kids) == 2
    for kid in kids:
        assert kid is not None
        assert kid.indirect_reference is not None
        assert (kid.idnum, kid.generation) in annot_ids  # kid is on the page
        assert kid.get_object()["/Subtype"] == "/Widget"


# FIX D — use pypdf public root_object, not the private _root_object
def test_engine_uses_public_root_object():
    # The public attribute exists on this pinned pypdf version.
    assert hasattr(pypdf.PdfWriter(), "root_object")
    # The engine source no longer reaches into the private attribute.
    src = inspect.getsource(reportlab_pypdf)
    assert "_root_object" not in src
    assert "writer.root_object" in src
