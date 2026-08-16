from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from submission.contracts import Item,RuntimeContext
from submission.deadline import DeadlineManager
from submission.orchestrator import DefaultPolicy,Orchestrator
from submission.predictors import REGISTRY
from submission.router import Router
from submission.settings import load_settings
from submission.sink import ResultSink
from submission.telemetry import Telemetry

class NoUselessWorkTests(unittest.TestCase):
    def test_rules_only_does_not_build_manifest(self):
        settings=load_settings('submission/config.json'); telemetry=Telemetry(); router=Router(settings.stages,REGISTRY); router.load(RuntimeContext(Path('submission'),settings,telemetry)); items=[Item(0,'1','x','x','БАД')]; defaults=DefaultPolicy(settings)
        with tempfile.TemporaryDirectory() as d:
            sink=ResultSink(Path(d)/'out.csv',items,defaults.result_for_item); sink.flush(); deadline=DeadlineManager(0.0,1,settings.deadline)
            # A deterministic budget avoids dependence on the deliberately old t0.
            deadline.budget=lambda: __import__('submission.contracts',fromlist=['Budget']).Budget('L0',100,0,0,False,False)
            with patch('submission.images.loader.ImageLoader.iter_batches',side_effect=AssertionError('manifest called')): Orchestrator(router,deadline,sink,telemetry,settings,Path(d)).run(items)
        router.close()
