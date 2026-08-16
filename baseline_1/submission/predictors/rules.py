"""Rubric rules. Every score emitted here is already ``p_regulated``."""
from __future__ import annotations

from functools import lru_cache
import re

try:
    from ..contracts import Evidence, Prediction
    from ..result_format import sanitize_comment
    from . import register
    from .base import BasePredictor
except ImportError:
    from contracts import Evidence, Prediction
    from result_format import sanitize_comment
    from predictors import register
    from predictors.base import BasePredictor

BAD = "БАД"
FLAMMABLE = "Легковоспламеняющиеся"


def _stem_patterns(*stems: str) -> tuple[str, ...]:
    return tuple(rf"\b{stem}\w*\b" for stem in stems)


RULES = {
    BAD: {
        "positive": (
            r"\bбад\b",
            r"\bбиологически\s+активн\w*\s+добавк\w*\b",
            r"\bdietary\s+supplement\b",
            r"\bбиодобавк\w*\b",
        ),
        "negative": (
            r"\bспортивн\w*\s+питан\w*\b",
            r"\bспортпит\w*\b",
            r"\bпротеин\w*\b",
            r"\bbcaa\b",
            r"\bаминокислот\w*\b",
            r"\b[лl]-?карнитин\w*\b",
        ),
    },
    FLAMMABLE: {
        "positive": _stem_patterns(
            "спич", "зажигалк", "легковоспламен", "горюч", "воспламен",
            "бензин", "горелк", "топлив", "огнеопас", "спирт", "этанол",
            "ацетон", "растворител", "керосин", "аэрозол", "свеч", "фитил",
            "парафин", "баллончик", "хлопушк", "пиротех",
            "розжиг",
        ) + (
            r"\bлак\b", r"\bлака\b", r"\bлаком\b",
            r"\bлакокрасоч\w*\b",
            r"\bкраска\b", r"\bкраски\b", r"\bкраску\b",
            r"\bкраской\b", r"\bкрасок\b",
        ),
        "negative": _stem_patterns(
            "мангал", "грил", "газ плит", "газовая плит",
            "уголь для рисования", "активированный уголь", "негорюч",
            "невоспламен", "встроенн",
        ),
    },
}

_NEGATION_WORDS = {"не", "без", "нет"}
_NEGATION_PHRASE = re.compile(r"(?:не\s+является|не\s+содержит)\s*$")
_EXPLICIT_EXCLUSION = re.compile(
    r"\bне\s+(?:является|содержит)\b|\bнегорюч\w*\b|"
    r"\bне\s+воспламен\w*\b|\bневоспламен\w*\b"
)
def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower().replace("ё", "е")).strip()


def _negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 60):start]
    words = re.findall(r"[а-яa-z]+", prefix)[-3:]
    return bool(
        _NEGATION_WORDS.intersection(words)
        or _NEGATION_PHRASE.search(prefix)
        or prefix.endswith("не")
    )


def _evidence(kind: str, pattern: str, text: str, match: re.Match) -> Evidence:
    excerpt = text[max(0, match.start() - 25):match.end() + 25].strip(" ,.;:-")
    return Evidence(
        kind=kind,
        source="rules",
        pattern=pattern,
        text=sanitize_comment(excerpt or match.group(0)),
    )


def _collect(patterns: tuple[str, ...], text: str, kind: str) -> list[Evidence]:
    hits: list[Evidence] = []
    for pattern in patterns:
        for match in _compiled(pattern).finditer(text):
            hits.append(_evidence(kind, pattern, text, match))
    return hits


def _collect_positive(
    patterns: tuple[str, ...], text: str
) -> tuple[list[Evidence], list[Evidence]]:
    positive: list[Evidence] = []
    negated: list[Evidence] = []
    for pattern in patterns:
        for match in _compiled(pattern).finditer(text):
            target = negated if _negated(text, match.start()) else positive
            kind = "negative" if target is negated else "positive"
            target.append(_evidence(kind, pattern, text, match))
    return positive, negated


@lru_cache(maxsize=None)
def _compiled(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


def _positive_bucket(hit_count: int) -> str:
    if hit_count <= 0:
        return "0"
    return "1" if hit_count == 1 else "2+"


def extract_rule_features(item, max_text_chars: int = 20_000):
    """Return evidence signature independently from its learned direction."""
    text = _normalized(f"{item.name} {item.description}"[:max_text_chars])
    spec = RULES.get(item.category)
    if spec is None:
        return None, [], []
    explicit_negative = _collect(spec["negative"], text, "negative") if text else []
    positive, negated_positive = (
        _collect_positive(spec["positive"], text) if text else ([], [])
    )
    negative = explicit_negative + negated_positive
    # Evidence.text is the bounded marker window built by _evidence (roughly
    # 25 characters on each side). Card length therefore cannot disable an
    # explicit rubric exclusion and distant unrelated words cannot enable it.
    explicit_exclusion = any(
        _EXPLICIT_EXCLUSION.search(value.text.lower()) for value in negative
    )
    features = {
        "category": item.category,
        "has_positive": bool(positive),
        "has_negative": bool(negative),
        "n_positive_bucket": _positive_bucket(len(positive)),
        "explicit_exclusion": explicit_exclusion,
    }
    return features, positive, negative


@register("rules")
class RulesPredictor(BasePredictor):
    name = "rules"
    needs_images = False

    def predict_batch(self, items, budget):
        output: list[Prediction] = []
        for item in items:
            try:
                output.append(self._predict_one(item))
            except Exception:
                output.append(self.fallback(item, error=True))
        return output

    def _predict_one(self, item) -> Prediction:
        max_chars = max(256, int(self.params.get("max_text_chars", 20_000)))
        features, positive, negative = extract_rule_features(item, max_chars)
        if features is None:
            return self.fallback(item)

        # Positive and negative clues are independent inputs to calibration.
        evidence = positive + negative
        if not evidence:
            evidence = [Evidence("none", self.name, "", "маркеры рубрики не найдены")]
        p_regulated = self.calibrated_probability(features, item.category)

        return Prediction(
            row_index=item.row_index,
            p_regulated=p_regulated,
            stage=self.name,
            evidence=evidence,
            features=features,
            confidence=abs(p_regulated - 0.5) * 2,
        )
