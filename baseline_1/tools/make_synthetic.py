"""Create portable valid/edge synthetic input CSVs for smoke tests."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def rows(count: int) -> list[dict]:
    seed = [
        {"id": "empty", "name": "", "description": "", "category": "БАД"},
        {"id": "unsafe", "name": "<спички>, \"набор\"", "description": "горючее\nвещество", "category": "Легковоспламеняющиеся"},
        {"id": "long", "name": "Протеин", "description": "x" * 100_000, "category": "БАД"},
        {"id": "emoji", "name": "🔥 mixed Ελληνικά", "description": "зажигалка", "category": "Легковоспламеняющиеся"},
        {"id": "unknown", "name": "товар", "description": "тест", "category": "неизвестно"},
    ]
    return [dict(seed[i % len(seed)], id=str(i) if i >= len(seed) else seed[i]["id"]) for i in range(count)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=10)
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()
    with open(args.output, "w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=["id", "name", "description", "category"])
        writer.writeheader(); writer.writerows(rows(args.n))


if __name__ == "__main__":
    main()
