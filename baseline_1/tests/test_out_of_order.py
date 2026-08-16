from __future__ import annotations
import csv,tempfile,unittest
from pathlib import Path
from submission.contracts import Budget,Item,Prediction
from submission.orchestrator import Orchestrator,DefaultPolicy
from submission.settings import load_settings
from submission.sink import ResultSink
from submission.telemetry import Telemetry

class ReverseRouter:
    needs_images=False
    def run(self,items,budget): return [Prediction(i.row_index,.1,'reverse') for i in reversed(items)]
class FixedDeadline:
    def budget(self): return Budget('L0',100,0,0,False,False)
    def observe(self,n): pass

class OrderTests(unittest.TestCase):
    def test_reversed_predictions_keep_input_order(self):
        settings=load_settings('submission/config.json'); items=[Item(i,str(i),'x','x','БАД') for i in range(10)]; defaults=DefaultPolicy(settings)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'out.csv'; sink=ResultSink(path,items,defaults.result_for_item); sink.flush(); Orchestrator(ReverseRouter(),FixedDeadline(),sink,Telemetry(),settings,Path(d)).run(items)
            with path.open(encoding='utf-8',newline='') as source: rows=list(csv.DictReader(source))
            self.assertEqual([r['id'] for r in rows],[str(i) for i in range(10)])
