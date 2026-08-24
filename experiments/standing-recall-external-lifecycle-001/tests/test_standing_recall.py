from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SCRIPTS = HERE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_fixture import build_fixture
from standing_recall import (
    StandingOracle,
    dgrr_style_prediction,
    gold_from_episode,
    memorepair_style_prediction,
    openline_prediction,
    run_benchmark,
)


class StandingRecallTests(unittest.TestCase):
    def setUp(self):
        self.fixture = build_fixture()

    def test_fixture_has_all_four_lifecycle_events(self):
        counts = {}
        for ep in self.fixture["episodes"]:
            counts[ep["event"]["type"]] = counts.get(ep["event"]["type"], 0) + 1
        self.assertEqual(
            counts,
            {"EXPIRE": 16, "REVOKE": 16, "SUPERSEDE": 16, "CORRECT": 16},
        )

    def test_every_scored_decision_stood_before_event(self):
        for ep in self.fixture["episodes"]:
            before = StandingOracle(ep, "before").standings()
            self.assertTrue(all(before.values()), ep["episode_id"])

    def test_centerpiece_partial_facet_case(self):
        ep = next(
            ep for ep in self.fixture["episodes"]
            if ep["event"]["type"] == "REVOKE"
            and ep["pattern"] == "partial_facet"
            and ep["variant"] == 3
        )
        gold = gold_from_episode(ep)
        self.assertEqual(gold["reopen"], ["D2"])
        self.assertEqual(gold["survive"], ["D1", "D3"])
        self.assertEqual(openline_prediction(ep)["reopen"], ["D2"])
        self.assertEqual(dgrr_style_prediction(ep)["reopen"], [])
        self.assertEqual(memorepair_style_prediction(ep)["reopen"], [])

    def test_unrelated_facet_does_not_force_reopen(self):
        ep = next(
            ep for ep in self.fixture["episodes"]
            if ep["pattern"] == "irrelevant_facet" and ep["variant"] == 2
        )
        self.assertEqual(gold_from_episode(ep)["reopen"], [])
        self.assertEqual(openline_prediction(ep)["reopen"], [])

    def test_conformance_score_is_mechanics_only(self):
        score = run_benchmark(self.fixture)
        self.assertEqual(score["status"], "MECHANICS_ONLY_EXTERNAL_BENCHMARK_UNRUN")
        systems = {item["system"]: item for item in score["systems"]}
        openline = systems["OPENLINE_STANDING_PROPAGATION_V1"]
        self.assertEqual(openline["affected_decision_recall"], 1.0)
        self.assertEqual(openline["unaffected_state_preservation"], 1.0)
        self.assertGreater(
            systems["DGRR_STYLE_NODE_SUPPORT_V1"]["fn"], 0
        )
        self.assertGreater(
            systems["MEMOREPAIR_STYLE_CASCADE_V1"]["fn"], 0
        )

    def test_memorepair_barrier_has_larger_replay_surface(self):
        score = run_benchmark(self.fixture)
        systems = {item["system"]: item for item in score["systems"]}
        self.assertGreater(
            systems["MEMOREPAIR_STYLE_CASCADE_V1"]["replay_surface"],
            systems["OPENLINE_STANDING_PROPAGATION_V1"]["replay_surface"],
        )


if __name__ == "__main__":
    unittest.main()
