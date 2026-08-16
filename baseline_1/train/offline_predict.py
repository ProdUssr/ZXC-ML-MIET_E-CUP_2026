"""Offline parity runner: uses the shipped Router and predictor implementations."""
from __future__ import annotations
import argparse,csv,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from submission.contracts import Budget,RuntimeContext
from submission.io_utils import read_items
from submission.predictors import REGISTRY
from submission.router import Router
from submission.settings import load_settings
from submission.telemetry import Telemetry

def main():
    p=argparse.ArgumentParser(); p.add_argument('-i',required=True); p.add_argument('-o',required=True); p.add_argument('--config',default=str(ROOT/'submission'/'config.json')); args=p.parse_args()
    settings=load_settings(args.config); items=read_items(args.i); telemetry=Telemetry(); router=Router(settings.stages,REGISTRY); router.load(RuntimeContext(ROOT/'submission',settings,telemetry)); budget=Budget('L0',10**9,0,0,False,True)
    predictions=[]
    try:
        for start in range(0,len(items),settings.batch_size): predictions.extend(router.run(items[start:start+settings.batch_size],budget))
    finally: router.close()
    by_index={prediction.row_index:prediction for prediction in predictions}
    with open(args.i,encoding='utf-8-sig',errors='replace',newline='') as source: raw=list(csv.DictReader(source))
    with open(args.o,'w',encoding='utf-8',newline='') as target:
        writer=csv.DictWriter(target,fieldnames=['row_index','id','category','label','p_regulated']); writer.writeheader()
        for item,row in zip(items,raw): writer.writerow({'row_index':item.row_index,'id':item.id,'category':item.category,'label':row.get('label',''),'p_regulated':by_index[item.row_index].p_regulated})

if __name__=='__main__': main()
