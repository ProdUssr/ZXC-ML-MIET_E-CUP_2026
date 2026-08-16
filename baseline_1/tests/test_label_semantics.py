from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "submission"))
from label_semantics import VERDICT_BAN, VERDICT_OK, label_from_verdict, verdict_from_label


class LabelCanaries(unittest.TestCase):
    # These six train ids all have label=1. The organiser's authoritative
    # verdict_map fixes label=1 as OK even when marker correlations look surprising.
    def test_six_data_backed_canaries(self):
        for product_id in ("0", "5", "6", "165", "479", "1265"):
            with self.subTest(product_id=product_id):
                self.assertEqual(verdict_from_label(1, mapping="direct"), VERDICT_OK)
                self.assertEqual(label_from_verdict(VERDICT_OK, mapping="direct"), 1)
        self.assertEqual(verdict_from_label(0, mapping="direct"), VERDICT_BAN)
        self.assertEqual(label_from_verdict(VERDICT_BAN, mapping="direct"), 0)
