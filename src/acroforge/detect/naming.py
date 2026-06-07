from __future__ import annotations

import re
from typing import Any

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Horizontal reach for a left-side label, in PDF points.
_LEFT_MAX_GAP = 160.0
# A word counts as "to the left" if its right edge is at/under the field left + this slack.
_LEFT_SLACK = 2.0
# Vertical-band overlap tolerance, in points.
_ROW_TOL = 3.0
# How far above the field's top edge an above-label may sit, in points.
_ABOVE_MAX_GAP = 18.0
# Maximum number of qualifying label words to include.
_MAX_LABEL_WORDS = 4
# Maximum slug length (characters) before falling back.
_MAX_LABEL_LEN = 28


def slugify(text: str) -> str:
    """Lowercase, collapse runs of non-[a-z0-9] to '_', strip edge underscores."""
    return _NON_ALNUM.sub("_", text.lower()).strip("_")


def label_from_cell_text(text: str) -> str:
    """Derive a field-name slug from a table cell's text (label line + value line).

    Takes the FIRST line of the cell, then its first 3 whitespace words, and
    slugifies them. If the slug is empty or too long (> _MAX_LABEL_LEN), it is
    truncated to its first 3 `_`-parts. Returns "" if nothing usable; callers
    supply their own fallback.
    """
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    words = first_line.split()[:3]
    slug = slugify(" ".join(words))
    if not slug or len(slug) > _MAX_LABEL_LEN:
        slug = "_".join(slug.split("_")[:3])
    return slug


def _bands_overlap(a0: float, a1: float, b0: float, b1: float, tol: float) -> bool:
    """True if [a0,a1] and [b0,b1] overlap, allowing `tol` points of slack."""
    return (min(a1, b1) - max(a0, b0)) >= -tol


def name_for(
    rect: tuple[float, float, float, float],
    words: list[dict[str, Any]],
    fallback: str,
) -> str:
    """Derive a field name from the nearest label text (bottom-up PDF coords).

    Words use keys x0,x1,top,bottom where the vertical band is [bottom, top]
    (top = larger y), matching the field rect's [y0, y1]. Prefers same-row words
    to the LEFT of the field; falls back to a word directly ABOVE; else `fallback`.
    """
    x_left, y0, _x_right, y1 = rect[0], rect[1], rect[2], rect[3]

    def _is_upright(w: dict[str, Any]) -> bool:
        return bool(w.get("upright", True))

    def _slug_is_valid(slug: str) -> bool:
        return bool(slug) and len(slug) <= _MAX_LABEL_LEN and len(slug.split("_")) <= _MAX_LABEL_WORDS

    # (a) Same-row words to the left of the field, near enough horizontally.
    left: list[dict[str, Any]] = []
    for w in words:
        if not _is_upright(w):
            continue
        wx1 = float(w["x1"])
        if wx1 > x_left + _LEFT_SLACK:
            continue
        if (x_left - wx1) > _LEFT_MAX_GAP:
            continue
        if not _bands_overlap(y0, y1, float(w["bottom"]), float(w["top"]), _ROW_TOL):
            continue
        left.append(w)
    if left:
        if len(left) > _MAX_LABEL_WORDS:
            # More words than the cap indicates a dense/paragraph context - skip to fallback.
            pass
        else:
            # Pick the _MAX_LABEL_WORDS nearest words by x-distance to the field, then re-sort left→right.
            left.sort(key=lambda w: x_left - float(w["x1"]))
            left = left[:_MAX_LABEL_WORDS]
            left.sort(key=lambda w: float(w["x0"]))
            slug = slugify(" ".join(str(w["text"]) for w in left))
            if _slug_is_valid(slug):
                return slug

    # (b) Otherwise a word directly above, horizontally overlapping the field.
    above: list[dict[str, Any]] = []
    for w in words:
        if not _is_upright(w):
            continue
        wbottom = float(w["bottom"])
        if not (y1 - _ROW_TOL <= wbottom <= y1 + _ABOVE_MAX_GAP):
            continue
        if not _bands_overlap(x_left, _x_right, float(w["x0"]), float(w["x1"]), _ROW_TOL):
            continue
        above.append(w)
    if above:
        above.sort(key=lambda w: (float(w["bottom"]), float(w["x0"])))
        above = above[:_MAX_LABEL_WORDS]
        slug = slugify(" ".join(str(w["text"]) for w in above))
        if _slug_is_valid(slug):
            return slug

    return fallback
