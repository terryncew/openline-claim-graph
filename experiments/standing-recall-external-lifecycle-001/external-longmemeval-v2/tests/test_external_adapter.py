from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURE = ROOT / "tests" / "fixtures" / "schema_fixture.jsonl"

spec = importlib.util.spec_from_file_location("external_common", SCRIPTS / "external_common.py")
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ExternalAdapterTests(unittest.TestCase):
    def setUp(self):
        self.rows = m.read_jsonl(FIXTURE)
        self.pins = m.load_json(ROOT / "SOURCE_PINS.json")
        self.policy = m.load_json(ROOT / "ADAPTER_POLICY.json")

    def test_selection_is_structural_and_deterministic(self):
        selected = m.select_trajectories(list(reversed(self.rows)), 10)
        self.assertEqual([row["id"] for row in selected], [f"t{i:02d}" for i in range(10)])

    def test_builds_exact_frozen_event_distribution(self):
        adaptation = m.build_adaptation(self.rows, self.pins, self.policy)
        self.assertEqual(adaptation["episode_count"], 40)
        self.assertEqual(adaptation["event_distribution"], {event: 10 for event in m.EVENT_TYPES})
        self.assertEqual(len(set(adaptation["selected_trajectory_ids"])), 5)
        self.assertEqual(adaptation["selected_anchor_count"], 10)

    def test_centerpiece_gold_is_property_specific(self):
        adaptation = m.build_adaptation(self.rows, self.pins, self.policy)
        frozen = m._load_frozen_standing_module()
        for episode in adaptation["episodes"]:
            gold = frozen.gold_from_episode(episode)
            self.assertEqual(gold["reopen"], ["D2"])
            self.assertEqual(gold["survive"], ["D1", "D3", "D4"])

    def test_strong_memorepair_matches_accuracy_but_replays_more(self):
        adaptation = m.build_adaptation(self.rows, self.pins, self.policy)
        score = m.run_external_benchmark(adaptation)
        systems = {item["system"]: item for item in score["systems"]}
        ol = systems["OPENLINE_STANDING_PROPAGATION_EXTERNAL_V1"]
        mr = systems["MEMOREPAIR_CONTRACT_PROPERTY_VALIDATION_EXTERNAL_V1"]
        self.assertEqual((ol["tp"], ol["fp"], ol["fn"], ol["tn"]), (mr["tp"], mr["fp"], mr["fn"], mr["tn"]))
        self.assertLess(ol["replay_surface"], mr["replay_surface"])

    def test_dgrr_contract_preserves_root_decision_but_over_recalls_downstream(self):
        adaptation = m.build_adaptation(self.rows, self.pins, self.policy)
        pred = m.dgrr_contract_prediction(adaptation["episodes"][0])
        self.assertEqual(pred["reopen"], ["D2", "D3"])

    def test_manifest_binds_source_and_adaptation(self):
        adaptation = m.build_adaptation(self.rows, self.pins, self.policy)
        manifest = m.adaptation_manifest(adaptation, FIXTURE, self.pins)
        self.assertEqual(manifest["mapping_count"], 40)
        self.assertEqual(manifest["adaptation_sha256"], m.sha256_bytes(m.canonical_bytes(adaptation)))
        self.assertEqual(manifest["source_file_sha256"], m.sha256_file(FIXTURE))

    def test_external_gate_passes_only_on_expected_mechanics(self):
        adaptation = m.build_adaptation(self.rows, self.pins, self.policy)
        score = m.run_external_benchmark(adaptation)
        promotion = m.load_json(ROOT.parent / "promotion-policy.json")
        verdict = m.grade_external(adaptation, score, promotion)
        self.assertEqual(verdict["verdict"], "EXTERNAL_STANDING_SEPARATION_ADAPTED_LONGMEMEVAL_V2")
        self.assertEqual(verdict["openline"]["affected_decision_recall"], 1.0)
        self.assertEqual(verdict["openline"]["unaffected_state_preservation"], 1.0)
        self.assertAlmostEqual(verdict["replay_surface_reduction_vs_best_accuracy_matching_baseline"], 2 / 3)

    def test_insufficient_external_rows_fail_closed(self):
        with self.assertRaises(ValueError):
            m.build_adaptation(self.rows[:4], self.pins, self.policy)


if __name__ == "__main__":
    unittest.main()
