# acroforge

**Turn flat PDFs into real, fillable AcroForms. Permissive (Apache-2.0), deterministic, zero-copyleft.**

---

## What it does

acroforge takes any PDF — vector or scanned — and injects real AcroForm fields at positions you specify. The result is a standards-compliant fillable PDF that renders correctly in Chrome's pdfium and Firefox's pdf.js.

Three operations:

| Operation | What it does |
|-----------|--------------|
| `build` | Inject interactive AcroForm fields into a flat PDF |
| `fill` | Set field values by name on a fillable PDF |
| `flatten` | Bake field appearances into page content; remove interactive fields |

All three functions accept and return plain `bytes`, making them easy to compose in any pipeline.

---

## Install

**Not yet published to PyPI.** Install from source:

```bash
pip install -e .
# or, with uv:
uv pip install -e .
```

When published:

```bash
pip install acroforge
```

---

## Python usage

```python
import io
from reportlab.pdfgen import canvas  # any PDF source works
import acroforge as af
from acroforge import FieldSpec, FieldType

# --- Step 0: obtain a flat PDF (bytes) any way you like ---
buf = io.BytesIO()
c = canvas.Canvas(buf, pagesize=(612, 792))
c.drawString(72, 720, "Name:")
c.drawString(72, 680, "Agree to terms:")
c.save()
flat_pdf: bytes = buf.getvalue()

# --- Step 1: describe the fields you want ---
fields = [
    FieldSpec(
        type=FieldType.TEXT,
        page=0,
        rect=(200, 700, 450, 730),  # (x0, y0, x1, y1) in PDF points
        name="full_name",
    ),
    FieldSpec(
        type=FieldType.CHECKBOX,
        page=0,
        rect=(200, 660, 220, 680),
        name="agree",
        export_value="Yes",
    ),
]

# --- Step 2: inject the fields ---
fillable: bytes = af.build(flat_pdf, fields)

# --- Step 3: fill values ---
filled: bytes = af.fill(fillable, {"full_name": "Jane Doe", "agree": True})

# --- Step 4: flatten (optional — locks the form) ---
final: bytes = af.flatten(filled)

# Write to disk
with open("output.pdf", "wb") as f:
    f.write(final)
```

---

## CLI usage

```bash
# 1. Inject fields described in a JSON manifest
acroforge build in.pdf manifest.json fillable.pdf

# 2. Fill fields from a JSON object {name: value}
acroforge fill fillable.pdf data.json filled.pdf

# 3. Flatten (bake and lock)
acroforge flatten filled.pdf final.pdf
```

**Example `manifest.json`:**

```json
[
  {
    "type": "text",
    "page": 0,
    "rect": [200, 700, 450, 730],
    "name": "full_name"
  },
  {
    "type": "checkbox",
    "page": 0,
    "rect": [200, 660, 220, 680],
    "name": "agree",
    "export_value": "Yes"
  },
  {
    "type": "radio",
    "page": 0,
    "rect": [200, 620, 220, 640],
    "name": "plan",
    "options": ["basic", "pro", "enterprise"],
    "export_value": "pro"
  }
]
```

**Example `data.json`:**

```json
{"full_name": "Jane Doe", "agree": true, "plan": "pro"}
```

---

## Field types

| Type | `FieldType` | Notes |
|------|-------------|-------|
| Single-line text | `FieldType.TEXT` | Optional `maxlen` to cap character count |
| Multi-cell comb | `FieldType.COMB` | `maxlen` sets the number of cells (e.g. SSN = 9) |
| Checkbox | `FieldType.CHECKBOX` | `export_value` is the on-state value (default `"Yes"`) |
| Radio button | `FieldType.RADIO` | One `FieldSpec` per button; share `name`, set `export_value` per button |
| Signature | `FieldType.SIGNATURE` | Placeholder widget — renders a blank sig box |

### `FieldSpec` reference

```python
class FieldSpec(BaseModel):
    type: FieldType
    page: int                                    # 0-indexed
    rect: tuple[float, float, float, float]      # (x0, y0, x1, y1) in PDF points
    name: str                                    # AcroForm field name
    options: list[str] | None = None             # radio group member labels
    maxlen: int | None = None                    # TEXT cap / COMB cell count
    export_value: str | None = None              # radio/checkbox on-value
    confidence: float = 1.0                      # 1.0 = explicit; <1.0 = best-effort guess
```

---

## Scope and honest limits

**v1 is the deterministic engine.** You supply field positions via `FieldSpec`s — acroforge injects, fills, and flattens them reliably. It does not guess where fields belong.

Automatic field *detection* on a flat PDF (finding the boxes, labelling them, grouping radio buttons) is a **separate, later module** not included in this release. There is no AI in this package.

The engine accepts any PDF as input (vector or scanned) — it adds fields at exactly the coordinates you give it. Automatically locating those coordinates from a scanned page is future work.

---

## Engine and dependencies

Runtime dependencies are strictly permissive:

| Package | License | Role |
|---------|---------|------|
| `reportlab` | BSD | Field widget rendering |
| `pypdf` | BSD-3-Clause | PDF read / merge / flatten |
| `pdfplumber` | MIT | PDF geometry utilities |
| `PyPDFForm` | MIT | Fill helpers |
| `pydantic` | MIT | `FieldSpec` / `FormManifest` validation |

Optional extras:

- `[fallback]` — adds `pikepdf` (MPL-2.0) as a fallback PDF writer; **not required** for the default engine path.
- `[harness]` — adds `pypdfium2` + `Pillow` for cross-viewer visual regression tests.

No GPL, AGPL, LGPL, or SSPL in the runtime tree. CI enforces this on every push via `pip-licenses --fail-on='GPL;AGPL;LGPL;SSPL'`.

---

## License

Apache-2.0. See [`LICENSE`](LICENSE).

No copyrighted form templates are included or bundled. Bring your own PDFs.
