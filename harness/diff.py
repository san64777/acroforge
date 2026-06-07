from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops


def png_mismatch_ratio(a: Path | str, b: Path | str) -> float:
    """Fraction of pixels that differ after resizing b to a's size. 0.0 == identical."""
    ia = Image.open(a).convert("RGB")
    ib = Image.open(b).convert("RGB")
    if ia.size != ib.size:
        ib = ib.resize(ia.size)
    diff = ImageChops.difference(ia, ib)
    if diff.getbbox() is None:
        return 0.0
    nonzero = sum(1 for px in diff.get_flattened_data() if px != (0, 0, 0))
    return nonzero / (ia.width * ia.height)


def renders_match(a: Path | str, b: Path | str, tolerance: float = 0.01) -> bool:
    return png_mismatch_ratio(a, b) <= tolerance
