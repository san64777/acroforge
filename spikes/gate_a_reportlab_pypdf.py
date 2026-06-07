"""GATE A probe: reportlab + pypdf DIY (BSD + BSD -> strictly permissive).

Draws a text field + checkbox onto a same-size overlay using reportlab's
`canvas.acroForm.textfield/checkbox`, then merges that overlay onto page 1 of
the base form with pypdf and explicitly registers the new widgets in the
AcroForm `/Fields` array (so pdf.js, which enumerates `/Fields`, renders them).

Researched API:
  - reportlab `reportlab.pdfgen.canvas.Canvas(buf, pagesize=(w,h))`; the form
    object is `canvas.acroForm` with:
      textfield(value='', x=, y=, width=, height=, name=, fontSize=,
                borderStyle='solid', borderWidth=, fieldFlags='', ...)
      checkbox(checked=False, x=, y=, size=, name=, buttonStyle='check',
               borderStyle='solid', ...)
    (x, y) is the bottom-left of the widget in PDF points.
  - pypdf `PdfWriter`: `append(reader)` clones a doc (incl. its /AcroForm
    /Fields); `pages[i].merge_page(other_page)` composites content + copies
    annotations. We append the BASE first, then merge the overlay page so the
    overlay's widget annotations are laid on top, then move those new widget
    refs into the base AcroForm /Fields.

Strategy notes:
  - We do NOT rely on merge_page to register fields in /AcroForm /Fields (it
    composites content and may drop or fail to register widgets), so we build
    the widget annotation dicts ourselves from the overlay, attach them to the
    base page /Annots, AND append them to /AcroForm /Fields. This is the
    "copy widget refs explicitly" fallback and is the robust path for a
    duplicate-field-name base form.
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

TEXT_NAME = "af_probe_text"
TEXT_VALUE = "ACROFORGE"
CHECK_NAME = "af_probe_check"

PAGE_W = 612.0
PAGE_H = 792.0


def _build_overlay() -> bytes:
    """Reportlab overlay (same page size) carrying the two widgets."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    form = c.acroForm

    form.textfield(
        name=TEXT_NAME,
        value=TEXT_VALUE,
        x=200,
        y=772,
        width=160,
        height=16,
        fontSize=10,
        borderStyle="solid",
        borderWidth=1,
        forceBorder=True,
    )
    form.checkbox(
        name=CHECK_NAME,
        checked=True,
        x=380,
        y=772,
        size=14,
        buttonStyle="check",
        borderStyle="solid",
        borderWidth=1,
        forceBorder=True,
    )
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def run(src: str = "tests/fixtures/f1040.pdf", out: str = "spikes/out_reportlab_pypdf.pdf") -> str:
    overlay_bytes = _build_overlay()

    writer = PdfWriter()
    writer.append(PdfReader(src))  # clones base incl. its /AcroForm tree

    overlay_reader = PdfReader(BytesIO(overlay_bytes))
    overlay_page = overlay_reader.pages[0]

    base_page = writer.pages[0]

    # Collect the widget annotation refs from the overlay (these are the real
    # field dicts reportlab built, with /T, /FT, /V, /AP, /Rect, ...).
    overlay_annots = overlay_page.get("/Annots")
    if not overlay_annots:
        raise RuntimeError("reportlab overlay produced no widget annotations")

    # Composite the overlay's *visual* content under nothing special - we just
    # need the appearance streams, which travel with the annotation /AP, so a
    # content merge isn't strictly required. But merge_page also draws any page
    # content; reportlab put none besides the widgets, so skip merge_page and
    # copy the widget annotations directly (robust against merge_page dropping
    # them on a duplicate-name base).
    new_widget_refs = []
    for annot in overlay_annots:
        annot_obj = annot.get_object()
        # Deep-clone the annotation into the writer so refs are valid.
        cloned = annot_obj.clone(writer)
        ref = cloned.indirect_reference
        # Point the widget back at the base page.
        cloned[NameObject("/P")] = base_page.indirect_reference
        new_widget_refs.append(ref)

    # Attach to base page /Annots.
    if "/Annots" in base_page:
        base_page[NameObject("/Annots")].extend(new_widget_refs)
    else:
        base_page[NameObject("/Annots")] = ArrayObject(new_widget_refs)

    # Register in /AcroForm /Fields (REQUIRED for spec-correct, cross-viewer
    # enumeration; pdf.js renders fields it finds here).
    root = writer._root_object
    if "/AcroForm" not in root:
        acro = DictionaryObject()
        acro[NameObject("/Fields")] = ArrayObject()
        root[NameObject("/AcroForm")] = writer._add_object(acro)
    acro = root["/AcroForm"].get_object()
    if "/Fields" not in acro:
        acro[NameObject("/Fields")] = ArrayObject()
    acro[NameObject("/Fields")].extend(new_widget_refs)

    # Reportlab already supplied correct /AP appearance streams for both widgets
    # (verified: text /N stream + checkbox /N {/Off,/Yes}). We therefore do NOT
    # set /NeedAppearances: pdf.js, in ENABLE_FORMS mode, renders blank when
    # NeedAppearances is on but it cannot regenerate the stream, whereas with the
    # flag off it honours the embedded /AP and renders the values. We force it
    # off explicitly in case the base form had it set.
    if "/NeedAppearances" in acro:
        acro[NameObject("/NeedAppearances")] = BooleanObject(False)
    # Drop XFA so the AcroForm (not the XFA template) governs rendering.
    if "/XFA" in acro:
        del acro[NameObject("/XFA")]

    with open(out, "wb") as fh:
        writer.write(fh)

    # Structural self-check.
    r = PdfReader(out)
    fields = r.get_fields() or {}
    missing = [n for n in (TEXT_NAME, CHECK_NAME) if n not in fields]
    if missing:
        raise RuntimeError(
            f"reportlab+pypdf failed to register {missing} in /AcroForm /Fields"
        )

    return out


if __name__ == "__main__":
    print(run())
