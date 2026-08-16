"""Group-safe, category×label-stratified holdout and GroupKFold helpers."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import re


def normalized_hash(row: dict) -> str:
    text = f"{row.get('name', '')} {row.get('description', '')}".lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _groups(rows: list[dict]) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for idx, row in enumerate(rows):
        groups.setdefault(normalized_hash(row), []).append(idx)
    return groups


def _stratum(rows: list[dict], indices: list[int]) -> tuple[str, str]:
    counts = Counter((str(rows[i].get("category", "")), str(rows[i].get("label", ""))) for i in indices)
    return counts.most_common(1)[0][0]


def holdout_indices(rows: list[dict], fraction: float = 0.15) -> tuple[list[int], list[int], int]:
    """Allocate whole duplicate groups within each category×label stratum."""
    groups = _groups(rows)
    by_stratum: dict[tuple[str, str], list[tuple[str, list[int]]]] = defaultdict(list)
    for digest, indices in groups.items():
        by_stratum[_stratum(rows, indices)].append((digest, indices))
    held: list[int] = []
    for entries in by_stratum.values():
        target = round(sum(len(indices) for _, indices in entries) * fraction)
        count = 0
        for _, indices in sorted(entries):
            if count >= target:
                break
            held.extend(indices)
            count += len(indices)
    held_set = set(held)
    train = [idx for idx in range(len(rows)) if idx not in held_set]
    duplicate_groups = sum(len(indices) > 1 for indices in groups.values())
    return train, sorted(held), duplicate_groups


def group_kfold_indices(rows: list[dict], n_splits: int = 5) -> list[tuple[list[int], list[int]]]:
    """Greedy stratified GroupKFold without a scikit-learn runtime dependency."""
    if n_splits < 2:
        raise ValueError("n_splits must be at least 2")
    groups = _groups(rows)
    fold_groups: list[list[int]] = [[] for _ in range(n_splits)]
    fold_sizes = [0] * n_splits
    fold_strata = [Counter() for _ in range(n_splits)]
    total_strata = Counter((str(r.get("category", "")), str(r.get("label", ""))) for r in rows)
    target_size = len(rows) / n_splits

    ordered = sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0]))
    for _, indices in ordered:
        group_counts = Counter((str(rows[i].get("category", "")), str(rows[i].get("label", ""))) for i in indices)
        best_fold = min(
            range(n_splits),
            key=lambda fold: (
                ((fold_sizes[fold] + len(indices)) / max(target_size, 1.0)) ** 2
                + sum(
                    ((fold_strata[fold][key] + value) / max(total_strata[key] / n_splits, 1.0)) ** 2
                    for key, value in group_counts.items()
                ),
                fold_sizes[fold],
                fold,
            ),
        )
        fold_groups[best_fold].extend(indices)
        fold_sizes[best_fold] += len(indices)
        fold_strata[best_fold].update(group_counts)

    all_indices = set(range(len(rows)))
    result = []
    for validation in fold_groups:
        validation = sorted(validation)
        result.append((sorted(all_indices - set(validation)), validation))
    return result
