from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from pydantic import TypeAdapter

from acroforge import api
from acroforge.models import FieldSpec

_field_list_adapter: TypeAdapter[list[FieldSpec]] = TypeAdapter(list[FieldSpec])


def _cmd_build(args: argparse.Namespace) -> None:
    pdf = Path(args.input).read_bytes()
    manifest_text = Path(args.manifest).read_bytes()
    fields = _field_list_adapter.validate_json(manifest_text)
    out = api.build(pdf, fields)
    Path(args.output).write_bytes(out)


def _cmd_fill(args: argparse.Namespace) -> None:
    import json

    pdf = Path(args.input).read_bytes()
    values: dict[str, object] = json.loads(Path(args.data).read_text())
    out = api.fill(pdf, values)
    Path(args.output).write_bytes(out)


def _cmd_flatten(args: argparse.Namespace) -> None:
    pdf = Path(args.input).read_bytes()
    out = api.flatten(pdf)
    Path(args.output).write_bytes(out)


def _cmd_detect(args: argparse.Namespace) -> None:
    pdf = Path(args.input).read_bytes()
    manifest = api.detect(pdf)
    print(manifest.model_dump_json(indent=2))


def _cmd_make_fillable(args: argparse.Namespace) -> None:
    pdf = Path(args.input).read_bytes()
    out = api.make_fillable(pdf)
    Path(args.output).write_bytes(out)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="acroforge",
        description="Build, fill, and flatten AcroForm PDFs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Inject form fields from a JSON manifest.")
    p_build.add_argument("input", help="Source PDF path.")
    p_build.add_argument("manifest", help="JSON array of FieldSpec dicts.")
    p_build.add_argument("output", help="Output PDF path.")
    p_build.set_defaults(func=_cmd_build)

    p_fill = sub.add_parser("fill", help="Fill fields from a JSON object {name: value}.")
    p_fill.add_argument("input", help="Source PDF path.")
    p_fill.add_argument("data", help="JSON object {name: value}.")
    p_fill.add_argument("output", help="Output PDF path.")
    p_fill.set_defaults(func=_cmd_fill)

    p_flatten = sub.add_parser("flatten", help="Bake field values into page content.")
    p_flatten.add_argument("input", help="Source PDF path.")
    p_flatten.add_argument("output", help="Output PDF path.")
    p_flatten.set_defaults(func=_cmd_flatten)

    p_detect = sub.add_parser("detect", help="Detect candidate fields and print JSON manifest.")
    p_detect.add_argument("input", help="Source PDF path.")
    p_detect.set_defaults(func=_cmd_detect)

    p_make_fillable = sub.add_parser(
        "make-fillable", help="Detect fields and produce a fillable PDF."
    )
    p_make_fillable.add_argument("input", help="Source PDF path.")
    p_make_fillable.add_argument("output", help="Output PDF path.")
    p_make_fillable.set_defaults(func=_cmd_make_fillable)

    args = parser.parse_args(list(argv) if argv is not None else None)
    args.func(args)


if __name__ == "__main__":
    main()
