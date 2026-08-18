from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openline_claim_graph.decision_recall import (
    DecisionRecallError,
    SYSTEM_DECISION_RECALL,
    aggregate_scores,
    create_adjudication_packet,
    create_gold,
    create_manifest,
    create_pre_trigger_record,
    create_promotion_policy,
    create_review_packet,
    create_review_outcome,
    create_review_times,
    create_revocation_event,
    create_stream_seal,
    run_predictions,
    score_predictions,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "artifacts/decision-recall-prospective/conformance"


def catalog_custody(*, builder_id: str = "independent-catalog-builder", manifest_visible: bool = False, method: str = "MANIFEST_BLIND_RECORD_ENUMERATION") -> dict:
    return {
        "built_at": "2026-08-18T00:59:00Z",
        "builder_id": builder_id,
        "method": method,
        "source_scope": "CONVENTIONAL_PRE_TRIGGER_RECORDS_ONLY",
        "manifest_visible": manifest_visible,
    }


class DecisionRecallProspectiveTests(unittest.TestCase):
    def test_manifest_is_content_addressed_and_capture_cost_is_measured(self):
        manifest = create_manifest(
            decision_id="retry-policy",
            accepted_at="2026-08-18T00:00:30Z",
            decision="Accept retry policy",
            basis=[{"basis_id": "req", "kind": "REQUIREMENT", "statement": "Retries are required", "role": "REQUIRED"}],
            required_dependencies=["req"],
            alternative_support=[],
            assumptions=[],
            invalidation_conditions=[{"condition_id": "req-loss", "dependency_id": "req", "event_types": ["LOSS_OF_STANDING"]}],
            resulting_artifact={"kind": "COMMIT", "locator": "abc"},
            capture={"started_at": "2026-08-18T00:00:00Z", "confirmed_at": "2026-08-18T00:00:30Z", "drafted_by": "agent", "confirmed_by": "human", "correction_count": 0},
        )
        self.assertTrue(validate_manifest(manifest)["valid"])
        self.assertEqual(30000, manifest["capture"]["human_capture_milliseconds"])
        tampered = json.loads(json.dumps(manifest)); tampered["decision"] = "Different"
        self.assertFalse(validate_manifest(tampered)["valid"])

    def test_required_loss_reopens_but_alternative_survives(self):
        base = dict(
            accepted_at="2026-08-18T00:00:10Z",
            basis=[
                {"basis_id": "a", "kind": "REQ", "statement": "primary", "role": "REQUIRED"},
                {"basis_id": "b", "kind": "TEST", "statement": "independent", "role": "ALTERNATIVE", "alternative_group": "g"},
            ],
            required_dependencies=["a"],
            assumptions=[],
            invalidation_conditions=[{"condition_id": "a-loss", "dependency_id": "a", "event_types": ["LOSS_OF_STANDING"]}],
            resulting_artifact={"kind": "COMMIT", "locator": "x"},
            capture={"started_at": "2026-08-18T00:00:00Z", "confirmed_at": "2026-08-18T00:00:10Z"},
        )
        with_alt = create_manifest(decision_id="with-alt", decision="with alternative", alternative_support=[{"group_id": "g", "dependency_ids": ["b"]}], **base)
        no_alt_base = dict(base)
        no_alt_base["basis"] = [base["basis"][0]]
        no_alt = create_manifest(decision_id="no-alt", decision="no alternative", alternative_support=[], **no_alt_base)
        records = [
            create_pre_trigger_record(decision_id=item["decision_id"], decision=item["decision"], available_at=item["accepted_at"], materials=[{"material_id": f"m-{idx}", "text": "a b"}])
            for idx, item in enumerate([with_alt, no_alt], start=1)
        ]
        eligible = [
            {"basis_id": "a", "mentioned_record_ids": [item["pre_trigger_record_id"] for item in records]},
            {"basis_id": "b", "mentioned_record_ids": [records[0]["pre_trigger_record_id"]]},
        ]
        seal = create_stream_seal(benchmark_id="x", sealed_at="2026-08-18T01:00:00Z", manifests=[with_alt, no_alt], pre_trigger_records=records, eligible_bases=eligible, eligible_basis_catalog_custody=catalog_custody(), protocol_id="p")
        event = create_revocation_event(stream_seal=seal, basis_id="a", event_at="2026-08-18T02:00:00Z", reason="test")
        predictions = run_predictions(seal=seal, event=event)
        mapping = {row["decision"]: row[SYSTEM_DECISION_RECALL]["disposition"] for row in predictions["rows"]}
        self.assertEqual("SURVIVE", mapping["with alternative"])
        self.assertEqual("REOPEN", mapping["no alternative"])

    def test_controlled_selection_proof_fails_closed_on_wrong_rank(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        with self.assertRaises(DecisionRecallError):
            create_revocation_event(
                stream_seal=seal,
                basis_id="dep-3",
                event_at="2026-08-18T04:00:00Z",
                reason="controlled",
                stratum="CONTROLLED",
                selection_proof={
                    "selection_at": "2026-08-18T03:59:00Z",
                    "selection_method": "sha256_rank(seed || stream_seal_id || basis_id)",
                    "seed_hex": b"independent-seed-after-seal".hex(),
                    "selected_count": 3,
                    "rank": 99,
                },
            )

    def test_natural_revocation_can_expose_basis_omitted_from_controlled_catalog(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        decision_five = next(item for item in seal["manifests"] if item["decision_id"] == "decision-5")
        record = next(item for item in seal["pre_trigger_records"] if item["decision_id"] == "decision-5")
        record["materials"][0]["text"] += " natural-hidden-basis"
        # Rebuild the record and seal so the lexical occurrence is genuinely sealed pre-trigger.
        rebuilt_record = create_pre_trigger_record(
            decision_id=record["decision_id"],
            decision=record["decision"],
            available_at=record["available_at"],
            materials=record["materials"],
        )
        records = [rebuilt_record if item["decision_id"] == "decision-5" else item for item in seal["pre_trigger_records"]]
        # Preserve the controlled catalog without adding the natural basis.
        eligible = []
        old_to_new = {record["pre_trigger_record_id"]: rebuilt_record["pre_trigger_record_id"]}
        for item in seal["eligible_bases"]:
            copy = json.loads(json.dumps(item))
            copy["mentioned_record_ids"] = [old_to_new.get(rid, rid) for rid in copy["mentioned_record_ids"]]
            eligible.append(copy)
        natural_seal = create_stream_seal(
            benchmark_id="natural-catalog-omission",
            sealed_at=seal["sealed_at"],
            manifests=seal["manifests"],
            pre_trigger_records=records,
            eligible_bases=eligible,
            eligible_basis_catalog_custody=catalog_custody(),
            protocol_id=seal["protocol_id"],
        )
        event = create_revocation_event(
            stream_seal=natural_seal,
            basis_id="natural-hidden-basis",
            event_at="2026-08-18T05:00:00Z",
            reason="real upstream failure",
            stratum="NATURAL",
        )
        predictions = run_predictions(seal=natural_seal, event=event)
        row = next(item for item in predictions["rows"] if item["decision_id"] == decision_five["decision_id"])
        self.assertEqual("REVIEW", row["FLAT_LOG_SEARCH"]["disposition"])
        self.assertEqual("SURVIVE", row[SYSTEM_DECISION_RECALL]["disposition"])

    def test_omitted_dependency_can_be_selected_and_count_as_a_miss(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        event = json.loads((CASE / "event-05/event.json").read_text())
        predictions = json.loads((CASE / "event-05/predictions.json").read_text())
        gold = json.loads((CASE / "event-05/gold.private.json").read_text())
        score = score_predictions(seal=seal, event=event, predictions=predictions, gold=gold)
        self.assertEqual("hidden-5", event["basis_id"])
        self.assertEqual(1, score["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"])
        self.assertEqual(0, score["metrics"]["FLAT_LOG_SEARCH"]["missed_reopenings"])

    def test_blind_packet_does_not_contain_predictions(self):
        fixture = json.loads((CASE / "stream-seal.json").read_text())
        event = json.loads((CASE / "event-01/event.json").read_text())
        packet = create_adjudication_packet(seal=fixture, event=event)
        text = json.dumps(packet, sort_keys=True).lower()
        self.assertNotIn("predictions_id", text)
        self.assertNotIn("full_history_review", text)
        self.assertNotIn("flat_log_search", text)
        self.assertNotIn("openline.decision-recall-manifest", text)
        self.assertNotIn("manifest_id", text)

    def test_fixture_is_mechanics_only_and_reproducible(self):
        report = json.loads((CASE / "REPORT.json").read_text())
        self.assertEqual("MECHANICS_ONLY_NOT_PRODUCT_EVIDENCE", report["status"])
        self.assertFalse(report["promotion_eligible"])
        with tempfile.TemporaryDirectory(prefix="decision-recall-fixture-") as temp:
            out = Path(temp) / "case"
            env = os.environ.copy(); env["PYTHONPATH"] = str(ROOT / "src")
            subprocess.run([sys.executable, str(ROOT / "scripts/build_decision_recall_prospective_fixture.py"), "--output", str(out)], cwd=ROOT, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for rel in [
                "stream-seal.json", "promotion-policy.json", "REPORT.json",
                "event-01/event.json", "event-01/predictions.json", "event-01/adjudication-packet.json", "event-01/gold.private.json", "event-01/score.json",
            ]:
                self.assertEqual((CASE / rel).read_bytes(), (out / rel).read_bytes(), rel)

    def test_promotion_policy_fails_small_fixture(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        policy = json.loads((CASE / "promotion-policy.json").read_text())
        scores = [json.loads(path.read_text()) for path in sorted(CASE.glob("event-*/score.json"))]
        result = aggregate_scores(seal=seal, scores=scores, policy=policy)
        self.assertEqual("NO_PROMOTION", result["verdict"])
        self.assertIn("minimum_decisions", result["failed_conditions"])
        self.assertIn("minimum_controlled_revocations", result["failed_conditions"])
        self.assertIn("independent_manifest_blind_gold", result["failed_conditions"])

    def test_aggregate_does_not_trust_a_standalone_score_content_id(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        policy = json.loads((CASE / "promotion-policy.json").read_text())
        score = json.loads((CASE / "event-01/score.json").read_text())
        result = aggregate_scores(seal=seal, scores=[score], policy=policy)
        self.assertFalse(result["conditions"]["verified_score_artifacts"])
        self.assertIn("verified_score_artifacts", result["failed_conditions"])

    def test_aggregate_replays_bound_score_artifacts(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        policy = json.loads((CASE / "promotion-policy.json").read_text())
        run_dir = CASE / "event-01"
        bundle = {
            "event": json.loads((run_dir / "event.json").read_text()),
            "predictions": json.loads((run_dir / "predictions.json").read_text()),
            "gold": json.loads((run_dir / "gold.private.json").read_text()),
            "review_times": json.loads((run_dir / "review-times.fixture.json").read_text()),
            "review_outcomes": [
                json.loads((run_dir / "review-outcome.full-history.fixture.json").read_text()),
                json.loads((run_dir / "review-outcome.flat-search.fixture.json").read_text()),
            ],
            "score": json.loads((run_dir / "score.json").read_text()),
        }
        result = aggregate_scores(seal=seal, scores=[bundle["score"]], policy=policy, score_artifacts=[bundle])
        self.assertTrue(result["conditions"]["verified_score_artifacts"])
        tampered = json.loads(json.dumps(bundle))
        tampered["predictions"]["rows"][0][SYSTEM_DECISION_RECALL]["disposition"] = "SURVIVE"
        with self.assertRaises(DecisionRecallError):
            aggregate_scores(seal=seal, scores=[bundle["score"]], policy=policy, score_artifacts=[tampered])

    def test_aggregate_rejects_duplicate_or_tampered_scores(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        policy = json.loads((CASE / "promotion-policy.json").read_text())
        score = json.loads((CASE / "event-01/score.json").read_text())
        with self.assertRaises(DecisionRecallError):
            aggregate_scores(seal=seal, scores=[score, score], policy=policy)
        tampered = json.loads(json.dumps(score))
        tampered["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"] = 0 if score["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"] else 1
        with self.assertRaises(DecisionRecallError):
            aggregate_scores(seal=seal, scores=[tampered], policy=policy)

    def test_gold_adjudicator_cannot_be_a_capture_actor_for_promotion(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        event = json.loads((CASE / "event-01/event.json").read_text())
        predictions = json.loads((CASE / "event-01/predictions.json").read_text())
        packet = create_adjudication_packet(seal=seal, event=event)
        labels = []
        for row in packet["rows"]:
            labels.append({
                "decision_id": row["decision_id"],
                "label": "REOPEN" if row["decision"] == "Accept software change 1" else "SURVIVE",
                "rationale": "test",
            })
        gold = create_gold(
            adjudication_packet=packet,
            adjudicated_at="2026-08-18T03:30:00Z",
            adjudicator_id="fixture-receiver",
            labels=labels,
            method="INDEPENDENT_BLINDED_REVIEW",
        )
        score = score_predictions(seal=seal, event=event, predictions=predictions, gold=gold)
        policy = create_promotion_policy(
            declared_at="2026-08-18T01:00:00Z",
            minimum_decisions=1,
            minimum_controlled_revocations=1,
            minimum_review_load_reduction_basis_points=0,
            maximum_median_capture_milliseconds=999999,
            minimum_review_load_reduction_vs_flat_search_basis_points=-10000,
            minimum_timed_revocations=0,
            require_positive_conditional_attention_savings=False,
            require_instrumented_capture=False,
            require_outperform_flat_search=False,
            minimum_mixed_gold_revocations=1,
        )
        result = aggregate_scores(seal=seal, scores=[score], policy=policy)
        self.assertFalse(result["conditions"]["adjudicator_role_separation"])
        self.assertIn("adjudicator_role_separation", result["failed_conditions"])

    def test_review_timing_must_bind_the_exact_system_workload(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        event = json.loads((CASE / "event-01/event.json").read_text())
        predictions = json.loads((CASE / "event-01/predictions.json").read_text())
        packet = create_adjudication_packet(seal=seal, event=event)
        labels = [
            {
                "decision_id": row["decision_id"],
                "label": "REOPEN" if row["decision_id"] == "decision-1" else "SURVIVE",
                "rationale": "test",
            }
            for row in packet["rows"]
        ]
        gold = create_gold(
            adjudication_packet=packet,
            adjudicated_at="2026-08-18T03:30:00Z",
            adjudicator_id="independent-adjudicator",
            labels=labels,
            method="INDEPENDENT_BLINDED_REVIEW",
        )
        packets = {
            system: create_review_packet(seal=seal, event=event, predictions=predictions, system=system)
            for system in ("FULL_HISTORY_REVIEW", "FLAT_LOG_SEARCH", "DECISION_RECALL")
        }
        outcomes = []
        for system in ("FULL_HISTORY_REVIEW", "FLAT_LOG_SEARCH"):
            packet_labels = [
                {
                    "decision_id": row["decision_id"],
                    "label": "REOPEN" if row["decision_id"] == "decision-1" else "SURVIVE",
                    "rationale": "test baseline review",
                }
                for row in packets[system]["rows"]
            ]
            outcomes.append(create_review_outcome(
                review_packet=packets[system],
                reviewed_at="2026-08-18T03:40:00Z",
                reviewer_id=f"reviewer-{system}",
                labels=packet_labels,
            ))
        records = [
            {
                "system": system,
                "reviewer_id": f"reviewer-{system}",
                "review_packet_id": packets[system]["review_packet_id"],
                "review_milliseconds": 1000,
                "timing_source": "MONOTONIC_CLI",
            }
            for system in packets
        ]
        good_times = create_review_times(seal=seal, event=event, records=records)
        good_score = score_predictions(seal=seal, event=event, predictions=predictions, gold=gold, review_times=good_times, review_outcomes=outcomes)
        self.assertTrue(good_score["economics"]["review_packet_bindings_valid"])
        self.assertTrue(good_score["economics"]["review_timing_instrumented"])

        bad = json.loads(json.dumps(records))
        bad[0]["review_packet_id"] = packets["DECISION_RECALL"]["review_packet_id"]
        bad_times = create_review_times(seal=seal, event=event, records=bad)
        bad_score = score_predictions(seal=seal, event=event, predictions=predictions, gold=gold, review_times=bad_times, review_outcomes=outcomes)
        self.assertFalse(bad_score["economics"]["review_packet_bindings_valid"])
        self.assertFalse(bad_score["economics"]["review_timing_instrumented"])

    def test_catalog_must_be_manifest_blind_and_role_separated_for_promotion(self):
        base_seal = json.loads((CASE / "stream-seal.json").read_text())
        policy = create_promotion_policy(
            declared_at="2026-08-18T01:00:00Z",
            minimum_decisions=1,
            minimum_controlled_revocations=0,
            minimum_review_load_reduction_basis_points=0,
            maximum_median_capture_milliseconds=999999,
            minimum_review_load_reduction_vs_flat_search_basis_points=-10000,
            minimum_timed_revocations=0,
            require_positive_conditional_attention_savings=False,
            require_instrumented_capture=False,
            require_outperform_flat_search=False,
            minimum_mixed_gold_revocations=0,
            require_adjudicator_role_separation=False,
            require_verified_controlled_selection=False,
            require_instrumented_review_timing=False,
            require_verified_score_artifacts=False,
            require_baseline_review_outcomes=False,
            require_baseline_reviewer_role_separation=False,
            require_policy_predeclared_before_capture=False,
        )

        def result_for(custody):
            seal = create_stream_seal(
                benchmark_id="catalog-policy-test",
                sealed_at=base_seal["sealed_at"],
                manifests=base_seal["manifests"],
                pre_trigger_records=base_seal["pre_trigger_records"],
                eligible_bases=base_seal["eligible_bases"],
                eligible_basis_catalog_custody=custody,
                protocol_id=base_seal["protocol_id"],
            )
            event = create_revocation_event(
                stream_seal=seal,
                basis_id="dep-1",
                event_at="2026-08-18T05:00:00Z",
                reason="natural policy test",
                stratum="NATURAL",
            )
            predictions = run_predictions(seal=seal, event=event)
            packet = create_adjudication_packet(seal=seal, event=event)
            gold = create_gold(
                adjudication_packet=packet,
                adjudicated_at="2026-08-18T05:30:00Z",
                adjudicator_id="independent-adjudicator",
                labels=[{"decision_id": row["decision_id"], "label": "SURVIVE", "rationale": "policy-test gold"} for row in packet["rows"]],
                method="INDEPENDENT_BLINDED_REVIEW",
            )
            score = score_predictions(seal=seal, event=event, predictions=predictions, gold=gold)
            return aggregate_scores(seal=seal, scores=[score], policy=policy)

        role_bad = result_for(catalog_custody(builder_id="fixture-receiver"))
        self.assertFalse(role_bad["conditions"]["catalog_role_separation"])

        blind_bad = result_for(catalog_custody(manifest_visible=True))
        self.assertFalse(blind_bad["conditions"]["manifest_blind_basis_catalog"])

    def test_promotion_policy_must_precede_first_captured_decision(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        score = json.loads((CASE / "event-01/score.json").read_text())
        late_policy = create_promotion_policy(
            declared_at="2026-08-18T00:02:00Z",
            minimum_decisions=1,
            minimum_controlled_revocations=0,
            minimum_review_load_reduction_basis_points=0,
            maximum_median_capture_milliseconds=999999,
            minimum_review_load_reduction_vs_flat_search_basis_points=-10000,
            minimum_timed_revocations=0,
            require_positive_conditional_attention_savings=False,
            require_instrumented_capture=False,
            require_outperform_flat_search=False,
            minimum_mixed_gold_revocations=0,
            require_adjudicator_role_separation=False,
            require_verified_controlled_selection=False,
            require_instrumented_review_timing=False,
            require_verified_score_artifacts=False,
            require_manifest_blind_basis_catalog=False,
            require_catalog_role_separation=False,
            require_baseline_review_outcomes=False,
            require_baseline_reviewer_role_separation=False,
        )
        result = aggregate_scores(seal=seal, scores=[score], policy=late_policy)
        self.assertFalse(result["conditions"]["policy_predeclared_before_capture"])
        self.assertIn("policy_predeclared_before_capture", result["failed_conditions"])

    def test_full_history_human_baseline_is_not_the_gold_oracle(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        event = json.loads((CASE / "event-01/event.json").read_text())
        predictions = json.loads((CASE / "event-01/predictions.json").read_text())
        gold = json.loads((CASE / "event-01/gold.private.json").read_text())
        outcomes = [
            json.loads((CASE / "event-01/review-outcome.full-history.fixture.json").read_text()),
            json.loads((CASE / "event-01/review-outcome.flat-search.fixture.json").read_text()),
        ]
        score = score_predictions(seal=seal, event=event, predictions=predictions, gold=gold, review_outcomes=outcomes)
        self.assertEqual(1, score["metrics"]["FULL_HISTORY_REVIEW"]["missed_reopenings"])
        self.assertEqual(0, score["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"])
        self.assertTrue(score["baseline_review_outcomes_verified"])

    def test_module_free_verifier_runs_in_isolated_mode(self):
        source = (ROOT / "scripts/verify_decision_recall_prospective_fixture.py").read_text(encoding="utf-8")
        self.assertNotIn("from openline_claim_graph", source)
        self.assertNotIn("import openline_claim_graph", source)
        with tempfile.TemporaryDirectory(prefix="decision-recall-independent-verify-") as temp:
            output = Path(temp) / "verification.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(ROOT / "scripts/verify_decision_recall_prospective_fixture.py"),
                    "--artifact",
                    str(CASE),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            result = json.loads(output.read_text())
            self.assertTrue(result["valid"], completed.stdout)
            self.assertTrue(result["module_free"])
            self.assertGreaterEqual(result["check_count"], 160)

    def test_valid_reopen_against_gold_escalate_counts_as_overreach(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        event = json.loads((CASE / "event-01/event.json").read_text())
        predictions = json.loads((CASE / "event-01/predictions.json").read_text())
        packet = create_adjudication_packet(seal=seal, event=event)
        labels = [
            {
                "decision_id": row["decision_id"],
                "label": "ESCALATE" if row["decision_id"] == "decision-1" else "SURVIVE",
                "rationale": "independent record says automatic reopening is not justified",
            }
            for row in packet["rows"]
        ]
        gold = create_gold(
            adjudication_packet=packet,
            adjudicated_at="2026-08-18T03:30:00Z",
            adjudicator_id="independent-adjudicator",
            labels=labels,
            method="INDEPENDENT_BLINDED_REVIEW",
        )
        score = score_predictions(seal=seal, event=event, predictions=predictions, gold=gold)
        self.assertEqual(1, score["metrics"][SYSTEM_DECISION_RECALL]["ambiguous_overreach"])
        policy = create_promotion_policy(
            declared_at="2026-08-18T01:00:00Z",
            minimum_decisions=1,
            minimum_controlled_revocations=1,
            minimum_review_load_reduction_basis_points=0,
            maximum_median_capture_milliseconds=999999,
            minimum_review_load_reduction_vs_flat_search_basis_points=-10000,
            minimum_timed_revocations=0,
            require_positive_conditional_attention_savings=False,
            require_instrumented_capture=False,
            require_outperform_flat_search=False,
            minimum_mixed_gold_revocations=0,
            require_adjudicator_role_separation=False,
            require_verified_controlled_selection=False,
            require_instrumented_review_timing=False,
        )
        result = aggregate_scores(seal=seal, scores=[score], policy=policy)
        self.assertFalse(result["conditions"]["maximum_ambiguous_overreach"])
        self.assertIn("maximum_ambiguous_overreach", result["failed_conditions"])

    def test_gold_escalation_cannot_be_forced_reopen_without_failing_policy(self):
        seal = json.loads((CASE / "stream-seal.json").read_text())
        event = json.loads((CASE / "event-04/event.json").read_text())
        predictions = json.loads((CASE / "event-04/predictions.json").read_text())
        packet = create_adjudication_packet(seal=seal, event=event)
        labels = [
            {
                "decision_id": row["decision_id"],
                "label": "ESCALATE" if row["decision_id"] == "decision-4" else "SURVIVE",
                "rationale": "test",
            }
            for row in packet["rows"]
        ]
        gold = create_gold(
            adjudication_packet=packet,
            adjudicated_at="2026-08-18T03:30:00Z",
            adjudicator_id="independent-adjudicator",
            labels=labels,
            method="INDEPENDENT_BLINDED_REVIEW",
        )
        tampered_predictions = json.loads(json.dumps(predictions))
        target = next(row for row in tampered_predictions["rows"] if row["decision_id"] == "decision-4")
        target[SYSTEM_DECISION_RECALL]["disposition"] = "REOPEN"
        # Re-content-addressing a semantically wrong prediction should still be
        # rejected by score_predictions because predictions must reproduce from
        # the frozen state, so overreach cannot be smuggled in through scoring.
        from openline_claim_graph.canonical import content_id
        body = dict(tampered_predictions); body.pop("predictions_id", None)
        tampered_predictions["predictions_id"] = content_id("decision-recall-predictions", body)
        with self.assertRaises(DecisionRecallError):
            score_predictions(seal=seal, event=event, predictions=tampered_predictions, gold=gold)



if __name__ == "__main__":
    unittest.main()
