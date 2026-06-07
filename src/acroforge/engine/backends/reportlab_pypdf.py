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
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    IndirectObject,
    NameObject,
    NumberObject,
    TextStringObject,
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
    elif spec.type is FieldType.COMB:
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
            fieldFlags="comb",
            maxlen=spec.maxlen or 1,
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


def _build_signature_widget(
    writer: PdfWriter, spec: FieldSpec, page_ref: IndirectObject
) -> IndirectObject:
    """Build an UNSIGNED ``/Sig`` placeholder widget and register its objects.

    reportlab has no signature helper, so the widget is assembled directly from
    pypdf objects: a ``/FT /Sig`` widget annotation with an empty bordered-box
    ``/AP`` ``/N`` appearance stream so it renders as a visible placeholder.
    This is a placeholder field only — not a digital-signature workflow.
    """
    x0, y0, x1, y1 = spec.rect
    w, h = x1 - x0, y1 - y0

    ap_stream = DecodedStreamObject()
    # Stroke a 1pt black rectangle inset by 0.5pt so the border sits inside /BBox.
    ap_stream.set_data(
        f"1 w 0 0 0 RG 0.5 0.5 {w - 1:.2f} {h - 1:.2f} re S".encode("latin-1")
    )
    ap_stream[NameObject("/Type")] = NameObject("/XObject")
    ap_stream[NameObject("/Subtype")] = NameObject("/Form")
    ap_stream[NameObject("/FormType")] = NumberObject(1)
    ap_stream[NameObject("/BBox")] = ArrayObject(
        [FloatObject(0), FloatObject(0), FloatObject(w), FloatObject(h)]
    )
    ap_ref = writer._add_object(ap_stream)

    ap = DictionaryObject()
    ap[NameObject("/N")] = ap_ref

    mk = DictionaryObject()
    mk[NameObject("/BC")] = ArrayObject([NumberObject(0), NumberObject(0), NumberObject(0)])

    widget = DictionaryObject()
    widget[NameObject("/Type")] = NameObject("/Annot")
    widget[NameObject("/Subtype")] = NameObject("/Widget")
    widget[NameObject("/FT")] = NameObject("/Sig")
    widget[NameObject("/T")] = TextStringObject(spec.name)
    widget[NameObject("/Rect")] = ArrayObject(
        [FloatObject(x0), FloatObject(y0), FloatObject(x1), FloatObject(y1)]
    )
    widget[NameObject("/F")] = NumberObject(4)  # Print
    widget[NameObject("/P")] = page_ref
    widget[NameObject("/MK")] = mk
    widget[NameObject("/AP")] = ap
    return writer._add_object(widget)


class ReportlabPypdfWriter:
    """Writer backend: creates AcroForm fields via reportlab overlays + pypdf."""

    def create_fields(self, pdf: bytes, fields: list[FieldSpec]) -> bytes:
        writer = PdfWriter()
        writer.append(PdfReader(io.BytesIO(pdf)))

        # SIGNATURE widgets are built directly (reportlab has no /Sig helper) and
        # are kept out of the overlay loop; everything else goes via reportlab.
        by_page: defaultdict[int, list[FieldSpec]] = defaultdict(list)
        sig_by_page: defaultdict[int, list[FieldSpec]] = defaultdict(list)
        for f in fields:
            if f.type is FieldType.SIGNATURE:
                sig_by_page[f.page].append(f)
            else:
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

        for page_idx, sig_specs in sig_by_page.items():
            base_page = writer.pages[page_idx]
            page_ref = cast(IndirectObject, base_page.indirect_reference)
            sig_refs = [
                _build_signature_widget(writer, spec, page_ref) for spec in sig_specs
            ]
            if "/Annots" in base_page:
                base_page[NameObject("/Annots")].extend(sig_refs)  # type: ignore[attr-defined]
            else:
                base_page[NameObject("/Annots")] = ArrayObject(sig_refs)
            acro[NameObject("/Fields")].extend(sig_refs)  # type: ignore[attr-defined]

        acro[NameObject("/NeedAppearances")] = BooleanObject(False)
        if "/XFA" in acro:
            del acro[NameObject("/XFA")]

        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    def fill(self, pdf: bytes, values: dict[str, object]) -> bytes:
        reader = PdfReader(io.BytesIO(pdf))
        writer = PdfWriter()
        writer.append(reader)
        str_values: dict[str, str] = {
            k: (v if isinstance(v, str) else ("/Yes" if v is True else str(v)))
            for k, v in values.items()
        }
        for page in writer.pages:
            writer.update_page_form_field_values(page, str_values, auto_regenerate=False)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    def flatten(self, pdf: bytes) -> bytes:
        reader = PdfReader(io.BytesIO(pdf))
        writer = PdfWriter()
        writer.append(reader)
        # pypdf 6.13 only bakes an /AP into the page content for fields named in
        # the ``fields`` mapping (the flatten path lives inside that loop), so an
        # empty mapping bakes nothing. Re-supply each field's existing ``/V`` so
        # ``flatten=True`` draws the appearance XObject into the page stream.
        values: dict[str, str] = {}
        for name, info in (reader.get_fields() or {}).items():
            value = info.get("/V")
            if value is not None:
                values[name] = value if isinstance(value, str) else str(value)
        for page in writer.pages:
            writer.update_page_form_field_values(
                page, values, auto_regenerate=False, flatten=True
            )
        # Drop the now-redundant interactive layer: widget annotations + AcroForm.
        writer.remove_annotations(subtypes="/Widget")
        root = writer._root_object
        if "/AcroForm" in root:
            del root[NameObject("/AcroForm")]
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
