from __future__ import annotations
import unittest
from types import SimpleNamespace
from submission.contracts import Budget,Item,Prediction
from submission.router import Router
from submission.telemetry import Telemetry

class RecordingPredictor:
    name='recording'; needs_images=False
    def __init__(self): self.levels=[]
    def predict_batch(self,items,budget):
        self.levels.append(budget.level)
        return [Prediction(item.row_index,.5,self.name) for item in items]

class DegradationTests(unittest.TestCase):
    def test_levels_are_plain_immutable_inputs(self):
        budgets=[Budget(f'L{i}',100-i,0 if i>=2 else 1,640,False,i<4) for i in range(1,5)]
        predictor=RecordingPredictor(); router=Router([]); router.predictors=[(None,predictor)]
        router.ctx=SimpleNamespace(telemetry=Telemetry())
        items=[Item(0,'1','','','БАД')]
        for budget in budgets:
            router.run(items,budget)
        self.assertEqual(predictor.levels,['L1','L2','L3','L4'])
        self.assertFalse(budgets[-1].allow_escalation)
        with self.assertRaises(Exception): budgets[-1].level='L0'
