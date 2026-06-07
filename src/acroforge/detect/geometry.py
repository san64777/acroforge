from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class Candidate:
    kind: Literal["text", "checkbox"]
    rect: tuple[float, float, float, float]
    confidence: float


_MIN_UNDERLINE_W = 40.0
_FIELD_HEIGHT = 16.0
_MAX_RULE_RECT_H = 2.0


def _is_horizontal(obj: dict[str, Any], tol: float = 1.5) -> bool:
    return abs(float(obj["y1"]) - float(obj["y0"])) <= tol


def _rule_rects(page: Any) -> list[dict[str, Any]]:
    """Thin, wide rects that gov forms draw as rules instead of 1pt strokes.

    A rect with height <= _MAX_RULE_RECT_H and width >= _MIN_UNDERLINE_W is
    treated as an underline; its bottom edge (y0) is used as the line.
    """
    out: list[dict[str, Any]] = []
    for r in page.rects:
        if (float(r["y1"]) - float(r["y0"])) > _MAX_RULE_RECT_H:
            continue
        if (float(r["x1"]) - float(r["x0"])) < _MIN_UNDERLINE_W:
            continue
        out.append({"x0": r["x0"], "x1": r["x1"], "y0": r["y0"], "y1": r["y0"]})
    return out


def _is_vertical(obj: dict[str, Any], tol: float = 1.5) -> bool:
    return abs(float(obj["x1"]) - float(obj["x0"])) <= tol


def _vertical_segments(page: Any) -> list[tuple[float, float, float]]:
    """Vertical rules as (x, y_lo, y_hi) in PDF-native bottom-up coords.

    Pulls verticals from: vertical lines, vertical edges, and BOTH side
    verticals (x0 and x1, each spanning y0..y1) of every page.rects entry.
    """
    out: list[tuple[float, float, float]] = []
    for line in page.lines:
        if _is_vertical(line):
            x = float(line["x0"])
            y0, y1 = float(line["y0"]), float(line["y1"])
            out.append((x, min(y0, y1), max(y0, y1)))
    for edge in page.edges:
        if edge.get("orientation") == "v":
            x = float(edge["x0"])
            y0, y1 = float(edge["y0"]), float(edge["y1"])
            out.append((x, min(y0, y1), max(y0, y1)))
    for r in page.rects:
        x0, x1 = float(r["x0"]), float(r["x1"])
        y0, y1 = float(r["y0"]), float(r["y1"])
        y_lo, y_hi = min(y0, y1), max(y0, y1)
        out.append((x0, y_lo, y_hi))
        out.append((x1, y_lo, y_hi))
    return out


def _end_near_vertical(
    x: float,
    y: float,
    verts: list[tuple[float, float, float]],
    xtol: float = 3.0,
    ytol: float = 3.0,
) -> bool:
    """True if (x, y) sits at the end of any vertical rule."""
    for vx, y_lo, y_hi in verts:
        if abs(vx - x) <= xtol and (y_lo - ytol) <= y <= (y_hi + ytol):
            return True
    return False


def find_underlines(page: Any) -> list[Candidate]:
    out: list[Candidate] = []
    segs = (
        list(page.lines)
        + [e for e in page.edges if e.get("orientation") == "h"]
        + _rule_rects(page)
    )
    verts = _vertical_segments(page)
    seen: set[tuple[int, int, int]] = set()
    for s in segs:
        if not _is_horizontal(s):
            continue
        x0, x1 = float(s["x0"]), float(s["x1"])
        y = float(s["y0"])
        if (x1 - x0) < _MIN_UNDERLINE_W:
            continue
        # A write-on underline has OPEN ends; a table/box edge is bounded by
        # vertical rules at BOTH ends. Skip the latter.
        if _end_near_vertical(x0, y, verts) and _end_near_vertical(x1, y, verts):
            continue
        key = (round(x0), round(x1), round(y))
        if key in seen:
            continue
        seen.add(key)
        out.append(Candidate("text", (x0, y, x1, y + _FIELD_HEIGHT), 0.6))
    return out


_CB_MIN, _CB_MAX = 6.0, 22.0
_CB_SQUARE_TOL = 0.35


def find_boxes(page: Any) -> list[Candidate]:
    out: list[Candidate] = []
    seen: set[tuple[int, int]] = set()
    for r in page.rects:
        x0, y0, x1, y1 = float(r["x0"]), float(r["y0"]), float(r["x1"]), float(r["y1"])
        w, h = x1 - x0, y1 - y0
        if not (_CB_MIN <= w <= _CB_MAX and _CB_MIN <= h <= _CB_MAX):
            continue
        if abs(w - h) / max(w, h) > _CB_SQUARE_TOL:
            continue
        key = (round(x0), round(y0))
        if key in seen:
            continue
        seen.add(key)
        out.append(Candidate("checkbox", (x0, y0, x1, y1), 0.5))
    return out
