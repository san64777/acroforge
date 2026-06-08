"""Error-handling robustness: clear errors, no crashes/hangs, skip-and-continue."""

import io
import warnings

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    TextStringObject,
)

import acroforge as af
from acroforge.models import FieldSpec, FieldType
from tests.test_engine_text_checkbox import _blank_pdf


def test_fill_list_on_non_choice_raises_clear_error():
    # a list value aimed at a TEXT field must raise a clear acroforge error, not
    # leak a cryptic "ArrayObject has no attribute replace" from pypdf.
    built = af.build(_blank_pdf(), [FieldSpec(type=FieldType.TEXT, page=0,
                                              rect=(100, 700, 300, 718), name="t")])
    with pytest.raises(ValueError, match="multi-select"):
        af.fill(built, {"t": ["a", "b"]})


def test_flatten_no_fields_is_noop():
    out = af.flatten(_blank_pdf())             # used to raise a raw pypdf error
    assert isinstance(out, bytes) and out[:5] == b"%PDF-"


def _pdf_with_widgets(widgets) -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    page = w.pages[0]
    annots = ArrayObject()
    fields = ArrayObject()
    for d in widgets:
        d[NameObject("/P")] = page.indirect_reference
        ref = w._add_object(d)
        annots.append(ref)
        fields.append(ref)
    page[NameObject("/Annots")] = annots
    acro = DictionaryObject()
    acro[NameObject("/Fields")] = fields
    w.root_object[NameObject("/AcroForm")] = w._add_object(acro)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _text_widget(name, rect):
    d = DictionaryObject()
    d[NameObject("/Type")] = NameObject("/Annot")
    d[NameObject("/Subtype")] = NameObject("/Widget")
    d[NameObject("/FT")] = NameObject("/Tx")
    d[NameObject("/T")] = TextStringObject(name)
    d[NameObject("/Rect")] = ArrayObject([FloatObject(c) for c in rect])
    return d


def test_read_fields_skips_malformed_widget():
    good = _text_widget("good", (50, 700, 250, 718))
    bad = _text_widget("bad", (50, 660, 250, 678))
    # corrupt the bad widget's /Rect so float() coercion throws inside the parser
    bad[NameObject("/Rect")] = ArrayObject([TextStringObject(s) for s in ("x", "y", "z", "w")])
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        specs = af.read_fields(_pdf_with_widgets([good, bad]))
    assert "good" in {s.name for s in specs}    # the valid widget still recovered
    assert any("malformed" in str(w.message) for w in rec)


def test_inherited_cycle_does_not_hang():
    # a widget whose /Parent points back to itself must terminate, not loop forever
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    page = w.pages[0]
    kid = DictionaryObject()
    kid[NameObject("/Type")] = NameObject("/Annot")
    kid[NameObject("/Subtype")] = NameObject("/Widget")
    kid[NameObject("/Rect")] = ArrayObject([FloatObject(c) for c in (50, 700, 250, 718)])
    kid[NameObject("/P")] = page.indirect_reference
    kid_ref = w._add_object(kid)
    kid[NameObject("/Parent")] = kid_ref        # self-referential /Parent
    page[NameObject("/Annots")] = ArrayObject([kid_ref])
    acro = DictionaryObject()
    acro[NameObject("/Fields")] = ArrayObject([kid_ref])
    w.root_object[NameObject("/AcroForm")] = w._add_object(acro)
    buf = io.BytesIO()
    w.write(buf)
    assert isinstance(af.read_fields(buf.getvalue()), list)   # completes (no hang)


def test_build_single_member_radio_does_not_crash():
    # a 1-button radio group crashed reportlab ("has 1 < 2 RadioBoxes"); real
    # forms have these. Now it builds (converted to a checkbox).
    f = FieldSpec(type=FieldType.RADIO, page=0, rect=(100, 700, 114, 714),
                  name="solo", export_value="Y")
    out = af.build(_blank_pdf(), [f])
    assert "solo" in (PdfReader(io.BytesIO(out)).get_fields() or {})


def test_fill_widget_with_ap_missing_n_does_not_crash():
    # a widget with /AP but no /N broke pypdf's get_fields() with KeyError '/N';
    # fill must survive it (real form: cal_poly purchase requisition).
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    page = w.pages[0]
    d = DictionaryObject()
    d[NameObject("/Type")] = NameObject("/Annot")
    d[NameObject("/Subtype")] = NameObject("/Widget")
    d[NameObject("/FT")] = NameObject("/Tx")
    d[NameObject("/T")] = TextStringObject("fld")
    d[NameObject("/Rect")] = ArrayObject([FloatObject(c) for c in (50, 700, 250, 718)])
    d[NameObject("/AP")] = DictionaryObject()  # /AP present but no /N
    d[NameObject("/P")] = page.indirect_reference
    ref = w._add_object(d)
    page[NameObject("/Annots")] = ArrayObject([ref])
    acro = DictionaryObject()
    acro[NameObject("/Fields")] = ArrayObject([ref])
    w.root_object[NameObject("/AcroForm")] = w._add_object(acro)
    buf = io.BytesIO()
    w.write(buf)
    filled = af.fill(buf.getvalue(), {"fld": "X"})   # fill's get_fields() must survive
    af.flatten(filled)                                # flatten's get_fields() must survive too
