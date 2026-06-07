import inspect
import io

import pypdf
import pytest
from pypdf.generic import NameObject

import acroforge as af
from acroforge.engine.backends import reportlab_pypdf
from acroforge.models import FieldSpec, FieldType
from tests.test_engine_text_checkbox import _blank_pdf


def _checkbox_with_on_state(name: str, on: str) -> bytes:
    """An acroforge checkbox whose /AP /N on-state key is `on` (e.g. "/On")."""
    built = af.build(
        _blank_pdf(),
        [FieldSpec(type=FieldType.CHECKBOX, page=0, rect=(100, 700, 130, 730), name=name)],
    )
    w = pypdf.PdfWriter()
    w.append(pypdf.PdfReader(io.BytesIO(built)))
    widget = [
        a.get_object() for a in w.pages[0]["/Annots"] if a.get_object().get("/T") == name
    ][0]
    apn = widget["/AP"]["/N"]
    yes = apn[NameObject("/Yes")]
    del apn[NameObject("/Yes")]
    apn[NameObject(on)] = yes
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def _offset_origin_pdf() -> bytes:
    """A 1-page PDF whose MediaBox lower-left is non-zero: [36 36 648 828]."""
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.drawString(100, 100, "base")
    c.showPage()
    c.save()
    w = pypdf.PdfWriter()
    w.append(pypdf.PdfReader(io.BytesIO(buf.getvalue())))
    pg = w.pages[0]
    pg.mediabox.lower_left = (36, 36)
    pg.mediabox.upper_right = (648, 828)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


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


# FIX F — non-zero MediaBox origin: field lands at the correct visual location
def test_field_on_offset_origin_mediabox_renders_in_place(tmp_path):
    from harness.diff import png_mismatch_ratio
    from harness.render_pdfium import render_pdfium
    from PIL import Image, ImageChops

    base = _offset_origin_pdf()
    rect = (100.0, 700.0, 130.0, 730.0)
    built = af.fill(
        af.build(base, [FieldSpec(type=FieldType.CHECKBOX, page=0, rect=rect, name="cb")]),
        {"cb": True},
    )

    # The widget /Rect must equal the requested rect (page coordinate space).
    r = pypdf.PdfReader(io.BytesIO(built))
    widget = [
        a.get_object() for a in r.pages[0]["/Annots"] if a.get_object().get("/T") == "cb"
    ][0]
    assert tuple(float(v) for v in widget["/Rect"]) == rect

    # The field must add visible ink versus the blank base, in the expected region.
    base_pdf = tmp_path / "base.pdf"
    built_pdf = tmp_path / "built.pdf"
    base_pdf.write_bytes(base)
    built_pdf.write_bytes(built)
    pa = render_pdfium(str(base_pdf), tmp_path / "base.png", scale=2.0)
    pb = render_pdfium(str(built_pdf), tmp_path / "built.png", scale=2.0)
    assert png_mismatch_ratio(pa, pb) > 0.0  # ink appeared somewhere

    # Expected pixel region: rect minus MediaBox origin (36,36), y from page top.
    # box = [36 36 648 828] -> w=612 h=792; scale 2.0.
    x0_px = int((rect[0] - 36) * 2)
    x1_px = int((rect[2] - 36) * 2)
    top_px = int((828 - rect[3]) * 2)
    bot_px = int((828 - rect[1]) * 2)
    diff = ImageChops.difference(
        Image.open(pa).convert("RGB"), Image.open(pb).convert("RGB")
    )
    bbox = diff.getbbox()
    assert bbox is not None
    bx0, by0, bx1, by1 = bbox
    # All ink falls inside the expected checkbox region (no offset bug).
    assert x0_px - 2 <= bx0 and bx1 <= x1_px + 2
    assert top_px - 2 <= by0 and by1 <= bot_px + 2


# FIX D — use pypdf public root_object, not the private _root_object
def test_engine_uses_public_root_object():
    # The public attribute exists on this pinned pypdf version.
    assert hasattr(pypdf.PdfWriter(), "root_object")
    # The engine source no longer reaches into the private attribute.
    src = inspect.getsource(reportlab_pypdf)
    assert "_root_object" not in src
    assert "writer.root_object" in src


# FIX G — fill() checks a checkbox using its actual /AP /N on-state name
def test_fill_true_uses_actual_on_state():
    pdf = _checkbox_with_on_state("cb", "/On")
    filled = af.fill(pdf, {"cb": True})
    r = pypdf.PdfReader(io.BytesIO(filled))
    f = r.get_fields() or {}
    assert f["cb"]["/V"] == "/On"  # not the hard-coded /Yes
    widget = [
        a.get_object() for a in r.pages[0]["/Annots"] if a.get_object().get("/T") == "cb"
    ][0]
    assert widget["/AS"] == "/On"


def test_fill_true_keeps_default_yes_on_state():
    built = af.build(
        _blank_pdf(),
        [FieldSpec(type=FieldType.CHECKBOX, page=0, rect=(100, 700, 130, 730), name="cb")],
    )
    filled = af.fill(built, {"cb": True})
    f = pypdf.PdfReader(io.BytesIO(filled)).get_fields() or {}
    assert f["cb"]["/V"] == "/Yes"
