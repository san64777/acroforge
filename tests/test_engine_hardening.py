import io

import pypdf
import pytest

import acroforge as af
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
