from __future__ import annotations
import builtins,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from submission.contracts import Budget,Item,RuntimeContext
from submission.predictors import REGISTRY, build
import submission.predictors.embedding
import submission.predictors.rules
import submission.predictors.vlm
from submission.settings import load_settings
from submission.telemetry import Telemetry

class PredictorContractTests(unittest.TestCase):
    def test_every_registered_predictor(self):
        settings=load_settings(Path('submission/config.json')); items=[Item(0,'a','Бадяга','','БАД'),Item(1,'b','','',''),Item(2,'c','🔥','не воспламеняется','Легковоспламеняющиеся')]; budget=Budget('L2',100,0,0,False,False)
        with tempfile.TemporaryDirectory() as root:
            for name in sorted(REGISTRY):
                with self.subTest(name=name):
                    predictor=build(name,{}); predictor.load(RuntimeContext(Path(root),settings,Telemetry()))
                    original_open=builtins.open
                    def guarded_open(file,*args,**kwargs):
                        if str(file).lower().endswith(('.jpg','.jpeg','.png')):
                            raise AssertionError('image opened with max_images=0')
                        return original_open(file,*args,**kwargs)
                    with patch('builtins.open',side_effect=guarded_open):
                        first=predictor.predict_batch(items,budget); second=predictor.predict_batch(items,budget)
                    predictor.close()
                    self.assertEqual(len(first),len(items)); self.assertEqual(first,second); self.assertEqual({p.row_index for p in first},{i.row_index for i in items}); self.assertTrue(all(0<=p.p_regulated<=1 for p in first))
