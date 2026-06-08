import acroforge as af
from acroforge.models import FieldType
from tests.test_engine_text_checkbox import _blank_pdf


def _built():
    fields = [
        af.FieldSpec(type=FieldType.TEXT, page=0, rect=(100, 700, 300, 716), name="full_name"),
        af.FieldSpec(type=FieldType.CHECKBOX, page=0, rect=(100, 670, 112, 682), name="agree"),
        af.FieldSpec(type=FieldType.COMB, page=0, rect=(100, 640, 260, 656), name="ssn", maxlen=9),
    ]
    return af.build(_blank_pdf(), fields)


def test_read_fields_roundtrips_build():
    got = af.read_fields(_built())
    by = {f.name: f for f in got}
    assert {"full_name", "agree", "ssn"} <= set(by)
    assert by["full_name"].type == FieldType.TEXT
    assert by["agree"].type == FieldType.CHECKBOX
    assert by["ssn"].type == FieldType.COMB and by["ssn"].maxlen == 9
    # real fields -> confidence 1.0
    assert all(f.confidence == 1.0 for f in got)
    # rect recovered (approx)
    r = by["full_name"].rect
    assert abs(r[0] - 100) < 3 and abs(r[2] - 300) < 3


def test_read_fields_empty_pdf_returns_empty():
    assert af.read_fields(_blank_pdf()) == []


def test_read_fields_accepts_path(tmp_path):
    p = tmp_path / "f.pdf"
    p.write_bytes(_built())
    assert len(af.read_fields(str(p))) >= 3


def test_read_then_rebuild_roundtrip():
    # build -> read -> build again: names survive the loop
    specs = af.read_fields(_built())
    rebuilt = af.build(_blank_pdf(), specs)
    names = {f.name for f in af.read_fields(rebuilt)}
    assert {"full_name", "agree", "ssn"} <= names


def _flatten_opts(opts):
    return [o if isinstance(o, str) else o[0] for o in (opts or [])]


def test_read_fields_dropdown_roundtrip():
    f = af.FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 700, 300, 720),
                     name="state", options=["CA", "NY", "TX"])
    spec = [s for s in af.read_fields(af.build(_blank_pdf(), [f])) if s.name == "state"][0]
    assert spec.type == FieldType.CHOICE
    assert spec.list_box is False and spec.editable is False
    assert set(_flatten_opts(spec.options)) == {"CA", "NY", "TX"}


def test_read_fields_listbox_roundtrip():
    f = af.FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 620, 260, 700),
                     name="colors", options=["Red", "Green", "Blue"], list_box=True)
    spec = [s for s in af.read_fields(af.build(_blank_pdf(), [f])) if s.name == "colors"][0]
    assert spec.type == FieldType.CHOICE and spec.list_box is True


def test_read_fields_editable_roundtrip():
    f = af.FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 560, 300, 580),
                     name="city", options=["NYC", "LA"], editable=True)
    spec = [s for s in af.read_fields(af.build(_blank_pdf(), [f])) if s.name == "city"][0]
    assert spec.editable is True and spec.list_box is False


def test_read_fields_multi_select_roundtrip():
    f = af.FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 500, 260, 560),
                     name="langs", options=["en", "fr"], list_box=True, multi_select=True)
    spec = [s for s in af.read_fields(af.build(_blank_pdf(), [f])) if s.name == "langs"][0]
    assert spec.multi_select is True and spec.list_box is True


def test_read_fields_pairs_roundtrip():
    f = af.FieldSpec(type=FieldType.CHOICE, page=0, rect=(100, 700, 300, 720),
                     name="st", options=[("CA", "California"), ("NY", "New York")])
    spec = [s for s in af.read_fields(af.build(_blank_pdf(), [f])) if s.name == "st"][0]
    assert ("CA", "California") in spec.options


