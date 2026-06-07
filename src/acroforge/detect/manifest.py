from __future__ import annotations

import io
from typing import Any

import pdfplumber

from acroforge.detect.geometry import (
    find_boxes,
    find_glyph_checkboxes,
    find_table_cells,
    find_underlines,
)
from acroforge.detect.grouping import group_checkboxes
from acroforge.detect.naming import name_for
from acroforge.detect.scanned import is_scanned_page
from acroforge.models import FieldSpec, FieldType, FormManifest, ScannedPDFError


def _words_bottom_up(page: Any) -> list[dict[str, Any]]:
    """Convert pdfplumber's TOP-DOWN words to BOTTOM-UP coords for `name_for`.

    pdfplumber gives each word `top`/`bottom` measured from the page top. We flip
    them to PDF bottom-up coords using `page.height`, where a word's vertical band
    is [bottom, top] with `top` the larger (upper) y.
    """
    height = float(page.height)
    out: list[dict[str, Any]] = []
    for w in page.extract_words():
        out.append(
            {
                "x0": float(w["x0"]),
                "x1": float(w["x1"]),
                "top": height - float(w["top"]),  # upper edge -> larger y
                "bottom": height - float(w["bottom"]),  # lower edge -> smaller y
                "text": str(w["text"]),
            }
        )
    return out


def detect_manifest(pdf: str | bytes) -> FormManifest:
    """Orchestrate geometry + grouping + naming into a FormManifest.

    Refuses scanned (image-only) pages by raising ScannedPDFError.
    """
    if isinstance(pdf, bytes):
        source = "<bytes>"
        handle: Any = io.BytesIO(pdf)
    else:
        source = pdf
        handle = pdf

    fields: list[FieldSpec] = []
    with pdfplumber.open(handle) as doc:
        for pno, page in enumerate(doc.pages):
            if is_scanned_page(page):
                raise ScannedPDFError(f"page {pno} is image-only; auto-detection refused")

            words = _words_bottom_up(page)

            # Track rounded positions of text fields to dedup table cells vs underlines.
            text_positions: set[tuple[int, int]] = set()

            for i, cand in enumerate(find_underlines(page)):
                name = name_for(cand.rect, words, fallback=f"text_{pno}_{i}")
                text_positions.add((round(cand.rect[0]), round(cand.rect[1])))
                fields.append(
                    FieldSpec(
                        type=FieldType.TEXT,
                        page=pno,
                        rect=cand.rect,
                        name=name,
                        confidence=cand.confidence,
                    )
                )

            for ci, (cand, label) in enumerate(find_table_cells(page)):
                pos = (round(cand.rect[0]), round(cand.rect[1]))
                if pos in text_positions:
                    continue  # already detected at ~this position (e.g. an underline)
                text_positions.add(pos)
                name = label or name_for(cand.rect, words, fallback=f"cell_{pno}_{ci}")
                fields.append(
                    FieldSpec(
                        type=FieldType.TEXT,
                        page=pno,
                        rect=cand.rect,
                        name=name,
                        confidence=cand.confidence,
                    )
                )

            boxes = find_boxes(page) + find_glyph_checkboxes(page)
            for gi, group in enumerate(group_checkboxes(boxes)):
                for bi, cand in enumerate(group):
                    name = name_for(cand.rect, words, fallback=f"checkbox_{pno}_{gi}_{bi}")
                    fields.append(
                        FieldSpec(
                            type=FieldType.CHECKBOX,
                            page=pno,
                            rect=cand.rect,
                            name=name,
                            confidence=cand.confidence,
                        )
                    )

    return FormManifest(source=source, fields=fields)
