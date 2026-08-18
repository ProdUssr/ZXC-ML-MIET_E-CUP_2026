# ADR 003: lazy predictor registry

Predictors register from their own module and are imported lazily from the stage name in configuration. Adding a Phase 1 predictor therefore requires one file under `predictors/` and one config entry, with no edit to `run.py`, `router.py`, the orchestrator or sink. Heavy libraries must be imported only inside `load()`.
