"""acroforge — turn flat PDFs into fillable AcroForms."""

__version__ = "0.0.0"

from .api import build, detect, fill, flatten, make_fillable
from .models import FieldType, FieldSpec, FormManifest, ScannedPDFError

__all__ = [
    "FieldType",
    "FieldSpec",
    "FormManifest",
    "ScannedPDFError",
    "build",
    "detect",
    "fill",
    "flatten",
    "make_fillable",
]
