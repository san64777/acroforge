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


def _is_horizontal(obj: dict[str, Any], tol: float = 1.5) -> bool:
    return abs(float(obj["y1"]) - float(obj["y0"])) <= tol


def find_underlines(page: Any) -> list[Candidate]:
    out: list[Candidate] = []
    segs = list(page.lines) + [e for e in page.edges if e.get("orientation") == "h"]
    seen: set[tuple[int, int, int]] = set()
    for s in segs:
        if not _is_horizontal(s):
            continue
        x0, x1 = float(s["x0"]), float(s["x1"])
        y = float(s["y0"])
        if (x1 - x0) < _MIN_UNDERLINE_W:
            continue
        key = (round(x0), round(x1), round(y))
        if key in seen:
            continue
        seen.add(key)
        out.append(Candidate("text", (x0, y, x1, y + _FIELD_HEIGHT), 0.6))
    return out
