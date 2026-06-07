from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Literal

from acroforge.detect.naming import label_from_cell_text, slugify


@dataclass
class Candidate:
    kind: Literal["text", "checkbox"]
    rect: tuple[float, float, float, float]
    confidence: float


_MIN_UNDERLINE_W = 40.0
_FIELD_HEIGHT = 16.0
_MAX_RULE_RECT_H = 2.0
_H_TOL = 1.5
_V_TOL = 1.5


def _xy(obj: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """(x0, x1, y0, y1) for a pdfplumber geom object, or None if unavailable.

    Real-world PDFs contain geometry objects that don't carry the full
    x0/x1/y0/y1 set; those are skipped rather than crashing detection.
    """
    try:
        return float(obj["x0"]), float(obj["x1"]), float(obj["y0"]), float(obj["y1"])
    except (KeyError, TypeError, ValueError):
        return None


def _rule_rects(page: Any) -> list[dict[str, Any]]:
    """Thin, wide rects that gov forms draw as rules instead of 1pt strokes.

    A rect with height <= _MAX_RULE_RECT_H and width >= _MIN_UNDERLINE_W is
    treated as an underline; its bottom edge (y0) is used as the line.
    """
    out: list[dict[str, Any]] = []
    for r in page.rects:
        c = _xy(r)
        if c is None:
            continue
        x0, x1, y0, y1 = c
        if (y1 - y0) > _MAX_RULE_RECT_H:
            continue
        if (x1 - x0) < _MIN_UNDERLINE_W:
            continue
        out.append({"x0": x0, "x1": x1, "y0": y0, "y1": y0})
    return out


def _vertical_segments(page: Any) -> list[tuple[float, float, float]]:
    """Vertical rules as (x, y_lo, y_hi) in PDF-native bottom-up coords.

    Pulls verticals from: vertical lines, vertical edges, and BOTH side
    verticals (x0 and x1, each spanning y0..y1) of every page.rects entry.
    Objects missing coordinates are skipped.
    """
    out: list[tuple[float, float, float]] = []
    for line in page.lines:
        c = _xy(line)
        if c is None:
            continue
        x0, x1, y0, y1 = c
        if abs(x1 - x0) <= _V_TOL:
            out.append((x0, min(y0, y1), max(y0, y1)))
    for edge in page.edges:
        if edge.get("orientation") != "v":
            continue
        c = _xy(edge)
        if c is None:
            continue
        x0, x1, y0, y1 = c
        out.append((x0, min(y0, y1), max(y0, y1)))
    for r in page.rects:
        c = _xy(r)
        if c is None:
            continue
        x0, x1, y0, y1 = c
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
        c = _xy(s)
        if c is None:
            continue
        x0, x1, y0, y1 = c
        if abs(y1 - y0) > _H_TOL:  # not horizontal
            continue
        y = y0
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
        c = _xy(r)
        if c is None:
            continue
        x0, x1, y0, y1 = c
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


# Ballot/checkbox glyphs forms use instead of drawn rectangles: ☐ ☑ ☒ □ ■
_CHECKBOX_GLYPHS = {"☐", "☑", "☒", "□", "■"}


def find_glyph_checkboxes(page: Any) -> list[Candidate]:
    """Checkboxes drawn as font glyphs (☐/☑/☒) rather than vector rects.

    Many real forms (credentialing, government) render checkboxes as characters,
    which are invisible to find_boxes. Scan page.chars for ballot-box glyphs.
    """
    out: list[Candidate] = []
    seen: set[tuple[int, int]] = set()
    for ch in getattr(page, "chars", []):
        if ch.get("text") not in _CHECKBOX_GLYPHS:
            continue
        c = _xy(ch)
        if c is None:
            continue
        x0, x1, y0, y1 = c
        side = max(x1 - x0, y1 - y0)
        if not (4.0 <= side <= 28.0):
            continue
        key = (round(x0), round(y0))
        if key in seen:
            continue
        seen.add(key)
        out.append(Candidate("checkbox", (x0, y0, x1, y1), 0.55))
    return out


# Table-cell sizing limits, in PDF points.
_CELL_MIN_W = 30.0
_CELL_MIN_H = 12.0
_CELL_MAX_H = 60.0  # taller cells are instruction/paragraph blocks, not inputs
_CELL_MAX_TXT = 120  # longer text means a paragraph/instruction cell, not an input

# Words whose `top` values fall within this many points belong to one text line.
_LINE_TOL = 4.0
# A header cell must be wider than this fraction of the page.
_HEADER_WIDTH_FRAC = 0.8
# A header's largest glyph must exceed this multiple of the page body font size.
_HEADER_SIZE_FACTOR = 1.2
# Minimum writable height (points) below the label line; under this we fall back.
_MIN_WRITABLE_H = 8.0
# Horizontal gap (points) between top-line words that starts a new label cluster.
_SPLIT_MIN_GAP = 35.0
_SPLIT_GAP_FACTOR = 2.5
# First N words of a cluster used to name its split field (matches label_from_cell_text).
_CLUSTER_NAME_WORDS = 3


def _body_font_size(page: Any) -> float | None:
    """Median glyph size across the page, or None if no sized chars exist."""
    sizes = [float(c["size"]) for c in page.chars if "size" in c]
    if not sizes:
        return None
    return float(statistics.median(sizes))


def _top_line_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The topmost line of words: those within _LINE_TOL of the minimum `top`."""
    if not words:
        return []
    min_top = min(float(w["top"]) for w in words)
    return [w for w in words if float(w["top"]) <= min_top + _LINE_TOL]


def _is_header_cell(
    x0: float,
    x1: float,
    words: list[dict[str, Any]],
    page_width: float,
    body_size: float | None,
) -> bool:
    """True if the cell is a large, full-width, single-line section header."""
    if body_size is None or not words:
        return False
    if (x1 - x0) <= _HEADER_WIDTH_FRAC * page_width:
        return False
    tops = [float(w["top"]) for w in words]
    if (max(tops) - min(tops)) > _LINE_TOL:  # more than one text line
        return False
    max_size = max((float(w["size"]) for w in words if "size" in w), default=0.0)
    return max_size > _HEADER_SIZE_FACTOR * body_size


def _label_clusters(top_line: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Cluster top-line words by horizontal gaps into label groups (left→right)."""
    if not top_line:
        return []
    ordered = sorted(top_line, key=lambda w: float(w["x0"]))
    if len(ordered) < 2:
        return [ordered]
    gaps = [
        float(ordered[i + 1]["x0"]) - float(ordered[i]["x1"]) for i in range(len(ordered) - 1)
    ]
    threshold = max(_SPLIT_MIN_GAP, _SPLIT_GAP_FACTOR * statistics.median(gaps))
    clusters: list[list[dict[str, Any]]] = [[ordered[0]]]
    for i, w in enumerate(ordered[1:], start=1):
        if gaps[i - 1] > threshold:
            clusters.append([w])
        else:
            clusters[-1].append(w)
    return clusters


def _cluster_slug(cluster: list[dict[str, Any]]) -> str:
    """Slug for a cluster's words (first N words joined), matching cell naming."""
    words = [str(w["text"]) for w in cluster][:_CLUSTER_NAME_WORDS]
    return slugify(" ".join(words))


def find_table_cells(page: Any) -> list[tuple[Candidate, str]]:
    """Treat each suitable bordered table cell as a TEXT field candidate.

    Real gov/credentialing forms are table grids where every input is a bordered
    cell whose text is "LABEL / value". Uses pdfplumber `page.find_tables()`,
    whose cells are `(x0, top, x1, bottom)` in TOP-DOWN coords; we convert to
    bottom-up PDF points (inset 1pt) via `page.height`.

    Returns `(Candidate, label_slug)` pairs; the slug is derived from the cell's
    text (may be "" — callers supply a fallback). Cells that are too small/tall,
    hold a checkbox glyph, or contain paragraph-length text are skipped.

    Three precision refinements run per passing cell (each may add 0..N fields):
      A. Skip large, full-width, single-line section-header cells.
      B. Shrink the field to the writable area BELOW the cell's label line.
      C. Split a cell holding multiple horizontally separated labels into one
         field per label, named from that label's own words.
    """
    out: list[tuple[Candidate, str]] = []
    height = float(page.height)
    page_width = float(page.width)
    body_size = _body_font_size(page)
    seen: set[tuple[int, int]] = set()
    for table in page.find_tables():
        for cell in table.cells:
            if cell is None:
                continue
            x0, top, x1, bottom = (float(cell[0]), float(cell[1]), float(cell[2]), float(cell[3]))
            w = x1 - x0
            h = bottom - top
            if w < _CELL_MIN_W or h < _CELL_MIN_H or h > _CELL_MAX_H:
                continue
            try:
                txt = page.crop(cell).extract_text() or ""
            except Exception:
                txt = ""
            if any(g in txt for g in _CHECKBOX_GLYPHS):
                continue  # checkbox cell, handled by find_boxes/find_glyph_checkboxes
            if len(txt) > _CELL_MAX_TXT:
                continue  # paragraph/instruction cell, not an input

            # Cell words in TOP-DOWN coords (top/bottom from page top); request
            # per-word font size so the header test can compare against body size.
            try:
                cell_words = page.crop(cell).extract_words(extra_attrs=["size"])
            except Exception:
                cell_words = []

            # Refinement A — skip section-header cells.
            if _is_header_cell(x0, x1, cell_words, page_width, body_size):
                continue

            # Refinement B — find the writable area below the label line.
            top_line = _top_line_words(cell_words)
            if top_line:
                label_bottom = max(float(w_["bottom"]) for w_ in top_line) + 1.0
                if (bottom - label_bottom) < _MIN_WRITABLE_H:
                    label_bottom = top  # too short: label & input share the line
            else:
                label_bottom = top  # empty input cell: use the whole cell
            write_top = label_bottom  # top-down top edge of the writable region

            # Refinement C — split multi-label cells by the top line's clusters.
            clusters = _label_clusters(top_line)
            if len(clusters) > 1:
                spans: list[tuple[float, float, str]] = []
                for i, cluster in enumerate(clusters):
                    left = float(cluster[0]["x0"])
                    right = x1 if i == len(clusters) - 1 else float(clusters[i + 1][0]["x0"])
                    left = max(x0, min(left, x1))
                    right = max(x0, min(right, x1))
                    spans.append((left, right, _cluster_slug(cluster)))
            else:
                slug = _cluster_slug(clusters[0]) if clusters else label_from_cell_text(txt)
                spans = [(x0, x1, slug)]

            for sx0, sx1, slug in spans:
                rx0 = sx0 + 1.0
                rx1 = sx1 - 1.0
                ry0 = height - bottom + 1.0
                ry1 = height - write_top - 1.0
                if rx1 <= rx0 or ry1 <= ry0:
                    continue  # degenerate
                key = (round(rx0), round(ry0))
                if key in seen:
                    continue
                seen.add(key)
                out.append((Candidate("text", (rx0, ry0, rx1, ry1), 0.5), slug))
    return out
