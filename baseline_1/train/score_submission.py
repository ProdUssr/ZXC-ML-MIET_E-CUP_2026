"""Score a submission with all metric interpretations required by the project."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from submission.label_semantics import label_from_verdict
from submission.result_format import RESULT_RE, is_valid_result
from train.validation.scorer import print_scores

_RESULT_RX = re.compile(RESULT_RE)


def _read(path: str | Path) -> tuple[list[str], list[dict]]:
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or ()), list(reader)


def _require_columns(path: str | Path, fields: list[str], required: set[str]) -> None:
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("submit", help="submission CSV with id,result")
    parser.add_argument("labels", help="reference CSV with id,category,label")
    parser.add_argument("--mapping", choices=("direct", "inverted"), default="direct")
    args = parser.parse_args()

    label_fields, label_rows = _read(args.labels)
    submit_fields, submit_rows = _read(args.submit)
    _require_columns(args.labels, label_fields, {"id", "category", "label"})
    _require_columns(args.submit, submit_fields, {"id", "result"})

    expected_ids = [str(row.get("id", "") or "") for row in label_rows]
    submitted_ids = [str(row.get("id", "") or "") for row in submit_rows]
    expected_set = set(expected_ids)
    submitted_set = set(submitted_ids)
    duplicate_input = len(expected_ids) - len(expected_set)
    duplicate_output = len(submitted_ids) - len(submitted_set)
    missing_ids = expected_set - submitted_set
    extra_ids = submitted_set - expected_set
    covered = len(expected_set & submitted_set)
    coverage = covered / len(expected_set) if expected_set else 1.0
    order_match = submitted_ids == expected_ids

    outputs: dict[str, list[dict]] = defaultdict(list)
    for row in submit_rows:
        outputs[str(row.get("id", "") or "")].append(row)

    invalid_results = 0
    invalid_examples: list[str] = []
    scored_rows: list[dict] = []
    predictions: list[int] = []
    verdicts: dict[str, Counter] = defaultdict(Counter)
    for row in label_rows:
        product_id = str(row.get("id", "") or "")
        matches = outputs.get(product_id, [])
        if len(matches) != 1:
            continue
        result = str(matches[0].get("result", "") or "")
        if not is_valid_result(result):
            invalid_results += 1
            if len(invalid_examples) < 10:
                invalid_examples.append(product_id)
            continue
        match = _RESULT_RX.fullmatch(result)
        if match is None:
            raise AssertionError("validator and RESULT_RE disagree")
        verdict = match.group(1)
        prediction = label_from_verdict(verdict, mapping=args.mapping)
        category = str(row.get("category", "") or "")
        scored_rows.append(row)
        predictions.append(prediction)
        verdicts[category][verdict] += 1

    print(f"input_rows={len(label_rows)} output_rows={len(submit_rows)}")
    print(f"coverage={covered}/{len(expected_set)} ({coverage:.6f})")
    print(f"missing_ids={len(missing_ids)} extra_ids={len(extra_ids)}")
    print(f"duplicate_input={duplicate_input} duplicate_output={duplicate_output}")
    print(f"invalid_results={invalid_results} scored_rows={len(scored_rows)}")
    print(f"order_match={str(order_match).lower()}")
    if invalid_examples:
        print(f"invalid_result_ids={','.join(invalid_examples)}")
    for category in sorted(verdicts):
        counts = verdicts[category]
        print(
            f"verdicts[{category}]: "
            f"бан={counts['бан']} не бан={counts['не бан']}"
        )
    if scored_rows:
        print_scores(scored_rows, predictions)

    complete = (
        len(submit_rows) == len(label_rows)
        and coverage == 1.0
        and not missing_ids
        and not extra_ids
        and duplicate_input == 0
        and duplicate_output == 0
        and invalid_results == 0
        and len(scored_rows) == len(label_rows)
        and order_match
    )
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
