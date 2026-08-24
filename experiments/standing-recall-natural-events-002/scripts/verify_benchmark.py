#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

OPENLINE="OPENLINE_STANDING_PROPAGATION_NATURAL_V1"
DGRR="DGRR_CONTRACT_NODE_SUPPORT_NATURAL_V1"
MEMO="MEMOREPAIR_CONTRACT_PROPERTY_VALIDATION_NATURAL_V1"
ACCEPTED="ACCEPTED"


def canon(v: Any) -> bytes:
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def sha(v: bytes) -> str: return hashlib.sha256(v).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')

def decision_ids(ep): return {d['id'] for d in ep['decisions']}
def source_map(ep): return {x['id']:x for x in ep['evidence']+ep['decisions']}

def edges(ep):
    out=set()
    for d in ep['decisions']:
        for req in d['requires']:
            for b in req['bindings']: out.add((b['source'],d['id']))
        for output in d.get('outputs',{}).values():
            for b in output['bindings']: out.add((b['source'],d['id']))
    return sorted(out)

def descendants(ep, roots):
    ch=defaultdict(set)
    for a,b in edges(ep): ch[a].add(b)
    seen=set(roots); q=deque(roots)
    while q:
        n=q.popleft()
        for c in sorted(ch.get(n,set())):
            if c not in seen: seen.add(c); q.append(c)
    return seen & decision_ids(ep)

def predecessors(ep):
    p=defaultdict(set)
    for a,b in edges(ep): p[b].add(a)
    return p

def topo(ep):
    ids=decision_ids(ep); pred=predecessors(ep); deg={x:0 for x in ids}; ch=defaultdict(set)
    for d in ids:
        for s in pred.get(d,set()):
            if s in ids: deg[d]+=1; ch[s].add(d)
    q=deque(sorted(d for d,v in deg.items() if v==0)); order=[]
    while q:
        n=q.popleft(); order.append(n)
        for c in sorted(ch.get(n,set())):
            deg[c]-=1
            if deg[c]==0:q.append(c)
    if len(order)!=len(ids): raise ValueError('cycle')
    return order

class Oracle:
    def __init__(self,ep,when):
        self.ep=ep; self.when=when; self.src=source_map(ep); self.dec={d['id']:d for d in ep['decisions']}; self.dc={}; self.fc={}; self.active=set()
    def binding(self,b,expected):
        sid=b['source']; facet=b['facet']; exp=b.get('equals',expected); src=self.src[sid]
        if src['kind']=='evidence': return src[self.when]['standing']==ACCEPTED and src[self.when].get('facets',{}).get(facet)==exp
        return self.decision(sid) and self.facet(sid,facet,exp)
    def requirement(self,r): return any(self.binding(b,r['equals']) for b in r['bindings'])
    def decision(self,did):
        if did in self.dc:return self.dc[did]
        key=('d',did,'')
        if key in self.active: raise ValueError('cycle')
        self.active.add(key)
        try:
            v=all(self.requirement(r) for r in self.dec[did]['requires']); self.dc[did]=v; return v
        finally:self.active.remove(key)
    def facet(self,did,facet,expected):
        key=(did,facet,json.dumps(expected,sort_keys=True))
        if key in self.fc:return self.fc[key]
        output=self.dec[did].get('outputs',{}).get(facet)
        if output is None or output.get('value')!=expected: self.fc[key]=False; return False
        active=('f',did,facet)
        if active in self.active: raise ValueError('cycle')
        self.active.add(active)
        try:
            v=any(self.binding(b,expected) for b in output['bindings']); self.fc[key]=v; return v
        finally:self.active.remove(active)
    def standings(self): return {d:self.decision(d) for d in self.dec}

def alive(ep,eid):
    for e in ep['evidence']:
        if e['id']==eid:return e['after']['standing']==ACCEPTED
    raise KeyError(eid)

def pred_dgrr(ep):
    roots=list(ep['event']['roots']); affected=descendants(ep,roots); pred=predecessors(ep); ids=decision_ids(ep); reopened=set()
    for did in topo(ep):
        if did not in affected:continue
        independent=False
        for s in pred.get(did,set()):
            if s in roots or s in affected:continue
            if s in ids or alive(ep,s): independent=True; break
        if not independent: reopened.add(did)
    return {'system':DGRR,'reopen':sorted(reopened),'replay':sorted(reopened),'analysis_surface':sorted(affected),'boundary':'DGRR-style diagnosed-root/node-support contract abstraction; not author code or reported paper results.'}

def pred_memo(ep):
    affected=descendants(ep,list(ep['event']['roots'])); o=Oracle(ep,'after'); reopened=sorted(d for d in affected if not o.decision(d))
    return {'system':MEMO,'reopen':reopened,'replay':sorted(affected),'analysis_surface':sorted(affected),'boundary':'Strong MemoRepair-style barrier-first contract abstraction with exact property-aware validation; not author code, min-cut implementation, or reported paper results.'}

