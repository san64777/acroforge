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
from typing import cast

from pypdf import PdfReader
from pypdf.generic import DictionaryObject, NumberObject

from acroforge.models import FieldSpec, FieldType

# AcroForm field flags (/Ff bits). Bit N is value ``1 << N`` per PDF spec.
_FF_PUSHBUTTON = 1 << 16  # /Btn: it is a pushbutton, not a data field.
_FF_RADIO = 1 << 15  # /Btn: it is a radio button (else a checkbox).
_FF_COMB = 1 << 24  # /Tx: laid out as evenly spaced comb cells.


def _inherited(obj: DictionaryObject, key: str) -> object | None:
    """Return ``obj[key]``, walking up ``/Parent`` chain until found (or None)."""
    cur: DictionaryObject | None = obj
    while cur is not None:
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
        annots = page.get("/Annots") or []
        for a in annots:
            obj = cast(DictionaryObject, a.get_object())
            if obj.get("/Subtype") != "/Widget":
                continue

            name = _inherited(obj, "/T")
            if name is None:
                continue  # unnamed widget: nothing to address it by, skip.

            ft = _inherited(obj, "/FT")
            ff_raw = _inherited(obj, "/Ff")
            ff = int(cast(NumberObject, ff_raw)) if ff_raw is not None else 0
            maxlen_raw = _inherited(obj, "/MaxLen")

            rect = obj.get("/Rect")
            if rect is None or len(rect) != 4:
                continue
            xs = (float(rect[0]), float(rect[2]))
            ys = (float(rect[1]), float(rect[3]))
            x0, x1 = min(xs), max(xs)
            y0, y1 = min(ys), max(ys)
            if x1 <= x0 or y1 <= y0:
                continue  # degenerate rect.
            norm_rect = (x0, y0, x1, y1)

            ftype = str(ft) if ft is not None else ""
            field_type: FieldType
            export_value: str | None = None
            maxlen: int | None = None

            if ftype == "/Btn":
                if ff & _FF_PUSHBUTTON:
                    continue  # a button, not a data field.
                field_type = FieldType.RADIO if (ff & _FF_RADIO) else FieldType.CHECKBOX
                export_value = _on_state(obj)
            elif ftype == "/Tx":
                if ff & _FF_COMB:
                    field_type = FieldType.COMB
                else:
                    field_type = FieldType.TEXT
                if maxlen_raw is not None:
                    maxlen = int(cast(NumberObject, maxlen_raw))
            elif ftype == "/Sig":
                field_type = FieldType.SIGNATURE
            elif ftype == "/Ch":
                # Choice (dropdown/listbox). acroforge has no dropdown type yet,
                # so approximate as TEXT to capture name and position.
                field_type = FieldType.TEXT
            else:
                continue  # unknown field type, skip.

            specs.append(
                FieldSpec(
                    type=field_type,
                    page=pno,
                    rect=norm_rect,
                    name=str(name),
                    maxlen=maxlen,
                    export_value=export_value,
                    confidence=1.0,
                )
            )
    return specs
