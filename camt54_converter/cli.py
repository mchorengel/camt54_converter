"""Command line entry point for the camt.054 → CSV converter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from camt54_converter.parser import parse_camt054, write_csv


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="camt54-to-csv",
        description=(
            "Convert camt.054 (ISO 20022 Bank-to-Customer Debit/Credit "
            "Notification) XML files to CSV."
        ),
    )
    p.add_argument(
        "input",
        nargs="+",
        help="One or more camt.054 XML files. Use '-' to read from stdin.",
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
            all_tx.extend(parse_camt054(data))
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