def pred_openline(ep):
    before=Oracle(ep,'before').standings(); after=Oracle(ep,'after').standings()
    if not all(before.values()): raise ValueError('non-standing pre-event target')
    reopen=sorted(d for d in before if before[d] and not after[d]); affected=descendants(ep,list(ep['event']['roots']))
    return {'system':OPENLINE,'reopen':reopen,'replay':reopen,'analysis_surface':sorted(affected),'boundary':'Frozen SRE-001 receiver-owned facet/value standing; no new SRE-002 inference semantics.'}

def score_system(episodes,predictor):
    tp=fp=fn=tn=replay=analysis=0; per=[]
    for ep in episodes:
        g=set(ep['gold']['reopen']); p=predictor(ep); universe=decision_ids(ep); r=set(p['reopen'])
        te=len(g&r); fe=len(r-g); ne=len(g-r); tne=len((universe-g)-r)
        tp+=te;fp+=fe;fn+=ne;tn+=tne;replay+=len(p['replay']);analysis+=len(p['analysis_surface'])
        per.append({'event_id':ep['event_id'],'event_type':ep['event_type'],'gold_reopen':sorted(g),'gold_survive':sorted(ep['gold']['survive']),'predicted_reopen':sorted(r),'replay':sorted(p['replay']),'tp':te,'fp':fe,'fn':ne,'tn':tne})
    return {'system':predictor(episodes[0])['system'],'events':len(episodes),'targets':sum(len(e['decisions']) for e in episodes),'tp':tp,'fp':fp,'fn':fn,'tn':tn,'affected_decision_recall':tp/(tp+fn) if tp+fn else 1.0,'unaffected_state_preservation':tn/(tn+fp) if tn+fp else 1.0,'replay_surface':replay,'analysis_surface':analysis,'per_episode':per}

def recompute_score(fixture):
    systems=[score_system(fixture['episodes'],pred_dgrr),score_system(fixture['episodes'],pred_memo),score_system(fixture['episodes'],pred_openline)]
    return {'schema':'openline.standing-recall-natural-score.v1','experiment':fixture['experiment'],'fixture_sha256':sha(canon(fixture)),'corpus_sha256':fixture['corpus_sha256'],'systems':systems,'policy_authority':'NONE','claim_boundary':['Gold is the frozen public-record disposition mapping, not the OpenLine evaluator\'s output.','DGRR and MemoRepair comparisons are contract abstractions, not author implementations.','The dependency/facet representation was authored retrospectively and can be incomplete or mistaken.']}

def system(score,sid): return next(x for x in score['systems'] if x['system']==sid)
def direct_alt(episodes):
    n=0
    for ep in episodes:
        roots=set(ep['event']['roots']); survive=set(ep['gold']['survive'])
        for d in ep['decisions']:
            if d['id'] not in survive:continue
            mixed=False
            for req in d.get('requires',[]):
                ss={b['source'] for b in req.get('bindings',[])}; mixed |= bool(ss&roots and ss-roots)
            for out in d.get('outputs',{}).values():
                ss={b['source'] for b in out.get('bindings',[])}; mixed |= bool(ss&roots and ss-roots)
            if mixed:n+=1
    return n

