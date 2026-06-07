"""acroforge demo — run this to SEE it work and learn the API.

    uv run python examples/demo.py

It writes PDFs you can open in any viewer into examples/output/.
Two demos:
  A) THE ENGINE (reliable): take a flat form, add named fields, fill, flatten.
  B) DETECTION (best-effort): auto-find fields on the real IRS W-9.
"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.pdfgen import canvas

import acroforge as af

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)


def make_flat_form() -> bytes:
    """Draw a simple FLAT form (just labels + lines + a box — NO real fields)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 740, "Membership Registration")
    c.setFont("Helvetica", 11)
    # label + write-on line for each field
    c.drawString(72, 700, "Full name")
    c.line(150, 698, 460, 698)
    c.drawString(72, 670, "Email")
    c.line(150, 668, 460, 668)
    c.drawString(72, 640, "I agree to the terms")
    c.rect(300, 636, 12, 12)            # a checkbox outline
    c.save()
    return buf.getvalue()


def demo_a_engine() -> None:
    print("\n=== Demo A: THE ENGINE (you supply field positions) ===")
    flat = make_flat_form()
    (OUT / "A1_flat_form.pdf").write_bytes(flat)
    print("  wrote A1_flat_form.pdf      (a flat form — you can't type in it)")

    # 1) BUILD — add real, named, fillable fields at the positions above
    fields = [
        af.FieldSpec(type=af.FieldType.TEXT, page=0, rect=(150, 698, 460, 714), name="full_name"),
        af.FieldSpec(type=af.FieldType.TEXT, page=0, rect=(150, 668, 460, 684), name="email"),
        af.FieldSpec(type=af.FieldType.CHECKBOX, page=0, rect=(300, 636, 312, 648), name="agree"),
    ]
    built = af.build(flat, fields)
    (OUT / "A2_fillable.pdf").write_bytes(built)
    print("  wrote A2_fillable.pdf       (now it has real fields — open it and type!)")

    # 2) FILL — set values by name
    filled = af.fill(built, {"full_name": "Asha Rao", "email": "asha@example.com", "agree": True})
    (OUT / "A3_filled.pdf").write_bytes(filled)
    print("  wrote A3_filled.pdf         (filled in programmatically)")

    # 3) FLATTEN — bake the values in permanently (no longer editable)
    flat_final = af.flatten(filled)
    (OUT / "A4_flattened.pdf").write_bytes(flat_final)
    print("  wrote A4_flattened.pdf      (values baked in — final, non-editable)")


def demo_b_detection() -> None:
    print("\n=== Demo B: DETECTION (best-effort, auto-find fields) ===")
    w9 = Path("tests/fixtures/fw9.pdf")
    if not w9.exists():
        print("  (skipped — tests/fixtures/fw9.pdf not found; run from the repo root)")
        return
    data = w9.read_bytes()

    manifest = af.detect(data)              # FormManifest with confidence-scored guesses
    print(f"  detect() found {len(manifest.fields)} candidate fields (best-effort, review these)")
    for f in manifest.fields[:5]:
        print(f"    - {f.type.value:8} '{f.name}'  confidence={f.confidence}")

    auto = af.make_fillable(data)           # detect() then build()
    (OUT / "B_w9_autofillable.pdf").write_bytes(auto)
    print("  wrote B_w9_autofillable.pdf (the flat W-9, now auto-fillable — imperfect, review it)")


if __name__ == "__main__":
    demo_a_engine()
    demo_b_detection()
    print(f"\nDone. Open the PDFs in: {OUT}")
