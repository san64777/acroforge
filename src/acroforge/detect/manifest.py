from __future__ import annotations

import io
import warnings
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


def _detect_page(page: Any, pno: int) -> list[FieldSpec]:
    """Detect all candidate fields on a single (non-scanned) page."""
    words = _words_bottom_up(page)
    fields: list[FieldSpec] = []

    # Track rounded positions of text fields to dedup table cells vs underlines.
    text_positions: set[tuple[int, int]] = set()

    for i, cand in enumerate(find_underlines(page)):
        name = name_for(cand.rect, words, fallback=f"text_{pno}_{i}")
        text_positions.add((round(cand.rect[0]), round(cand.rect[1])))
        fields.append(
            FieldSpec(
                type=FieldType.TEXT, page=pno, rect=cand.rect, name=name,
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
                type=FieldType.TEXT, page=pno, rect=cand.rect, name=name,
                confidence=cand.confidence,
            )
        )

    boxes = find_boxes(page) + find_glyph_checkboxes(page)
    for gi, group in enumerate(group_checkboxes(boxes)):
        for bi, cand in enumerate(group):
            name = name_for(cand.rect, words, fallback=f"checkbox_{pno}_{gi}_{bi}")
            fields.append(
                FieldSpec(
                    type=FieldType.CHECKBOX, page=pno, rect=cand.rect, name=name,
                    confidence=cand.confidence,
                )
            )
    return fields


def detect_manifest(pdf: str | bytes) -> FormManifest:
    """Orchestrate geometry + grouping + naming into a FormManifest.

    Best-effort and resilient per CLAUDE.md rule 3: an image-only page or a page
    that errors during detection is skipped with a ``warnings.warn`` and the rest
    of the document is still processed. ``ScannedPDFError`` is raised only when
    *every* page is image-only (preserving the scanned-PDF refusal, Gate C).
    """
    if isinstance(pdf, bytes):
        source = "<bytes>"
        handle: Any = io.BytesIO(pdf)
    else:
        source = pdf
        handle = pdf

    fields: list[FieldSpec] = []
    scanned_pages: list[int] = []
    with pdfplumber.open(handle) as doc:
        n_pages = len(doc.pages)
        for pno, page in enumerate(doc.pages):
            if is_scanned_page(page):
                scanned_pages.append(pno)
                warnings.warn(
                    f"acroforge: page {pno} is image-only; skipped (no fields detected there)",
                    stacklevel=2,
                )
                continue
            try:
                fields.extend(_detect_page(page, pno))
            except Exception as exc:  # noqa: BLE001 - one bad page must not abort the rest
                warnings.warn(
                    f"acroforge: page {pno} detection skipped ({type(exc).__name__}: {exc})",
                    stacklevel=2,
                )
                continue

    if n_pages > 0 and len(scanned_pages) == n_pages:
        raise ScannedPDFError(f"all {n_pages} page(s) are image-only; auto-detection refused")
    return FormManifest(source=source, fields=fields)
