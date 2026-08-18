from __future__ import annotations
import csv,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path

class SwapTests(unittest.TestCase):
    def test_new_file_and_config_are_sufficient(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); shutil.copytree('submission',root/'submission',ignore=shutil.ignore_patterns('__pycache__'))
            fake=root/'submission'/'predictors'/'fake.py'
            fake.write_text('from . import register\nfrom .base import BasePredictor\nfrom ..contracts import Prediction\n@register("fake")\nclass FakePredictor(BasePredictor):\n name="fake"; needs_images=False\n def predict_batch(self,items,budget): return [Prediction(i.row_index,.99,self.name) for i in items]\n',encoding='utf-8')
            cfg=json.loads((root/'submission'/'config.json').read_text(encoding='utf-8')); cfg['stages']=[{'predictor':'fake','escalate_band':[0,1],'min_level':'L4','params':{}}]; (root/'fake.json').write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
            inp=root/'test.csv'; out=root/'out.csv'
            with inp.open('w',encoding='utf-8',newline='') as f: w=csv.DictWriter(f,fieldnames=['id','name','description','category']); w.writeheader(); w.writerow({'id':'1','name':'x','description':'x','category':'БАД'})
            subprocess.run([sys.executable,str(root/'submission'/'run.py'),'-i',str(inp),'-o',str(out),'--config',str(root/'fake.json')],check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            with out.open(encoding='utf-8',newline='') as source:
                result=list(csv.DictReader(source))[0]['result']
            self.assertIn('огранич',result)
