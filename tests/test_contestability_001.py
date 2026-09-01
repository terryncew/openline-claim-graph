from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "contestability-001"
SCRIPTS = EXP / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "contestability", SCRIPTS / "contestability.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load contestability module")
contestability = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contestability)

runner_spec = importlib.util.spec_from_file_location(
    "contestability_runner", SCRIPTS / "run_contestability.py"
)
if runner_spec is None or runner_spec.loader is None:
    raise RuntimeError("could not load contestability runner")
runner = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner)


class Contestability001Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = contestability.load_json(EXP / "fixtures" / "scenario.json")
        cls.foreign = contestability.load_json(
            EXP / "fixtures" / "foreign-verifier-result.json"
        )
        cls.profile = contestability.load_json(EXP / "adapter-profile.json")
        cls.policy = contestability.load_json(EXP / "receiver-policy.json")

    def test_filing_is_ingest_only(self):
        event = contestability.normalize_foreign(self.foreign, self.profile)
        s = contestability.stages(event, None, None)
        self.assertTrue(s["authenticated_filing_trigger"]["observed"])
        self.assertEqual(s["receiver_acceptance"], "NOT_EVALUATED")
        self.assertEqual(s["local_application"], "NOT_APPLIED")

    def test_declared_effect_and_executor_acceptance_do_not_self_apply(self):
        foreign = copy.deepcopy(self.foreign)
        foreign["effect"]["authenticated_trigger"]["valid"] = False
        event = contestability.normalize_foreign(foreign, self.profile)
        decision = contestability.evaluate_receiver(event, self.policy, self.graph)
        application = contestability.apply_receiver_decision(
            self.graph, decision, self.policy
        )
        self.assertTrue(event["stages"]["issuer_declared_effect"]["observed"])
        self.assertTrue(event["executor_acceptance"])
        self.assertFalse(decision["accepted"])
        self.assertEqual(application["reopened"], [])
        self.assertEqual(
            application["state_before_sha256"], application["state_after_sha256"]
        )

    def test_foreign_application_claim_is_not_local_authority(self):
        foreign = copy.deepcopy(self.foreign)
        foreign["effect"]["application_record"]["valid"] = True
        foreign["contestability"]["forum"]["id"] = "forum:unaccepted"
        event = contestability.normalize_foreign(foreign, self.profile)
        decision = contestability.evaluate_receiver(event, self.policy, self.graph)
        application = contestability.apply_receiver_decision(
            self.graph, decision, self.policy
        )
        self.assertTrue(event["foreign_application"])
        self.assertFalse(decision["accepted"])
        self.assertFalse(application["applied"])
        self.assertEqual(application["reopened"], [])

    def test_valid_event_needs_separate_receiver_acceptance_then_application(self):
        event = contestability.normalize_foreign(self.foreign, self.profile)
        self.assertEqual(
            contestability.stages(event, None, None)["receiver_acceptance"],
            "NOT_EVALUATED",
        )
        decision = contestability.evaluate_receiver(event, self.policy, self.graph)
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["application_state"], "NOT_APPLIED")
        application = contestability.apply_receiver_decision(
            self.graph, decision, self.policy
        )
        self.assertTrue(application["applied"])

    def test_selective_reopen_is_exact_and_preserves_execution_history(self):
        event = contestability.normalize_foreign(self.foreign, self.profile)
        decision = contestability.evaluate_receiver(event, self.policy, self.graph)
        application = contestability.apply_receiver_decision(
            self.graph, decision, self.policy
        )
        self.assertEqual(
            sorted(application["reopened"]),
            sorted(self.graph["expected_reopen"]),
        )
        nodes = {row["id"]: row for row in application["state"]["nodes"]}
        self.assertEqual(nodes["action-A"]["status"], "EXECUTED")
        self.assertEqual(nodes["consequence-B-benefit"]["status"], "CLOSED")
        self.assertEqual(nodes["auth-B"]["status"], "VALID")

    def test_wrong_forum_is_locally_rejected_even_with_authenticated_filing(self):
        foreign = copy.deepcopy(self.foreign)
        foreign["contestability"]["forum"]["id"] = "forum:other"
        event = contestability.normalize_foreign(foreign, self.profile)
        self.assertTrue(event["filing_authenticated"])
        decision = contestability.evaluate_receiver(event, self.policy, self.graph)
        self.assertFalse(decision["accepted"])

    def test_foreign_layout_is_replaceable_by_profile_only(self):
        alternate, alt_profile = runner._alternate_projection(
            self.foreign, self.profile
        )
        original = contestability.normalize_foreign(self.foreign, self.profile)
        alt = contestability.normalize_foreign(alternate, alt_profile)
        self.assertEqual(
            runner._neutral_semantics(original),
            runner._neutral_semantics(alt),
        )
        original_decision = contestability.evaluate_receiver(
            original, self.policy, self.graph
        )
        alt_decision = contestability.evaluate_receiver(
            alt, self.policy, self.graph
        )
        self.assertEqual(
            original_decision["disposition"], alt_decision["disposition"]
        )

    def test_unknown_authorization_fails_receiver_acceptance(self):
        foreign = copy.deepcopy(self.foreign)
        foreign["authorization"]["id"] = "auth-missing"
        event = contestability.normalize_foreign(foreign, self.profile)
        decision = contestability.evaluate_receiver(event, self.policy, self.graph)
        self.assertFalse(decision["accepted"])

    def test_full_five_arm_result_passes(self):
        result = runner.run_experiment()
        self.assertEqual(result["verdict"], "PASS")
        self.assertTrue(all(result["assertions"].values()))
        self.assertEqual(result["production_core_files_changed"], [])


if __name__ == "__main__":
    unittest.main()
