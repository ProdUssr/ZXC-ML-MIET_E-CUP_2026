"""Dependency-free metric variants required while organisers' wording is ambiguous."""
from __future__ import annotations

from collections import defaultdict
import json


def binary_f1(y_true: list[int], y_pred: list[int], positive: int) -> float:
    tp = sum(t == positive and p == positive for t, p in zip(y_true, y_pred))
    fp = sum(t != positive and p == positive for t, p in zip(y_true, y_pred))
    fn = sum(t == positive and p != positive for t, p in zip(y_true, y_pred))
    return 0.0 if 2 * tp + fp + fn == 0 else 2 * tp / (2 * tp + fp + fn)


def macro_f1(y_true: list[int], y_pred: list[int]) -> float:
    return (binary_f1(y_true, y_pred, 0) + binary_f1(y_true, y_pred, 1)) / 2


def score(rows: list[dict], predictions: list[int]) -> dict:
    groups: dict[str, tuple[list[int], list[int]]] = {}
    for row, pred in zip(rows, predictions):
        actual, guessed = groups.setdefault(row["category"], ([], []))
        actual.append(int(row["label"]))
        guessed.append(int(pred))
    by_category = {category: {"macro": macro_f1(y, p), "positive": binary_f1(y, p, 1)} for category, (y, p) in groups.items()}
    values = list(by_category.values())
    y_all = [int(r["label"]) for r in rows]
    return {
        "category_macro_mean": sum(v["macro"] for v in values) / len(values),
        "category_positive_mean": sum(v["positive"] for v in values) / len(values),
        "global_macro": macro_f1(y_all, predictions),
        "by_category": by_category,
    }


def print_scores(rows: list[dict], predictions: list[int]) -> dict:
    """Always print all three interpretations plus category slices."""
    metrics = score(rows, predictions)
    print(f"(a) category macro-F1 mean: {metrics['category_macro_mean']:.6f}")
    print(f"(b) category positive-F1 mean: {metrics['category_positive_mean']:.6f}")
    print(f"(c) global macro-F1: {metrics['global_macro']:.6f}")
    for category, values in sorted(metrics["by_category"].items()):
        print(f"  {category}: macro={values['macro']:.6f} positive={values['positive']:.6f}")
    return metrics
