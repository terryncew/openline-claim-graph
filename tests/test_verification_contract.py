from __future__ import annotations
import copy, unittest
from openline_claim_graph.canonical import content_id
from openline_claim_graph.decision_recall import _decision_recall_disposition
from openline_claim_graph.verification_contract import VERIFICATION_ADMISSION_SCHEMA, VerificationContractError, create_receiver_admission, create_verification_contract, create_verification_result, decision_recall_binding, evaluate_verification_contract, validate_receiver_admission, validate_verification_contract, validate_verification_result

class VerificationContractTests(unittest.TestCase):
    def setUp(self):
        self.accepted_at="2026-09-05T02:00:00Z"
        self.contract=create_verification_contract(dependency_id="verification-contract:planning-policy-registry:trd-non-mdd-cost-use",subject_id="planning-policy-registry:trd-non-mdd-cost-use",required_value="ELIGIBLE",recognized_verifier_id="receiver:planning-policy-registry-verifier:v1",freshness_seconds=3600)
        b=decision_recall_binding(self.contract)
        self.target={"basis":[{"basis_id":"recorded:plos:cost","role":"REQUIRED"},b["basis"]],"assumptions":[],"required_dependencies":["recorded:plos:cost",b["required_dependency"]],"alternative_support":[],"invalidation_conditions":[{"condition_id":"loss-recorded-cost","dependency_id":"recorded:plos:cost","event_types":["LOSS_OF_STANDING"]},b["invalidation_condition"]]}
        self.control={"basis":[{"basis_id":"recorded:plos:denominator","role":"REQUIRED"}],"assumptions":[],"required_dependencies":["recorded:plos:denominator"],"alternative_support":[],"invalidation_conditions":[{"condition_id":"loss-denominator","dependency_id":"recorded:plos:denominator","event_types":["LOSS_OF_STANDING"]}]}
    def result(self,*,value="WITHDRAWN",observed_at="2026-09-05T02:20:00Z",verifier="receiver:planning-policy-registry-verifier:v1",evidence="55"*32):
        return create_verification_result(contract=self.contract,verifier_id=verifier,observed_value=value,observed_at=observed_at,evidence_sha256=evidence,locator="registry://planning-policy/trd-non-mdd")
    def admit(self,result,admitted_at="2026-09-05T02:20:05Z"):
        return create_receiver_admission(contract=self.contract,result=result,receiver_id="receiver:openline:test",admitted_at=admitted_at)
    def evaluate(self,result=None,admission=None,at="2026-09-05T02:30:00Z"):
        return evaluate_verification_contract(contract=self.contract,accepted_at=self.accepted_at,evaluation_at=at,result=result,admission=admission)
    def test_contract_is_content_addressed_and_bindable(self):
        self.assertTrue(validate_verification_contract(self.contract)["valid"]); self.assertEqual(decision_recall_binding(self.contract)["basis"]["role"],"REQUIRED")
    def test_within_budget_without_result_survives(self): self.assertEqual(self.evaluate()["disposition"],"SURVIVE")
    def test_overdue_missing_result_escalates(self): self.assertEqual(self.evaluate(at="2026-09-05T03:00:01Z")["disposition"],"ESCALATE")
    def test_result_cannot_self_authorize(self):
        hostile=copy.deepcopy(self.result()); hostile["receiver_admitted"]=True; body=dict(hostile); body.pop("verification_result_id"); hostile["verification_result_id"]=content_id("verification-result",body)
        self.assertFalse(validate_verification_result(hostile,self.contract)["valid"]); self.assertEqual(self.evaluate(result=hostile)["disposition"],"ESCALATE")
    def test_recognized_result_needs_separate_admission(self): self.assertEqual(self.evaluate(result=self.result())["disposition"],"ESCALATE")
    def test_unrecognized_verifier_fails_closed(self):
        result=self.result(verifier="foreign:untrusted-verifier:v1"); body={"schema":VERIFICATION_ADMISSION_SCHEMA,"contract_id":self.contract["contract_id"],"verification_result_id":result["verification_result_id"],"receiver_id":"receiver:openline:test","admitted_at":"2026-09-05T02:20:05Z"}; forged={"admission_id":content_id("verification-admission",body),**body}
        self.assertEqual(self.evaluate(result=result,admission=forged)["disposition"],"ESCALATE")
        with self.assertRaises(VerificationContractError): self.admit(result)
    def test_stale_admitted_result_escalates(self):
        result=self.result(observed_at="2026-09-05T00:00:00Z"); self.assertEqual(self.evaluate(result=result,admission=self.admit(result))["disposition"],"ESCALATE")
    def test_pre_acceptance_replay_escalates(self):
        result=self.result(observed_at="2026-09-05T01:59:59Z"); self.assertEqual(self.evaluate(result=result,admission=self.admit(result,"2026-09-05T02:00:01Z"))["disposition"],"ESCALATE")
    def test_admission_cannot_replay_across_results(self):
        passing=self.result(value="ELIGIBLE",evidence="44"*32); failing=self.result(value="WITHDRAWN",evidence="55"*32); admission=self.admit(passing)
        self.assertFalse(validate_receiver_admission(admission,contract=self.contract,result=failing)["valid"]); self.assertEqual(self.evaluate(result=failing,admission=admission)["disposition"],"ESCALATE")
    def test_admission_after_evaluation_boundary_escalates(self):
        result=self.result(); self.assertEqual(self.evaluate(result=result,admission=self.admit(result,"2026-09-05T02:40:00Z"))["disposition"],"ESCALATE")
    def test_fresh_admitted_pass_survives(self):
        result=self.result(value="ELIGIBLE",evidence="44"*32); self.assertEqual(self.evaluate(result=result,admission=self.admit(result))["disposition"],"SURVIVE")
    def test_fresh_admitted_failure_emits_loss_of_standing(self):
        result=self.result(); ev=self.evaluate(result=result,admission=self.admit(result)); self.assertEqual(ev["disposition"],"EVENT"); self.assertEqual(ev["event"],{"basis_id":self.contract["dependency_id"],"event_type":"LOSS_OF_STANDING"})
    def test_event_reopens_exact_target_and_preserves_control(self):
        result=self.result(); event=self.evaluate(result=result,admission=self.admit(result))["event"]; target,_,_=_decision_recall_disposition(self.target,event); control,_,_=_decision_recall_disposition(self.control,event); self.assertEqual(target,"REOPEN"); self.assertEqual(control,"SURVIVE")
if __name__=="__main__": unittest.main()
