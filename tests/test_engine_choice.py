import io

import pypdf
import pytest

import acroforge as af
from acroforge.models import FieldSpec, FieldType
from tests.test_engine_text_checkbox import _blank_pdf

_FF_COMBO = 1 << 17
_FF_EDIT = 1 << 18
_FF_MULTI = 1 << 21


def _field(out, name):
    r = pypdf.PdfReader(io.BytesIO(out))
    return [a.get_object() for a in r.pages[0]["/Annots"] if a.get_object().get("/T") == name][0]


def _ff(out, name):
    return int(_field(out, name).get("/Ff") or 0)


def _dropdown():
    return FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 700, 300, 720),
                     name="state", options=["CA", "NY", "TX"])


def _listbox():
    return FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 620, 260, 700),
                     name="colors", options=["Red", "Green", "Blue"], list_box=True)


def _multi():
    return FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 540, 260, 660),
                     name="langs", options=["en", "fr", "de"], list_box=True, multi_select=True)


def _editable():
    return FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 500, 300, 520),
                     name="city", options=["NYC", "LA"], editable=True)


# --- model validation -------------------------------------------------------

def test_choice_type_exists():
    assert FieldType.CHOICE.value == "choice"


def test_choice_requires_options():
    with pytest.raises(ValueError):
        FieldSpec(type=FieldType.CHOICE, page=0, rect=(10, 10, 100, 30), name="s")


def test_choice_accepts_pairs():
    f = FieldSpec(type=FieldType.CHOICE, page=0, rect=(10, 10, 100, 30), name="s",
                  options=[("CA", "California")])
    assert f.options == [("CA", "California")]


def test_editable_only_on_combo():
    with pytest.raises(ValueError):
        FieldSpec(type=FieldType.CHOICE, page=0, rect=(10, 10, 100, 30), name="s",
                  options=["a"], list_box=True, editable=True)


def test_multi_select_only_on_listbox():
    with pytest.raises(ValueError):
        FieldSpec(type=FieldType.CHOICE, page=0, rect=(10, 10, 100, 30), name="s",
                  options=["a"], multi_select=True)


def test_choice_flags_rejected_on_non_choice():
    for kw in ({"list_box": True}, {"multi_select": True}, {"editable": True}):
        with pytest.raises(ValueError):
            FieldSpec(type=FieldType.TEXT, page=0, rect=(10, 10, 100, 30), name="t", **kw)


# --- build ------------------------------------------------------------------

def test_dropdown_registers_choice_field():
    out = af.build(_blank_pdf(), [_dropdown()])
    fld = _field(out, "state")
    assert fld.get("/FT") == "/Ch"
    assert "/AP" in fld
    assert fld.get("/Opt") is not None
    assert _ff(out, "state") & _FF_COMBO  # combo bit set


def test_dropdown_starts_blank():
    out = af.build(_blank_pdf(), [_dropdown()])
    v = _field(out, "state").get("/V")
    assert v in (None, "")  # no default selection after blanking


def test_listbox_is_not_combo():
    out = af.build(_blank_pdf(), [_listbox()])
    assert not (_ff(out, "colors") & _FF_COMBO)


def test_listbox_short_rect_does_not_crash():
    # an 18pt-tall list box used to crash reportlab (ZeroDivisionError); now builds
    f = FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 700, 300, 718),
                  name="lb", options=["a", "b", "c"], list_box=True)
    out = af.build(_blank_pdf(), [f])
    assert "lb" in (pypdf.PdfReader(io.BytesIO(out)).get_fields() or {})


def test_listbox_too_short_raises_clear_error():
    f = FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 700, 300, 704),
                  name="lb", options=["a", "b"], list_box=True)
    with pytest.raises(ValueError, match="too short"):
        af.build(_blank_pdf(), [f])


def test_editable_sets_edit_flag():
    ff = _ff(af.build(_blank_pdf(), [_editable()]), "city")
    assert ff & _FF_COMBO and ff & _FF_EDIT


def test_multi_select_sets_flag():
    assert _ff(af.build(_blank_pdf(), [_multi()]), "langs") & _FF_MULTI


def test_pairs_opt_uses_export_display_order():
    f = FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 700, 300, 720),
                  name="st", options=[("CA", "California"), ("NY", "New York")])
    out = af.build(_blank_pdf(), [f])
    opt = _field(out, "st").get("/Opt")
    # PDF spec /Opt pair is [export, display]
    assert [str(opt[0][0]), str(opt[0][1])] == ["CA", "California"]


# --- fill -------------------------------------------------------------------

def test_fill_dropdown_sets_value():
    filled = af.fill(af.build(_blank_pdf(), [_dropdown()]), {"state": "NY"})
    r = pypdf.PdfReader(io.BytesIO(filled))
    assert "NY" in str((r.get_fields() or {})["state"].get("/V"))


def test_fill_rejects_non_option():
    built = af.build(_blank_pdf(), [_dropdown()])
    with pytest.raises(ValueError):
        af.fill(built, {"state": "ZZ"})


def test_editable_allows_free_text():
    filled = af.fill(af.build(_blank_pdf(), [_editable()]), {"city": "Boston"})
    r = pypdf.PdfReader(io.BytesIO(filled))
    assert "Boston" in str((r.get_fields() or {})["city"].get("/V"))


def test_multi_select_fill_sets_array():
    filled = af.fill(af.build(_blank_pdf(), [_multi()]), {"langs": ["en", "de"]})
    r = pypdf.PdfReader(io.BytesIO(filled))
    v = (r.get_fields() or {})["langs"].get("/V")
    assert {str(x) for x in v} == {"en", "de"}


def test_multi_select_rejects_non_option():
    built = af.build(_blank_pdf(), [_multi()])
    with pytest.raises(ValueError):
        af.fill(built, {"langs": ["en", "zz"]})


def test_list_value_rejected_on_single_select():
    built = af.build(_blank_pdf(), [_dropdown()])
    with pytest.raises(ValueError):
        af.fill(built, {"state": ["CA", "NY"]})


# --- flatten ----------------------------------------------------------------

def test_flatten_choice_removes_widgets():
    final = af.flatten(af.fill(af.build(_blank_pdf(), [_dropdown()]), {"state": "NY"}))
    r = pypdf.PdfReader(io.BytesIO(final))
    assert "/AcroForm" not in r.trailer["/Root"]
    annots = r.pages[0].get("/Annots") or []
    assert all(a.get_object().get("/Subtype") != "/Widget" for a in annots)


# --- real-world: stamp a dropdown onto the actual IRS W-9 -------------------

def test_choice_on_real_w9():
    import pathlib

    w9 = (pathlib.Path(__file__).parent / "fixtures" / "fw9.pdf").read_bytes()
    state = FieldSpec(type=FieldType.CHOICE, page=0, rect=(400, 600, 520, 618),
                      name="af_state", options=["CA", "NY", "TX"])
    built = af.build(w9, [state])
    spec = [s for s in af.read_fields(built) if s.name == "af_state"][0]
    assert spec.type == FieldType.CHOICE
    assert set(spec.options) == {"CA", "NY", "TX"}
    final = af.flatten(af.fill(built, {"af_state": "CA"}))
    r = pypdf.PdfReader(io.BytesIO(final))
    assert "/AcroForm" not in r.trailer["/Root"]
