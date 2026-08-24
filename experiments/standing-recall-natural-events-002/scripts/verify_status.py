#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT_SRE001=ROOT.parent/'standing-recall-external-lifecycle-001'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description='Verify frozen SRE-002 natural-event instrument hashes')
    p.add_argument('--root',default=str(ROOT)); a=p.parse_args(); root=Path(a.root).resolve()
    status=json.loads((root/'STATUS.json').read_text(encoding='utf-8')); mismatches=[]
    for rel,expected in sorted(status['frozen_instrument_sha256'].items()):
        path=root/rel; observed=sha(path) if path.exists() else 'MISSING'
        if observed!=expected:mismatches.append({'path':rel,'expected':expected,'observed':observed})
    parent=root.parent/'standing-recall-external-lifecycle-001'
    for rel,expected in sorted(status.get('parent_frozen_sha256',{}).items()):
        path=parent/rel; observed=sha(path) if path.exists() else 'MISSING'
        if observed!=expected:mismatches.append({'path':f'parent/{rel}','expected':expected,'observed':observed})
    out={'valid':not mismatches,'status':status['status'],'external_run':False,'mismatches':mismatches}
    print(json.dumps(out,indent=2,sort_keys=True)); return 0 if not mismatches else 2
if __name__=='__main__': raise SystemExit(main())
