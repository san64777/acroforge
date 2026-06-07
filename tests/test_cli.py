import json
import subprocess
import sys

import pypdf

from tests.test_engine_text_checkbox import _blank_pdf


def test_cli_build_registers_field(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_blank_pdf())
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps([{"type": "text", "page": 0, "rect": [100, 700, 300, 718], "name": "nm"}])
    )
    out = tmp_path / "out.pdf"
    r = subprocess.run(
        [sys.executable, "-m", "acroforge.cli", "build", str(inp), str(manifest), str(out)]
    )
    assert r.returncode == 0
    assert "nm" in (pypdf.PdfReader(str(out)).get_fields() or {})


def test_cli_fill_then_flatten(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_blank_pdf())
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps([{"type": "text", "page": 0, "rect": [100, 700, 300, 718], "name": "nm"}])
    )
    built = tmp_path / "built.pdf"
    subprocess.run(
        [sys.executable, "-m", "acroforge.cli", "build", str(inp), str(manifest), str(built)],
        check=True,
    )
    data = tmp_path / "d.json"
    data.write_text(json.dumps({"nm": "Asha"}))
    filled = tmp_path / "filled.pdf"
    subprocess.run(
        [sys.executable, "-m", "acroforge.cli", "fill", str(built), str(data), str(filled)],
        check=True,
    )
    assert pypdf.PdfReader(str(filled)).get_fields()["nm"]["/V"] == "Asha"
    flat = tmp_path / "flat.pdf"
    subprocess.run(
        [sys.executable, "-m", "acroforge.cli", "flatten", str(filled), str(flat)],
        check=True,
    )
    assert not (pypdf.PdfReader(str(flat)).get_fields() or {})
