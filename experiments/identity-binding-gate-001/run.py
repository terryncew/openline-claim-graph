from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from identity_binding_gate import BindingEvidence, BindingPolicy, BindingProposal, IdentityBindingGate
POLICY=BindingPolicy(policy_id="PARSER-PROVENANCE-COLD-001-successor-v1",min_independent_matches=2,required_attributes=("name",),hard_conflict_attributes=("birth_date","parent","unique_id"),authoritative_attributes=("unique_id",))
def run():
    gate=IdentityBindingGate(POLICY)
    wrong=gate.evaluate(BindingProposal("parser-negative-control","person:princess-elene-of-georgia","person:similarly-named-elena",(BindingEvidence("name","Elene","Elene","synthetic://parser-provenance/misleading"),)))
    right=gate.evaluate(BindingProposal("parser-corroborated-control","person:princess-elene-of-georgia","person:princess-elene-of-georgia",(BindingEvidence("name","Princess Elene of Georgia","Princess Elene of Georgia","synthetic://parser-provenance/correct"),BindingEvidence("family_context","daughter of Heraclius II","daughter of Heraclius II","synthetic://parser-provenance/identity"))))
    verdict="IDENTITY_ADMISSION_BARRIER_HELD" if wrong["disposition"]!="COMMIT" and right["disposition"]=="COMMIT" else "IDENTITY_ADMISSION_BARRIER_FAILED"
    return {"schema":"openline.identity-binding-gate-001.result.v1","experiment":"IDENTITY-BINDING-GATE-001","predecessor_negative_result":"PROVENANCE_BARRIER_HELD_IDENTITY_SEMANTICS_UNEARNED","misleading_same_name":wrong,"corroborated_identity":right,"verdict":verdict,"earned_claim":"No identity mapping enters accepted state merely because its provenance is exact; it must also satisfy receiver-owned identity-binding rules.","nonclaims":["not proof of real-world identity truth","not a universal entity resolver","not a model-based semantic oracle"]}
if __name__=="__main__":
    r=run(); print(json.dumps(r,sort_keys=True,indent=2)); raise SystemExit(0 if r["verdict"]=="IDENTITY_ADMISSION_BARRIER_HELD" else 1)
