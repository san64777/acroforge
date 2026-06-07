import io

import pypdf

import acroforge as af


def test_detect_runs_on_real_w9():
    data = open("tests/fixtures/fw9.pdf", "rb").read()
    m = af.detect(data)
    assert len(m.fields) >= 1  # finds at least one plausible candidate


def test_make_fillable_on_real_w9_roundtrips():
    data = open("tests/fixtures/fw9.pdf", "rb").read()
    out = af.make_fillable(data)
    flds = pypdf.PdfReader(io.BytesIO(out)).get_fields() or {}
    assert flds != {}  # produced real, readable fields
