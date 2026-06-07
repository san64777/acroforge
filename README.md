# forma

**The permissive, AI-native toolkit for PDF *forms*** — turn any PDF form into a typed schema, fill it by meaning, and create fillable forms from flat PDFs. Apache-2.0, zero AGPL, deterministic core + confidence-scored AI, library + MCP server.

> *Tagline: "Pydantic for PDF forms."*

**Status:** research validated, **not yet built**. Verdict: `narrow-but-viable`, **6/10, go-with-fixes**. Do NOT write feature code until the three gating spikes below pass.

---

## What forma is — and is NOT
- **IS:** the *write/operate* direction for PDF forms — read fields → typed schema → fill by meaning → create fillable from flat → flatten, all permissive and self-hostable, plus an MCP server so agents can operate forms.
- **NOT** a PDF→markdown/RAG parser (Docling/Marker/MarkItDown own *read-for-text*).
- **NOT** a general PDF engine — we **wrap** permissive primitives (pikepdf MPL-2.0, pypdf BSD, reportlab BSD), never rebuild pdfium/MuPDF.
- **NOT** AGPL (unlike PyMuPDF/borb — runtime-toxic for regulated buyers). CI-enforced zero-copyleft tree.
- **NOT** autonomous: AI *proposes* (confidence-scored), deterministic code *commits*, low-confidence routes to human review. Never sold as perfect.

## The verified wedge (live June 2026)
- ✅ **"Pydantic for PDF forms" (semantic typed schema) is UNOWNED** — the lead wedge.
- ✅ flat→fillable auto-detect CREATE is unowned in permissive OSS (concede raw detection to CommonForms; own the layer above: grouping + naming + schema + fill).
- 🟡 fill-by-meaning is solved-and-monetized in *closed* cloud (Reducto/Instafill/Anvil) — we're the permissive self-hostable version, not novel.
- 🟡 forms-MCP exists but weak — claim "first *permissive semantic* forms-MCP," not "first."
- ⚠️ **Live threat: `pdf_oxide`** (MIT/Apache, Rust, ~804★, already ships form *creation* + MCP, fast). If it adds typed schema + form-MCP tools, the wedge closes. Speed matters.

## Must-fix BEFORE any feature code (the gating Week-0 work)
1. **Backend spike — pikepdf duplicate-field-name failure.** `pikepdf.form` officially fails on duplicate field names = exactly IRS 1040 / W-9 / USCIS / ACORD (our headline forms). Prove a low-level `pikepdf.AcroForm`/pypdf fallback does fill+flatten+appearance-streams on a real gov fixture *before* committing the "wrap pikepdf" thesis.
2. **Cross-viewer visual-regression harness** (pdfium + pdf.js + Adobe spot-check) on day one — the only deterministic moat vs naive fillers.
3. **Confidence-calibration decision.** LLM self-reported confidence is NOT a calibrated probability. Decide: calibrate against a labeled set, or gate via deterministic re-validation + grammar-constrained enums. Until then thresholds 0.95+ and "AI proposes, human confirms."

## v1 scope (must be DEEP — not "plumbing + an LLM call")
Deterministic core (read/fill/flatten w/ baked appearance streams) **+** deep typed schema (junk→human name, **validation-rule inference**, **radio/checkbox group→enum consolidation**, **Zod/TS export**) **+** a constrained fill-by-meaning (dry-run default). CI license-gate ships in v1. AcroForm-only; XFA skipped; scanned excluded.

## Honest framing
- It's **off the rarest scraping moat** — a 2nd-edge (document-AI) breadth/credibility play. Build behind the rare-edge anchors, not as the headline.
- The deterministic plumbing is already commodity; **the only thing that makes forma matter is the AI-native layer, shipped deep and fast.**

## Research
Full validation + plan in [`research/`](research/):
- [`forma-validated-plan.md`](research/forma-validated-plan.md) — the 15-agent validated plan, "what we can build" tiered, competitor table, risks. **Start here.**
- [`fillability-idea-card.md`](research/fillability-idea-card.md) — original idea card + competitive landscape.
- [`fillability-product-plan-superseded.md`](research/fillability-product-plan-superseded.md) — earlier *product* (CLI) framing, superseded by the library framing.

## Next step
Build the task-by-task plan with the three gating spikes as Week-0, then start there. (Not scaffolded yet — no repo/git init until the spikes pass and you give the go.)
