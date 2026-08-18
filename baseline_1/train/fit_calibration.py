"""Fit calibration and thresholds on train; evaluate once on group-safe holdout."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from submission.calibration import CalibrationTable, signature_key
from submission.contracts import Item
from submission.predictors.rules import extract_rule_features
from train.validation.scorer import macro_f1, print_scores
from train.validation.split import holdout_indices

EXPLICIT_EXCLUSION_CAP = 0.01


def _item(index: int, row: dict) -> Item:
    return Item(
        index,
        str(row.get("id", "") or ""),
        str(row.get("name", "") or "")[:50_000],
        str(row.get("description", "") or "")[:50_000],
        str(row.get("category", "") or ""),
    )


def split_id(held_out: list[int], fraction: float) -> str:
    digest = hashlib.sha256(
        ",".join(map(str, held_out)).encode("ascii")
    ).hexdigest()[:16]
    return f"group_text_sha256_v1:f={fraction:.6f}:{digest}"


def fit(rows: list[dict], indices: list[int], alpha: float, minimum: int):
    raw_cells: dict[str, Counter] = defaultdict(Counter)
    categories: dict[str, Counter] = defaultdict(Counter)
    for index in indices:
        row = rows[index]
        label = int(row["label"])
        category = str(row["category"])
        categories[category][label] += 1
        features, _, _ = extract_rule_features(_item(index, row))
        if features is not None:
            raw_cells[signature_key(features)][label] += 1

    priors = {
        category: (counts[0] + alpha) / (sum(counts.values()) + 2 * alpha)
        for category, counts in categories.items()
    }
    cells = {}
    for key, counts in sorted(raw_cells.items()):
        count = sum(counts.values())
        category = str(json.loads(key)[0])
        calibrated = count >= minimum
        probability = (
            (counts[0] + alpha) / (count + 2 * alpha)
            if calibrated
            else priors.get(category, 0.5)
        )
        cells[key] = {
            "count": count,
            "label_0": counts[0],
            "label_1": counts[1],
            "calibrated": calibrated,
            "p_regulated": probability,
        }
    return cells, priors


def probabilities(rows, indices, cells, priors, constraints):
    table = CalibrationTable(cells, constraints)
    selected = []
    values = []
    for index in indices:
        row = rows[index]
        features, _, _ = extract_rule_features(_item(index, row))
        fallback = float(priors.get(str(row["category"]), 0.5))
        probability = (
            table.probability(features, fallback)
            if features is not None
            else fallback
        )
        selected.append(row)
        values.append(probability)
    return selected, values


def tune_thresholds(rows: list[dict], values: list[float]) -> dict[str, float]:
    by_category: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for row, probability in zip(rows, values):
        by_category[str(row["category"])].append((int(row["label"]), probability))

    thresholds = {}
    for category, pairs in sorted(by_category.items()):
        candidates = sorted({probability for _, probability in pairs})
        best = None
        for threshold in candidates:
            actual = [label for label, _ in pairs]
            predicted = [0 if probability >= threshold else 1 for _, probability in pairs]
            value = macro_f1(actual, predicted)
            candidate = (value, -abs(threshold - 0.5), -threshold, threshold)
            if best is None or candidate > best:
                best = candidate
        thresholds[category] = float(best[-1])
    return thresholds


def labels(rows, values, thresholds):
    return [
        0 if probability >= thresholds.get(str(row["category"]), 0.5) else 1
        for row, probability in zip(rows, values)
    ]


def update_config(path: Path, thresholds: dict[str, float]) -> None:
    config = json.loads(path.read_text(encoding="utf-8"))
    current = dict(config.get("thresholds_p_regulated", {}))
    current.update(thresholds)
    config["thresholds_p_regulated"] = current
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "data" / "data.csv"))
    parser.add_argument(
        "--output", default=str(ROOT / "submission" / "calibration.json")
    )
    parser.add_argument(
        "--metrics-output", default=str(ROOT / "train" / "metrics.json")
    )
    parser.add_argument(
        "--config", default=str(ROOT / "submission" / "config.json")
    )
    parser.add_argument("--holdout-fraction", type=float, default=0.15)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--min-cell-size", type=int, default=30)
    args = parser.parse_args()

    with open(args.data, encoding="utf-8-sig", errors="replace", newline="") as stream:
        rows = list(csv.DictReader(stream))
    train_indices, held_out, duplicate_groups = holdout_indices(
        rows, args.holdout_fraction
    )
    current_split_id = split_id(held_out, args.holdout_fraction)
    constraints = {
        "explicit_exclusion_cap": EXPLICIT_EXCLUSION_CAP,
        "note": (
            "Rubric-explicit negative-only evidence is capped despite adverse "
            "train correlation; mixed positive/negative signatures stay empirical."
        ),
    }
    cells, priors = fit(rows, train_indices, args.alpha, args.min_cell_size)

    train_rows, train_values = probabilities(
        rows, train_indices, cells, priors, constraints
    )
    thresholds = tune_thresholds(train_rows, train_values)
    print(
        f"rows={len(rows)} train={len(train_indices)} holdout={len(held_out)} "
        f"duplicate_groups={duplicate_groups} split_id={current_split_id}"
    )
    print(f"thresholds={json.dumps(thresholds, ensure_ascii=False, sort_keys=True)}")
    print("train metrics:")
    train_metrics = print_scores(
        train_rows, labels(train_rows, train_values, thresholds)
    )

    holdout_rows, holdout_values = probabilities(
        rows, held_out, cells, priors, constraints
    )
    print("holdout metrics:")
    holdout_metrics = print_scores(
        holdout_rows, labels(holdout_rows, holdout_values, thresholds)
    )

    payload = {
        "version": 2,
        "fit_rows": len(train_indices),
        "split_id": current_split_id,
        "signature_fields": [
            "category", "has_positive", "has_negative", "n_positive_bucket",
            "explicit_exclusion",
        ],
        "constraints": constraints,
        "alpha": args.alpha,
        "min_cell_size": args.min_cell_size,
        "category_priors_p_regulated": priors,
        "cells": cells,
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metrics = {
        "version": 1,
        "split_id": current_split_id,
        "total_rows": len(rows),
        "fit_rows": len(train_indices),
        "holdout_rows": len(held_out),
        "duplicate_groups": duplicate_groups,
        "thresholds_p_regulated": thresholds,
        "train_metrics": train_metrics,
        "holdout_metrics": holdout_metrics,
    }
    Path(args.metrics_output).write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    update_config(Path(args.config), thresholds)
    print(
        f"wrote {args.output} with {len(cells)} cells and "
        f"count_sum={sum(cell['count'] for cell in cells.values())}"
    )
    print(f"wrote {args.metrics_output} and updated {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
