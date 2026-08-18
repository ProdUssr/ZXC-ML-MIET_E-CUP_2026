"""Typed JSON settings with validation and explicit, logged fallbacks."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
from typing import Any

LOG = logging.getLogger("phase0.settings")


@dataclass(frozen=True)
class StageSettings:
    predictor: str = "rules"
    escalate_band: tuple[float, float] = (0.0, 1.0)
    min_level: str = "L4"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LevelSettings:
    level: str
    forecast_ratio: float
    max_images: int
    max_image_side: int
    allow_generation: bool
    allow_escalation: bool


@dataclass(frozen=True)
class DeadlineSettings:
    planned_fraction: float = 0.85
    reserve_sec: float = 60.0
    levels: tuple[LevelSettings, ...] = ()


@dataclass(frozen=True)
class Settings:
    label_mapping: str
    priors_p_label1: dict[str, float]
    thresholds_p_regulated: dict[str, float]
    stages: tuple[StageSettings, ...]
    batch_size: int
    flush_interval_sec: float
    calibration_path: str
    deadline: DeadlineSettings

    def p_label1_prior(self, category: str) -> float:
        return float(
            self.priors_p_label1.get(
                category, self.priors_p_label1.get("__default__", 0.5)
            )
        )

    def threshold(self, category: str) -> float:
        return float(
            self.thresholds_p_regulated.get(
                category, self.thresholds_p_regulated.get("__default__", 0.5)
            )
        )


_TOP_KEYS = {
    "label_mapping", "priors_p_label1", "thresholds_p_regulated", "stages",
    "batch_size", "flush_interval_sec", "deadline", "calibration",
    "calibration_path",
}
_STAGE_KEYS = {"predictor", "escalate_band", "min_level", "params"}
_DEADLINE_KEYS = {"planned_fraction", "reserve_sec", "levels"}
_LEVEL_KEYS = {
    "level", "forecast_ratio", "max_images", "max_image_side",
    "allow_generation", "allow_escalation",
}
_CALIBRATION_KEYS = {"note", "data"}


def _warn_unknown(value: Any, allowed: set[str], location: str) -> None:
    if isinstance(value, dict):
        for key in sorted(set(value) - allowed):
            LOG.error("unknown config key at %s: %s", location, key)


def _default_levels() -> tuple[LevelSettings, ...]:
    return (
        LevelSettings("L4", 1.00, 0, 0, False, False),
        LevelSettings("L3", 0.95, 0, 0, False, False),
        LevelSettings("L2", 0.90, 0, 0, False, True),
        LevelSettings("L1", 0.80, 1, 640, False, True),
        LevelSettings("L0", 0.00, 3, 896, True, True),
    )


def _float_map(value: Any, default: dict[str, float], name: str) -> dict[str, float]:
    if not isinstance(value, dict):
        LOG.error("%s must be an object; defaults used", name)
        return default
    try:
        result = {str(key): float(item) for key, item in value.items()}
        if any(not 0.0 <= item <= 1.0 for item in result.values()):
            raise ValueError("probabilities must be in [0, 1]")
        return result
    except (TypeError, ValueError):
        LOG.exception("invalid %s; defaults used", name)
        return default


def _parse_stages(raw: Any) -> tuple[StageSettings, ...]:
    if not isinstance(raw, list):
        LOG.error("stages must be a list; rules stage used")
        return (StageSettings(),)
    parsed: list[StageSettings] = []
    for index, value in enumerate(raw):
        _warn_unknown(value, _STAGE_KEYS, f"stages[{index}]")
        try:
            if not isinstance(value, dict):
                raise TypeError("stage must be an object")
            band = tuple(float(item) for item in value.get("escalate_band", (0, 1)))
            if len(band) != 2 or not 0 <= band[0] <= band[1] <= 1:
                raise ValueError("invalid escalation band")
            params = value.get("params", {})
            if not isinstance(params, dict):
                raise TypeError("params must be an object")
            parsed.append(StageSettings(
                predictor=str(value.get("predictor", "rules")),
                escalate_band=(band[0], band[1]),
                min_level=str(value.get("min_level", "L4")),
                params=dict(params),
            ))
        except (TypeError, ValueError, KeyError):
            LOG.exception("invalid stage %r; ignored", value)
    return tuple(parsed) or (StageSettings(),)


def _parse_deadline(raw: Any) -> DeadlineSettings:
    if not isinstance(raw, dict):
        LOG.error("deadline must be an object; defaults used")
        return DeadlineSettings(levels=_default_levels())
    _warn_unknown(raw, _DEADLINE_KEYS, "deadline")
    values = raw.get("levels", [])
    if not isinstance(values, list):
        LOG.error("deadline.levels must be a list; defaults used")
        values = []
    levels: list[LevelSettings] = []
    for index, value in enumerate(values):
        _warn_unknown(value, _LEVEL_KEYS, f"deadline.levels[{index}]")
        try:
            if not isinstance(value, dict):
                raise TypeError("level must be an object")
            levels.append(LevelSettings(
                level=str(value["level"]),
                forecast_ratio=float(value["forecast_ratio"]),
                max_images=max(0, int(value["max_images"])),
                max_image_side=max(0, int(value["max_image_side"])),
                allow_generation=bool(value["allow_generation"]),
                allow_escalation=bool(value["allow_escalation"]),
            ))
        except (TypeError, ValueError, KeyError):
            LOG.exception("invalid deadline level %r; ignored", value)
    planned_fraction = float(raw.get("planned_fraction", 0.85))
    if not 0 < planned_fraction < 1:
        LOG.error("planned_fraction must be in (0, 1); 0.85 used")
        planned_fraction = 0.85
    return DeadlineSettings(
        planned_fraction=planned_fraction,
        reserve_sec=max(0.0, float(raw.get("reserve_sec", 60.0))),
        levels=tuple(levels) or _default_levels(),
    )


def load_settings(path: str | Path) -> Settings:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError("config root must be an object")
    except (OSError, json.JSONDecodeError, TypeError):
        LOG.exception("invalid settings; defaults used")
        raw = {}

    _warn_unknown(raw, _TOP_KEYS, "root")
    _warn_unknown(raw.get("calibration"), _CALIBRATION_KEYS, "calibration")
    mapping = raw.get("label_mapping", "direct")
    if mapping not in ("direct", "inverted"):
        LOG.error("invalid label_mapping; direct used")
        mapping = "direct"

    return Settings(
        label_mapping=mapping,
        priors_p_label1=_float_map(
            raw.get("priors_p_label1"), {"__default__": 0.5}, "priors_p_label1"
        ),
        thresholds_p_regulated=_float_map(
            raw.get("thresholds_p_regulated"), {"__default__": 0.5},
            "thresholds_p_regulated",
        ),
        stages=_parse_stages(raw.get("stages", [{"predictor": "rules"}])),
        batch_size=max(1, int(raw.get("batch_size", 256))),
        flush_interval_sec=max(0.1, float(raw.get("flush_interval_sec", 5.0))),
        calibration_path=str(raw.get("calibration_path", "calibration.json")),
        deadline=_parse_deadline(raw.get("deadline", {})),
    )
