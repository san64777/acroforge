"""Cross-viewer render gate for choice fields (pdfium + pdf.js).

Each test renders the SAME field built-but-empty vs filled, and asserts the two
differ. That proves the selected value itself renders (not merely that a border
box appears) - the contract from CLAUDE.md rule 4. All four variants (dropdown,
list box, editable, multi-select) are verified in both engines.
"""

import shutil

import pytest

import acroforge as af
from harness.diff import png_mismatch_ratio
from harness.render_pdfium import render_pdfium
from tests.test_engine_text_checkbox import _blank_pdf

_has_node = shutil.which("node") is not None

VARIANTS = {
    "dropdown": (
        af.FieldSpec(type=af.FieldType.CHOICE, page=0, rect=(100, 700, 300, 720),
                     name="f", options=["CA", "NY", "TX"]),
        {"f": "NY"},
    ),
    "listbox": (
        af.FieldSpec(type=af.FieldType.CHOICE, page=0, rect=(100, 600, 260, 700),
                     name="f", options=["Red", "Green", "Blue"], list_box=True),
        {"f": "Green"},
    ),
    "editable": (
        af.FieldSpec(type=af.FieldType.CHOICE, page=0, rect=(100, 680, 300, 700),
                     name="f", options=["NYC", "LA"], editable=True),
        {"f": "Boston"},
    ),
    "multiselect": (
        af.FieldSpec(type=af.FieldType.CHOICE, page=0, rect=(100, 560, 260, 700),
                     name="f", options=["en", "fr", "de"], list_box=True, multi_select=True),
        {"f": ["en", "de"]},
    ),
}


def _value_renders(engine, name, tmp_path):
    """Mismatch between the empty-but-built field and the filled field."""
    spec, vals = VARIANTS[name]
    empty = af.build(_blank_pdf(), [spec])
    filled = af.fill(af.build(_blank_pdf(), [spec]), vals)
    ep = tmp_path / f"{name}_empty.pdf"
    ep.write_bytes(empty)
    fp = tmp_path / f"{name}_filled.pdf"
    fp.write_bytes(filled)
    a = engine(str(ep), tmp_path / f"{name}_e.png", scale=2.0)
    b = engine(str(fp), tmp_path / f"{name}_f.png", scale=2.0)
    return png_mismatch_ratio(a, b)


@pytest.mark.parametrize("name", list(VARIANTS))
def test_choice_value_renders_in_pdfium(name, tmp_path):
    assert _value_renders(render_pdfium, name, tmp_path) > 0.0


@pytest.mark.skipif(not _has_node, reason="node not available")
@pytest.mark.parametrize("name", list(VARIANTS))
def test_choice_value_renders_in_pdfjs(name, tmp_path):
    from harness.render_pdfjs import render_pdfjs

    assert _value_renders(render_pdfjs, name, tmp_path) > 0.0
