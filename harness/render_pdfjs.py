from __future__ import annotations
from pathlib import Path
import subprocess

_SCRIPT = Path(__file__).parent / "render_pdfjs.mjs"

def render_pdfjs(pdf_path: str, out_png: Path | str, page_index: int = 0, scale: float = 2.0) -> Path:
    out = Path(out_png).resolve()
    subprocess.run(
        ["node", str(_SCRIPT), str(Path(pdf_path).resolve()), str(out), str(page_index), str(scale)],
        check=True, cwd=str(_SCRIPT.parent),
    )
    return out
