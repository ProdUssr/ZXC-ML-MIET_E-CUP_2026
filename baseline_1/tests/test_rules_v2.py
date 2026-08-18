from __future__ import annotations
import inspect,unittest
from pathlib import Path
from submission.contracts import Budget,Item,RuntimeContext
from submission.predictors.rules import RulesPredictor
import submission.predictors.rules as rules_module
from submission.settings import load_settings
from submission.telemetry import Telemetry

class RulesV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings=load_settings('submission/config.json'); cls.predictor=RulesPredictor({}); cls.predictor.load(RuntimeContext(Path('submission'),cls.settings,Telemetry())); cls.budget=Budget('L0',100,0,0,False,False)
    def p(self,text,category): return self.predictor.predict_batch([Item(0,'x',text,'',category)],self.budget)[0].p_regulated
    def test_boundaries_negations_and_new_markers(self):
        for text in ('Ракетка для бадминтона','Бадяга гель','не является биологически активной добавкой'):
            self.assertLess(self.p(text,'БАД'),.5,text)
        for text in ('Плед негорючий','Ткань не воспламеняется'):
            self.assertLess(self.p(text,'Легковоспламеняющиеся'),.5,text)
        for text in ('Аэрозоль, огнеопасно','Спиртовка, этиловый спирт 96%','Свеча ароматическая'):
            self.assertGreater(self.p(text,'Легковоспламеняющиеся'),.5,text)
    def test_explicit_exclusion_survives_normal_description_length(self):
        filler=' обычное описание состава и свойств' * 8
        cases=(
            ('Товар не является биологически активной добавкой'+filler,'БАД'),
            ('Ткань не воспламеняется'+filler,'Легковоспламеняющиеся'),
        )
        for text,category in cases:
            prediction=self.predictor.predict_batch([Item(0,'x',text,'',category)],self.budget)[0]
            self.assertGreater(len(text),200)
            self.assertTrue(prediction.features['explicit_exclusion'])
            self.assertLess(prediction.p_regulated,self.settings.threshold(category))
    def test_independent_evidence_and_narrow_lacquer_stem(self):
        harmless=Item(0,'x','Лакомство для собак','','Легковоспламеняющиеся')
        mixed=Item(1,'y','Зажигалка со встроенным фонариком','','Легковоспламеняющиеся')
        first,second=self.predictor.predict_batch([harmless,mixed],self.budget)
        self.assertFalse(first.features['has_positive'])
        self.assertTrue(second.features['has_positive'])
        self.assertTrue(second.features['has_negative'])
        self.assertGreater(second.p_regulated,.5)
    def test_mapping_does_not_change_rule_score(self):
        direct=self.p('Спички туристические','Легковоспламеняющиеся'); old=self.predictor.ctx
        other=load_settings('submission/config.json'); object.__setattr__(other,'label_mapping','inverted'); self.predictor.load(RuntimeContext(Path('submission'),other,Telemetry())); inverted=self.p('Спички туристические','Легковоспламеняющиеся'); self.predictor.ctx=old
        self.assertEqual(direct,inverted)
    def test_no_marker_uses_category_prior(self):
        self.assertLess(self.p('обычный товар','БАД'),.5); self.assertGreater(self.p('обычный товар','Легковоспламеняющиеся'),.5)
    def test_rules_do_not_import_label_probability_conversion(self):
        self.assertNotIn('p_regulated_from_p_label1',inspect.getsource(rules_module))
