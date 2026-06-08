"""reportlab + pypdf field-creation backend (Gate A winner, BSD + BSD).

Productionizes the proven spike technique
(``spikes/gate_a_reportlab_pypdf.py``): reportlab draws each widget - with a
real ``/AP`` appearance stream - onto a same-size overlay page, then pypdf
clones those widget annotations into the target, repoints ``/P`` at the right
page, and registers the refs in ``/AcroForm /Fields`` so spec-correct viewers
(e.g. pdf.js, which enumerates ``/Fields``) render them. ``/NeedAppearances``
is forced off (embedded ``/AP`` is authoritative) and any ``/XFA`` is dropped.
"""

from __future__ import annotations

import io
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any, cast

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

_FF_EDIT = 1 << 18  # /Ch combo: editable (free text allowed)
_FF_MULTISELECT = 1 << 21  # /Ch list box: multiple selections allowed


def _reportlab_options(options: list[str] | list[tuple[str, str]]) -> list[object]:
    """Map acroforge options to reportlab's ``(label, value)`` tuple convention.

    acroforge stores choice options as plain strings or ``(export, label)``
    pairs. reportlab's ``choice``/``listbox`` want ``(label, value)``, so a pair
    is reversed; a plain string passes through (export == label).
    """
    out: list[object] = []
    for o in options:
        if isinstance(o, str):
            out.append(o)
        else:
            export, label = o
            out.append((label, export))
    return out


def _first_export(options: list[str] | list[tuple[str, str]]) -> str:
    """First option's export value (used as a build-time value to dodge the
    reportlab ``lbextras`` bug; the field is blanked afterwards)."""
    first = options[0]
    return first if isinstance(first, str) else first[0]


def _choice_font_size(spec: FieldSpec, h: float) -> float:
    """Font size for a choice widget's appearance.

    A list box needs the rect tall enough to fit at least one option row:
    reportlab computes ``nopts = int((h - 4*bw) / (1.2*fontSize))`` and then
    divides by ``nopts`` (a 0 is a ZeroDivisionError). Shrink the font so a row
    fits; raise a clear error if the rect is fundamentally too short. Dropdowns
    (combo boxes) do not hit this path, so they keep the simple sizing.
    """
    fs = max(4.0, min(12.0, h - 2))
    if spec.list_box:
        avail = h - 4.0  # height minus 4*borderWidth (borderWidth == 1)
        if 1.2 * fs > avail:
            fs = avail / 1.3  # shrink so >= 1 row fits, with float-rounding margin
        if fs < 2:
            raise ValueError(
                f"CHOICE list box '{spec.name}' rect height {h:.0f}pt is too short to render "
                f"an option row; increase its height or use a dropdown (list_box=False)"
            )
    return fs


