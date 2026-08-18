"""Prepare leakage-free real-data inputs using the calibration holdout split."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from train.fit_calibration import split_id
from train.validation.split import holdout_indices


def _write_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "data" / "data.csv"))
    parser.add_argument("--output-dir", default=str(ROOT / "work" / "real"))
    parser.add_argument("--metrics", default=str(ROOT / "train" / "metrics.json"))
    parser.add_argument("--holdout-fraction", type=float, default=0.15)
    args = parser.parse_args()

    with open(args.data, encoding="utf-8-sig", errors="replace", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or ())
        rows = list(reader)

    required = {"id", "name", "description", "category", "label"}
    missing = sorted(required - set(fieldnames))
    if missing:
        raise ValueError(f"source CSV is missing columns: {missing}")

    _, held_out, duplicate_groups = holdout_indices(rows, args.holdout_fraction)
    current_split_id = split_id(held_out, args.holdout_fraction)
    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    expected_split_id = str(metrics.get("split_id", ""))
    expected_count = int(metrics.get("holdout_rows", -1))
    if current_split_id != expected_split_id or len(held_out) != expected_count:
        raise RuntimeError(
            "holdout mismatch: "
            f"got {current_split_id} / {len(held_out)}, "
            f"expected {expected_split_id} / {expected_count}"
        )

    output_dir = Path(args.output_dir)
    holdout_rows = [rows[index] for index in held_out]
    test_fields = [name for name in fieldnames if name != "label"]
    if "label" in test_fields:
        raise AssertionError("label leaked into test columns")

    _write_rows(output_dir / "test_holdout.csv", test_fields, holdout_rows)
    _write_rows(output_dir / "test_full.csv", test_fields, rows)
    _write_rows(
        output_dir / "labels_holdout.csv",
        ["id", "category", "label"],
        holdout_rows,
    )

    print(f"rows={len(rows)} holdout={len(holdout_rows)}")
    print(f"duplicate_groups={duplicate_groups}")
    print(f"split_id={current_split_id}")
    print(f"source_columns={fieldnames!r}")
    print(f"test_columns={test_fields!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
