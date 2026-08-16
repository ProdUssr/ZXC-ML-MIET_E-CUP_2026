from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "submission"))
from result_format import is_valid_result


def validate(source: str, output: str) -> None:
    with open(source, encoding="utf-8-sig", errors="replace", newline="") as f: input_rows = list(csv.DictReader(f))
    with open(output, encoding="utf-8", newline="") as f: output_rows = list(csv.DictReader(f))
    assert [r.get("id", "") for r in output_rows] == [r.get("id", "") for r in input_rows]
    assert all(is_valid_result(r.get("result", "")) for r in output_rows)


if __name__ == "__main__":
    validate(*sys.argv[1:3])
