import pytest
from acroforge.models import FieldType, FieldSpec, ScannedPDFError

def test_fieldspec_minimal_text_field():
    f = FieldSpec(type=FieldType.TEXT, page=0, rect=(10, 20, 110, 40), name="full_name")
    assert f.type is FieldType.TEXT
    assert f.rect == (10.0, 20.0, 110.0, 40.0)
    assert f.confidence == 1.0  # explicit fields are certain by default

def test_fieldspec_rejects_bad_rect():
    with pytest.raises(ValueError):
        FieldSpec(type=FieldType.TEXT, page=0, rect=(10, 20, 5, 40), name="x")  # x1 < x0

def test_radio_group_carries_options():
    f = FieldSpec(type=FieldType.RADIO, page=0, rect=(0, 0, 10, 10), name="sex",
                  options=["M", "F", "X"])
    assert f.options == ["M", "F", "X"]

def test_scanned_error_is_exception():
    assert issubclass(ScannedPDFError, Exception)

def test_fieldspec_export_value_defaults_none():
    from acroforge.models import FieldSpec, FieldType
    f = FieldSpec(type=FieldType.CHECKBOX, page=0, rect=(0, 0, 10, 10), name="agree")
    assert f.export_value is None

def test_radio_member_has_export_value():
    from acroforge.models import FieldSpec, FieldType
    f = FieldSpec(type=FieldType.RADIO, page=0, rect=(0, 0, 10, 10), name="sex", export_value="M")
    assert f.export_value == "M"
