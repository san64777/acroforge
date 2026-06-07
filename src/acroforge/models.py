from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, field_validator


class FieldType(str, Enum):
    TEXT = "text"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    COMB = "comb"
    SIGNATURE = "signature"


class ScannedPDFError(Exception):
    """Raised when auto-detection is attempted on a scanned/image-only PDF."""


class FieldSpec(BaseModel):
    type: FieldType
    page: int
    rect: tuple[float, float, float, float]  # (x0, y0, x1, y1) in PDF points
    name: str
    options: list[str] | None = None  # radio/checkbox group members
    maxlen: int | None = None  # comb cell count
    export_value: str | None = None   # radio member on-value / checkbox on-state
    confidence: float = 1.0  # 1.0 = explicit; <1.0 = best-effort guess

    @field_validator("rect")
    @classmethod
    def _rect_ordered(cls, v: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = v
        if x1 <= x0 or y1 <= y0:
            raise ValueError("rect must have x1>x0 and y1>y0")
        return v


class FormManifest(BaseModel):
    source: str
    fields: list[FieldSpec]
