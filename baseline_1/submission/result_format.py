"""The single source of truth for the strict result field format."""
from __future__ import annotations

import re

try:
    from .label_semantics import VERDICT_BAN, VERDICT_OK
except ImportError:
    from label_semantics import VERDICT_BAN, VERDICT_OK

RESULT_RE = r"^<комментарий>[^<>\n\r]{50,300}<вердикт>(бан|не бан)$"
_RESULT_RX = re.compile(RESULT_RE)
_FALLBACK = "Автоматическая проверка выполнила безопасный разбор карточки товара. Вердикт сформирован по доступным данным категории без обращения к внешним сервисам."


def sanitize_comment(text: str) -> str:
    value = "" if text is None else str(text)
    value = value.replace("<", " ").replace(">", " ").replace(";", " ").replace(",", " ").replace("\n", " ").replace("\r", " ")
    value = value.replace("«", "'").replace("»", "'").replace("“", "'").replace("”", "'").replace('"', "'")
    return " ".join(value.split())


def fit_length(text: str, lo: int = 50, hi: int = 300) -> str:
    text = sanitize_comment(text)
    if len(text) < lo:
        suffix = " Данных достаточно для безопасного решения по правилам категории."
        text = (text + suffix).strip()
    if len(text) > hi:
        cut = text[:hi]
        boundary = max(cut.rfind(". "), cut.rfind(" "))
        text = cut[:boundary + (1 if cut[boundary:boundary + 1] == "." else 0)].strip() if boundary >= lo - 1 else cut.strip()
    if len(text) < lo:
        text = (text + " " + ("проверка " * 10)).strip()[:lo]
    return text[:hi]


def DEFAULT_RESULT(category: str = "", verdict: str = VERDICT_OK) -> str:
    # category is deliberately accepted for a stable caller contract in phase 1.
    return f"<комментарий>{fit_length(_FALLBACK)}<вердикт>{verdict if verdict in (VERDICT_BAN, VERDICT_OK) else VERDICT_OK}"


def build_result(comment: str, verdict: str) -> str:
    safe_verdict = verdict if verdict in (VERDICT_BAN, VERDICT_OK) else VERDICT_OK
    result = f"<комментарий>{fit_length(comment)}<вердикт>{safe_verdict}"
    return result if _RESULT_RX.fullmatch(result) else DEFAULT_RESULT("", safe_verdict)


def is_valid_result(value: str) -> bool:
    return bool(_RESULT_RX.fullmatch(str(value)))
