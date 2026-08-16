"""Configuration-driven predictor cascade."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import time

try:
    from .predictors import build
except ImportError:
    from predictors import build

LOG = logging.getLogger("phase0.router")
_LEVEL = {f"L{index}": index for index in range(5)}


@dataclass(frozen=True)
class StageSpec:
    predictor: str
    escalate_band: tuple[float, float]
    min_level: str
    params: dict


class Router:
    def __init__(self, stages, registry=None):
        self.specs = [
            StageSpec(
                stage.predictor,
                stage.escalate_band,
                stage.min_level,
                stage.params,
            )
            for stage in stages
        ]
        self.registry = registry if registry is not None else {}
        self.predictors = []
        self.ctx = None

    def _build(self, spec: StageSpec, allow_fallback: bool):
        return build(spec.predictor, spec.params, allow_fallback=allow_fallback)

    def load(self, ctx) -> None:
        self.ctx = ctx
        for index, spec in enumerate(self.specs):
            started = time.perf_counter()
            predictor = None
            try:
                predictor = self._build(spec, allow_fallback=(index == 0))
                predictor.load(ctx)
                self.predictors.append((spec, predictor))
            except Exception:
                LOG.exception("predictor %s failed to load; stage disabled", spec.predictor)
                ctx.telemetry.count(f"load_error:{spec.predictor}")
                if predictor is not None:
                    try:
                        predictor.close()
                    except Exception:
                        LOG.exception("failed predictor close after load error")
            finally:
                ctx.telemetry.timing(
                    f"init:{spec.predictor}",
                    (time.perf_counter() - started) * 1000,
                )

    @property
    def needs_images(self) -> bool:
        return any(
            getattr(predictor, "needs_images", False)
            for _, predictor in self.predictors
        )

    def run(self, items, budget):
        if not self.predictors:
            return []
        current = {}
        for index, (spec, predictor) in enumerate(self.predictors):
            selected = self._select(index, spec, items, current, budget)
            if not selected:
                continue
            started = time.perf_counter()
            try:
                predictions = predictor.predict_batch(selected, budget)
            except Exception:
                LOG.exception("predictor %s batch failed", predictor.name)
                self.ctx.telemetry.count(f"error:{predictor.name}")
                predictions = []
            self.ctx.telemetry.timing(
                f"predict:{predictor.name}",
                (time.perf_counter() - started) * 1000,
            )
            valid_indices = {item.row_index for item in selected}
            self.ctx.telemetry.count(f"stage_items:{predictor.name}", len(selected))
            for prediction in predictions:
                if (
                    prediction.row_index in valid_indices
                    and 0 <= prediction.p_regulated <= 1
                ):
                    current[prediction.row_index] = prediction
            if index:
                self.ctx.telemetry.count("escalations", len(selected))
        return list(current.values())

    @staticmethod
    def _select(index, spec, items, current, budget):
        if index == 0:
            return list(items)
        if not budget.allow_escalation:
            return []
        if _LEVEL.get(budget.level, 4) > _LEVEL.get(spec.min_level, 4):
            return []
        low, high = spec.escalate_band
        return [
            item
            for item in items
            if item.row_index in current
            and low <= current[item.row_index].p_regulated <= high
        ]

    def close(self) -> None:
        for _, predictor in reversed(self.predictors):
            try:
                predictor.close()
            except Exception:
                LOG.exception("predictor close failed")