def _draw_widget(form: object, spec: FieldSpec) -> None:
    """Draw one widget onto reportlab's AcroForm overlay.

    ``form`` is a ``reportlab.pdfbase.acroform.AcroForm`` (untyped - reportlab
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
    elif spec.type is FieldType.CHOICE:
        options = spec.options or []
        flags = []
        if not spec.list_box:
            flags.append("combo")
        if spec.editable:
            flags.append("edit")
        if spec.multi_select:
            flags.append("multiSelect")
        # reportlab choice()/listbox() crash on a falsy value (UnboundLocalError:
        # lbextras), so seed with the first export value; create_fields() blanks
        # the selection afterwards so the built field starts empty.
        draw = form.choice if not spec.list_box else form.listbox  # type: ignore[attr-defined]
        draw(
            name=spec.name,
            value=_first_export(options),
            options=_reportlab_options(options),
            x=x0,
            y=y0,
            width=w,
            height=h,
            fontSize=_choice_font_size(spec, h),
            borderStyle="solid",
            borderWidth=1,
            forceBorder=True,
            fieldFlags=" ".join(flags),
        )
    else:
        raise NotImplementedError(f"field type {spec.type} not supported")


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
    This is a placeholder field only - not a digital-signature workflow.
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
    # pypdf <7: no public add_object; pin enforced in pyproject
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
    # pypdf <7: no public add_object; pin enforced in pyproject
    return writer._add_object(widget)


def _on_state_name(field: DictionaryObject) -> str | None:
    """Return a button field's on-state name (the ``/AP /N`` key that isn't ``/Off``).

    Looks at the field's own ``/AP /N`` (widget-as-field, e.g. checkbox) and, if it
    is a group, at its kids. Returns the single on-state name (e.g. ``"/On"``) when
    there is exactly one, else ``None`` (ambiguous or none found).
    """
    states: set[str] = set()
    sources: list[DictionaryObject] = [field]
    kids = field.get("/Kids")
    if kids:
        sources = [cast(DictionaryObject, k.get_object()) for k in kids]
    for src in sources:
        ap = src.get("/AP")
        if ap is None:
            continue
        normal = cast(DictionaryObject, ap.get_object()).get("/N")
        if normal is None:
            continue
        for key in cast(DictionaryObject, normal.get_object()):
            if key != "/Off":
                states.add(key)
    return states.pop() if len(states) == 1 else None


def _leaf_widget_idnums(node: DictionaryObject, seen: set[int]) -> set[int]:
    """Object numbers of the leaf /Widget annotations under a field node."""
    ref = node.indirect_reference
    nid = ref.idnum if ref is not None else None
    if nid is not None:
        if nid in seen:
            return set()
        seen.add(nid)
    kids = node.get("/Kids")
    if not kids:
        return {nid} if (nid is not None and node.get("/Subtype") == "/Widget") else set()
    out: set[int] = set()
    for k in kids:
        out |= _leaf_widget_idnums(cast(DictionaryObject, k.get_object()), seen)
    return out


def _field_index(refs: Any, prefix: str, seen: set[int], out: dict[str, list[DictionaryObject]]) -> None:
    """Map fully-qualified field name -> field node(s) by walking the /Fields tree.

    A name maps to a list because a malformed form may have two distinct subtrees
    sharing one qualified name; we must collect the widgets of all of them so the
    /Annots surgery matches what the /Fields surgery removes (no orphan widgets).
    """
    for ref in refs:
        node = cast(DictionaryObject, ref.get_object())
        nr = node.indirect_reference
        nid = nr.idnum if nr is not None else id(node)
        if nid in seen:
            continue
        seen.add(nid)
        t = node.get("/T")
        if t is None:
            continue  # a widget-only kid (e.g. a radio button): not a named field
        qname = f"{prefix}.{t}" if prefix else str(t)
        out.setdefault(qname, []).append(node)
        kids = node.get("/Kids")
        if kids:
            subfields = [k for k in kids if cast(DictionaryObject, k.get_object()).get("/T") is not None]
            _field_index(subfields, qname, seen, out)


def _filter_fields(refs: Any, prefix: str, targets: set[str]) -> list[Any]:
    """The /Fields (or /Kids) refs to keep, dropping targets and emptied parents."""
    kept: list[Any] = []
    for ref in refs:
        node = cast(DictionaryObject, ref.get_object())
        t = node.get("/T")
        qname = (f"{prefix}.{t}" if prefix else str(t)) if t is not None else prefix
        if t is not None and qname in targets:
            continue  # drop this field and all its descendants
        kids = node.get("/Kids")
        if kids:
            subfields = [k for k in kids if cast(DictionaryObject, k.get_object()).get("/T") is not None]
            widget_kids = [k for k in kids if cast(DictionaryObject, k.get_object()).get("/T") is None]
            new_kids = _filter_fields(subfields, qname, targets) + widget_kids
            if not new_kids:
                continue  # parent emptied -> drop it too
            node[NameObject("/Kids")] = ArrayObject(new_kids)
        kept.append(ref)
    return kept


class ReportlabPypdfWriter:
    """Writer backend: creates AcroForm fields via reportlab overlays + pypdf."""

    def create_fields(self, pdf: bytes, fields: list[FieldSpec]) -> bytes:
        if not fields:
            return pdf  # no-op: don't synthesize an empty /AcroForm

        # reportlab raises (at write time) on a radio group with a single button.
        # A 1-member radio group is functionally a checkbox - convert it so real
        # forms with single-button radios don't crash build().
        radio_counts = Counter(f.name for f in fields if f.type is FieldType.RADIO)
        if any(c == 1 for c in radio_counts.values()):
            fields = [
                f.model_copy(update={"type": FieldType.CHECKBOX})
                if (f.type is FieldType.RADIO and radio_counts[f.name] == 1)
                else f
                for f in fields
            ]

        writer = PdfWriter()
        writer.append(PdfReader(io.BytesIO(pdf)))

        n_pages = len(writer.pages)
        for f in fields:
            if not 0 <= f.page < n_pages:
                raise ValueError(
                    f"FieldSpec '{f.name}' references page {f.page} "
                    f"but PDF has {n_pages} page(s)"
                )

        # SIGNATURE widgets are built directly (reportlab has no /Sig helper) and
        # are kept out of the overlay loop; everything else goes via reportlab.
        by_page: defaultdict[int, list[FieldSpec]] = defaultdict(list)
        sig_by_page: defaultdict[int, list[FieldSpec]] = defaultdict(list)
        for f in fields:
            if f.type is FieldType.SIGNATURE:
                sig_by_page[f.page].append(f)
            else:
                by_page[f.page].append(f)

        root = writer.root_object
        if "/AcroForm" not in root:
            acro = DictionaryObject()
            acro[NameObject("/Fields")] = ArrayObject()
            # pypdf <7: no public add_object; pin enforced in pyproject
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
                    # repoint each kid's /P and add the kids - not the parent -
                    # to the page /Annots; register the parent in /Fields.
                    for kid in kids:
                        kid_obj = cast(DictionaryObject, kid.get_object())
                        kid_obj[NameObject("/P")] = base_page.indirect_reference
                        # Guard: a kid widget must reach the page /Annots as a
                        # real indirect ref. clone() normally registers it, but
                        # if not, register it now so we never append None.
                        kid_ref = kid_obj.indirect_reference
                        if kid_ref is None:
                            # pypdf <7: no public add_object; pin enforced in pyproject
                            kid_ref = writer._add_object(kid_obj)
                        annot_refs.append(kid_ref)
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

        # Choice fields are seeded with a default selection to work around a
        # reportlab bug; blank them so a freshly built field starts unselected
        # (pypdf regenerates an empty /AP for the "" value).
        choice_names = {f.name: "" for f in fields if f.type is FieldType.CHOICE}
        if choice_names:
            for page in writer.pages:
                writer.update_page_form_field_values(
                    page, choice_names, auto_regenerate=False
                )

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
        try:
            existing: set[str] | None = set(reader.get_fields() or {})
        except Exception:  # noqa: BLE001 - malformed field dict (e.g. /AP without /N): skip the pre-check
            existing = None
        if existing is not None:
            unknown = set(values) - existing
            if unknown:
                raise ValueError(f"fill(): fields not found in PDF: {sorted(unknown)}")
        # Map field name -> its AcroForm field dict so a boolean True resolves to
        # the field's real on-state (e.g. /On, /Checked) rather than a hard /Yes.
        field_dicts: dict[str, DictionaryObject] = {}
        acroform = reader.root_object.get("/AcroForm")
        if acroform is not None:
            for ref in cast(DictionaryObject, acroform.get_object()).get("/Fields") or []:
                fld = cast(DictionaryObject, ref.get_object())
                name = fld.get("/T")
                if name is not None:
                    field_dicts[str(name)] = fld

        def _allowed_values(fld: DictionaryObject | None) -> set[str] | None:
            # Permitted export values for a non-editable choice field, else None.
            if fld is None or fld.get("/FT") != "/Ch":
                return None
            if int(fld.get("/Ff") or 0) & _FF_EDIT:
                return None  # editable combo: free text allowed
            opts = fld.get("/Opt")
            if opts is None:
                return None
            allowed: set[str] = set()
            for item in opts.get_object():
                io_ = item.get_object()
                allowed.add(str(io_[0]) if isinstance(io_, ArrayObject) else str(io_))
            return allowed

        def _coerce(key: str, val: object) -> str:
            if isinstance(val, str):
                return val
            if val is True:
                fld = field_dicts.get(key)
                on = _on_state_name(fld) if fld is not None else None
                return on if on is not None else "/Yes"
            return str(val)

        def _is_multiselect(fld: DictionaryObject | None) -> bool:
            return (
                fld is not None
                and fld.get("/FT") == "/Ch"
                and bool(int(fld.get("/Ff") or 0) & _FF_MULTISELECT)
            )

        # Build one value map: scalars for text/buttons/single-select, lists for
        # multi-select choice. pypdf regenerates the /AP for both (so multi-select
        # selections render and stale /I is cleared), validated against options.
        out_values: dict[str, str | list[str]] = {}
        for key, val in values.items():
            fd = field_dicts.get(key)
            allowed = _allowed_values(fd)
            if isinstance(val, (list, tuple)):
                if not _is_multiselect(fd):
                    raise ValueError(
                        f"fill(): list value for '{key}' is only valid for a multi-select "
                        f"choice field"
                    )
                items = [str(x) for x in val]
                if allowed is not None:
                    bad = [x for x in items if x not in allowed]
                    if bad:
                        raise ValueError(f"fill(): {bad} not options of choice field '{key}'")
                out_values[key] = items
            else:
                s = _coerce(key, val)
                if allowed is not None and s != "" and s not in allowed:
                    raise ValueError(f"fill(): '{s}' is not an option of choice field '{key}'")
                out_values[key] = s

        for page in writer.pages:
            writer.update_page_form_field_values(page, out_values, auto_regenerate=False)

        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    def flatten(self, pdf: bytes) -> bytes:
        reader = PdfReader(io.BytesIO(pdf))
        try:
            fields = reader.get_fields() or {}
        except Exception:  # noqa: BLE001 - malformed field dict (e.g. /AP without /N)
            fields = {}
        if not fields and "/AcroForm" not in reader.root_object:
            return pdf  # no form fields: nothing to bake, return unchanged
        writer = PdfWriter()
        writer.append(reader)
        # pypdf 6.13 only bakes an /AP into the page content for fields named in
        # the ``fields`` mapping (the flatten path lives inside that loop), so an
        # empty mapping bakes nothing. Re-supply each field's existing ``/V`` so
        # ``flatten=True`` draws the appearance XObject into the page stream.
        values: dict[str, str | list[str]] = {}
        for name, info in fields.items():
            value = info.get("/V")
            if value is None:
                continue
            if isinstance(value, (list, tuple, ArrayObject)):
                values[name] = [str(x) for x in value]  # multi-select: keep as list
            else:
                values[name] = value if isinstance(value, str) else str(value)
        for page in writer.pages:
            writer.update_page_form_field_values(
                page, values, auto_regenerate=False, flatten=True
            )
        # Drop the now-redundant interactive layer: widget annotations + AcroForm.
        writer.remove_annotations(subtypes="/Widget")
        root = writer.root_object
        if "/AcroForm" in root:
            del root[NameObject("/AcroForm")]
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    def remove(self, pdf: bytes, names: str | Iterable[str]) -> bytes:
        name_set = {names} if isinstance(names, str) else set(names)
        if not name_set:
            return pdf  # nothing requested: no-op
        reader = PdfReader(io.BytesIO(pdf))
        writer = PdfWriter()
        writer.append(reader)
        acro_ref = writer.root_object.get("/AcroForm")
        acro = cast(DictionaryObject, acro_ref.get_object()) if acro_ref is not None else None
        top_fields = list(acro.get("/Fields") or []) if acro is not None else []

        # Match by fully-qualified name (what read_fields returns) over the field TREE,
        # not just top-level /Fields - nested/XFA field names live on parent chains.
        index: dict[str, list[DictionaryObject]] = {}
        _field_index(top_fields, "", set(), index)
        missing = name_set - index.keys()
        if missing:
            raise ValueError(f"remove(): fields not found in PDF: {sorted(missing)}")

        removed_widgets: set[int] = set()
        for qname in name_set:
            for node in index[qname]:
                removed_widgets |= _leaf_widget_idnums(node, set())

        # /Fields surgery: drop named fields, prune any parent left with no kids.
        if acro is not None:
            acro[NameObject("/Fields")] = ArrayObject(_filter_fields(top_fields, "", name_set))

        # /Annots surgery: drop the removed widgets from every page (match by object id;
        # radio/hierarchical kids have no /T so they cannot be matched by name here).
        for page in writer.pages:
            annots = page.get("/Annots")
            if not annots:
                continue
            page[NameObject("/Annots")] = ArrayObject(
                a for a in annots if getattr(a, "idnum", None) not in removed_widgets
            )

        # XFA would now describe fields that no longer exist; drop it (as build/flatten do).
        if acro is not None and "/XFA" in acro:
            del acro[NameObject("/XFA")]

        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
