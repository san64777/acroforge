# GATE A — Engine Bake-off Results

## VERDICT

**WINNER: reportlab + pypdf** — strictly permissive (reportlab BSD + pypdf BSD-3-Clause), no copyleft anywhere in the dep tree; correctly registers and renders the field on the real f1040 (XFA + duplicate field names).

**Fallback: pikepdf** — MPL-2.0 (weak/file-level copyleft); structurally correct but not "strictly permissive".

**Rejected: PyPDFForm** — two independent failures: (1) orphaned fields not registered in `/AcroForm /Fields`; (2) broken text `/AP` stream. Additionally, PyPDFForm 5.2.0 is transitively MPL-2.0 (pikepdf is a required runtime dep), so it is no longer strictly permissive.

---

**Task:** add ONE text field (`af_probe_text` = `ACROFORGE`) and ONE checkbox
(`af_probe_check`, checked) near the top of page 1 of `tests/fixtures/f1040.pdf`
— a form with **duplicate annotation-level `/T` field names** (verified: 6 dup
names incl. `Dependent1[0]` x3, `c1_8[0]` x2) **and an XFA template**.

Fields placed in clear whitespace in the strip above the "1040" title:
text at `[200, 772, 360, 788]`, checkbox 14pt at `[380, 772, 394, 786]`
(page is 612x792 pt, bottom-left origin).

> Note for the judge: the harness `render_pdfjs.mjs` uses
> `AnnotationMode.ENABLE_FORMS`. In this **headless `@napi-rs/canvas`** setup,
> pdf.js does **not paint interactive widget values onto the canvas** under
> ENABLE_FORMS (it expects an HTML annotation layer) — so for **all** candidates
> the `*_pdfjs.png` top strip is blank even when the field is 100% correct.
> pdf.js *does* parse the fields with the right names/types/values. Rendering the
> same files under `AnnotationMode.ENABLE` (honour embedded `/AP`) is the true
> cross-viewer test and is reported in the "pdf.js (ENABLE / `/AP`)" column.

## Results table

| candidate | license posture | probe ran | structural check (field registered + value) | both PNGs produced | pdfium render | pdf.js (ENABLE / `/AP`) | errors / notes |
|---|---|---|---|---|---|---|---|
| **PyPDFForm** | MIT itself, but **NOT strictly permissive in 5.2.0**: its runtime deps now include **pikepdf (MPL-2.0)** + cryptography (Apache/BSD), fonttools (MIT), pillow (MIT-CMU), pypdf (BSD-3), reportlab (BSD). The old "on pypdf+reportlab only" premise is outdated — MPL-2.0 is now in the tree. | y | **FAIL** — `get_fields()` finds neither field. Widgets are added to page `/Annots` (with `/T`,`/FT`,`/V`,`/AS`) but **never registered in `/AcroForm /Fields`** (top-level still only `topmostSubform[0]`). | y | text + checkbox both visible (pdfium walks page annots, regenerates from `/V`) | **checkbox visible, text NOT** — its text-field `/AP` is a bogus `TextStringObject`, not a real appearance stream; and fields aren't in `/Fields`. | Two distinct failures on this XFA/dup-name form: (1) orphaned fields not in `/Fields`; (2) broken text `/AP`. Root cause: `_apply_widgets_to_pages` only appends to `page[/Annots]`; XFA left intact. |
| **reportlab + pypdf (DIY)** | **strictly permissive** — reportlab BSD + pypdf BSD-3-Clause. No copyleft anywhere. | y | **PASS** — text registered, `/V = ACROFORGE`; checkbox registered, `/V = /Yes`. | y | text (blue bg + border) + checked checkbox both visible | **both visible** — reportlab emits real `/AP` streams (text `(ACROFORGE) Tj` + checkbox `/N {/Off,/Yes}`). | Probe registers widgets in `/AcroForm /Fields` explicitly (clone annots into writer, append refs to `/Fields`), drops XFA, leaves NeedAppearances off so `/AP` is honoured. Robust against the dup-name base because we don't use pypdf's field-tree merge. |
| **pikepdf (low-level)** | **MPL-2.0** — weak/file-level copyleft. Permissive enough for a fallback (only requires sharing changes to MPL files themselves), but **not "strictly permissive"** like MIT/BSD. | y | **PASS** — text registered, `/V = ACROFORGE`; checkbox registered, `/V = /Yes`. | y | text + checked checkbox both visible | **both visible** — text `/AP` generated; checkbox `/AP {/Off,/Yes}` built by hand. | Used core `pdf.acroform.add_and_rename_fields([...])` (handles dup names; `pikepdf.form.Form` would have raised). Gotchas found: `acroform.exists` is a **property** not a method; `generate_appearances_if_needed()` only fires when `/NeedAppearances` is set AND only handles text/choice fields — it does **NOT** synthesize **button** appearances, so the checkbox `/AP` had to be drawn manually (ZapfDingbats "4"). |

