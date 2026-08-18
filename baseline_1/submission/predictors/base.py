from __future__ import annotations
try:
    from ..calibration import CalibrationTable
    from ..contracts import Evidence, Prediction
    from ..label_semantics import p_regulated_from_p_label1
except ImportError:
    from calibration import CalibrationTable
    from contracts import Evidence, Prediction
    from label_semantics import p_regulated_from_p_label1

class BasePredictor:
    name = "base"
    needs_images = False

    def __init__(self, params: dict):
        self.params = params
        self.ctx = None
        self.calibration = CalibrationTable()

    def load(self, ctx):
        self.ctx = ctx
        path = ctx.root / ctx.settings.calibration_path
        self.calibration = CalibrationTable.load(path)

    def close(self):
        return None

    def prior(self, category: str) -> float:
        """Convert train-label priors at the only legal predictor boundary."""
        return p_regulated_from_p_label1(
            self.ctx.settings.p_label1_prior(category),
            self.ctx.settings.label_mapping,
        )

    def fallback(self, item, error: bool = False) -> Prediction:
        p_regulated = self.prior(item.category)
        known = item.category in self.ctx.settings.thresholds_p_regulated
        kind = "prior" if known else "unknown"
        evidence_text = (
            "решение по априору категории"
            if known
            else "категория не распознана"
        )
        return Prediction(
            row_index=item.row_index,
            p_regulated=p_regulated,
            stage=f"{self.name}:error" if error else self.name,
            evidence=[Evidence(kind, self.name, "", evidence_text)],
            confidence=abs(p_regulated - 0.5) * 2,
        )

    def calibrated_probability(self, features: dict, category: str) -> float:
        return self.calibration.probability(features, self.prior(category))
