from __future__ import annotations
try:
    from ..label_semantics import VERDICT_BAN
    from ..result_format import sanitize_comment
    from .templates import TEMPLATES,UNKNOWN
except ImportError:
    from label_semantics import VERDICT_BAN
    from result_format import sanitize_comment
    from explanations.templates import TEMPLATES,UNKNOWN

def _consistent(text,is_ban):
    low=text.lower(); bad=("не применяется","не требуется","без ограничения") if is_ban else ("требует ограничения","ограничивающее решение")
    return not any(x in low for x in bad)
def build(item,verdict,evidence):
    key=item.category if item.category in TEMPLATES else UNKNOWN; outcome="regulated" if verdict==VERDICT_BAN else "allowed"
    proof=sanitize_comment(evidence[0].text if evidence else "решение по доступным сведениям")[:100]
    choices=TEMPLATES[key][outcome]; text=choices[(item.row_index+len(proof))%len(choices)].format(evidence=proof)
    if not _consistent(text,verdict==VERDICT_BAN): text=choices[0].format(evidence="доступные сведения карточки")
    return sanitize_comment(text)
def validate_model_comment(text,verdict):
    clean=sanitize_comment(text or ""); return clean if clean and _consistent(clean,verdict==VERDICT_BAN) else None
