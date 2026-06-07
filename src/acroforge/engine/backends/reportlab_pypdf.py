"""reportlab + pypdf field-creation backend (Gate A winner, BSD + BSD).

Productionizes the proven spike technique
(``spikes/gate_a_reportlab_pypdf.py``): reportlab draws each widget — with a
real ``/AP`` appearance stream — onto a same-size overlay page, then pypdf
clones those widget annotations into the target, repoints ``/P`` at the right
page, and registers the refs in ``/AcroForm /Fields`` so spec-correct viewers
(e.g. pdf.js, which enumerates ``/Fields``) render them. ``/NeedAppearances``
is forced off (embedded ``/AP`` is authoritative) and any ``/XFA`` is dropped.
"""

from __future__ import annotations

import io
from collections import defaultdict
from typing import cast

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
)
from reportlab.pdfgen import canvas  # type: ignore[import-untyped]

from acroforge.models import FieldSpec, FieldType


def _draw_widget(form: object, spec: FieldSpec) -> None:
    """Draw one widget onto reportlab's AcroForm overlay.

    ``form`` is a ``reportlab.pdfbase.acroform.AcroForm`` (untyped — reportlab
    ships no stubs). Coordinate mapping: rect ``(x0, y0, x1, y1)`` →
    reportlab ``x=x0, y=y0, width=x1-x0, height=y1-y0``; checkbox uses the
    square ``size=min(w, h)`` anchored at the bottom-left.
    """
    x0, y0, x1, y1 = spec.rect
    w, h = x1 - x0, y1 - y0
    if spec.type is FieldType.TEXT:
        form.textfield(  # type: ignore[attr-defined]
            name=spec.name,
            value="",
            x=x0,
            y=y0,
            width=w,
            height=h,
            fontSize=min(12, h - 2),
            borderStyle="solid",
            borderWidth=1,
            forceBorder=True,
        )
    elif spec.type is FieldType.CHECKBOX:
        form.checkbox(  # type: ignore[attr-defined]
            name=spec.name,
            checked=False,
            x=x0,
            y=y0,
            size=min(w, h),
            buttonStyle="check",
            borderStyle="solid",
            borderWidth=1,
            forceBorder=True,
        )
    else:
        raise NotImplementedError(f"field type {spec.type} added in a later task")


def _overlay_for_page(page_w: float, page_h: float, specs: list[FieldSpec]) -> bytes:
    """Build a same-size reportlab overlay carrying the given widgets."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    form = c.acroForm
    for s in specs:
        if s.type is FieldType.RADIO:
            x0, y0, x1, y1 = s.rect
            form.radio(
                name=s.name,
                value=(s.export_value or "On"),
                selected=False,
                x=x0,
                y=y0,
                size=min(x1 - x0, y1 - y0),
                buttonStyle="check",
                borderStyle="solid",
                borderWidth=1,
                forceBorder=True,
            )
        else:
            _draw_widget(form, s)
    c.showPage()
    c.save()
    return buf.getvalue()


class ReportlabPypdfWriter:
    """Writer backend: creates AcroForm fields via reportlab overlays + pypdf."""

    def create_fields(self, pdf: bytes, fields: list[FieldSpec]) -> bytes:
        writer = PdfWriter()
        writer.append(PdfReader(io.BytesIO(pdf)))

        by_page: defaultdict[int, list[FieldSpec]] = defaultdict(list)
        for f in fields:
            by_page[f.page].append(f)

        root = writer._root_object
        if "/AcroForm" not in root:
            acro = DictionaryObject()
            acro[NameObject("/Fields")] = ArrayObject()
            root[NameObject("/AcroForm")] = writer._add_object(acro)
        acro = cast(DictionaryObject, root["/AcroForm"].get_object())
        if "/Fields" not in acro:
            acro[NameObject("/Fields")] = ArrayObject()

        for page_idx, specs in by_page.items():
            base_page = writer.pages[page_idx]
            box = base_page.mediabox
            overlay = PdfReader(
                io.BytesIO(_overlay_for_page(float(box.width), float(box.height), specs))
            )
            overlay_root = cast(DictionaryObject, overlay.trailer["/Root"].get_object())
            overlay_acro = cast(
                DictionaryObject, overlay_root["/AcroForm"].get_object()
            )
            field_refs: list[IndirectObject] = []
            annot_refs: list[IndirectObject] = []
            for fld in overlay_acro.get("/Fields") or []:
                cloned = fld.get_object().clone(writer)
                kids = cloned.get("/Kids")
                if kids:
                    # Group field (e.g. radio): the page widgets are its kids;
                    # repoint each kid's /P and add the kids — not the parent —
                    # to the page /Annots; register the parent in /Fields.
                    for kid in kids:
                        kid_obj = cast(DictionaryObject, kid.get_object())
                        kid_obj[NameObject("/P")] = base_page.indirect_reference
                        annot_refs.append(kid.indirect_reference)
                else:
                    # Widget-as-field (text/checkbox): one object is both the
                    # field and the page annotation.
                    cloned[NameObject("/P")] = base_page.indirect_reference
                    annot_refs.append(cloned.indirect_reference)
                field_refs.append(cloned.indirect_reference)
            if "/Annots" in base_page:
                base_page[NameObject("/Annots")].extend(annot_refs)  # type: ignore[attr-defined]
            else:
                base_page[NameObject("/Annots")] = ArrayObject(annot_refs)
            acro[NameObject("/Fields")].extend(field_refs)  # type: ignore[attr-defined]

        acro[NameObject("/NeedAppearances")] = BooleanObject(False)
        if "/XFA" in acro:
            del acro[NameObject("/XFA")]

        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    def fill(self, pdf: bytes, values: dict[str, object]) -> bytes:
        raise NotImplementedError("fill: later task")

    def flatten(self, pdf: bytes) -> bytes:
        raise NotImplementedError("flatten: later task")
