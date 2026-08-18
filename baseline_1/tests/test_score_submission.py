from __future__ import annotations

import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from submission.label_semantics import VERDICT_BAN, VERDICT_OK
from submission.result_format import build_result


class ScoreSubmissionTests(unittest.TestCase):
    def _write(self, path: Path, fields: list[str], rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_complete_submission_scores_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            labels = root / "labels.csv"
            submit = root / "submit.csv"
            self._write(labels, ["id", "category", "label"], [
                {"id": "a", "category": "БАД", "label": "0"},
                {"id": "b", "category": "БАД", "label": "1"},
            ])
            self._write(submit, ["id", "result"], [
                {"id": "a", "result": build_result("Нарушение подтверждено правилами категории товара", VERDICT_BAN)},
                {"id": "b", "result": build_result("Нарушение не подтверждено правилами категории товара", VERDICT_OK)},
            ])
            result = subprocess.run(
                [sys.executable, str(ROOT / "train" / "score_submission.py"), str(submit), str(labels)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("coverage=2/2 (1.000000)", result.stdout)
            self.assertIn("category macro-F1 mean: 1.000000", result.stdout)

    def test_invalid_result_is_reported_and_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            labels = root / "labels.csv"
            submit = root / "submit.csv"
            self._write(labels, ["id", "category", "label"], [
                {"id": "a", "category": "БАД", "label": "0"},
            ])
            self._write(submit, ["id", "result"], [
                {"id": "a", "result": "бан"},
            ])
            result = subprocess.run(
                [sys.executable, str(ROOT / "train" / "score_submission.py"), str(submit), str(labels)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid_results=1", result.stdout)


if __name__ == "__main__":
    unittest.main()
