from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "submission"))
from result_format import is_valid_result


class EndToEndTests(unittest.TestCase):
    def run_case(self, rows, bom=False):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp); source = tmp_path / "test.csv"; output = tmp_path / "out.csv"
            with source.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["id", "name", "description", "category"]); writer.writeheader(); writer.writerows(rows)
            subprocess.run([sys.executable, str(ROOT / "submission" / "run.py"), "-i", str(source), "-o", str(output)], check=True, timeout=30)
            with output.open(encoding="utf-8", newline="") as f: produced = list(csv.DictReader(f))
            self.assertEqual([r["id"] for r in produced], [r["id"] for r in rows])
            self.assertTrue(all(is_valid_result(r["result"]) for r in produced))

    def test_required_edges(self):
        self.run_case([
            {"id": "same", "name": "<\";\n", "description": "", "category": "БАД"},
            {"id": "same", "name": "emoji 🔥", "description": "x" * 100_000, "category": "Легковоспламеняющиеся"},
            {"id": "unknown", "name": "", "description": "   ", "category": "other"},
        ])

    def test_zero_rows(self):
        self.run_case([])

    def test_one_row(self):
        self.run_case([{"id": "one", "name": "обычный товар", "description": "описание", "category": "БАД"}])

    def test_bom_preserves_ids(self):
        self.run_case([{"id": "bom-id", "name": "товар", "description": "описание", "category": "БАД"}], bom=True)
