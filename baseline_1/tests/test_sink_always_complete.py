from __future__ import annotations
import csv,json,shutil,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from submission.contracts import Item
from submission.orchestrator import DefaultPolicy
from submission.settings import load_settings
from submission.sink import ResultSink
from submission.result_format import is_valid_result

class SinkTests(unittest.TestCase):
    def test_target_remains_complete_between_flushes(self):
        items=[Item(i,str(i),'','','БАД') for i in range(20)]; defaults=DefaultPolicy(load_settings('submission/config.json'))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'out.csv'; sink=ResultSink(path,items,defaults.result_for_item); sink.flush(); sink.submit(19,defaults.result_for_item(items[19]))
            with path.open(encoding='utf-8',newline='') as source:
                rows=list(csv.DictReader(source))
            self.assertEqual([r['id'] for r in rows],[i.id for i in items])
            self.assertTrue(all(is_valid_result(r['result']) for r in rows))

    def test_hard_kill_leaves_complete_atomic_snapshot(self):
        # Windows can briefly retain imported module handles after TerminateProcess.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            root=Path(d)
            shutil.copytree('submission',root/'submission',ignore=shutil.ignore_patterns('__pycache__'))
            (root/'submission'/'predictors'/'slow.py').write_text(
                'import time\nfrom . import register\nfrom .base import BasePredictor\n'
                '@register("slow")\nclass SlowPredictor(BasePredictor):\n'
                ' name="slow"; needs_images=False\n'
                ' def predict_batch(self,items,budget):\n  time.sleep(10)\n'
                '  return [self.fallback(item) for item in items]\n',
                encoding='utf-8',
            )
            config=json.loads((root/'submission'/'config.json').read_text(encoding='utf-8'))
            config['stages']=[{'predictor':'slow','params':{}}]
            config_path=root/'config.json'
            config_path.write_text(json.dumps(config,ensure_ascii=False),encoding='utf-8')
            input_path=root/'input.csv'; output_path=root/'output.csv'
            with input_path.open('w',encoding='utf-8',newline='') as target:
                writer=csv.DictWriter(target,fieldnames=['id','name','description','category'])
                writer.writeheader()
                for index in range(20):
                    writer.writerow({'id':str(index),'name':'товар','description':'','category':'БАД'})
            process=subprocess.Popen(
                [sys.executable,str(root/'submission'/'run.py'),'-i',str(input_path),
                 '-o',str(output_path),'--config',str(config_path)],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            )
            try:
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    try:
                        with output_path.open(encoding='utf-8',newline='') as source:
                            if len(list(csv.DictReader(source))) == 20:
                                break
                    except (OSError, csv.Error):
                        pass
                    time.sleep(.02)
                self.assertTrue(output_path.exists(),'initial output was not created')
                process.kill()
                process.wait(timeout=5)
                time.sleep(.1)
            finally:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=5)
            with output_path.open(encoding='utf-8',newline='') as source:
                rows=list(csv.DictReader(source))
            self.assertEqual([row['id'] for row in rows],[str(i) for i in range(20)])
            self.assertTrue(all(is_valid_result(row['result']) for row in rows))
