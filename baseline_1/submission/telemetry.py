from __future__ import annotations
from collections import Counter,defaultdict
import json,sys
class Telemetry:
    def __init__(self): self.counts=Counter(); self.timings=defaultdict(float); self.extra={}
    def count(self,key,value=1): self.counts[key]+=value
    def timing(self,key,value_ms): self.timings[key]+=float(value_ms)
    def set(self,key,value): self.extra[key]=value
    def summary(self): return {"counts":dict(self.counts),"timings_ms":{k:round(v,3) for k,v in self.timings.items()},**self.extra}
    def dump(self): print(json.dumps({"run_summary":self.summary()},ensure_ascii=False,separators=(",",":")),file=sys.stderr,flush=True)
