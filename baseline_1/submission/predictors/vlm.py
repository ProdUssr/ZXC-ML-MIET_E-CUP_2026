"""Phase 1 contract placeholder; heavy imports belong in load()."""
from . import register
from .base import BasePredictor


@register("vlm")
class VLMPredictor(BasePredictor):
    name = "vlm"
    needs_images = True

    def predict_batch(self, items, budget):
        return [self.fallback(item) for item in items]
