"""Stable domain contracts. This module imports project code nowhere."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence

@dataclass(frozen=True)
class Item:
    row_index: int
    id: str
    name: str
    description: str
    category: str
    image_paths: tuple[str, ...] = ()

@dataclass(frozen=True)
class Evidence:
    kind: str
    source: str
    pattern: str
    text: str

@dataclass
class Prediction:
    row_index: int
    p_regulated: float
    stage: str
    evidence: list[Evidence] = field(default_factory=list)
    features: dict[str, Any] = field(default_factory=dict)
    comment: str | None = None
    confidence: float = 0.0
    timings_ms: dict[str, float] = field(default_factory=dict)

@dataclass(frozen=True)
class Budget:
    level: str
    remaining_sec: float
    max_images: int
    max_image_side: int
    allow_generation: bool
    allow_escalation: bool
    deadline_monotonic: float = float("inf")

@dataclass(frozen=True)
class RuntimeContext:
    root: Path
    settings: Any
    telemetry: Any

class Predictor(Protocol):
    name: str
    needs_images: bool

    def load(self, ctx: RuntimeContext) -> None: ...

    def predict_batch(self, items: Sequence[Item], budget: Budget) -> list[Prediction]: ...

    def close(self) -> None: ...
