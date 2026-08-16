from __future__ import annotations

import copy
import unittest

from openline_claim_graph import validate_snapshot
from scripts.run_arct_development_check import build_mapping_graph, build_report, load_check_inputs


class ArctDevelopmentCheckTest(unittest.TestCase):
    def test_frozen_blind_mapping_result_and_controls(self) -> None:
        report = build_report()
        self.assertEqual("EXPLORATORY_INDEPENDENT_GOLD_POSITIVE_CONTROL", report["status"])
        self.assertEqual(21, report["checks"]["blind_mapping_hits"])
        self.assertEqual(24, report["checks"]["blind_mapping_total"])
        self.assertEqual(24, report["checks"]["gold_oracle_hits"])
        self.assertEqual(0, report["checks"]["inverted_control_hits"])
        self.assertEqual(72, report["checks"]["mechanically_valid_graphs"])
        self.assertEqual(24, report["checks"]["gold_vs_inverted_roots_distinct"])

    def test_case_gold_and_prediction_identifiers_match(self) -> None:
        _document, cases, gold, predictions = load_check_inputs()
        ids = {case["case_id"] for case in cases}
        self.assertEqual(24, len(ids))
        self.assertEqual(ids, set(gold))
        self.assertEqual(ids, set(predictions))

    def test_selected_warrant_changes_committed_state(self) -> None:
        _document, cases, _gold, _predictions = load_check_inputs()
        for case in cases:
            left, left_sources = build_mapping_graph(case, 0)
            right, right_sources = build_mapping_graph(case, 1)
            with self.subTest(case_id=case["case_id"]):
                self.assertNotEqual(left["state_root"], right["state_root"])
                self.assertTrue(validate_snapshot(left, left_sources, parent_snapshots=[])["valid"])
                self.assertTrue(validate_snapshot(right, right_sources, parent_snapshots=[])["valid"])

    def test_source_tamper_still_fails_on_real_benchmark_text(self) -> None:
        _document, cases, _gold, predictions = load_check_inputs()
        case = cases[0]
        snapshot, sources = build_mapping_graph(case, predictions[case["case_id"]])
        tampered = copy.deepcopy(sources)
        first_id = sorted(tampered)[0]
        tampered[first_id]["content"] += " silently changed"
        result = validate_snapshot(snapshot, tampered, parent_snapshots=[])
        self.assertFalse(result["valid"])
        self.assertTrue(any("source_hash_mismatch" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
