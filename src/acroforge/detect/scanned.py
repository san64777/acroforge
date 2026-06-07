from __future__ import annotations

from typing import Any

import pdfplumber


def is_scanned_page(page: Any) -> bool:
    """A page with no extractable text/vector geometry but a covering image is scanned."""
    has_vector = bool(page.chars) or bool(page.lines) or bool(page.rects) or bool(page.curves)
    has_image = bool(page.images)
    return (not has_vector) and has_image


def is_scanned_pdf(path: str) -> bool:
    """True if the first page is image-only (no vector text/geometry)."""
    with pdfplumber.open(path) as pdf:
        if not pdf.pages:
            return False
        return is_scanned_page(pdf.pages[0])
