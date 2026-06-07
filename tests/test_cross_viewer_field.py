import shutil

import pytest

import acroforge as af
from harness.diff import png_mismatch_ratio
from harness.render_pdfium import render_pdfium
from tests.test_engine_text_checkbox import _blank_pdf


def _built_doc():
    fields = [af.FieldSpec(type=af.FieldType.TEXT, page=0, rect=(100, 700, 400, 720), name="n")]
    return af.fill(af.build(_blank_pdf(), fields), {"n": "VISIBLE-TEXT"})


def test_field_renders_in_pdfium(tmp_path):
    base = tmp_path / "base.pdf"
    base.write_bytes(_blank_pdf())
    doc = tmp_path / "doc.pdf"
    doc.write_bytes(_built_doc())
    a = render_pdfium(str(base), tmp_path / "base.png", scale=2.0)
    b = render_pdfium(str(doc), tmp_path / "doc.png", scale=2.0)
    assert png_mismatch_ratio(a, b) > 0.0  # field added visible ink in pdfium


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_field_renders_in_pdfjs(tmp_path):
    from harness.render_pdfjs import render_pdfjs

    base = tmp_path / "base.pdf"
    base.write_bytes(_blank_pdf())
    doc = tmp_path / "doc.pdf"
    doc.write_bytes(_built_doc())
    a = render_pdfjs(str(base), tmp_path / "base_pj.png", scale=2.0)
    b = render_pdfjs(str(doc), tmp_path / "doc_pj.png", scale=2.0)
    assert png_mismatch_ratio(a, b) > 0.0  # field added visible ink in pdf.js
