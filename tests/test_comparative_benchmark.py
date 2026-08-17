from __future__ import annotations

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from openline_claim_graph.comparative_benchmark import (
    ComparativeBenchmarkError,
    SYSTEM_DIRECT,
    SYSTEM_EVIDENCE_RECALL,
    SYSTEM_NAIVE,
    build_published_diagnostic,
    create_authority,
    create_case,
    create_gold,
    create_pack,
    import_schneider_csv,
    import_van_der_vet_dot,
    parse_dot_edges,
    run_comparative,
    score_comparative,
    validate_gold,
    validate_pack,
    verify_predictions,
    verify_published_diagnostic,
    verify_score,
)


def make_pack():
    root = "root"
    direct = "direct"
    indirect = "indirect"
    clean = "clean"
    alt = "alt"

    edge_root_direct = {
        "prerequisite_node_id": root,
        "dependent_node_id": direct,
        "relation": "DERIVED_FROM",
        "evidence": ["direct citation"],
    }
    edge_direct_indirect = {
        "prerequisite_node_id": direct,
        "dependent_node_id": indirect,
        "relation": "DEPENDS_ON",
        "evidence": ["indirect citation"],
    }
    edge_direct_clean = {
        "prerequisite_node_id": direct,
        "dependent_node_id": clean,
        "relation": "DEPENDS_ON",
        "evidence": ["indirect citation"],
    }
    edge_root_alt = {
        "prerequisite_node_id": root,
        "dependent_node_id": alt,
        "relation": "SUPPORTS",
        "evidence": ["one support path"],
    }
    edge_backup_alt = {
        "prerequisite_node_id": "backup",
        "dependent_node_id": alt,
        "relation": "SUPPORTS",
        "evidence": ["independent support"],
    }
    nodes = [
        {"node_id": root, "label": "retracted root", "text": "retracted root"},
        {"node_id": direct, "label": "direct", "text": "direct"},
        {"node_id": indirect, "label": "indirect", "text": "indirect"},
        {"node_id": clean, "label": "clean", "text": "clean"},
        {"node_id": alt, "label": "alternative", "text": "alternative"},
        {"node_id": "backup", "label": "backup", "text": "backup", "independent_basis": True},
    ]
    cases = [
        create_case(
            stratum="TEST",
            invalidated_node_id=root,
            target_node_id=direct,
            nodes=nodes,
            edges=[edge_root_direct],
        ),
        create_case(
            stratum="TEST",
            invalidated_node_id=root,
            target_node_id=indirect,
            nodes=nodes,
            edges=[edge_root_direct, edge_direct_indirect],
        ),
        create_case(
            stratum="TEST",
            invalidated_node_id=root,
            target_node_id=clean,
            nodes=nodes,
            edges=[edge_root_direct, edge_direct_clean],
        ),
        create_case(
            stratum="TEST",
            invalidated_node_id=root,
            target_node_id=alt,
            nodes=nodes,
            edges=[edge_root_alt, edge_backup_alt],
        ),
    ]
    pack = create_pack(
        benchmark_id="fixture",
        cases=cases,
        source_manifest=[{"role": "fixture", "identifier": "local"}],
        construction_rule="test rule",
    )
    # Recover content-addressed edge IDs from the cases.  Make root->direct hard,
    # indirect paths advisory, and both alternative support paths hard.
    authority_map = {}
    for case in cases:
        for edge in case["edges"]:
            evidence = set(edge["evidence"])
            if "indirect citation" in evidence:
                authority_map[edge["edge_id"]] = "ADVISORY"
            else:
                authority_map[edge["edge_id"]] = "HARD"
    authority = create_authority(
        pack,
        edge_authority=authority_map,
        declared_by="test",
        construction_rule="fixed without gold",
    )
    labels = {
        cases[0]["case_id"]: "EXPOSED",
        cases[1]["case_id"]: "EXPOSED",
        cases[2]["case_id"]: "NO_EXPOSURE",
        cases[3]["case_id"]: "NO_EXPOSURE",
    }
    gold = create_gold(pack, labels, source="fixture gold", label_definition="fixture")
    return pack, authority, gold, cases


