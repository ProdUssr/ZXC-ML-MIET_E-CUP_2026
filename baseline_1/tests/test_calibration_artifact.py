from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CalibrationArtifactTests(unittest.TestCase):
    def test_train_only_artifact_and_holdout_gates(self):
        calibration=json.loads((ROOT/'submission'/'calibration.json').read_text(encoding='utf-8'))
        metrics=json.loads((ROOT/'train'/'metrics.json').read_text(encoding='utf-8'))
        config=json.loads((ROOT/'submission'/'config.json').read_text(encoding='utf-8'))
        self.assertNotIn('holdout_metrics',calibration)
        self.assertEqual(sum(cell['count'] for cell in calibration['cells'].values()),calibration['fit_rows'])
        self.assertEqual(calibration['fit_rows'],metrics['fit_rows'])
        self.assertEqual(calibration['split_id'],metrics['split_id'])
        self.assertEqual(config['thresholds_p_regulated']['БАД'],metrics['thresholds_p_regulated']['БАД'])
        holdout=metrics['holdout_metrics']
        self.assertGreater(holdout['by_category']['БАД']['macro'],0.4269)
        self.assertGreater(holdout['by_category']['Легковоспламеняющиеся']['macro'],0.4908)
        self.assertGreater(holdout['category_macro_mean'],0.5756)
