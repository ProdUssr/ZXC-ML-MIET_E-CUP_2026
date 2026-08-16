"""Lazy predictor registry: a new predictor needs only its module and config entry."""
from __future__ import annotations
import importlib, logging
from typing import Callable
LOG=logging.getLogger("phase0.predictors")
REGISTRY: dict[str,Callable[[dict],object]]={}

def register(name: str):
    def decorator(factory): REGISTRY[name]=factory; return factory
    return decorator

def build(name: str, params: dict, allow_fallback: bool = True):
    import_error = None
    if name not in REGISTRY:
        try:
            importlib.import_module(f"{__name__}.{name}")
        except Exception as exc:
            import_error = exc
            LOG.exception("predictor %s unavailable",name)
    if name not in REGISTRY:
        if not allow_fallback:
            raise LookupError(f"predictor {name!r} is unavailable") from import_error
        if name!="rules": LOG.error("unknown predictor %s; falling back to rules",name)
        importlib.import_module(f"{__name__}.rules"); name="rules"
    return REGISTRY[name](dict(params))
