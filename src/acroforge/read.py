"""Read existing AcroForm fields out of an already-fillable PDF into FieldSpecs.

This is the inverse of ``build``: instead of injecting widgets, it walks every
``/Widget`` annotation already registered in a PDF and reconstructs a
``FieldSpec`` for each one. Because these are real, registered fields (not
geometry guesses), every spec gets ``confidence = 1.0``. This makes the API
symmetric, so ``build(pdf, read_fields(other_pdf))`` round-trips a form's
field layout from one document onto another.

One ``FieldSpec`` is produced per widget annotation, so a radio group with two
buttons yields two specs sharing a name - matching how ``build`` and detection
already model groups.
"""

from __future__ import annotations

import io
import warnings
from typing import cast

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NumberObject

from acroforge.models import FieldSpec, FieldType

# AcroForm field flags (/Ff bits). Bit N is value ``1 << N`` per PDF spec.
_FF_PUSHBUTTON = 1 << 16  # /Btn: it is a pushbutton, not a data field.
_FF_RADIO = 1 << 15  # /Btn: it is a radio button (else a checkbox).
_FF_COMB = 1 << 24  # /Tx: laid out as evenly spaced comb cells.
_FF_COMBO = 1 << 17  # /Ch: combo box (else list box).
_FF_EDIT = 1 << 18  # /Ch combo: editable (free text allowed).
_FF_MULTISELECT = 1 << 21  # /Ch list box: multiple selections allowed.


def _inherited(obj: DictionaryObject, key: str) -> object | None:
    """Return ``obj[key]``, walking up the ``/Parent`` chain until found (or None).

    A ``seen`` set guards against a circular ``/Parent`` reference (malformed PDFs
    do contain these), which would otherwise loop forever.
    """
    cur: DictionaryObject | None = obj
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if key in cur:
            return cur[key]
        parent = cur.get("/Parent")
        cur = cast(DictionaryObject, parent.get_object()) if parent is not None else None
    return None


def _on_state(widget: DictionaryObject) -> str | None:
    """Return this widget's on-state name: the ``/AP /N`` key that is not ``/Off``.

    The name is stripped of its leading ``/`` (e.g. ``/M`` -> ``"M"``). Returns
    None when there is no appearance dictionary or no single non-Off state.
    """
    ap = widget.get("/AP")
    if ap is None:
        return None
    normal = cast(DictionaryObject, ap.get_object()).get("/N")
    if normal is None:
        return None
    for key in cast(DictionaryObject, normal.get_object()):
        if key != "/Off":
            return str(key).lstrip("/")
    return None


def _parse_opt(opt: object) -> list[str] | list[tuple[str, str]] | None:
    """Parse a ``/Ch`` ``/Opt`` array into options.

    Each element is a text string (export == label) or a two-element array
    ``[export, display]`` (PDF spec). Returns plain strings when no element has
    a distinct label, else ``(export, label)`` pairs.
    """
    if opt is None:
        return None
    resolved = opt.get_object() if isinstance(opt, IndirectObject) else opt
    if not isinstance(resolved, ArrayObject):
        return None
    plain: list[str] = []
    pairs: list[tuple[str, str]] = []
    any_pair = False
    for item in resolved:
        ob = item.get_object() if isinstance(item, IndirectObject) else item
        if isinstance(ob, ArrayObject) and len(ob) == 2:
            export, label = str(ob[0]), str(ob[1])
            pairs.append((export, label))
            plain.append(export)
            any_pair = True
        else:
            pairs.append((str(ob), str(ob)))
            plain.append(str(ob))
    return pairs if any_pair else plain


def _spec_from_widget(obj: DictionaryObject, pno: int) -> FieldSpec | None:
    """Reconstruct a FieldSpec from one ``/Widget`` annotation, or None to skip it."""
    name = _inherited(obj, "/T")
    if name is None:
        return None  # unnamed widget: nothing to address it by.

    ft = _inherited(obj, "/FT")
    ff_raw = _inherited(obj, "/Ff")
    ff = int(cast(NumberObject, ff_raw)) if ff_raw is not None else 0
    maxlen_raw = _inherited(obj, "/MaxLen")

    rect = obj.get("/Rect")
    if rect is None or len(rect) != 4:
        return None
    xs = (float(rect[0]), float(rect[2]))
    ys = (float(rect[1]), float(rect[3]))
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 <= x0 or y1 <= y0:
        return None  # degenerate rect.
    norm_rect = (x0, y0, x1, y1)

    ftype = str(ft) if ft is not None else ""
    field_type: FieldType
    export_value: str | None = None
    maxlen: int | None = None
    options: list[str] | list[tuple[str, str]] | None = None
    list_box = False
    multi_select = False
    editable = False

    if ftype == "/Btn":
        if ff & _FF_PUSHBUTTON:
            return None  # a button, not a data field.
        field_type = FieldType.RADIO if (ff & _FF_RADIO) else FieldType.CHECKBOX
        export_value = _on_state(obj)
    elif ftype == "/Tx":
        field_type = FieldType.COMB if (ff & _FF_COMB) else FieldType.TEXT
        if maxlen_raw is not None:
            maxlen = int(cast(NumberObject, maxlen_raw))
    elif ftype == "/Sig":
        field_type = FieldType.SIGNATURE
    elif ftype == "/Ch":
        field_type = FieldType.CHOICE
        options = _parse_opt(_inherited(obj, "/Opt"))
        list_box = not (ff & _FF_COMBO)
        editable = bool(ff & _FF_EDIT)
        multi_select = bool(ff & _FF_MULTISELECT)
    else:
        return None  # unknown field type.

    return FieldSpec(
        type=field_type,
        page=pno,
        rect=norm_rect,
        name=str(name),
        options=options,
        maxlen=maxlen,
        export_value=export_value,
        list_box=list_box,
        multi_select=multi_select,
        editable=editable,
        confidence=1.0,
    )


def read_fields(pdf: bytes | str) -> list[FieldSpec]:
    """Read existing AcroForm fields from a fillable PDF into FieldSpecs.

    ``pdf`` may be raw bytes or a path string. Returns one ``FieldSpec`` per
    ``/Widget`` annotation (so radio groups yield one spec per button, sharing a
    name), in page order then annotation order. Every spec has
    ``confidence = 1.0`` because these are real, registered fields.
    """
    source: io.BytesIO | str = io.BytesIO(pdf) if isinstance(pdf, bytes) else pdf
    reader = PdfReader(source)

    specs: list[FieldSpec] = []
    for pno, page in enumerate(reader.pages):
        for a in page.get("/Annots") or []:
            try:
                obj = cast(DictionaryObject, a.get_object())
                if obj.get("/Subtype") != "/Widget":
                    continue
                spec = _spec_from_widget(obj, pno)
            except Exception as exc:  # noqa: BLE001 - one bad widget must not lose the rest
                warnings.warn(
                    f"read_fields: skipped a malformed widget on page {pno} "
                    f"({type(exc).__name__}: {exc})",
                    stacklevel=2,
                )
                continue
            if spec is not None:
                specs.append(spec)
    return specs
