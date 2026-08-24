from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON_PATH = ROOT / "scripts" / "natural_common.py"
_spec = importlib.util.spec_from_file_location("sre002_natural_common_test", COMMON_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("could not load SRE-002 natural common")
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)


class NaturalStandingEventsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = common.load_json(ROOT / "NATURAL_CASES.json")
        cls.policy = common.load_json(ROOT / "promotion-policy.json")

    def test_registry_is_balanced_and_structurally_valid(self):
        check = common.validate_registry(self.registry)
        self.assertTrue(check["valid"], check["errors"])
        self.assertEqual(check["events"], 8)
        self.assertEqual(check["targets"], 24)
        self.assertEqual(check["gold_reopen"], 12)
        self.assertEqual(check["gold_survive"], 12)
        self.assertEqual(check["event_distribution"], {"CORRECT": 2, "EXPIRE": 2, "REVOKE": 2, "SUPERSEDE": 2})

    def test_every_target_has_disclosed_public_record_gold_basis(self):
        for event in self.registry["events"]:
            decision_ids = {d["id"] for d in event["decisions"]}
            basis_ids = {row["target"] for row in event["gold_basis"]}
            self.assertEqual(decision_ids, basis_ids, event["event_id"])
            self.assertTrue(event["sources"], event["event_id"])
            self.assertTrue(event["source_facts"], event["event_id"])

    def test_gold_partition_tamper_fails_closed(self):
        bad = deepcopy(self.registry)
        bad["events"][0]["gold"]["survive"].remove("D3")
        check = common.validate_registry(bad)
        self.assertFalse(check["valid"])
        self.assertTrue(any("gold does not partition" in err for err in check["errors"]))

    def test_candidate_mechanism_is_frozen_sre001(self):
        self.assertEqual(common.sha256_file(common.FROZEN_SRE001), common.EXPECTED_FROZEN_SRE001_SHA256)
        fixture = common.build_fixture(self.registry)
        for episode in fixture["episodes"]:
            before = common.load_frozen_sre001().StandingOracle(episode, "before").standings()
            self.assertTrue(all(before.values()), episode["event_id"])

    def test_scoring_reads_stored_gold_not_candidate_gold(self):
        fixture = common.build_fixture(self.registry)
        episode = deepcopy(fixture["episodes"][0])
        # Deliberately invert one stored disposition. A predictor that reopens
        # nothing must be scored against the stored public-record gold, not an
        # oracle-derived replacement.
        episode["gold"] = {"reopen": ["D2"], "survive": ["D1", "D3"]}
        def none(_episode):
            return {"system": "NONE", "reopen": [], "replay": [], "analysis_surface": []}
        score = common.score_system([episode], none)
        self.assertEqual(score["fn"], 1)
        self.assertEqual(score["tn"], 2)

    def test_strong_memorepair_baseline_uses_exact_property_validation(self):
        fixture = common.build_fixture(self.registry)
        bmj = next(ep for ep in fixture["episodes"] if ep["event_id"] == "correct-bmj-hemkens-2018")
        memo = common.memorepair_contract_prediction(bmj)
        self.assertEqual(memo["reopen"], ["D1"])
        self.assertEqual(memo["replay"], ["D1", "D2", "D3"])

    def test_runner_is_deterministic(self):
        fixture = common.build_fixture(self.registry)
        first = common.run_benchmark(fixture)
        second = common.run_benchmark(deepcopy(fixture))
        self.assertEqual(first, second)

    def test_promotion_policy_has_clean_falsifier(self):
        self.assertIn("MemoRepair-compatible", self.policy["falsifier"])
        self.assertEqual(self.policy["promotion_requirements"]["additional_missed_reopenings_vs_strongest_baseline_maximum"], 0)
        self.assertEqual(self.policy["promotion_requirements"]["additional_false_reopenings_vs_strongest_baseline_maximum"], 0)


if __name__ == "__main__":
    unittest.main()
