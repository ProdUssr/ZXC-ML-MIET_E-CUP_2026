from __future__ import annotations

import argparse
import csv
import logging
import os
from pathlib import Path
import sys

try: from .contracts import Item
except ImportError: from contracts import Item

LOG = logging.getLogger("phase0.io")
_REQUIRED_COLUMNS = ("id", "name", "description", "category")
_TEXT_LIMIT = 50_000


def parse_args(argv: list[str] | None = None):
    """Parse evaluator arguments without allowing argparse to terminate us."""
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument(
        "-i", "--input", "--test_data_path", "--data_path", "--test-data-path",
        dest="test_data_path", nargs="?", const=None,
    )
    parser.add_argument(
        "-o", "--output", "--output-path", "--output_path",
        dest="output_path", nargs="?", const=None,
    )
    parser.add_argument("--config", nargs="?", const=None, default=None)
    parser.add_argument("paths", nargs="*")
    supplied = list(sys.argv[1:] if argv is None else argv)
    try:
        args, unknown = parser.parse_known_args(supplied)
    except (argparse.ArgumentError, SystemExit) as exc:
        print(f"WARNING argument parsing recovered: {exc}", file=sys.stderr)
        args = parser.parse_args([])
        unknown = supplied

    positional = [value for value in args.paths if value and not value.startswith("-")]
    args.test_data_path = (
        args.test_data_path
        or os.environ.get("ECUP_TEST_DATA_PATH")
        or os.environ.get("TEST_DATA_PATH")
        or (positional[0] if positional else "./test.csv")
    )
    args.output_path = (
        args.output_path
        or os.environ.get("ECUP_OUTPUT_PATH")
        or os.environ.get("OUTPUT_PATH")
        or (positional[1] if len(positional) > 1 else "./submission.csv")
    )
    if unknown:
        print(f"WARNING ignored unknown arguments: {' '.join(unknown)}", file=sys.stderr)
    return args


def initialize_output(path: str | Path) -> None:
    """Create the evaluator-visible CSV before any fallible input work."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream).writerow(("id", "result"))
        stream.flush()


def _column_map(fieldnames) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in fieldnames or ():
        if field is None:
            continue
        normalized = str(field).strip().lower()
        if normalized and normalized not in result:
            result[normalized] = field
    return result


def read_items(path: str | Path) -> list[Item]:
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    items: list[Item] = []
    actual_headers: list[str] = []
    try:
        with open(
            path, "r", encoding="utf-8-sig", errors="replace", newline=""
        ) as stream:
            reader = csv.DictReader(stream)
            actual_headers = [str(value) for value in (reader.fieldnames or ())]
            columns = _column_map(reader.fieldnames)
            missing = [name for name in _REQUIRED_COLUMNS if name not in columns]
            if missing:
                LOG.error(
                    "input CSV missing required columns %s; actual headers=%s",
                    missing,
                    actual_headers,
                )
            for index, row in enumerate(reader):
                def value(name: str, limit: int | None = None) -> str:
                    source = columns.get(name)
                    text = str(row.get(source, "") or "") if source is not None else ""
                    return text[:limit] if limit is not None else text

                items.append(Item(
                    index,
                    value("id"),
                    value("name", _TEXT_LIMIT),
                    value("description", _TEXT_LIMIT),
                    value("category", 1_000),
                ))
    except (OSError, csv.Error, UnicodeError):
        LOG.exception(
            "input CSV read failed after %d rows; partial rows retained: %s",
            len(items),
            path,
        )

    if items:
        nonempty = sum(bool(item.id.strip()) for item in items)
        ratio = nonempty / len(items)
        if ratio <= 0.99:
            LOG.error(
                "non-empty id ratio %.6f is not above 0.99; actual headers=%s",
                ratio,
                actual_headers,
            )
    return items


def resource_root_for_csv(path: str | Path) -> Path:
    return Path(path).resolve().parent
