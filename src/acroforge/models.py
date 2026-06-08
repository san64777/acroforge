from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, field_validator, model_validator


class FieldType(str, Enum):
    TEXT = "text"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    COMB = "comb"
    SIGNATURE = "signature"
    CHOICE = "choice"  # dropdown / list box (/Ch)


class ScannedPDFError(Exception):
    """Raised when auto-detection is attempted on a scanned/image-only PDF."""


class FieldSpec(BaseModel):
    type: FieldType
    page: int
    rect: tuple[float, float, float, float]  # (x0, y0, x1, y1) in PDF points
    name: str
    # radio/checkbox group members; or choice options as plain strings or
    # (export_value, display_label) pairs.
    options: list[str] | list[tuple[str, str]] | None = None
    maxlen: int | None = None  # comb cell count
    export_value: str | None = None   # radio member on-value / checkbox on-state
    list_box: bool = False  # choice: False=dropdown/combo, True=scrolling list box
    multi_select: bool = False  # choice: list box allows multiple selections
    editable: bool = False  # choice: combo box accepts free-typed text
    confidence: float = 1.0  # 1.0 = explicit; <1.0 = best-effort guess

    @field_validator("rect")
    @classmethod
    def _rect_ordered(cls, v: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = v
        if x1 <= x0 or y1 <= y0:
            raise ValueError("rect must have x1>x0 and y1>y0")
        return v

    @model_validator(mode="after")
    def _check_choice(self) -> FieldSpec:
        if self.type is FieldType.CHOICE:
            if not self.options:
                raise ValueError("CHOICE field requires non-empty options")
            if self.editable and self.list_box:
                raise ValueError("editable applies to combo boxes only (list_box must be False)")
            if self.multi_select and not self.list_box:
                raise ValueError("multi_select applies to list boxes only (list_box must be True)")
        elif self.list_box or self.multi_select or self.editable:
            raise ValueError("list_box / multi_select / editable apply only to CHOICE fields")
        return self


class FormManifest(BaseModel):
    source: str
    fields: list[FieldSpec]
