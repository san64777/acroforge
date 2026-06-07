"""GATE C probe: stamp a filled AcroForm text field onto a scanned/image-only PDF.

Demonstrates that the reportlab+pypdf engine is source-agnostic - it can add a
properly-registered, viewer-renderable form field to a page that contains no
vector text whatsoever (chars==0, images==1, is_scanned_pdf==True).

The scanned page (tests/fixtures/scanned_sample.pdf) is 587.52 x 760.32 pt.
We place a text field near the top of the page in clear space where the stamp
is visually unambiguous against whatever background the scan has.

Strategy is identical to gate_a_reportlab_pypdf.py:
  1. Build an overlay PDF (same page size) with reportlab acroForm.textfield.
  2. Clone the widget annotations from the overlay into a PdfWriter that holds
     the scanned base.
  3. Attach cloned refs to the base page /Annots.
  4. Register them in /AcroForm /Fields so spec-correct viewers enumerate them.
  5. Force NeedAppearances off so viewers honour the embedded /AP stream.
"""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DictionaryObject,
    NameObject,
)
from reportlab.pdfgen import canvas

FIELD_NAME = "af_on_scan"
FIELD_VALUE = "STAMPED-ON-SCAN"

# Scanned sample page dimensions (confirmed via pypdf mediabox)
PAGE_W = 587.52
PAGE_H = 760.32


def _build_overlay() -> bytes:
    """Build a same-size overlay carrying one text widget near the top."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    form = c.acroForm

    # Place in top strip: x=60, y=730 (bottom-left of field),
    # width=280, height=18 - well within the 587.52-wide page and clearly
    # visible in the upper region of the scanned image.
    form.textfield(
        name=FIELD_NAME,
        value=FIELD_VALUE,
        x=60,
        y=730,
        width=280,
        height=18,
        fontSize=11,
        borderStyle="solid",
        borderWidth=1,
        forceBorder=True,
    )
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def run(
    src: str = "tests/fixtures/scanned_sample.pdf",
    out: str = "spikes/out_scanned_stamped.pdf",
) -> str:
    overlay_bytes = _build_overlay()

    writer = PdfWriter()
    writer.append(PdfReader(src))  # clone the scanned base (incl. any existing /AcroForm)

    overlay_reader = PdfReader(BytesIO(overlay_bytes))
    overlay_page = overlay_reader.pages[0]

    base_page = writer.pages[0]

    overlay_annots = overlay_page.get("/Annots")
    if not overlay_annots:
        raise RuntimeError("reportlab overlay produced no widget annotations")

    new_widget_refs = []
    for annot in overlay_annots:
        annot_obj = annot.get_object()
        cloned = annot_obj.clone(writer)
        ref = cloned.indirect_reference
        # Point the widget's parent page reference at the scanned base page.
        cloned[NameObject("/P")] = base_page.indirect_reference
        new_widget_refs.append(ref)

    # Attach to base page /Annots.
    if "/Annots" in base_page:
        base_page[NameObject("/Annots")].extend(new_widget_refs)
    else:
        base_page[NameObject("/Annots")] = ArrayObject(new_widget_refs)

    # Register in /AcroForm /Fields (required for cross-viewer enumeration).
    root = writer._root_object
    if "/AcroForm" not in root:
        acro = DictionaryObject()
        acro[NameObject("/Fields")] = ArrayObject()
        root[NameObject("/AcroForm")] = writer._add_object(acro)
    acro = root["/AcroForm"].get_object()
    if "/Fields" not in acro:
        acro[NameObject("/Fields")] = ArrayObject()
    acro[NameObject("/Fields")].extend(new_widget_refs)

    # Force NeedAppearances off so viewers honour the embedded /AP streams.
    if "/NeedAppearances" in acro:
        acro[NameObject("/NeedAppearances")] = BooleanObject(False)
    # Drop any XFA that might have been in the base (unlikely for a scanned
    # doc but safe to clear so AcroForm governs rendering).
    if "/XFA" in acro:
        del acro[NameObject("/XFA")]

    with open(out, "wb") as fh:
        writer.write(fh)

    # Structural self-check.
    r = PdfReader(out)
    fields = r.get_fields() or {}
    if FIELD_NAME not in fields:
        raise RuntimeError(
            f"gate_c: field '{FIELD_NAME}' not registered in /AcroForm /Fields"
        )

    return out


if __name__ == "__main__":
    print(run())
