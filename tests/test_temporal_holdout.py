from __future__ import annotations

import copy
import hashlib
import unittest

from openline_claim_graph.temporal_holdout import (
    SYSTEM_DIRECT,
    SYSTEM_EVIDENCE_RECALL,
    SYSTEM_REVIEW_ALL,
    TemporalHoldoutError,
    build_published_diagnostic,
    create_authority,
    create_episode,
    create_future_record,
    create_future_seal,
    create_gold,
    create_pack,
    run_temporal,
    score_temporal,
    validate_future_seal_for_pack,
    validate_gold,
    validate_pack,
    verify_predictions,
    verify_published_diagnostic,
    verify_score,
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_fixture():
    t0 = "2018-12-31T23:59:59Z"
    t1 = "2019-06-01T00:00:00Z"
    pre = "2018-01-01T00:00:00Z"
    root, a, b, c, d, backup, e = (
        "root",
        "a",
        "b",
        "c",
        "d",
        "backup",
        "e",
    )
    nodes = [
        {"node_id": root, "label": "root", "available_at": pre},
        {"node_id": a, "label": "direct", "available_at": pre},
        {"node_id": b, "label": "hard downstream", "available_at": pre},
        {"node_id": c, "label": "advisory downstream", "available_at": pre},
        {"node_id": d, "label": "alternative support", "available_at": pre},
        {"node_id": backup, "label": "backup", "available_at": pre, "independent_basis": True},
        {"node_id": e, "label": "unadmitted downstream", "available_at": pre},
    ]
    edges = [
        {"prerequisite_node_id": root, "dependent_node_id": a, "relation": "DERIVED_FROM", "available_at": pre, "evidence": ["pre-cutoff direct basis"]},
        {"prerequisite_node_id": a, "dependent_node_id": b, "relation": "DEPENDS_ON", "available_at": pre, "evidence": ["pre-cutoff hard dependency"]},
        {"prerequisite_node_id": a, "dependent_node_id": c, "relation": "DEPENDS_ON", "available_at": pre, "evidence": ["pre-cutoff inferred dependency"]},
        {"prerequisite_node_id": root, "dependent_node_id": d, "relation": "SUPPORTS", "available_at": pre, "evidence": ["pre-cutoff support"]},
        {"prerequisite_node_id": backup, "dependent_node_id": d, "relation": "SUPPORTS", "available_at": pre, "evidence": ["pre-cutoff independent support"]},
        {"prerequisite_node_id": a, "dependent_node_id": e, "relation": "DEPENDS_ON", "available_at": pre, "evidence": ["pre-cutoff unadmitted relation"]},
    ]
    episode = create_episode(
        episode_name="temporal conformance",
        cutoff_at=t0,
        event_at=t1,
        invalidated_node_id=root,
        target_node_ids=[a, b, c, d, e],
        nodes=nodes,
        edges=edges,
        event={
            "status": "RETRACTED",
            "identifier": "fixture-event",
            "locator": "fixture:event",
            "reason": "fixture invalidation",
            "available_at": t1,
            "evidence_sha256": digest("fixture event notice"),
        },
        metadata={"domain": "CONFORMANCE"},
    )
    records = [
        create_future_record(episode_id=episode["episode_id"], available_at="2020-01-01T00:00:00Z", record_type="DOWNSTREAM_CORRECTION", target_node_ids=[a], locator="future:a", evidence_sha256=digest("A corrected"), description="A was later corrected"),
        create_future_record(episode_id=episode["episode_id"], available_at="2020-02-01T00:00:00Z", record_type="ACCEPTED_DECISION_FORMALLY_REOPENED", target_node_ids=[b], locator="future:b", evidence_sha256=digest("B reopened"), description="B was later formally reopened"),
        create_future_record(episode_id=episode["episode_id"], available_at="2020-03-01T00:00:00Z", record_type="INDEPENDENT_DEPENDENCY_AUDIT_NO_RELIANCE", target_node_ids=[c], locator="future:c", evidence_sha256=digest("C no reliance"), description="Independent audit found no consequential reliance"),
        create_future_record(episode_id=episode["episode_id"], available_at="2020-04-01T00:00:00Z", record_type="FORMAL_SCOPE_EXCLUSION", target_node_ids=[d], locator="future:d", evidence_sha256=digest("D excluded"), description="Later record explicitly excluded D from the affected scope"),
        create_future_record(episode_id=episode["episode_id"], available_at="2020-05-01T00:00:00Z", record_type="INDEPENDENT_CITATION_CONTEXT_NO_RELIANCE", target_node_ids=[e], locator="future:e", evidence_sha256=digest("E no reliance"), description="Later context audit found no reliance"),
    ]
    seal = create_future_seal(
        benchmark_id="temporal-conformance-v1",
        scope_definition="All five predetermined later records in the conformance fixture.",
        retrieval_cutoff_at="2021-01-01T00:00:00Z",
        records=records,
    )
    pack = create_pack(
        benchmark_id="temporal-conformance-v1",
        episodes=[episode],
        source_manifest=[{"role": "conformance_only", "identifier": "self-authored"}],
        construction_rule="Only pre-cutoff fixture facts plus the trigger event are prediction-visible.",
        future_seal=seal,
        status="CONFORMANCE_ONLY",
    )
    authority_map = {}
    for edge in episode["edges"]:
        evidence = set(edge["evidence"])
        authority_map[edge["edge_id"]] = (
            "ADVISORY" if "pre-cutoff inferred dependency" in evidence
            else "UNADMITTED" if "pre-cutoff unadmitted relation" in evidence
            else "HARD"
        )
    authority = create_authority(
        pack,
        edge_authority=authority_map,
        declared_by="fixture-receiver",
        construction_rule="Fixture labels: inferred advisory, explicit unadmitted, all remaining hard.",
    )
    by_target = {record["target_node_ids"][0]: record["record_id"] for record in records}
    labels = [
        {"episode_id": episode["episode_id"], "target_node_id": target, "outcome": "REOPEN" if target in {a, b} else "NO_REOPEN", "future_record_ids": [by_target[target]]}
        for target in [a, b, c, d, e]
    ]
    gold = create_gold(
        pack,
        seal,
        labels,
        label_definition="Conformance-only later reconsideration labels; not empirical evidence.",
    )
    return pack, authority, seal, gold, episode


class TemporalHoldoutTests(unittest.TestCase):
    def test_temporal_conformance_separates_review_load_from_recall(self):
        pack, authority, seal, gold, _episode = make_fixture()
        self.assertTrue(validate_pack(pack)["valid"])
        self.assertTrue(validate_future_seal_for_pack(seal, pack)["valid"])
        self.assertTrue(validate_gold(gold, pack, seal)["valid"])
        predictions = run_temporal(pack, authority)
        score = score_temporal(pack, authority, seal, gold, predictions)
        direct = score["metrics"][SYSTEM_DIRECT]
        review_all = score["metrics"][SYSTEM_REVIEW_ALL]
        er = score["metrics"][SYSTEM_EVIDENCE_RECALL]
        self.assertEqual((1, 1, 1), (direct["true_reopen_reviews"], direct["unnecessary_reviews"], direct["missed_reopenings"]))
        self.assertEqual((2, 3, 0, 5), (review_all["true_reopen_reviews"], review_all["unnecessary_reviews"], review_all["missed_reopenings"], review_all["total_review_load"]))
        self.assertEqual((2, 1, 0, 3), (er["true_reopen_reviews"], er["unnecessary_reviews"], er["missed_reopenings"], er["total_review_load"]))
        self.assertEqual(2, score["comparisons_vs_review_all"][SYSTEM_EVIDENCE_RECALL]["reviewer_savings_vs_review_all"])
        self.assertEqual({"numerator": 2, "denominator": 1}, er["relevant_reopenings_caught_per_unnecessary_review"])
        self.assertTrue(verify_predictions(predictions, pack, authority)["valid"])
        self.assertTrue(verify_score(score, pack, authority, seal, gold, predictions)["valid"])

    def test_public_pack_rejects_post_cutoff_node(self):
        pack, _authority, _seal, _gold, _episode = make_fixture()
        broken = copy.deepcopy(pack)
        broken["episodes"][0]["nodes"][0]["available_at"] = "2020-01-01T00:00:00Z"
        # The content ID mismatch and the temporal violation both fail closed.
        check = validate_pack(broken)
        self.assertFalse(check["valid"])
        self.assertTrue(any("node_after_cutoff" in item for item in check["errors"]))

    def test_public_graph_rejects_answer_bearing_key(self):
        pack, _authority, _seal, _gold, _episode = make_fixture()
        broken = copy.deepcopy(pack)
        broken["episodes"][0]["metadata"]["gold_outcome"] = "REOPEN"
        self.assertFalse(validate_pack(broken)["valid"])

    def test_future_record_must_be_after_trigger_event(self):
        pack, _authority, seal, _gold, _episode = make_fixture()
        broken = copy.deepcopy(seal)
        broken["records"][0]["available_at"] = "2019-01-01T00:00:00Z"
        self.assertFalse(validate_future_seal_for_pack(broken, pack)["valid"])

    def test_no_reopen_cannot_be_inferred_from_silence(self):
        pack, _authority, seal, gold, _episode = make_fixture()
        broken = copy.deepcopy(gold)
        negative = next(item for item in broken["labels"] if item["outcome"] == "NO_REOPEN")
        negative["future_record_ids"] = []
        self.assertFalse(validate_gold(broken, pack, seal)["valid"])

    def test_no_change_after_reanalysis_is_positive_reconsideration_evidence(self):
        pack, _authority, seal, gold, episode = make_fixture()
        target = episode["target_node_ids"][0]
        record = create_future_record(
            episode_id=episode["episode_id"],
            available_at="2020-06-01T00:00:00Z",
            record_type="EXPLICIT_NO_CHANGE_AFTER_REANALYSIS",
            target_node_ids=[target],
            locator="future:no-change",
            evidence_sha256=digest("reanalysis no change"),
            description="A later reanalysis explicitly found no change.",
        )
        new_seal = create_future_seal(
            benchmark_id=seal["benchmark_id"],
            scope_definition=seal["scope_definition"],
            retrieval_cutoff_at=seal["retrieval_cutoff_at"],
            records=list(seal["records"]) + [record],
        )
        # A pack must be re-bound to the new seal before predictions; this is the blindfold.
        new_pack = create_pack(
            benchmark_id=pack["benchmark_id"],
            episodes=pack["episodes"],
            source_manifest=pack["source_manifest"],
            construction_rule=pack["construction_rule"],
            future_seal=new_seal,
            status=pack["status"],
        )
        labels = []
        for item in gold["labels"]:
            item = dict(item)
            if item["target_node_id"] == target:
                item["outcome"] = "NO_REOPEN"
                item["future_record_ids"] = [record["record_id"]]
            labels.append(item)
        negative_gold = create_gold(new_pack, new_seal, labels, label_definition="negative misuse")
        self.assertFalse(validate_gold(negative_gold, new_pack, new_seal)["valid"])


    def test_source_manifest_rejects_answer_bearing_key(self):
        pack, _authority, _seal, _gold, _episode = make_fixture()
        broken = copy.deepcopy(pack)
        broken["source_manifest"][0]["future_result"] = "answer"
        self.assertFalse(validate_pack(broken)["valid"])

    def test_future_record_cannot_postdate_seal_retrieval_cutoff(self):
        pack, _authority, seal, _gold, _episode = make_fixture()
        broken = copy.deepcopy(seal)
        broken["records"][0]["available_at"] = "2022-01-01T00:00:00Z"
        self.assertFalse(validate_future_seal_for_pack(broken, pack)["valid"])

    def test_future_seal_commitment_tamper_breaks_prediction_verification(self):
        pack, authority, _seal, _gold, _episode = make_fixture()
        predictions = run_temporal(pack, authority)
        broken = copy.deepcopy(predictions)
        broken["future_seal_id"] = "future:wrong"
        self.assertFalse(verify_predictions(broken, pack, authority)["valid"])

    def test_unassessed_targets_do_not_affect_metrics(self):
        pack, authority, seal, gold, _episode = make_fixture()
        labels = copy.deepcopy(gold["labels"])
        labels[0]["outcome"] = "UNASSESSED"
        labels[0]["future_record_ids"] = []
        revised = create_gold(pack, seal, labels, label_definition="one unassessed")
        predictions = run_temporal(pack, authority)
        score = score_temporal(pack, authority, seal, revised, predictions)
        self.assertEqual(4, score["metrics"][SYSTEM_EVIDENCE_RECALL]["scored_cases"])

    def test_published_diagnostic_claims_no_temporal_result(self):
        report = build_published_diagnostic()
        self.assertTrue(verify_published_diagnostic(report)["valid"])
        self.assertEqual(
            "TEMPORAL_CORPUS_CANDIDATES_VERIFIED_CASE_LEVEL_HOLDOUT_NOT_YET_RUN",
            report["status"],
        )
        self.assertIn("empirical Evidence Recall temporal advantage", report["not_present"])
        self.assertEqual(166, report["candidate_corpora"]["jama_2025"]["published_facts"]["meta_analyses_recomputed"])


if __name__ == "__main__":
    unittest.main()
