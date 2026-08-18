from __future__ import annotations
import csv,os,subprocess,sys,tempfile,unittest
from pathlib import Path

class ExitTests(unittest.TestCase):
    def test_unused_image_special_file_cannot_block_rules_run(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'images'/'1').mkdir(parents=True); special=root/'images'/'1'/'blocked.jpg'
            if hasattr(os,'mkfifo') and os.name!='nt': os.mkfifo(special)
            else: special.write_bytes(b'')
            inp=root/'test.csv'; out=root/'out.csv'
            with inp.open('w',encoding='utf-8',newline='') as f: w=csv.DictWriter(f,fieldnames=['id','name','description','category']); w.writeheader(); w.writerow({'id':'1','name':'товар','description':'','category':'БАД'})
            completed=subprocess.run([sys.executable,'submission/run.py','-i',str(inp),'-o',str(out)],timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.assertEqual(completed.returncode,0); self.assertTrue(out.exists())
