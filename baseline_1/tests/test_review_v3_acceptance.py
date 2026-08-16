from __future__ import annotations

import csv
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from submission.contracts import Budget, Item, Prediction, RuntimeContext
from submission.deadline import DeadlineManager, hard_limit_for
from submission.images.loader import ImageLoader
from submission.images.manifest import attach_images
from submission.orchestrator import DefaultPolicy, Orchestrator
from submission.predictors import REGISTRY
from submission.router import Router
from submission.settings import StageSettings, load_settings
from submission.sink import ResultSink
from submission.telemetry import Telemetry

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "submission" / "run.py"


def write_csv(path: Path, rows, fieldnames=("id", "name", "description", "category")):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class BlockAAcceptanceTests(unittest.TestCase):
    def run_process(self, *arguments):
        return subprocess.run(
            [sys.executable, str(RUN), *map(str, arguments)],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
        )

    def test_missing_broken_and_empty_inputs_leave_output_and_exit_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = (root / "missing.csv", root / "broken.csv", root / "empty.csv")
            cases[1].write_bytes(b"\xff\xfe\x00not,csv\x00")
            cases[2].write_bytes(b"")
            for index, source in enumerate(cases):
                output = root / f"out-{index}.csv"
                completed = self.run_process("-i", source, "-o", output)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertTrue(output.exists())
                with output.open(encoding="utf-8", newline="") as stream:
                    self.assertEqual(next(csv.reader(stream)), ["id", "result"])

    def test_500k_field_unknown_args_and_case_normalized_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input.csv", root / "output.csv"
            write_csv(
                source,
                [{"ID": "long", " Name ": "x", "DESCRIPTION": "z" * 500_000,
                  "Category": "БАД"}],
                ("ID", " Name ", "DESCRIPTION", "Category"),
            )
            completed = self.run_process(
                "--input", source, "--output", output, "--gpu", "0", "--whatever"
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("ignored unknown arguments", completed.stderr)
            with output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["id"] for row in rows], ["long"])

    def test_missing_id_header_is_loud(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input.csv", root / "output.csv"
            write_csv(source, [{"name": "x", "description": "x", "category": "БАД"}],
                      ("name", "description", "category"))
            completed = self.run_process("-i", source, "-o", output)
            self.assertEqual(completed.returncode, 0)
            self.assertIn("missing required columns", completed.stderr)
            self.assertIn("non-empty id ratio", completed.stderr)

    def test_parent_settings_file_cannot_intercept_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "submission", root / "payload")
            (root / "settings.py").write_text(
                "raise RuntimeError('intercepted')\n", encoding="utf-8"
            )
            source, output = root / "input.csv", root / "output.csv"
            write_csv(source, [{"id": "1", "name": "x", "description": "", "category": "БАД"}])
            completed = subprocess.run(
                [sys.executable, str(root / "payload" / "run.py"), "-i", str(source), "-o", str(output)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn("intercepted", completed.stderr)


class BlockCAcceptanceTests(unittest.TestCase):
    def test_failed_load_keeps_rules_stage(self):
        class Failing:
            name = "failing"
            needs_images = False
            def __init__(self, params): pass
            def load(self, ctx): raise RuntimeError("load boom")
            def close(self): pass

        REGISTRY["failing"] = Failing
        try:
            settings = load_settings(ROOT / "submission" / "config.json")
            stages = (
                settings.stages[0],
                StageSettings("failing", (0.0, 1.0), "L4", {}),
            )
            telemetry = Telemetry()
            router = Router(stages, REGISTRY)
            router.load(RuntimeContext(ROOT / "submission", settings, telemetry))
            item = Item(0, "1", "БАД", "", "БАД")
            predictions = router.run(
                [item], Budget("L0", 100, 0, 0, False, True)
            )
            self.assertEqual(len(predictions), 1)
            self.assertEqual(predictions[0].stage, "rules")
            self.assertEqual(telemetry.counts["load_error:failing"], 1)
            router.close()
        finally:
            REGISTRY.pop("failing", None)

    def test_unimportable_later_stage_is_disabled_not_replaced_by_rules(self):
        settings = load_settings(ROOT / "submission" / "config.json")
        stages = (
            settings.stages[0],
            StageSettings("torch_vlm_missing", (0.0, 1.0), "L4", {}),
        )
        telemetry = Telemetry()
        router = Router(stages, REGISTRY)
        router.load(RuntimeContext(ROOT / "submission", settings, telemetry))
        items = [Item(i, str(i), "товар", "", "БАД") for i in range(1600)]
        predictions = router.run(
            items, Budget("L0", 100, 0, 0, False, True)
        )
        self.assertEqual(len(predictions), len(items))
        self.assertEqual(telemetry.counts["stage_items:rules"], len(items))
        self.assertEqual(telemetry.counts["load_error:torch_vlm_missing"], 1)
        router.close()

    def test_batch8_flush_count_is_time_based(self):
        class FastRouter:
            needs_images = False
            def run(self, items, budget):
                return [Prediction(item.row_index, 0.1, "fast") for item in items]
        class Deadline:
            def budget(self): return Budget("L0", 100, 0, 0, False, False)
            def observe(self, count): pass

        settings = replace(load_settings(ROOT / "submission" / "config.json"), batch_size=8)
        items = [Item(i, str(i), "x", "", "БАД") for i in range(4000)]
        defaults = DefaultPolicy(settings)
        with tempfile.TemporaryDirectory() as directory:
            sink = ResultSink(Path(directory) / "out.csv", items, defaults.result_for_item)
            sink.flush()
            telemetry = Telemetry()
            started = time.perf_counter()
            Orchestrator(FastRouter(), Deadline(), sink, telemetry, settings, Path(directory)).run(items)
            sink.finalize()
            elapsed = time.perf_counter() - started
            self.assertLess(telemetry.timings.get("flush", 0.0), 2000.0)
            self.assertLessEqual(sink.flush_count, 3)
            self.assertLess(elapsed, 5.0)

    def test_deadline_fast_stays_l0_and_slow_degrades_smoothly(self):
        settings = load_settings(ROOT / "submission" / "config.json")

        fast_now = [0.0]
        fast = DeadlineManager(0.0, 3800, settings.deadline, clock=lambda: fast_now[0])
        fast_now[0] = 120.0
        fast.start_processing(256)
        fast_levels = []
        while fast.done < 3800:
            count = min(256, 3800 - fast.done)
            fast_now[0] += 0.35 * count
            fast.observe(count)
            fast_levels.append(fast.budget().level)
        self.assertEqual(set(fast_levels), {"L0"})

        slow_now = [0.0]
        slow = DeadlineManager(0.0, 3800, settings.deadline, clock=lambda: slow_now[0])
        slow_now[0] = 120.0
        slow.start_processing(256)
        slow_levels = []
        costs = {"L0": 0.8, "L1": 0.5, "L2": 0.25, "L3": 0.1, "L4": 0.01}
        while slow.done < 3800:
            level = slow.budget().level
            count = min(256, 3800 - slow.done)
            slow_now[0] += costs[level] * count
            slow.observe(count)
            slow_levels.append(slow.budget().level)
        indices = [int(level[1:]) for level in slow_levels]
        self.assertTrue(any(value > 0 for value in indices))
        self.assertTrue(all(b - a <= 1 or b == 4 for a, b in zip(indices, indices[1:])))
        self.assertLess(slow_now[0], slow.planned)

    def test_public_warmup_cap_and_small_batch_transition_limit(self):
        settings = load_settings(ROOT / "submission" / "config.json")
        now = [0.0]
        deadline = DeadlineManager(0.0, 1600, settings.deadline, clock=lambda: now[0])
        now[0] = 120.0
        deadline.start_processing(8)
        costs = {"L0": 1.2, "L1": 0.7, "L2": 0.35, "L3": 0.15, "L4": 0.01}
        while deadline.done < 1600:
            level = deadline.budget().level
            count = min(8, 1600 - deadline.done)
            now[0] += costs[level] * count
            deadline.observe(count)
            deadline.budget()
        self.assertLessEqual(len(deadline.transitions), 10)

        large_batch = DeadlineManager(0.0, 1600, settings.deadline, clock=lambda: 120.0)
        large_batch.start_processing(256)
        self.assertLessEqual(large_batch.warmup_items, 240)

    def test_hard_limit_is_continuous(self):
        values = [hard_limit_for(n) for n in range(1, 5001)]
        self.assertTrue(all(b / a <= 1.5 for a, b in zip(values, values[1:])))

    def test_image_selection_is_sorted_and_budgeted_per_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "images" / "1"
            folder.mkdir(parents=True)
            for name in ("z.jpeg", "a.jpg", "c.jpg", "b.png", "m.webp"):
                (folder / name).write_bytes(b"x")
            item = Item(0, "1", "", "", "БАД")
            high = Budget("L0", 100, 3, 896, False, True)
            low = Budget("L1", 100, 1, 640, False, True)
            first, _ = attach_images([item], root, high)
            second, _ = attach_images([item], root, high)
            loader = ImageLoader(root)
            reduced = next(loader.iter_batches([item], low))
            self.assertEqual(first[0].image_paths, second[0].image_paths)
            self.assertEqual([Path(path).name for path in first[0].image_paths], ["a.jpg", "b.png", "c.jpg"])
            self.assertEqual(len(reduced[0].image_paths), 1)

    def test_partial_predictor_keeps_complete_output(self):
        class PartialRouter:
            needs_images = False
            def run(self, items, budget):
                return [Prediction(item.row_index, 0.1, "partial") for item in items[:len(items)//2]]
        class Deadline:
            def budget(self): return Budget("L0", 100, 0, 0, False, False, time.monotonic() + 10)
            def observe(self, count): pass

        settings = load_settings(ROOT / "submission" / "config.json")
        items = [Item(i, str(i), "x", "", "БАД") for i in range(10)]
        defaults = DefaultPolicy(settings)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.csv"
            sink = ResultSink(output, items, defaults.result_for_item)
            sink.flush()
            Orchestrator(PartialRouter(), Deadline(), sink, Telemetry(), settings, Path(directory)).run(items)
            sink.finalize()
            with output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(items))


if __name__ == "__main__":
    unittest.main()
