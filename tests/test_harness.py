from harness.render_pdfium import render_pdfium


def test_pdfium_renders_first_page_to_png(tmp_path):
    out = tmp_path / "w9_pdfium.png"
    render_pdfium("tests/fixtures/fw9.pdf", out, page_index=0, scale=1.5)
    assert out.exists() and out.stat().st_size > 1000
