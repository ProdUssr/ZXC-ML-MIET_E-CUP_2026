"""Single source of truth for train-label semantics and verdict decisions."""
LABEL_GOOD = 1
LABEL_BAD = 0
VERDICT_BAN = "бан"
VERDICT_OK = "не бан"


def verdict_from_label(label: int, mapping: str = "direct") -> str:
    good = int(label) == LABEL_GOOD
    if mapping == "inverted": good = not good
    return VERDICT_OK if good else VERDICT_BAN


def label_from_verdict(verdict: str, mapping: str = "direct") -> int:
    if verdict not in (VERDICT_BAN, VERDICT_OK):
        raise ValueError("unknown verdict")
    direct = LABEL_GOOD if verdict == VERDICT_OK else LABEL_BAD
    return 1 - direct if mapping == "inverted" else direct


def p_regulated_from_p_label1(p: float, mapping: str = "direct") -> float:
    value = min(1.0, max(0.0, float(p)))
    return 1.0 - value if mapping == "direct" else value


def verdict_from_p_regulated(p: float, threshold: float) -> str:
    return VERDICT_BAN if float(p) >= float(threshold) else VERDICT_OK


# Compatibility alias for early Phase 0 callers.
verdict_from_score = verdict_from_p_regulated
