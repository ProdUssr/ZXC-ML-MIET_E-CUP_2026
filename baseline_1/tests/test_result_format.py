from __future__ import annotations

import random
import string
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "submission"))
from label_semantics import VERDICT_BAN, VERDICT_OK
from result_format import build_result, is_valid_result, sanitize_comment


class ResultFormatTests(unittest.TestCase):
    def test_non_ascii_is_counted_as_characters(self):
        result = build_result("ё" * 500, VERDICT_BAN)
        self.assertTrue(is_valid_result(result))
        self.assertEqual(result.count("ё"), 300)

    def test_property_random_20000(self):
        alphabet = string.printable + "ёж🔥< >\n\r«»"
        random.seed(20260815)
        for _ in range(20_000):
            text = "".join(random.choice(alphabet) for _ in range(random.randrange(5001)))
            self.assertTrue(is_valid_result(build_result(text, random.choice([VERDICT_BAN, VERDICT_OK, "bad"])) ))

    def test_sanitizer_removes_delimiters(self):
        self.assertNotIn("<", sanitize_comment("a<b\nc>"))
        self.assertNotIn(";", sanitize_comment("a;b"))
        self.assertNotIn(",", sanitize_comment("a,b"))
