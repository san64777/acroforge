"""GATE A probe: pikepdf low-level AcroForm (MPL-2.0 -> robust fallback).

Builds raw combined widget+field dictionaries, attaches them to page 1's
/Annots, and registers them via the LOW-LEVEL core AcroForm helper
`pdf.acroform.add_and_rename_fields(...)` (NOT `pikepdf.form.Form`, which raises
on the duplicate annotation-level /T names this fixture contains). Then it sets
the values and generates appearance streams.

Researched API (pikepdf 10.7.3):
  - `pdf.acroform` -> `pikepdf._core.AcroForm` (a QPDFAcroFormDocumentHelper),
    with methods including:
      add_and_rename_fields(fields: ObjectList) -> None   # dedups names safely
      add_field(field: AcroFormField) -> None
      get_fields() / fields()
      generate_appearances_if_needed() -> None  # only when NeedAppearances set;
                                                 # handles text/choice, NOT buttons
  - `pdf.generate_appearance_streams()` also exists on the Pdf object.
  - `pikepdf.AcroFormField` wraps a field dict; `.set_value(str|Object,
    need_appearance=True)`, `.generate_appearance(annot)`.
  - We pass raw widget dicts (each is its own field: /T,/FT,/Ff,/Rect,/V,...) as
    a `pikepdf.Array` / list to `add_and_rename_fields`, which appends them to
    /AcroForm /Fields (renaming on collision) — exactly what a duplicate-name
    base needs.

Coords (page 612x792, bottom-left origin): text at x0=200,y0=772,x1=360,y1=788;
checkbox 14pt box at x0=380,y0=772.
"""

from __future__ import annotations

import pikepdf
from pikepdf import Array, Dictionary, Name, String


def _make_check_appearance(pdf: pikepdf.Pdf, w: float, h: float) -> Dictionary:
    """Build a /AP appearance dict for a checkbox with /Yes (checked) and /Off
    (empty) states. pikepdf's appearance generator does NOT synthesize button
    appearances, so we draw them ourselves with a ZapfDingbats check glyph (4)."""
    bbox = Array([0, 0, w, h])
    font_size = h * 0.8
    dr = Dictionary(
        Font=Dictionary(
            ZaDb=pdf.make_indirect(
                Dictionary(
                    Type=Name.Font,
                    Subtype=Name.Type1,
                    BaseFont=Name.ZapfDingbats,
                )
            )
        )
    )
    # "4" is the check mark in ZapfDingbats. Centre it roughly in the box.
    on_content = (
        f"q 0.85 0.92 1.0 rg 0 0 {w} {h} re f Q\n"
        f"q BT /ZaDb {font_size:.2f} Tf 0 g {w * 0.18:.2f} {h * 0.18:.2f} Td (4) Tj ET Q\n"
    ).encode()
    off_content = f"q 0.85 0.92 1.0 rg 0 0 {w} {h} re f Q\n".encode()

    on_stream = pdf.make_stream(on_content)
    on_stream.Type = Name.XObject
    on_stream.Subtype = Name.Form
    on_stream.FormType = 1
    on_stream.BBox = bbox
    on_stream.Resources = Dictionary(dr)

    off_stream = pdf.make_stream(off_content)
    off_stream.Type = Name.XObject
    off_stream.Subtype = Name.Form
    off_stream.FormType = 1
    off_stream.BBox = bbox
    off_stream.Resources = Dictionary(ProcSet=Array([Name.PDF]))

    return Dictionary(
        N=Dictionary(Yes=pdf.make_indirect(on_stream), Off=pdf.make_indirect(off_stream))
    )

TEXT_NAME = "af_probe_text"
TEXT_VALUE = "ACROFORGE"
CHECK_NAME = "af_probe_check"


def run(src: str = "tests/fixtures/f1040.pdf", out: str = "spikes/out_pikepdf.pdf") -> str:
    pdf = pikepdf.open(src)
    page = pdf.pages[0]

    # --- Text field widget (combined field+widget dict) ---
    text_widget = pdf.make_indirect(
        Dictionary(
            Type=Name.Annot,
            Subtype=Name.Widget,
            FT=Name.Tx,
            T=String(TEXT_NAME),
            V=String(TEXT_VALUE),
            DA=String("/Helv 10 Tf 0 g"),
            Rect=Array([200, 772, 360, 788]),
            F=4,  # Print flag
            P=page.obj,
            MK=Dictionary(BC=Array([0, 0, 0]), BG=Array([0.85, 0.92, 1.0])),
            BS=Dictionary(W=1, S=Name.S),
        )
    )

    # --- Checkbox widget (checked) ---
    # /AS = /Yes selects the "on" appearance; /V = /Yes is the field value.
    # We attach a hand-built /AP (pikepdf won't generate button appearances).
    check_ap = _make_check_appearance(pdf, 14.0, 14.0)
    check_widget = pdf.make_indirect(
        Dictionary(
            Type=Name.Annot,
            Subtype=Name.Widget,
            FT=Name.Btn,
            T=String(CHECK_NAME),
            V=Name.Yes,
            AS=Name.Yes,
            Rect=Array([380, 772, 394, 786]),
            F=4,
            P=page.obj,
            DA=String("/ZaDb 0 Tf 0 g"),
            MK=Dictionary(
                BC=Array([0, 0, 0]),
                BG=Array([0.85, 0.92, 1.0]),
                CA=String("4"),  # ZapfDingbats check glyph
            ),
            BS=Dictionary(W=1, S=Name.S),
            AP=check_ap,
        )
    )

    # --- Attach widgets to the page's /Annots ---
    if "/Annots" in page:
        page.Annots.append(text_widget)
        page.Annots.append(check_widget)
    else:
        page.Annots = Array([text_widget, check_widget])

    # --- Register in /AcroForm /Fields via the core helper (handles dup names) ---
    acro = pdf.acroform
    if not acro.exists:
        # Create a minimal AcroForm if missing (this fixture has one already).
        pdf.Root.AcroForm = pdf.make_indirect(Dictionary(Fields=Array([])))
    acro.add_and_rename_fields([text_widget, check_widget])

    # The base form ships an XFA template; remove it so the AcroForm we just
    # extended governs rendering (otherwise XFA-aware viewers ignore AcroForm).
    af_obj = pdf.Root.AcroForm
    if "/XFA" in af_obj:
        del af_obj.XFA

    # Generate appearance streams for the TEXT field. pikepdf's generator only
    # acts when /NeedAppearances is set, and only handles text/choice fields
    # (NOT buttons) -- the checkbox /AP was built explicitly above. This
    # fixture's /DR carries /Helv and /ZaDb so DA font lookups resolve.
    af_obj.NeedAppearances = True
    acro.generate_appearances_if_needed()
    # Turn the flag back off: with real /AP streams now present we want viewers
    # to honour them rather than (fail to) regenerate.
    af_obj.NeedAppearances = False

    pdf.save(out)
    pdf.close()

    # Structural self-check.
    import pypdf

    r = pypdf.PdfReader(out)
    fields = r.get_fields() or {}
    # add_and_rename_fields may rename on collision; our names are unique here,
    # but accept any key that startswith our names just in case.
    def present(base: str) -> bool:
        return any(k == base or k.startswith(base) for k in fields)

    missing = [n for n in (TEXT_NAME, CHECK_NAME) if not present(n)]
    if missing:
        raise RuntimeError(
            f"pikepdf failed to register {missing} in /AcroForm /Fields; "
            f"got keys sample: {sorted(fields)[:8]}"
        )

    return out


if __name__ == "__main__":
    print(run())
