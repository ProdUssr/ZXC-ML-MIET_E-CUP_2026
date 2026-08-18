"""Generic batch orchestration; predictor-specific logic belongs elsewhere."""
from __future__ import annotations

import logging
import time

try:
    from .contracts import Evidence, Prediction
    from .explanations import build as build_explanation, validate_model_comment
    from .images.loader import ImageLoader
    from .label_semantics import (
        p_regulated_from_p_label1,
        verdict_from_p_regulated,
    )
    from .result_format import build_result
except ImportError:
    from contracts import Evidence, Prediction
    from explanations import build as build_explanation, validate_model_comment
    from images.loader import ImageLoader
    from label_semantics import p_regulated_from_p_label1, verdict_from_p_regulated
    from result_format import build_result

LOG = logging.getLogger("phase0.orchestrator")


class DefaultPolicy:
    def __init__(self, settings):
        self.settings = settings

    def prediction(self, item, error: bool = False) -> Prediction:
        p_regulated = p_regulated_from_p_label1(
            self.settings.p_label1_prior(item.category),
            self.settings.label_mapping,
        )
        known = item.category in self.settings.thresholds_p_regulated
        evidence = Evidence(
            kind="prior" if known else "unknown",
            source="default",
            pattern="",
            text=(
                "решение по априору категории"
                if known
                else "категория не распознана"
            ),
        )
        return Prediction(
            row_index=item.row_index,
            p_regulated=p_regulated,
            stage="default:error" if error else "default",
            evidence=[evidence],
            confidence=abs(p_regulated - 0.5) * 2,
        )

    def result_for_item(self, item) -> str:
        prediction = self.prediction(item)
        verdict = verdict_from_p_regulated(
            prediction.p_regulated,
            self.settings.threshold(item.category),
        )
        return build_result(
            build_explanation(item, verdict, prediction.evidence),
            verdict,
        )


class BatchPlanner:
    def __init__(self, size: int):
        self.size = max(1, size)

    def plan(self, items, budget):
        del budget  # Kept in the seam for Phase 1 adaptive batching.
        for start in range(0, len(items), self.size):
            yield items[start:start + self.size]


class Orchestrator:
    def __init__(
        self,
        router,
        deadline,
        sink,
        telemetry,
        settings,
        resource_root,
    ):
        self.router = router
        self.deadline = deadline
        self.sink = sink
        self.telemetry = telemetry
        self.settings = settings
        self.resource_root = resource_root
        self.defaults = DefaultPolicy(settings)
        self.planner = BatchPlanner(settings.batch_size)
        self.image_loader = ImageLoader(resource_root)

    def run(self, items) -> None:
        last_flush = time.monotonic()
        manifest_scanned = 0
        manifest_attached = 0
        for raw_batch in self.planner.plan(list(items), self.deadline.budget()):
            budget = self.deadline.budget()
            batches = (raw_batch,)
            if self.router.needs_images:
                started = time.perf_counter()
                batches = self.image_loader.iter_batches(raw_batch, budget)
            for batch in batches:
                if self.router.needs_images:
                    stats = self.image_loader.last_stats
                    manifest_scanned += int(stats.get("scanned", 0))
                    manifest_attached += int(stats.get("attached", 0))
                    self.telemetry.timing(
                        "manifest", (time.perf_counter() - started) * 1000
                    )
                predictions = self._predict(batch, budget)
                self._consume(batch, predictions, budget)
                self.deadline.observe(len(batch))
                if time.monotonic() - last_flush >= self.settings.flush_interval_sec:
                    flush_started = time.perf_counter()
                    self.sink.flush()
                    self.telemetry.timing(
                        "flush", (time.perf_counter() - flush_started) * 1000
                    )
                    last_flush = time.monotonic()
        if self.router.needs_images:
            self.telemetry.set(
                "manifest",
                {"scanned": manifest_scanned, "attached": manifest_attached},
            )
            self.telemetry.count("images_attached", manifest_attached)

    def _predict(self, batch, budget):
        if budget.level == "L4":
            return [self.defaults.prediction(item) for item in batch]
        try:
            return self.router.run(batch, budget)
        except Exception:
            LOG.exception("router batch failed")
            self.telemetry.count("router_batch_error")
            return []

    def _consume(self, batch, predictions, budget) -> None:
        by_index = {prediction.row_index: prediction for prediction in predictions}
        for item in batch:
            prediction = by_index.get(item.row_index)
            if prediction is None:
                prediction = self.defaults.prediction(item, error=True)
            verdict = verdict_from_p_regulated(
                prediction.p_regulated,
                self.settings.threshold(item.category),
            )
            comment = (
                validate_model_comment(prediction.comment, verdict)
                if prediction.comment
                else None
            )
            if comment is None:
                comment = build_explanation(item, verdict, prediction.evidence)
            self.sink.submit(item.row_index, build_result(comment, verdict))
            self.telemetry.count("processed")
            self.telemetry.count(f"stage:{prediction.stage}")
            source = (
                "prior"
                if prediction.stage.startswith("default")
                or any(value.kind in ("prior", "unknown") for value in prediction.evidence)
                else prediction.stage.split(":", 1)[0]
            )
            self.telemetry.count(f"resolved:{source}")
            probability_bin = min(9, max(0, int(prediction.p_regulated * 10)))
            self.telemetry.count(f"p_regulated_bin:{probability_bin}")
            self.telemetry.count(f"level_items:{budget.level}")
            self.telemetry.count(f"category:{item.category}")
