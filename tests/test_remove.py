import io
import pathlib

import pypdf
import pytest

import acroforge as af
from acroforge.models import FieldSpec, FieldType
from tests.test_engine_text_checkbox import _blank_pdf


def _two_field_pdf():
    fields = [
        FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 700, 300, 718), name="keep"),
        FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 660, 300, 678), name="drop"),
    ]
    return af.build(_blank_pdf(), fields)


def _names(pdf):
    return {s.name for s in af.read_fields(pdf)}


# --- Task 1: API surface ----------------------------------------------------

def test_remove_is_exported_and_callable():
    assert callable(af.remove)


# --- Task 2: flat fields ----------------------------------------------------

def test_remove_flat_field_drops_only_that_field():
    out = af.remove(_two_field_pdf(), "drop")
    assert _names(out) == {"keep"}
    fields = pypdf.PdfReader(io.BytesIO(out)).get_fields() or {}
    assert "drop" not in fields and "keep" in fields


def test_remove_accepts_iterable():
    fields = [
        FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 700, 300, 718), name="a"),
        FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 660, 300, 678), name="b"),
        FieldSpec(type=FieldType.CHECKBOX, page=0, rect=(100, 620, 114, 634), name="c"),
    ]
    out = af.remove(af.build(_blank_pdf(), fields), ["a", "c"])
    assert _names(out) == {"b"}


def test_remove_result_is_valid_pdf_and_rereadable():
    out = af.remove(_two_field_pdf(), "drop")
    assert out[:5] == b"%PDF-"
    af.read_fields(out)  # must not raise


# --- Task 3: radio, hierarchical, parent pruning ----------------------------

def _radio_pdf():
    fields = [
        FieldSpec(type=FieldType.RADIO, page=0, rect=(100, 700, 114, 714), name="sex", export_value="M"),
        FieldSpec(type=FieldType.RADIO, page=0, rect=(140, 700, 154, 714), name="sex", export_value="F"),
        FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 660, 300, 678), name="other"),
    ]
    return af.build(_blank_pdf(), fields)


def test_remove_radio_group_dedups_and_drops_whole_group():
    pdf = _radio_pdf()
    radio_names = [s.name for s in af.read_fields(pdf) if s.type == FieldType.RADIO]  # ["sex","sex"]
    out = af.remove(pdf, radio_names)
    assert "sex" not in _names(out)
    assert "other" in _names(out)


def _hierarchical_pdf():
    from pypdf import PdfWriter
    from pypdf.generic import (
        ArrayObject,
        DictionaryObject,
        FloatObject,
        NameObject,
        TextStringObject,
    )

    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    page = w.pages[0]
    parent = DictionaryObject()
    parent[NameObject("/FT")] = NameObject("/Tx")
    parent[NameObject("/T")] = TextStringObject("section")
    pref = w._add_object(parent)
    kid_refs = []
    for i, leaf in enumerate(("a", "b")):
        kid = DictionaryObject()
        kid[NameObject("/Type")] = NameObject("/Annot")
        kid[NameObject("/Subtype")] = NameObject("/Widget")
        kid[NameObject("/T")] = TextStringObject(leaf)
        kid[NameObject("/Rect")] = ArrayObject(
            [FloatObject(c) for c in (50, 700 - i * 40, 250, 718 - i * 40)])
        kid[NameObject("/P")] = page.indirect_reference
        kid[NameObject("/Parent")] = pref
        kid_refs.append(w._add_object(kid))
    parent[NameObject("/Kids")] = ArrayObject(kid_refs)
    page[NameObject("/Annots")] = ArrayObject(kid_refs)
    acro = DictionaryObject()
    acro[NameObject("/Fields")] = ArrayObject([pref])
    w.root_object[NameObject("/AcroForm")] = w._add_object(acro)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_remove_hierarchical_leaf_keeps_sibling():
    pdf = _hierarchical_pdf()
    assert _names(pdf) == {"section.a", "section.b"}
    out = af.remove(pdf, "section.a")
    assert _names(out) == {"section.b"}


def test_remove_last_child_prunes_empty_parent():
    out = af.remove(_hierarchical_pdf(), ["section.a", "section.b"])
    assert _names(out) == set()
    acro = pypdf.PdfReader(io.BytesIO(out)).trailer["/Root"]["/AcroForm"].get_object()
    assert len(acro.get("/Fields") or []) == 0


