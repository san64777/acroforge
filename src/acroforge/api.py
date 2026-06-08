from __future__ import annotations

from collections.abc import Iterable

from acroforge.detect.manifest import detect_manifest
from acroforge.engine.base import default_writer
from acroforge.models import FieldSpec, FormManifest
from acroforge.read import read_fields as _read_fields


def build(pdf: bytes, fields: list[FieldSpec]) -> bytes:
    """Inject real, fillable AcroForm fields into `pdf` at the given specs.

    Pass ``manifest.fields`` from a detected or deserialized ``FormManifest``.
    """
    return default_writer().create_fields(pdf, fields)


def fill(pdf: bytes, values: dict[str, object]) -> bytes:
    """Set values on a fillable PDF's fields by name."""
    return default_writer().fill(pdf, values)


def flatten(pdf: bytes) -> bytes:
    """Bake field appearances into page content and remove the interactive fields."""
    return default_writer().flatten(pdf)


def detect(pdf: bytes | str) -> FormManifest:
    """Best-effort: find candidate fields on a vector PDF (each confidence < 1.0).

    Raises ScannedPDFError on scans.
    """
    return detect_manifest(pdf)


def read_fields(pdf: bytes | str) -> list[FieldSpec]:
    """Read existing AcroForm fields out of an already-fillable PDF.

    Returns one FieldSpec per /Widget annotation (so a radio group yields one
    spec per button, sharing a name). Because these are real, registered fields
    rather than geometry guesses, every spec has confidence = 1.0. This makes
    the API symmetric: build(pdf, read_fields(other_pdf)).

    Serialize the result with pydantic: ``FieldSpec`` / ``FormManifest`` support
    ``model_dump_json()`` and ``model_validate_json()``.
    """
    return _read_fields(pdf)


def make_fillable(pdf: bytes) -> bytes:
    """Best-effort convenience: detect() then build().

    Review low-confidence fields before trusting.
    """
    manifest = detect_manifest(pdf)
    return build(pdf, manifest.fields)


def remove(pdf: bytes, names: str | Iterable[str]) -> bytes:
    """Remove specific AcroForm fields by fully-qualified name.

    ``names`` are the name or names exactly as returned by ``read_fields`` (a
    duplicate radio name is deduplicated). Raises ``ValueError`` if any name is
    not present (all-or-nothing). Naming a radio group removes the whole group;
    naming a container (parent) field removes everything nested under it.
    Leaves an empty ``/AcroForm`` if the last field is removed; strips ``/XFA``.
    """
    return default_writer().remove(pdf, names)
