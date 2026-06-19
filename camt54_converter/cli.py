"""Command line entry point for the ISO 20022 → CSV converter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from camt54_converter.parser import parse, write_csv


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="camt54-to-csv",
        description=(
            "Convert ISO 20022 XML files to CSV. The source format "
            "(camt.054, camt.053, pain.001, pain.008) is detected automatically."
        ),
    )
    p.add_argument(
        "input",
        nargs="+",
        help="One or more ISO 20022 XML files. Use '-' to read from stdin.",
    )
    p.add_argument(
        "-o",
        "--output",
        help=(
            "Output CSV file (default: stdout). When multiple inputs are given, "
            "rows from all files are concatenated into one CSV."
        ),
    )
    p.add_argument(
        "-d",
        "--delimiter",
        default=";",
        help="CSV field delimiter (default: ';').",
    )
    p.add_argument(
        "--encoding",
        default="utf-8",
        help="Output encoding (default: utf-8).",
    )
    return p


def _read_source(path: str) -> bytes:
    if path == "-":
        return sys.stdin.buffer.read()
    return Path(path).read_bytes()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    all_tx = []
    for path in args.input:
        try:
            data = _read_source(path)
            all_tx.extend(parse(data))
        except FileNotFoundError:
            print(f"error: file not found: {path}", file=sys.stderr)
            return 2
        except ValueError as exc:
            print(f"error: {path}: {exc}", file=sys.stderr)
            return 2

    if args.output:
        with open(args.output, "w", encoding=args.encoding, newline="") as fh:
            count = write_csv(all_tx, fh, delimiter=args.delimiter)
        print(f"Wrote {count} rows to {args.output}", file=sys.stderr)
    else:
        count = write_csv(all_tx, sys.stdout, delimiter=args.delimiter)
        print(f"Wrote {count} rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
