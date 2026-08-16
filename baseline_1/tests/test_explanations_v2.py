from __future__ import annotations

import unittest

from submission.contracts import Evidence, Item
from submission.explanations import build, validate_model_comment
from submission.explanations.templates import TEMPLATES, UNKNOWN
from submission.label_semantics import VERDICT_BAN, VERDICT_OK
from submission.result_format import sanitize_comment


class ExplanationV2Tests(unittest.TestCase):
    def test_templates_have_required_count_and_source_length(self):
        for category, outcomes in TEMPLATES.items():
            for outcome, templates in outcomes.items():
                with self.subTest(category=category, outcome=outcome):
                    self.assertGreaterEqual(len(templates), 3)
                    self.assertLessEqual(len(templates), 5)
                    self.assertTrue(all(120 <= len(text) <= 220 for text in templates))
                    self.assertTrue(all("," not in text for text in templates))

    def test_twenty_rendered_comments_are_readable_and_in_bounds(self):
        categories=list(TEMPLATES)
        verdicts=(VERDICT_BAN,VERDICT_OK)
        for index in range(20):
            category=categories[index % len(categories)]
            actual_category='unknown' if category == UNKNOWN else category
            item=Item(index,str(index),'товар','описание',actual_category)
            text=build(item,verdicts[index % 2],[Evidence('model','test','marker','проверенный признак')])
            self.assertNotIn(',',text)
            self.assertTrue(50 <= len(text) <= 300)
            self.assertGreaterEqual(text.count('.'),2)

    def test_unknown_category_uses_neutral_templates(self):
        item=Item(0,'1','товар','','неизвестная категория')
        text=build(item,VERDICT_OK,[Evidence('unknown','test','','категория не распознана')])
        self.assertIn(text,[sanitize_comment(t.format(evidence='категория не распознана')) for t in TEMPLATES[UNKNOWN]['allowed']])
        self.assertNotIn('биологически актив',text.lower())

    def test_bad_model_comment_is_rejected_without_regeneration(self):
        self.assertIsNone(validate_model_comment('Ограничение не применяется',VERDICT_BAN))
        self.assertIsNone(validate_model_comment('Товар требует ограничения',VERDICT_OK))
