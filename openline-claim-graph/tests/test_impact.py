from __future__ import annotations

import copy
import unittest

from openline_claim_graph import (
    ImpactValidationError,
    analyze_source_impact,
    build_source,
    create_claim,
    create_impact_policy,
    create_relation,
    create_snapshot,
    create_source_status_event,
    private_key_from_hex,
    provenance_anchor,
    public_key_hex,
    render_impact_review,
    sign_snapshot,
    source_span,
    validate_source_status_event,
    verify_impact_report,
    verify_impact_bundle,
)
from openline_claim_graph.impact_review import ImpactReviewError


ACTOR = "fixture:accepted-reviewer"


class ImpactAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.bad_source = build_source("Study A reports response rate 62%.", locator="doi:study-a")
        self.good_source = build_source("Study B reports response rate 61%.", locator="doi:study-b")
        self.other_source = build_source("The safety endpoint remained stable.", locator="doi:study-c")
        self.notice_source = build_source(
            "Correction: the response-rate result in Study A is withdrawn.",
            locator="doi:study-a-correction",
        )
        self.sources = {
            item["source_id"]: item
            for item in (self.bad_source, self.good_source, self.other_source, self.notice_source)
        }

        self.bad = self.quote_claim(self.bad_source, "Study A reports response rate 62%.")
        self.good = self.quote_claim(self.good_source, "Study B reports response rate 61%.")
        self.other = self.quote_claim(self.other_source, "The safety endpoint remained stable.")
        self.derived = self.unanchored("The expected response rate is 62%.", "INFERENCE")
        self.decision = self.unanchored("Use 62% in the launch forecast.", "ASSUMPTION")
        self.redundant = self.unanchored("Response is approximately 60%.", "INFERENCE")
        self.advisory = self.unanchored("The executive summary may need revision.", "INFERENCE")

        self.derived_edge = self.edge(self.derived, self.bad, "DERIVED_FROM")
        self.decision_edge = self.edge(self.decision, self.derived, "DEPENDS_ON")
        self.bad_support = self.edge(self.bad, self.redundant, "SUPPORTS")
        self.good_support = self.edge(self.good, self.redundant, "SUPPORTS")
        self.advisory_edge = self.edge(self.advisory, self.bad, "DERIVED_FROM")
        self.snapshot = create_snapshot(
            claims=[
                self.bad,
                self.good,
                self.other,
                self.derived,
                self.decision,
                self.redundant,
                self.advisory,
            ],
            relations=[
                self.derived_edge,
                self.decision_edge,
                self.bad_support,
                self.good_support,
                self.advisory_edge,
            ],
        )
        self.event = create_source_status_event(
            status="CORRECTED",
            affected=[{"source_id": self.bad_source["source_id"]}],
            evidence=[
                provenance_anchor(
                    self.notice_source,
                    "Correction: the response-rate result in Study A is withdrawn.",
                    mode="QUOTE",
                    asserted_by="fixture:correction-notice",
                )
            ],
            asserted_by="fixture:correction-notice",
            effective_at="2026-08-16T00:00:00Z",
            reason="The published correction withdraws the named result.",
        )
        self.policy = create_impact_policy(
            self.snapshot,
            hard_relation_ids=[
                self.derived_edge["relation_id"],
                self.decision_edge["relation_id"],
                self.bad_support["relation_id"],
                self.good_support["relation_id"],
            ],
            advisory_relation_ids=[self.advisory_edge["relation_id"]],
            decision_claim_ids=[self.decision["claim_id"], self.other["claim_id"]],
        )
        self.key = private_key_from_hex("55" * 32)
        self.pin = public_key_hex(self.key)
        self.receipt = sign_snapshot(
            self.snapshot,
            self.sources,
            private_key=self.key,
            issuer="fixture:impact-state",
            issued_at="2026-08-16T00:00:00Z",
            parent_snapshots=[],
        )

    @staticmethod
    def unanchored(text: str, kind: str) -> dict:
        return create_claim(kind=kind, text=text, asserted_by=ACTOR)

    @staticmethod
    def edge(source: dict, target: dict, relation: str) -> dict:
        return create_relation(
            source_claim_id=source["claim_id"],
            target_claim_id=target["claim_id"],
            relation=relation,
            asserted_by=ACTOR,
        )

    @staticmethod
    def quote_claim(source: dict, quote: str) -> dict:
        return create_claim(
            kind="SOURCE_ASSERTION",
            text=quote,
            asserted_by=ACTOR,
            provenance=[provenance_anchor(source, quote, mode="QUOTE", asserted_by=ACTOR)],
        )

    def test_blast_radius_separates_quarantine_survival_review_and_unaffected(self):
        report = analyze_source_impact(self.snapshot, self.sources, self.event, self.policy)
        ids = {
            name: {entry["claim_id"] for entry in entries}
            for name, entries in report["classifications"].items()
        }
        self.assertEqual(
            {self.bad["claim_id"], self.derived["claim_id"], self.decision["claim_id"]},
            ids["quarantine"],
        )
        self.assertEqual({self.redundant["claim_id"]}, ids["survives"])
        self.assertEqual({self.advisory["claim_id"]}, ids["affected_unresolved"])
        self.assertEqual({self.good["claim_id"], self.other["claim_id"]}, ids["unaffected"])
        self.assertEqual([self.decision["claim_id"]], report["decision_claim_ids_touched"])

    def test_witness_path_reaches_two_hop_decision(self):
        report = analyze_source_impact(self.snapshot, self.sources, self.event, self.policy)
        decision = next(
            item
            for item in report["classifications"]["quarantine"]
            if item["claim_id"] == self.decision["claim_id"]
        )
        self.assertEqual(self.bad["claim_id"], decision["witness_path"]["origin_claim_id"])
        self.assertEqual(2, len(decision["witness_path"]["steps"]))

    def test_independent_support_prevents_over_quarantine(self):
        report = analyze_source_impact(self.snapshot, self.sources, self.event, self.policy)
        survivor = report["classifications"]["survives"][0]
        self.assertEqual(self.redundant["claim_id"], survivor["claim_id"])
        self.assertEqual([self.good["claim_id"]], survivor["retained_support_claim_ids"])

    def test_independent_support_can_preserve_a_directly_exposed_claim(self):
        independent = self.edge(self.good, self.bad, "SUPPORTS")
        snapshot = create_snapshot(
            claims=[self.bad, self.good],
            relations=[independent],
        )
        policy = create_impact_policy(
            snapshot,
            hard_relation_ids=[independent["relation_id"]],
        )
        report = analyze_source_impact(snapshot, self.sources, self.event, policy)
        self.assertEqual([], report["classifications"]["quarantine"])
        survivor = report["classifications"]["survives"][0]
        self.assertEqual(self.bad["claim_id"], survivor["claim_id"])
        self.assertEqual([self.good["claim_id"]], survivor["retained_support_claim_ids"])

    def test_ungrounded_support_cycle_cannot_self_rescue(self):
        cyclic = self.unanchored("A circular restatement of Study A.", "INFERENCE")
        bad_supports_cycle = self.edge(self.bad, cyclic, "SUPPORTS")
        cycle_supports_bad = self.edge(cyclic, self.bad, "SUPPORTS")
        snapshot = create_snapshot(
            claims=[self.bad, cyclic],
            relations=[bad_supports_cycle, cycle_supports_bad],
        )
        policy = create_impact_policy(
            snapshot,
            hard_relation_ids=[bad_supports_cycle["relation_id"], cycle_supports_bad["relation_id"]],
        )
        report = analyze_source_impact(snapshot, self.sources, self.event, policy)
        quarantined = {item["claim_id"] for item in report["classifications"]["quarantine"]}
        self.assertEqual({self.bad["claim_id"], cyclic["claim_id"]}, quarantined)

    def test_grounded_required_cycle_is_not_false_quarantined(self):
        primary = build_source("Primary record: Shared accepted fact.", locator="fixture:primary")
        backup = build_source("Independent record: Shared accepted fact.", locator="fixture:backup")
        notice = build_source("Correction applies to the primary copy.", locator="fixture:notice")
        grounded = create_claim(
            kind="SOURCE_ASSERTION",
            text="Shared accepted fact.",
            asserted_by=ACTOR,
            provenance=[
                provenance_anchor(primary, "Shared accepted fact.", mode="QUOTE", asserted_by=ACTOR),
                provenance_anchor(backup, "Shared accepted fact.", mode="QUOTE", asserted_by=ACTOR),
            ],
        )
        companion = self.unanchored("Accepted companion claim.", "ASSUMPTION")
        grounded_depends = self.edge(grounded, companion, "DEPENDS_ON")
        companion_depends = self.edge(companion, grounded, "DEPENDS_ON")
        snapshot = create_snapshot(
            claims=[grounded, companion],
            relations=[grounded_depends, companion_depends],
        )
        event = create_source_status_event(
            status="CORRECTED",
            affected=[{"source_id": primary["source_id"]}],
            evidence=[
                provenance_anchor(
                    notice,
                    "Correction applies to the primary copy.",
                    mode="QUOTE",
                    asserted_by=ACTOR,
                )
            ],
            asserted_by=ACTOR,
            effective_at="2026-08-16T00:00:00Z",
            reason="The backup source remains admitted.",
        )
        policy = create_impact_policy(
            snapshot,
            hard_relation_ids=[grounded_depends["relation_id"], companion_depends["relation_id"]],
        )
        sources = {item["source_id"]: item for item in (primary, backup, notice)}
        report = analyze_source_impact(snapshot, sources, event, policy)
        self.assertEqual([], report["classifications"]["quarantine"])
        self.assertEqual(
            {grounded["claim_id"], companion["claim_id"]},
            {item["claim_id"] for item in report["classifications"]["survives"]},
        )

    def test_advisory_edge_cannot_launder_inference_into_hard_quarantine(self):
        report = analyze_source_impact(self.snapshot, self.sources, self.event, self.policy)
        review_ids = {
            item["claim_id"] for item in report["classifications"]["affected_unresolved"]
        }
        quarantine_ids = {item["claim_id"] for item in report["classifications"]["quarantine"]}
        self.assertIn(self.advisory["claim_id"], review_ids)
        self.assertNotIn(self.advisory["claim_id"], quarantine_ids)
        item = next(
            row
            for row in report["classifications"]["affected_unresolved"]
            if row["claim_id"] == self.advisory["claim_id"]
        )
        self.assertIn("ADVISORY", {step["authority"] for step in item["witness_path"]["steps"]})

    def test_unadmitted_relation_has_no_propagation_authority(self):
        unadmitted = self.edge(self.bad, self.other, "SUPPORTS")
        snapshot = create_snapshot(claims=[self.bad, self.other], relations=[unadmitted])
        policy = create_impact_policy(snapshot, hard_relation_ids=[])
        report = analyze_source_impact(snapshot, self.sources, self.event, policy)
        quarantined = {item["claim_id"] for item in report["classifications"]["quarantine"]}
        unaffected = {item["claim_id"] for item in report["classifications"]["unaffected"]}
        self.assertEqual({self.bad["claim_id"]}, quarantined)
        self.assertEqual({self.other["claim_id"]}, unaffected)
        self.assertEqual([unadmitted["relation_id"]], report["ignored_relation_ids"])

    def test_unsupported_relation_cannot_be_granted_impact_authority(self):
        contradiction = self.edge(self.bad, self.other, "CONTRADICTS")
        snapshot = create_snapshot(claims=[self.bad, self.other], relations=[contradiction])
        policy = create_impact_policy(
            snapshot,
            hard_relation_ids=[contradiction["relation_id"]],
        )
        with self.assertRaises(ImpactValidationError):
            analyze_source_impact(snapshot, self.sources, self.event, policy)

    def test_exact_event_span_does_not_revoke_another_claim_in_same_source(self):
        combined = build_source("Value A is 10. Value B is 20.", locator="fixture:combined")
        notice = build_source("Correction: Value A is withdrawn.", locator="fixture:notice")
        a = self.quote_claim(combined, "Value A is 10.")
        b = self.quote_claim(combined, "Value B is 20.")
        snapshot = create_snapshot(claims=[a, b], relations=[])
        start, end = source_span(combined, "Value A is 10.")
        event = create_source_status_event(
            status="CORRECTED",
            affected=[{"source_id": combined["source_id"], "spans": [{"start": start, "end": end}]}],
            evidence=[
                provenance_anchor(
                    notice,
                    "Correction: Value A is withdrawn.",
                    mode="QUOTE",
                    asserted_by=ACTOR,
                )
            ],
            asserted_by=ACTOR,
            effective_at="2026-08-16T00:00:00Z",
            reason="Exact-span correction.",
        )
        policy = create_impact_policy(snapshot, hard_relation_ids=[])
        sources = {item["source_id"]: item for item in (combined, notice)}
        report = analyze_source_impact(snapshot, sources, event, policy)
        quarantined = {item["claim_id"] for item in report["classifications"]["quarantine"]}
        unaffected = {item["claim_id"] for item in report["classifications"]["unaffected"]}
        self.assertEqual({a["claim_id"]}, quarantined)
        self.assertEqual({b["claim_id"]}, unaffected)

    def test_report_reproduction_detects_tampering(self):
        report = analyze_source_impact(self.snapshot, self.sources, self.event, self.policy)
        self.assertTrue(
            verify_impact_report(report, self.snapshot, self.sources, self.event, self.policy)["valid"]
        )
        tampered = copy.deepcopy(report)
        tampered["summary"]["quarantine"] = 0
        verification = verify_impact_report(
            tampered, self.snapshot, self.sources, self.event, self.policy
        )
        self.assertFalse(verification["valid"])
        self.assertIn("impact_report_id_mismatch", verification["errors"])

    def test_review_renders_only_after_exact_report_reproduction(self):
        report = analyze_source_impact(self.snapshot, self.sources, self.event, self.policy)
        rendered = render_impact_review(
            report=report,
            snapshot=self.snapshot,
            sources=self.sources,
            event=self.event,
            policy=self.policy,
            accepted_receipt=self.receipt,
            pinned_public_key=self.pin,
            parent_snapshots=[],
            title="Fixture Evidence Recall",
        )
        self.assertIn("Fixture Evidence Recall", rendered)
        self.assertIn("STATE RECEIPT + IMPACT REPRODUCED", rendered)
        self.assertIn("Use 62% in the launch forecast", rendered)
        tampered = copy.deepcopy(report)
        tampered["summary"]["quarantine"] = 0
        with self.assertRaises(ImpactReviewError):
            render_impact_review(
                report=tampered,
                snapshot=self.snapshot,
                sources=self.sources,
                event=self.event,
                policy=self.policy,
                accepted_receipt=self.receipt,
                pinned_public_key=self.pin,
                parent_snapshots=[],
            )

    def test_composed_impact_bundle_rejects_wrong_accepted_state_pin(self):
        report = analyze_source_impact(self.snapshot, self.sources, self.event, self.policy)
        admitted = verify_impact_bundle(
            report,
            self.snapshot,
            self.sources,
            self.event,
            self.policy,
            self.receipt,
            pinned_public_key=self.pin,
            parent_snapshots=[],
        )
        self.assertTrue(admitted["valid"], admitted)
        denied = verify_impact_bundle(
            report,
            self.snapshot,
            self.sources,
            self.event,
            self.policy,
            self.receipt,
            pinned_public_key="00" * 32,
            parent_snapshots=[],
        )
        self.assertFalse(denied["valid"])
        self.assertEqual("DENY_IMPACT_REVIEW", denied["disposition"])

    def test_event_anchor_tampering_fails_closed(self):
        tampered = copy.deepcopy(self.event)
        tampered["evidence"][0]["quote_sha256"] = "0" * 64
        tampered["event_id"] = create_source_status_event(
            status=tampered["status"],
            affected=tampered["affected"],
            evidence=tampered["evidence"],
            asserted_by=tampered["asserted_by"],
            effective_at=tampered["effective_at"],
            reason=tampered["reason"],
        )["event_id"]
        check = validate_source_status_event(tampered, self.sources)
        self.assertFalse(check["valid"])
        with self.assertRaises(ImpactValidationError):
            analyze_source_impact(self.snapshot, self.sources, tampered, self.policy)


if __name__ == "__main__":
    unittest.main()
