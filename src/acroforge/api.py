from __future__ import annotations

from acroforge.engine.base import default_writer
from acroforge.models import FieldSpec


def build(pdf: bytes, fields: list[FieldSpec]) -> bytes:
    """Inject real, fillable AcroForm fields into `pdf` at the given specs."""
    return default_writer().create_fields(pdf, fields)


def fill(pdf: bytes, values: dict[str, object]) -> bytes:
    """Set values on a fillable PDF's fields by name."""
    return default_writer().fill(pdf, values)


def flatten(pdf: bytes) -> bytes:
    """Bake field appearances into page content and remove the interactive fields."""
    return default_writer().flatten(pdf)
