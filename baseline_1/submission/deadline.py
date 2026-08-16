from __future__ import annotations

import math
import os
import time
try: from .contracts import Budget
except ImportError: from contracts import Budget

def hard_limit_for(n: int) -> float:
    override = os.environ.get("ECUP_HARD_LIMIT_SEC")
    if override:
        try:
            return max(1.0, float(override))
        except ValueError:
            pass
    # 0.63 s/item interpolates the published Public/Private limits; the caps
    # preserve the 180 s Check floor and 2400 s Private ceiling continuously.
    return max(180.0, min(2400.0, 0.63 * max(0, int(n))))

class DeadlineManager:
    def __init__(self, t0: float, n_items: int, policy, clock=None):
        self.clock = clock or time.monotonic
        self.t0 = t0
        self.n_items = n_items
        self.policy = policy
        self.planned = hard_limit_for(n_items) * policy.planned_fraction
        self.done = 0
        self.processing_start = None
        self.warmup_items = max(1, math.ceil(0.05 * n_items))
        self._last_level = None
        self._transition_done = -1
        self.transition_interval_items = max(1, n_items // 50)
        self.recovery_interval_items = max(
            self.transition_interval_items, n_items // 5
        )
        self.transitions = []

    def start_processing(self, batch_size: int) -> None:
        self.processing_start = self.clock()
        desired = max(
            3 * max(1, int(batch_size)), math.ceil(0.05 * self.n_items)
        )
        self.warmup_items = min(desired, max(1, math.ceil(0.15 * self.n_items)))

    def observe(self, done_items: int) -> None:
        self.done = min(self.n_items, self.done + max(0, int(done_items)))

    def _now(self) -> float:
        return self.clock()

    def _processing_elapsed(self, now: float) -> float:
        start = self.processing_start if self.processing_start is not None else now
        return max(0.0, now - start)

    def forecast_overrun_sec(self) -> float:
        now = self._now()
        remaining = max(0.0, self.planned - (now - self.t0))
        if self.done <= 0:
            return 0.0
        rate = self._processing_elapsed(now) / self.done
        return max(0.0, rate * (self.n_items - self.done) - remaining)

    def _target_level(self, ratio: float):
        ordered = sorted(
            self.policy.levels, key=lambda value: value.forecast_ratio, reverse=True
        )
        for level in ordered:
            if ratio >= level.forecast_ratio:
                return level
        return ordered[-1]

    def budget(self) -> Budget:
        now = self._now()
        elapsed = max(0.0, now - self.t0)
        remaining = max(0.0, self.planned - elapsed)
        levels = {level.level: level for level in self.policy.levels}
        current_name = self._last_level or "L0"

        if remaining <= self.policy.reserve_sec:
            target_name = "L4"
        elif self.done < self.warmup_items or self.done <= 0:
            target_name = "L0"
        else:
            rate = self._processing_elapsed(now) / self.done
            predicted = rate * (self.n_items - self.done)
            ratio = predicted / max(remaining, 1e-6)
            target_name = self._target_level(ratio).level
            current_index = int(current_name[1:]) if current_name in levels else 0
            target_index = int(target_name[1:]) if target_name in levels else 4
            if target_index < current_index:
                current_threshold = levels[current_name].forecast_ratio
                if ratio >= max(0.0, current_threshold - 0.05):
                    target_index = current_index
            minimum_interval = (
                self.recovery_interval_items
                if target_index < current_index
                else self.transition_interval_items
            )
            if self.done - self._transition_done < minimum_interval:
                target_index = current_index
            elif target_index > current_index:
                target_index = current_index + 1
            elif target_index < current_index:
                target_index = current_index - 1
            target_name = f"L{target_index}"

        chosen = levels.get(target_name) or levels.get("L4") or self.policy.levels[0]
        if chosen.level != self._last_level:
            self.transitions.append({"level": chosen.level, "elapsed_sec": elapsed})
            self._last_level = chosen.level
            self._transition_done = self.done
        return Budget(
            chosen.level,
            remaining,
            chosen.max_images,
            chosen.max_image_side,
            chosen.allow_generation,
            chosen.allow_escalation,
            self.t0 + self.planned,
        )

    def summary(self):
        init_sec = (
            max(0.0, self.processing_start - self.t0)
            if self.processing_start is not None
            else None
        )
        return {
            "planned_sec": self.planned,
            "init_sec": init_sec,
            "done": self.done,
            "level": self._last_level,
            "warmup_items": self.warmup_items,
            "transition_interval_items": self.transition_interval_items,
            "recovery_interval_items": self.recovery_interval_items,
            "transitions": self.transitions,
            "forecast_overrun_sec": self.forecast_overrun_sec(),
        }