def recompute_verdict(fixture,score,policy):
    episodes=fixture['episodes']; o=system(score,OPENLINE); bases=[x for x in score['systems'] if x['system']!=OPENLINE]; counts=Counter(e['event_type'] for e in episodes); gr=sum(len(e['gold']['reopen']) for e in episodes); gs=sum(len(e['gold']['survive']) for e in episodes); alt=direct_alt(episodes); req=policy['promotion_requirements']
    strongest=sorted(bases,key=lambda x:(x['fn']+x['fp'],x['replay_surface'],x['system']))[0]; extra_fn=o['fn']-strongest['fn']; extra_fp=o['fp']-strongest['fp']
    matching=[x for x in bases if (x['tp'],x['fp'],x['fn'],x['tn'])==(o['tp'],o['fp'],o['fn'],o['tn'])]; best=min(matching,key=lambda x:x['replay_surface']) if matching else None; reduction=((best['replay_surface']-o['replay_surface'])/best['replay_surface']) if best and best['replay_surface'] else None
    structural={'minimum_natural_events':len(episodes)>=int(policy['minimum_natural_events']),'minimum_scored_targets':fixture['target_count']>=int(policy['minimum_scored_targets']),'minimum_gold_reopen':gr>=int(policy['minimum_gold_reopen']),'minimum_gold_survive':gs>=int(policy['minimum_gold_survive']),'minimum_direct_alternative_support_survivals':alt>=int(policy['minimum_direct_alternative_support_survivals']),'minimum_per_event_type':all(counts.get(k,0)>=int(policy['minimum_per_event_type']) for k in policy['required_event_types'])}
    accuracy={'openline_recall':o['affected_decision_recall']>=float(req['openline_recall_minimum']),'openline_preservation':o['unaffected_state_preservation']>=float(req['openline_preservation_minimum']),'no_additional_missed_reopenings':extra_fn<=int(req['additional_missed_reopenings_vs_strongest_baseline_maximum']),'no_additional_false_reopenings':extra_fp<=int(req['additional_false_reopenings_vs_strongest_baseline_maximum'])}
    replay_ok=reduction is not None and reduction>=float(req['replay_surface_reduction_vs_best_accuracy_matching_baseline_minimum'])
    if not all(structural.values()): verdict='INCOMPLETE_NATURAL_CORPUS'
    elif not all(accuracy.values()): verdict='NATURAL_STANDING_SELECTIVITY_NOT_EARNED'
    elif best is None or not replay_ok: verdict='NO_NATURAL_REPAIR_SURFACE_SEPARATION'
    else: verdict='NATURAL_STANDING_SELECTIVITY'
    return {'schema':'openline.standing-recall-natural-verdict.v1','experiment':fixture['experiment'],'verdict':verdict,'status':verdict,'natural_event_count':len(episodes),'scored_target_count':fixture['target_count'],'event_distribution':dict(sorted(counts.items())),'gold_distribution':{'REOPEN':gr,'SURVIVE':gs},'direct_alternative_support_survival_targets':alt,'openline':{'affected_decision_recall':o['affected_decision_recall'],'unaffected_state_preservation':o['unaffected_state_preservation'],'replay_surface':o['replay_surface'],'fn':o['fn'],'fp':o['fp']},'strongest_accuracy_baseline':strongest['system'],'best_accuracy_matching_baseline':best['system'] if best else None,'best_accuracy_matching_baseline_replay_surface':best['replay_surface'] if best else None,'replay_surface_reduction_vs_best_accuracy_matching_baseline':reduction,'structural_checks':structural,'accuracy_checks':accuracy,'replay_check':replay_ok,'falsifier_readout':'A strong MemoRepair-style property-aware baseline matched the public-record target dispositions; any surviving OpenLine distinction is limited to repair-surface selectivity.' if best and best['system']==MEMO else "No strong MemoRepair-style baseline matched OpenLine's target-level accuracy; the mechanism boundary remains unresolved without author code.",'claim_boundary':['Eight natural public lifecycle events yield 24 scored target dispositions; the 24 targets are not 24 independent events.','The public records anchor event occurrence and target disposition, while dependency/facet mappings remain retrospective human-authored representations.','The corpus is not blinded, prospective, randomly sampled, or representative of natural event frequency.','DGRR and MemoRepair systems are contract abstractions, not author implementations.','A successful verdict supports selectivity only on this frozen corpus and does not establish truth discovery or rollback of irreversible external effects.'],'policy_authority':'NONE'}

def main():
    p=argparse.ArgumentParser(description='Independent stdlib-only SRE-002 replay')
    p.add_argument('--cases',required=True); p.add_argument('--fixture',required=True); p.add_argument('--score',required=True); p.add_argument('--verdict',required=True); p.add_argument('--promotion-policy',required=True); p.add_argument('--output',required=True); a=p.parse_args()
    cases=load(a.cases); fixture=load(a.fixture); score=load(a.score); verdict=load(a.verdict); policy=load(a.promotion_policy); mism=[]
    if fixture.get('corpus_sha256')!=sha(canon(cases)): mism.append('fixture corpus hash mismatch')
    rs=recompute_score(fixture); rv=recompute_verdict(fixture,rs,policy)
    if rs!=score:mism.append('score mismatch')
    if rv!=verdict:mism.append('verdict mismatch')
    expected_types=Counter(e['event_type'] for e in fixture['episodes'])
    if set(expected_types)!={'CORRECT','REVOKE','SUPERSEDE','EXPIRE'}:mism.append('event family mismatch')
    out={'schema':'openline.standing-recall-natural-independent-verification.v1','experiment':'standing-recall-natural-events-002','verified':not mism,'mismatch_count':len(mism),'mismatches':mism,'corpus_sha256':fixture.get('corpus_sha256'),'fixture_sha256':sha(canon(fixture)),'score_sha256':sha(canon(score)),'verdict':verdict.get('verdict'),'policy_authority':'NONE'}
    write(a.output,out); print(json.dumps(out,indent=2,sort_keys=True)); return 0 if not mism else 2
if __name__=='__main__': raise SystemExit(main())