def test_remove_duplicate_qualified_name_leaves_no_orphan_widget():
    # two distinct top-level fields share the qualified name "dup": removing it must
    # drop BOTH from /Fields AND both widgets from /Annots (no orphan left behind).
    from pypdf import PdfWriter
    from pypdf.generic import (
        ArrayObject,
        DictionaryObject,
        FloatObject,
        NameObject,
        TextStringObject,
    )

    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    page = w.pages[0]
    refs = []
    for i in range(2):
        d = DictionaryObject()
        d[NameObject("/Type")] = NameObject("/Annot")
        d[NameObject("/Subtype")] = NameObject("/Widget")
        d[NameObject("/FT")] = NameObject("/Tx")
        d[NameObject("/T")] = TextStringObject("dup")
        d[NameObject("/Rect")] = ArrayObject(
            [FloatObject(c) for c in (50, 700 - i * 40, 250, 718 - i * 40)])
        d[NameObject("/P")] = page.indirect_reference
        refs.append(w._add_object(d))
    page[NameObject("/Annots")] = ArrayObject(refs)
    acro = DictionaryObject()
    acro[NameObject("/Fields")] = ArrayObject(refs)
    w.root_object[NameObject("/AcroForm")] = w._add_object(acro)
    buf = io.BytesIO()
    w.write(buf)

    out = af.remove(buf.getvalue(), "dup")
    r = pypdf.PdfReader(io.BytesIO(out))
    acro = r.trailer["/Root"]["/AcroForm"].get_object()
    assert len(acro.get("/Fields") or []) == 0
    annots = r.pages[0].get("/Annots") or []
    assert [a for a in annots if a.get_object().get("/Subtype") == "/Widget"] == []


# --- Task 4: edge cases -----------------------------------------------------

def test_remove_missing_name_raises_all_or_nothing():
    pdf = _two_field_pdf()
    with pytest.raises(ValueError, match="not found"):
        af.remove(pdf, ["keep", "nope"])
    assert _names(pdf) == {"keep", "drop"}  # input bytes unchanged


def test_remove_on_pdf_without_acroform_raises():
    with pytest.raises(ValueError, match="not found"):
        af.remove(_blank_pdf(), "anything")


def test_remove_all_leaves_empty_acroform_not_deleted():
    out = af.remove(_two_field_pdf(), ["keep", "drop"])
    assert "/AcroForm" in pypdf.PdfReader(io.BytesIO(out)).trailer["/Root"]
    assert af.read_fields(out) == []
    rebuilt = af.build(out, [FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 700, 300, 718), name="new")])
    assert _names(rebuilt) == {"new"}


def test_remove_empty_names_is_noop():
    assert _names(af.remove(_two_field_pdf(), [])) == {"keep", "drop"}


# --- Task 5: cross-viewer + real form ---------------------------------------

def test_remove_survivors_render_in_pdfium(tmp_path):
    from harness.diff import png_mismatch_ratio
    from harness.render_pdfium import render_pdfium

    fields = [
        FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 700, 300, 718), name="keep"),
        FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 660, 300, 678), name="drop"),
    ]
    filled = af.fill(af.build(_blank_pdf(), fields), {"keep": "VISIBLE", "drop": "GONE"})
    final = af.flatten(af.remove(filled, "drop"))
    base = tmp_path / "b.pdf"
    base.write_bytes(_blank_pdf())
    doc = tmp_path / "d.pdf"
    doc.write_bytes(final)
    a = render_pdfium(str(base), tmp_path / "b.png", scale=2.0)
    b = render_pdfium(str(doc), tmp_path / "d.png", scale=2.0)
    assert png_mismatch_ratio(a, b) > 0.0  # surviving "keep" field still renders


def test_remove_on_real_w9_fixture():
    w9 = (pathlib.Path(__file__).parent / "fixtures" / "fw9.pdf").read_bytes()
    before = {s.name for s in af.read_fields(w9)}
    victim = sorted(before)[0]  # a real fully-qualified field name
    after = {s.name for s in af.read_fields(af.remove(w9, victim))}
    assert victim not in after
    assert after == before - {victim}
