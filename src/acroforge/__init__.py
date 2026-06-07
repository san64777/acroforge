"""acroforge - turn flat PDFs into fillable AcroForms."""

from importlib.metadata import PackageNotFoundError, version

from .api import build, detect, fill, flatten, make_fillable, read_fields
from .models import FieldSpec, FieldType, FormManifest, ScannedPDFError

try:
    __version__ = version("acroforge")
except PackageNotFoundError:  # running from a source checkout that isn't installed
    __version__ = "0.0.0"

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
    "read_fields",
]
