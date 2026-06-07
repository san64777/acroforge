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