def _foreign_choice_pdf() -> bytes:
    """A PDF with /Ch fields authored the way a non-acroforge tool would, incl. a
    parent/kid field whose /FT,/Ff,/Opt are inherited by the kid widget. Exercises
    read_fields against foreign structures acroforge does not itself emit."""
    import io as _io

    from pypdf import PdfWriter
    from pypdf.generic import (
        ArrayObject,
        DictionaryObject,
        FloatObject,
        NameObject,
        NumberObject,
        TextStringObject,
    )

    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    page = w.pages[0]
    page_ref = page.indirect_reference

    def _rect(r):
        return ArrayObject([FloatObject(c) for c in r])

    def _opt_strings(items):
        return ArrayObject([TextStringObject(s) for s in items])

    def _opt_pairs(pairs):
        return ArrayObject(
            [ArrayObject([TextStringObject(e), TextStringObject(d)]) for e, d in pairs]
        )

    field_refs = ArrayObject()
    annot_refs = ArrayObject()

    def _flat(name, r, ff, opt):
        d = DictionaryObject()
        d[NameObject("/Type")] = NameObject("/Annot")
        d[NameObject("/Subtype")] = NameObject("/Widget")
        d[NameObject("/FT")] = NameObject("/Ch")
        d[NameObject("/T")] = TextStringObject(name)
        d[NameObject("/Ff")] = NumberObject(ff)
        d[NameObject("/Opt")] = opt
        d[NameObject("/Rect")] = _rect(r)
        d[NameObject("/F")] = NumberObject(4)
        d[NameObject("/P")] = page_ref
        ref = w._add_object(d)
        field_refs.append(ref)
        annot_refs.append(ref)

    _flat("combo", (50, 700, 250, 718), 1 << 17, _opt_strings(["a", "b", "c"]))
    _flat("editcombo", (50, 660, 250, 678), (1 << 17) | (1 << 18), _opt_strings(["x", "y"]))
    _flat("listbox", (50, 560, 250, 640), 0, _opt_strings(["p", "q", "r"]))
    _flat("multilist", (50, 460, 250, 540), 1 << 21, _opt_strings(["m1", "m2"]))
    _flat("pairs", (50, 420, 250, 438), 1 << 17, _opt_pairs([("US", "United States"), ("CA", "Canada")]))

    # parent/kid: /FT,/Ff,/Opt live on the parent; the kid widget inherits them
    parent = DictionaryObject()
    parent[NameObject("/FT")] = NameObject("/Ch")
    parent[NameObject("/T")] = TextStringObject("inherited")
    parent[NameObject("/Ff")] = NumberObject(1 << 17)
    parent[NameObject("/Opt")] = _opt_strings(["i1", "i2"])
    parent_ref = w._add_object(parent)
    kid = DictionaryObject()
    kid[NameObject("/Type")] = NameObject("/Annot")
    kid[NameObject("/Subtype")] = NameObject("/Widget")
    kid[NameObject("/Rect")] = _rect((50, 380, 250, 398))
    kid[NameObject("/F")] = NumberObject(4)
    kid[NameObject("/P")] = page_ref
    kid[NameObject("/Parent")] = parent_ref
    kid_ref = w._add_object(kid)
    parent[NameObject("/Kids")] = ArrayObject([kid_ref])
    field_refs.append(parent_ref)
    annot_refs.append(kid_ref)

    page[NameObject("/Annots")] = annot_refs
    acro = DictionaryObject()
    acro[NameObject("/Fields")] = field_refs
    w.root_object[NameObject("/AcroForm")] = w._add_object(acro)

    buf = _io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_read_fields_foreign_authored_choice():
    specs = {s.name: s for s in af.read_fields(_foreign_choice_pdf())
             if s.type == FieldType.CHOICE}
    assert set(specs) == {"combo", "editcombo", "listbox", "multilist", "pairs", "inherited"}
    assert not specs["combo"].list_box and not specs["combo"].editable
    assert specs["editcombo"].editable and not specs["editcombo"].list_box
    assert specs["listbox"].list_box and not specs["listbox"].multi_select
    assert specs["multilist"].list_box and specs["multilist"].multi_select
    assert ("US", "United States") in specs["pairs"].options
    # /FT, /Ff, /Opt inherited from /Parent are recovered on the kid widget
    assert not specs["inherited"].list_box
    assert specs["inherited"].options == ["i1", "i2"]


def test_read_fields_returns_qualified_fillable_name():
    """A widget nested under a parent field reads back as the fully-qualified
    'parent.child' name, so read_fields output is usable by fill() (real-world
    forms: read_fields used to return the leaf name, which fill could not address)."""
    import io as _io

    import pypdf
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
    parent[NameObject("/T")] = TextStringObject("form")
    parent_ref = w._add_object(parent)
    kid = DictionaryObject()
    kid[NameObject("/Type")] = NameObject("/Annot")
    kid[NameObject("/Subtype")] = NameObject("/Widget")
    kid[NameObject("/T")] = TextStringObject("name")
    kid[NameObject("/Rect")] = ArrayObject([FloatObject(c) for c in (50, 700, 250, 718)])
    kid[NameObject("/P")] = page.indirect_reference
    kid[NameObject("/Parent")] = parent_ref
    kid_ref = w._add_object(kid)
    parent[NameObject("/Kids")] = ArrayObject([kid_ref])
    page[NameObject("/Annots")] = ArrayObject([kid_ref])
    acro = DictionaryObject()
    acro[NameObject("/Fields")] = ArrayObject([parent_ref])
    w.root_object[NameObject("/AcroForm")] = w._add_object(acro)
    buf = _io.BytesIO()
    w.write(buf)
    data = buf.getvalue()

    spec = [s for s in af.read_fields(data) if s.type == FieldType.TEXT][0]
    assert spec.name == "form.name"   # qualified, not the leaf "name"
    filled = af.fill(data, {spec.name: "VALUE"})   # the read name must be fill-addressable
    assert "form.name" in (pypdf.PdfReader(_io.BytesIO(filled)).get_fields() or {})


def test_read_fields_radio_roundtrip():
    fields = [
        af.FieldSpec(type=FieldType.RADIO, page=0, rect=(100, 700, 114, 714), name="sex", export_value="M"),
        af.FieldSpec(type=FieldType.RADIO, page=0, rect=(140, 700, 154, 714), name="sex", export_value="F"),
    ]
    built = af.build(_blank_pdf(), fields)
    got = af.read_fields(built)
    radios = [f for f in got if f.name == "sex"]
    # both radio widgets come back as RADIO named "sex"
    assert len(radios) == 2
    assert all(f.type == FieldType.RADIO for f in radios)
    assert all(f.confidence == 1.0 for f in radios)
    # on-state export values recovered (M and F)
    exports = {f.export_value for f in radios}
    assert exports == {"M", "F"}
