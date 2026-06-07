from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium


def render_pdfium(
    pdf_path: str,
    out_png: "Path | str",
    page_index: int = 0,
    scale: float = 2.0,
) -> Path:
    """Render a PDF page to PNG using pdfium (Chrome's engine), with form widgets drawn.

    Uses ``may_draw_forms=True`` (the correct kwarg in pypdfium2 >= 4.x / 5.x).
    ``init_forms()`` must be called before page access so widgets are drawn.
    """
    pdf = pdfium.PdfDocument(pdf_path)
    pdf.init_forms()  # MUST precede page access or widgets won't draw
    page = pdf[page_index]
    bitmap = page.render(scale=scale, may_draw_forms=True, rev_byteorder=True)
    out = Path(out_png)
    bitmap.to_pil().save(out)
    return out
