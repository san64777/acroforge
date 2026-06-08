from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from acroforge.models import FieldSpec


@runtime_checkable
class Writer(Protocol):
    def create_fields(self, pdf: bytes, fields: list[FieldSpec]) -> bytes: ...
    def fill(self, pdf: bytes, values: dict[str, object]) -> bytes: ...
    def flatten(self, pdf: bytes) -> bytes: ...
    def remove(self, pdf: bytes, names: str | Iterable[str]) -> bytes: ...


def default_writer() -> Writer:
    from acroforge.engine.backends.reportlab_pypdf import ReportlabPypdfWriter

    return ReportlabPypdfWriter()
