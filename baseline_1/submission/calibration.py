"""Data-driven mapping from predictor features to regulated probability."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

LOG = logging.getLogger("phase0.calibration")


def signature_key(features: dict[str, Any]) -> str:
    ordered = (
        str(features.get("category", "")),
        int(bool(features.get("has_positive", False))),
        int(bool(features.get("has_negative", False))),
        str(features.get("n_positive_bucket", "0")),
        int(bool(features.get("explicit_exclusion", False))),
    )
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))


class CalibrationTable:
    def __init__(
        self,
        cells: dict[str, dict[str, Any]] | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> None:
        self.cells = cells or {}
        self.constraints = constraints or {}

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationTable":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            cells = raw.get("cells", {})
            if not isinstance(cells, dict):
                raise TypeError("calibration cells must be an object")
            constraints = raw.get("constraints", {})
            return cls(cells, constraints if isinstance(constraints, dict) else {})
        except (OSError, ValueError, TypeError):
            LOG.exception("calibration unavailable at %s; category priors used", path)
            return cls()

    def probability(self, features: dict[str, Any], fallback: float) -> float:
        cell = self.cells.get(signature_key(features))
        probability = min(1.0, max(0.0, float(fallback)))
        try:
            if isinstance(cell, dict):
                probability = min(1.0, max(0.0, float(cell["p_regulated"])))
        except (KeyError, TypeError, ValueError):
            pass
        if features.get("explicit_exclusion") and not features.get("has_positive"):
            probability = min(
                probability,
                float(self.constraints.get("explicit_exclusion_cap", 0.49)),
            )
        return probability
