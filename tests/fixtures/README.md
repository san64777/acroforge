# Test Fixtures

Public-domain US government forms used for acroforge integration tests.
All files listed here are **public domain (US government work)** and safe to commit.

## Files

| File | Source URL | License / Notes |
|------|-----------|-----------------|
| `fw9.pdf` | https://www.irs.gov/pub/irs-pdf/fw9.pdf | Public domain (US government work) — IRS Form W-9, Request for Taxpayer Identification Number |
| `f1040.pdf` | https://www.irs.gov/pub/irs-pdf/f1040.pdf | Public domain (US government work) — IRS Form 1040, US Individual Income Tax Return. Contains duplicate annotation-level field names (`/T`), used to test Gate A (duplicate-name handling). |
| `scanned_sample.pdf` | Derived from `fw9.pdf` | Public domain (US government work, derived) — First page of fw9.pdf rasterized to PNG at 2x scale via pypdfium2, then re-saved as an image-only PDF via Pillow. Contains zero vector text/lines/rects; used to test `is_scanned` detection (Gate C). |

## Notes

- `i9.pdf` (USCIS Form I-9) was attempted but the USCIS download endpoint returned an HTML redirect rather than a PDF; it is omitted from this fixture set.
- Do **not** add copyrighted commercial forms (ACORD, UB-04, CAQH, etc.) to this directory.
