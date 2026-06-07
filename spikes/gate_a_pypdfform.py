"""GATE A probe: PyPDFForm (MIT, on pypdf+reportlab).

Adds a text field `af_probe_text` and a checkbox `af_probe_check` near the top of
page 1 of a duplicate-field-name form, fills them, and writes the output.

Researched API (PyPDFForm 5.2.0):
  - Widget creation is via `PdfWrapper.bulk_create_fields([FieldTypes...])`
    (the older `create_widget` method does NOT exist in 5.x).
  - Field types live on the `PyPDFForm.Fields` class: `Fields.TextField`,
    `Fields.CheckBoxField`, ...
      TextField(name, page_number, x, y, width=, height=, ...)
      CheckBoxField(name, page_number, x, y, size=, ...)
    `page_number` is 1-indexed; (x, y) is the bottom-left corner in PDF points
    (PyPDFForm draws via a reportlab canvas overlay).
  - `.fill({name: value})` fills; checkbox value is a bool.
  - `.read()` returns bytes; it also removes XFA / handles NeedAppearances.
"""

from __future__ import annotations

from PyPDFForm import Fields, PdfWrapper

TextField = Fields.TextField
CheckBoxField = Fields.CheckBoxField

TEXT_NAME = "af_probe_text"
TEXT_VALUE = "ACROFORGE"
CHECK_NAME = "af_probe_check"


def run(src: str = "tests/fixtures/f1040.pdf", out: str = "spikes/out_pypdfform.pdf") -> str:
    wrapper = PdfWrapper(src)

    # Coords: the strip above the "1040" title (pdfY ~770-790, x 200-560) is
    # empty whitespace on page 1 (verified with pdfplumber), so the widgets land
    # in clear space. (x, y) is bottom-left in PDF points; page is 612x792.
    text_field = TextField(
        name=TEXT_NAME,
        page_number=1,
        x=200,
        y=772,
        width=160,
        height=16,
        font_size=10,
    )
    check_field = CheckBoxField(
        name=CHECK_NAME,
        page_number=1,
        x=380,
        y=772,
        size=14,
    )

    wrapper = wrapper.bulk_create_fields([text_field, check_field])

    # Fill values (checkbox -> True for checked).
    wrapper = wrapper.fill({TEXT_NAME: TEXT_VALUE, CHECK_NAME: True})

    data = wrapper.read()
    if not data:
        raise RuntimeError("PyPDFForm produced empty output bytes")

    with open(out, "wb") as fh:
        fh.write(data)

    # Sanity: confirm fields exist in the schema PyPDFForm tracks.
    schema_props = (wrapper.schema or {}).get("properties", {})
    missing = [n for n in (TEXT_NAME, CHECK_NAME) if n not in schema_props]
    if missing:
        raise RuntimeError(
            f"PyPDFForm did not register fields {missing}; "
            f"schema props: {sorted(schema_props)[:10]}"
        )

    return out


if __name__ == "__main__":
    print(run())