class ComparativeBenchmarkTests(unittest.TestCase):
    def test_three_systems_preserve_declared_difference(self):
        pack, authority, _gold, cases = make_pack()
        predictions = run_comparative(pack, authority)
        by_case = {row["case_id"]: row["predictions"] for row in predictions["rows"]}
        self.assertEqual("QUARANTINE", by_case[cases[0]["case_id"]][SYSTEM_DIRECT])
        self.assertEqual("UNAFFECTED", by_case[cases[1]["case_id"]][SYSTEM_DIRECT])
        self.assertEqual("QUARANTINE", by_case[cases[1]["case_id"]][SYSTEM_NAIVE])
        self.assertEqual(
            "AFFECTED_UNRESOLVED", by_case[cases[1]["case_id"]][SYSTEM_EVIDENCE_RECALL]
        )
        self.assertEqual("QUARANTINE", by_case[cases[3]["case_id"]][SYSTEM_NAIVE])
        self.assertEqual("SURVIVES", by_case[cases[3]["case_id"]][SYSTEM_EVIDENCE_RECALL])
        self.assertTrue(verify_predictions(predictions, pack, authority)["valid"])

    def test_score_exposes_fn_fp_and_review_burden_without_composite(self):
        pack, authority, gold, _cases = make_pack()
        predictions = run_comparative(pack, authority)
        score = score_comparative(pack, authority, gold, predictions)
        overall = score["metrics"]["ALL"]
        self.assertEqual(1, overall[SYSTEM_DIRECT]["missed_exposure"])
        self.assertEqual(2, overall[SYSTEM_NAIVE]["hard_false_quarantine"])
        self.assertEqual(1, overall[SYSTEM_EVIDENCE_RECALL]["unnecessary_unresolved_review"])
        self.assertEqual(3, overall[SYSTEM_EVIDENCE_RECALL]["total_review_load"])
        self.assertNotIn("composite", score)
        self.assertTrue(verify_score(score, pack, authority, gold, predictions)["valid"])

    def test_gold_is_bound_to_exact_public_pack(self):
        pack, authority, gold, _cases = make_pack()
        changed = copy.deepcopy(pack)
        changed["construction_rule"] = "changed"
        # Re-content-address the changed pack so the failure is the gold binding,
        # not merely a stale public pack ID.
        from openline_claim_graph.canonical import content_id

        changed["pack_id"] = content_id(
            "evidence-recall-comparative-pack",
            {k: v for k, v in changed.items() if k != "pack_id"},
        )
        check = validate_gold(gold, changed)
        self.assertFalse(check["valid"])
        self.assertIn("gold_pack_mismatch", check["errors"])

    def test_public_pack_rejects_answer_bearing_metadata(self):
        pack, _authority, _gold, _cases = make_pack()
        corrupted = copy.deepcopy(pack)
        corrupted["cases"][0]["metadata"]["possible misinformation"] = "Y"
        from openline_claim_graph.canonical import content_id

        case = corrupted["cases"][0]
        case["case_id"] = content_id("comparative-case", {k: v for k, v in case.items() if k != "case_id"})
        corrupted["cases"].sort(key=lambda item: item["case_id"])
        corrupted["pack_id"] = content_id(
            "evidence-recall-comparative-pack",
            {k: v for k, v in corrupted.items() if k != "pack_id"},
        )
        check = validate_pack(corrupted)
        self.assertFalse(check["valid"])
        self.assertTrue(any(item.startswith("reserved_public_key:") for item in check["errors"]))

    def test_unassessed_gold_is_excluded_from_scoring(self):
        pack, authority, gold, cases = make_pack()
        labels = {item["case_id"]: "UNASSESSED" for item in cases}
        gold = create_gold(pack, labels, source="fixture", label_definition="unassessed")
        score = score_comparative(pack, authority, gold, run_comparative(pack, authority))
        for system in (SYSTEM_DIRECT, SYSTEM_NAIVE, SYSTEM_EVIDENCE_RECALL):
            self.assertEqual(0, score["metrics"]["ALL"][system]["scored_cases"])

    def test_dot_parser_preserves_citing_to_cited_direction_for_caller_to_invert(self):
        text = 'digraph G { "Citing A" -> "Cited B"; X -> Y [label="z"]; }'
        self.assertEqual([("Citing A", "Cited B"), ("X", "Y")], parse_dot_edges(text))

    def test_van_der_vet_importer_inverts_dot_and_freezes_indirect_edges_as_advisory(self):
        # DOT uses citing -> cited. A cites B, B cites ROOT, so evidence flow is ROOT -> B -> A.
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "network.dot"
            path.write_text('digraph G { A -> B; B -> ROOT; }', encoding="utf-8")
            pack, authority, gold, report = import_van_der_vet_dot(
                path, root_node_id="ROOT", inspected_target_ids=["A"]
            )
        self.assertEqual(1, report["inspected_targets"])
        case = pack["cases"][0]
        self.assertEqual("A", case["target_node_id"])
        by_edge = {item["edge_id"]: item["authority"] for item in authority["edge_authority"]}
        for edge in case["edges"]:
            expected = "HARD" if edge["prerequisite_node_id"] == "ROOT" else "ADVISORY"
            self.assertEqual(expected, by_edge[edge["edge_id"]])
        predictions = run_comparative(pack, authority)
        score = score_comparative(pack, authority, gold, predictions)
        self.assertEqual(1, score["metrics"]["ALL"][SYSTEM_NAIVE]["hard_false_quarantine"])
        self.assertEqual(1, score["metrics"]["ALL"][SYSTEM_EVIDENCE_RECALL]["unnecessary_unresolved_review"])

    def test_published_diagnostic_is_reproducible_and_does_not_claim_case_level_win(self):
        report = build_published_diagnostic()
        self.assertTrue(verify_published_diagnostic(report)["valid"])
        self.assertEqual(
            "AGGREGATE_DIAGNOSTIC_ONLY_CASE_LEVEL_EMPIRICAL_PROMOTION_BLOCKED",
            report["status"],
        )
        schneider = report["schneider"]["systems"]
        self.assertEqual(23, schneider[SYSTEM_DIRECT]["missed_exposure"])
        self.assertEqual(125, schneider[SYSTEM_NAIVE]["hard_false_quarantine_lower_bound"])
        self.assertEqual(125, schneider[SYSTEM_EVIDENCE_RECALL]["unnecessary_unresolved_review_lower_bound"])
        self.assertEqual(
            schneider[SYSTEM_NAIVE]["total_review_load"],
            schneider[SYSTEM_EVIDENCE_RECALL]["total_review_load"],
        )

    def test_schneider_importer_splits_gold_and_never_uses_it_for_authority(self):
        headers = [
            "No access",
            "Annotation pending",
            "2G article",
            "2G Title",
            "2G URL",
            "2G is also FG",
            "FG in bibliography",
            "FG Title",
            "Review possible impact overall?",
            "Seriousness/Risk",
        ]
        rows = [
            ["", "", "S1", "Two G one", "https://example/1", "", "F1", "First one", "Y", "high"],
            ["", "", "S2", "Two G two", "https://example/2", "", "F2", "First two", "N", "low"],
            ["", "", "D3", "Direct overlap", "https://example/3", "Yes", "F3", "First three", "not assessed - first-generation too", ""],
            ["No access", "", "S4", "No access", "", "", "F4", "First four", "Y", ""],
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "schneider.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                writer.writerows(rows)
            pack, authority, gold, report = import_schneider_csv(path, canonical_counts=False)
        self.assertEqual(3, report["accessible_rows"])
        self.assertEqual(1, report["positive_rows"])
        self.assertEqual(1, report["unassessed_rows"])
        public_dump = json.dumps(pack).casefold()
        self.assertNotIn("possible impact", public_dump)
        self.assertNotIn("seriousness", public_dump)
        by_edge = {item["edge_id"]: item["authority"] for item in authority["edge_authority"]}
        # Every ordinary second-generation citation is advisory independent of Y/N.
        second_edges = [
            edge
            for case in pack["cases"]
            for edge in case["edges"]
            if any("second-generation citation" in item for item in edge["evidence"])
        ]
        self.assertTrue(second_edges)
        self.assertTrue(all(by_edge[edge["edge_id"]] == "ADVISORY" for edge in second_edges))
        self.assertTrue(validate_gold(gold, pack)["valid"])

    def test_importer_canonical_counts_fail_closed_on_toy_data(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "toy.csv"
            path.write_text(
                "2G article,FG in bibliography,Review possible impact overall?\nS1,F1,Y\n",
                encoding="utf-8",
            )
            with self.assertRaises(ComparativeBenchmarkError):
                import_schneider_csv(path, canonical_counts=True)


if __name__ == "__main__":
    unittest.main()
