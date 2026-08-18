from __future__ import annotations

try:
    from .manifest import attach_images
except ImportError:
    from images.manifest import attach_images


class ImageLoader:
    """Synchronous Phase 0 implementation of the stable streaming seam."""

    def __init__(self, root):
        self.root = root
        self.last_stats = {"scanned": 0, "attached": 0}

    def iter_batches(self, items, budget):
        loaded, self.last_stats = attach_images(items, self.root, budget)
        yield loaded