## License summary (verified via `uv run pip-licenses`)

```
PyPDFForm   5.2.0   MIT          -> but deps include pikepdf 10.7.3 MPL-2.0
pypdf       6.13.0  BSD-3-Clause
reportlab   4.5.1   BSD License
pikepdf     10.7.3  MPL-2.0
cryptography 48.0.0 Apache-2.0 OR BSD-3-Clause   (PyPDFForm dep)
fonttools   4.63.0  MIT                          (PyPDFForm dep)
pillow      12.2.0  MIT-CMU                      (PyPDFForm dep)
```

`PyPDFForm` declared runtime requires (`importlib.metadata`):
`cryptography, fonttools, pikepdf, pillow, pypdf, reportlab`.
The single copyleft entry in the PyPDFForm tree is **pikepdf (MPL-2.0)**.

**Strictly-permissive ranking by actual dep tree:**
1. **reportlab + pypdf** — BSD + BSD-3 only. Strictly permissive. ✅
2. **PyPDFForm** — MIT package, but transitively MPL-2.0 (pikepdf) in 5.2.0. ⚠️
3. **pikepdf** — MPL-2.0. ⚠️ (same copyleft tier as #2's transitive dep)

## API notes (researched, not assumed)

- **PyPDFForm 5.2.0:** no `create_widget`. Use
  `PdfWrapper.bulk_create_fields([Fields.TextField(...), Fields.CheckBoxField(...)])`
  then `.fill({name: value/bool})` then `.read()`. Field ctors are 1-indexed
  `page_number`, bottom-left `(x, y)`; `TextField(... width=, height=)`,
  `CheckBoxField(... size=)`.
- **pikepdf 10.7.3:** `pdf.acroform` -> core `AcroForm` helper with
  `add_and_rename_fields(list_of_field_dicts)`, `add_field`, `exists`
  (**property**), `needs_appearances`, `generate_appearances_if_needed()`.
  `pdf.generate_appearance_streams()` exists too but, like the helper, won't
  build **button** appearances.
- **reportlab 4.5.1:** `canvas.acroForm.textfield(name=, value=, x=, y=, width=,
  height=, fontSize=, borderStyle=, borderWidth=, forceBorder=, ...)` and
  `.checkbox(name=, checked=, x=, y=, size=, buttonStyle=, borderStyle=, ...)`.

## Files produced

- Probes: `spikes/gate_a_pypdfform.py`, `spikes/gate_a_reportlab_pypdf.py`, `spikes/gate_a_pikepdf.py`
- Outputs: `spikes/out_pypdfform.pdf`, `spikes/out_reportlab_pypdf.pdf`, `spikes/out_pikepdf.pdf`
- Renders: `spikes/pypdfform_pdfium.png` / `spikes/pypdfform_pdfjs.png`,
  `spikes/reportlab_pypdf_pdfium.png` / `spikes/reportlab_pypdf_pdfjs.png`,
  `spikes/pikepdf_pdfium.png` / `spikes/pikepdf_pdfjs.png`
