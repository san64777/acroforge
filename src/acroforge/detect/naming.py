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


def slugify(text: str) -> str:
    """Lowercase, collapse runs of non-[a-z0-9] to '_', strip edge underscores."""
    return _NON_ALNUM.sub("_", text.lower()).strip("_")


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

    # (a) Same-row words to the left of the field, near enough horizontally.
    left: list[dict[str, Any]] = []
    for w in words:
        wx1 = float(w["x1"])
        if wx1 > x_left + _LEFT_SLACK:
            continue
        if (x_left - wx1) > _LEFT_MAX_GAP:
            continue
        if not _bands_overlap(y0, y1, float(w["bottom"]), float(w["top"]), _ROW_TOL):
            continue
        left.append(w)
    if left:
        left.sort(key=lambda w: float(w["x0"]))
        slug = slugify(" ".join(str(w["text"]) for w in left))
        if slug:
            return slug

    # (b) Otherwise a word directly above, horizontally overlapping the field.
    above: list[dict[str, Any]] = []
    for w in words:
        wbottom = float(w["bottom"])
        if not (y1 - _ROW_TOL <= wbottom <= y1 + _ABOVE_MAX_GAP):
            continue
        if not _bands_overlap(x_left, _x_right, float(w["x0"]), float(w["x1"]), _ROW_TOL):
            continue
        above.append(w)
    if above:
        above.sort(key=lambda w: (float(w["bottom"]), float(w["x0"])))
        slug = slugify(" ".join(str(w["text"]) for w in above))
        if slug:
            return slug

    return fallback
