from __future__ import annotations

from acroforge.detect.geometry import Candidate

_SAME_ROW_TOL = 6.0
_MAX_GAP = 60.0


def group_checkboxes(cands: list[Candidate]) -> list[list[Candidate]]:
    boxes = [c for c in cands if c.kind == "checkbox"]
    boxes.sort(key=lambda c: (round((c.rect[1] + c.rect[3]) / 2, 1), c.rect[0]))
    groups: list[list[Candidate]] = []
    for c in boxes:
        cy = (c.rect[1] + c.rect[3]) / 2
        placed = False
        for g in groups:
            last = g[-1]
            lcy = (last.rect[1] + last.rect[3]) / 2
            gap = c.rect[0] - last.rect[2]
            if abs(cy - lcy) <= _SAME_ROW_TOL and -1 <= gap <= _MAX_GAP:
                g.append(c)
                placed = True
                break
        if not placed:
            groups.append([c])
    return groups
