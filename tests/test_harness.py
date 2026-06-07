from harness.render_pdfium import render_pdfium
from harness.render_pdfjs import render_pdfjs
from harness.diff import png_mismatch_ratio, renders_match
from PIL import Image


def test_pdfium_renders_first_page_to_png(tmp_path):
    out = tmp_path / "w9_pdfium.png"
    render_pdfium("tests/fixtures/fw9.pdf", out, page_index=0, scale=1.5)
    assert out.exists() and out.stat().st_size > 1000


def test_pdfjs_renders_first_page_to_png(tmp_path):
    out = tmp_path / "w9_pdfjs.png"
    render_pdfjs("tests/fixtures/fw9.pdf", out, page_index=0, scale=1.5)
    assert out.exists() and out.stat().st_size > 1000


def test_identical_pngs_match(tmp_path):
    a = render_pdfium("tests/fixtures/fw9.pdf", tmp_path / "a.png", scale=1.5)
    b = render_pdfium("tests/fixtures/fw9.pdf", tmp_path / "b.png", scale=1.5)
    assert png_mismatch_ratio(a, b) == 0.0
    assert renders_match(a, b) is True


def test_gate_b_catches_a_broken_render(tmp_path):
    # GATE B: the harness must DETECT a difference between a real render and a blank page
    good = render_pdfium("tests/fixtures/fw9.pdf", tmp_path / "good.png", scale=1.5)
    blank = tmp_path / "blank.png"
    Image.new("RGB", Image.open(good).size, "white").save(blank)
    assert renders_match(good, blank) is False
