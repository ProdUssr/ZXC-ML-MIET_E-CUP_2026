"""Atomic, order-independent output snapshots."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Callable, Sequence

try:
    from .contracts import Item
    from .result_format import is_valid_result
except ImportError:
    from contracts import Item
    from result_format import is_valid_result


class ResultSink:
    """Keep the target complete at every visible point in the run.

    Each flush writes a full snapshot to a sibling temporary file and performs an
    atomic replace. Predictions may arrive in any order; absent/invalid entries
    are materialized through ``default_fn``.
    """

    def __init__(
        self,
        path: str | Path,
        items: Sequence[Item],
        default_fn: Callable[[Item], str],
        telemetry=None,
    ) -> None:
        self.path = Path(path)
        self.items = list(items)
        self.default_fn = default_fn
        self.values: list[str | None] = [None] * len(self.items)
        self.flush_count = 0
        self.telemetry = telemetry

    def submit(self, row_index: int, result: str) -> None:
        if 0 <= row_index < len(self.values):
            if is_valid_result(result):
                self.values[row_index] = result
            else:
                self.values[row_index] = None
                if self.telemetry is not None:
                    self.telemetry.count("sink_invalid_rejected")

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=["id", "result"])
            writer.writeheader()
            for item, value in zip(self.items, self.values):
                writer.writerow({
                    "id": item.id,
                    "result": value if value is not None else self.default_fn(item),
                })
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, self.path)
        self.flush_count += 1

    def finalize(self) -> None:
        self.flush()

    @property
    def pending(self) -> int:
        return sum(value is None for value in self.values)


def repair_invalid_rows(
    path: str | Path,
    items: Sequence[Item],
    default_fn: Callable[[Item], str],
) -> None:
    """Retain valid positional rows and repair only invalid/missing entries."""
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
    except (OSError, csv.Error):
        rows = []

    sink = ResultSink(path, items, default_fn)
    for item in items:
        if item.row_index >= len(rows):
            continue
        row = rows[item.row_index]
        result = row.get("result", "")
        if row.get("id", "") == item.id and is_valid_result(result):
            sink.submit(item.row_index, result)
    sink.flush()
