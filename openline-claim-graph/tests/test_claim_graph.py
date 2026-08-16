from __future__ import annotations

import copy
import unittest

from openline_claim_graph import (
    ClaimGraphWallet,
    GraphValidationError,
    build_source,
    compare_snapshots,
    create_claim,
    create_projection,
    create_relation,
    create_snapshot,
    create_source_disclosure,
    disagreement_report,
    private_key_from_hex,
    provenance_anchor,
    public_key_hex,
    sign_snapshot,
    validate_snapshot,
    verify_projection,
    verify_receipt,
    verify_source_disclosure,
    verify_bundle,
)
from openline_claim_graph.canonical import CanonicalizationError, canonical_json


ACTOR = "fixture:independent-extractor-v1"
ISSUER = "fixture:openline-claim-graph"
ISSUED_AT = "2026-08-15T08:00:00Z"


class ClaimGraphTest(unittest.TestCase):
    def setUp(self):
        self.policy_source = build_source(
            "Routine production changes require two approvals.\n"
            "During a declared outage, one approval is sufficient.\n",
            locator="fixture://policy.txt",
        )
        self.no_outage_source = build_source(
            "No outage has been declared.", locator="fixture://status-no-outage.txt"
        )
        self.outage_source = build_source(
            "An outage has been declared.", locator="fixture://status-outage.txt"
        )
        self.sources = {
            item["source_id"]: item
            for item in (self.policy_source, self.no_outage_source, self.outage_source)
        }
        self.key = private_key_from_hex("11" * 32)
        self.pin = public_key_hex(self.key)

        self.routine = self.quote_claim(
            self.policy_source,
            "Routine production changes require two approvals.",
            slot="policy.routine_approvals",
            value=2,
        )
        self.emergency = self.quote_claim(
            self.policy_source,
            "During a declared outage, one approval is sufficient.",
            slot="policy.outage_approvals",
            value=1,
        )
        self.base = create_snapshot(claims=[self.routine, self.emergency], relations=[])

    def quote_claim(self, source, quote, *, slot, value):
        return create_claim(
            kind="SOURCE_ASSERTION",
            text=quote,
            asserted_by=ACTOR,
            provenance=[provenance_anchor(source, quote, mode="QUOTE", asserted_by=ACTOR)],
            slot=slot,
            value=value,
        )

    def inferred_claim(self, source, quote, text, *, slot, value):
        return create_claim(
            kind="INFERENCE",
            text=text,
            asserted_by=ACTOR,
            provenance=[provenance_anchor(source, quote, mode="INFERENCE", asserted_by=ACTOR)],
            slot=slot,
            value=value,
        )

    def branch(self, *, outage: bool):
        if outage:
            status_source = self.outage_source
            status_quote = "An outage has been declared."
            approvals = 1
        else:
            status_source = self.no_outage_source
            status_quote = "No outage has been declared."
            approvals = 2
        status = self.quote_claim(
            status_source,
            status_quote,
            slot="environment.outage_declared",
            value=outage,
        )
        conclusion = self.inferred_claim(
            status_source,
            status_quote,
            f"The current change requires {approvals} approval{'s' if approvals != 1 else ''}.",
            slot="decision.required_approvals",
            value=approvals,
        )
        graph = create_snapshot(
            claims=[self.routine, self.emergency, status, conclusion],
            relations=[],
            parent_snapshots=[self.base],
        )
        return graph, status, conclusion

    def signed(self, snapshot, parents):
        return sign_snapshot(
            snapshot,
            self.sources,
            private_key=self.key,
            issuer=ISSUER,
            issued_at=ISSUED_AT,
            parent_snapshots=parents,
        )

    def merged(self):
        branch_a, status_a, conclusion_a = self.branch(outage=False)
        branch_b, status_b, conclusion_b = self.branch(outage=True)
        status_conflict = create_relation(
            source_claim_id=status_a["claim_id"],
            target_claim_id=status_b["claim_id"],
            relation="CONTRADICTS",
            asserted_by=ACTOR,
        )
        decision_conflict = create_relation(
            source_claim_id=conclusion_a["claim_id"],
            target_claim_id=conclusion_b["claim_id"],
            relation="CONTRADICTS",
            asserted_by=ACTOR,
        )
        claims = {
            item["claim_id"]: item
            for item in branch_a["claims"] + branch_b["claims"]
        }
        resolutions = [
            {
                "slot": "environment.outage_declared",
                "action": "PRESERVE_ALL",
                "parent_claim_ids": sorted([status_a["claim_id"], status_b["claim_id"]]),
                "reason": "The source states conflict; the merge must not manufacture agreement.",
            },
            {
                "slot": "decision.required_approvals",
                "action": "PRESERVE_ALL",
                "parent_claim_ids": sorted([conclusion_a["claim_id"], conclusion_b["claim_id"]]),
                "reason": "The conclusions depend on the unresolved outage-status conflict.",
            },
        ]
        merged = create_snapshot(
            claims=claims.values(),
            relations=[status_conflict, decision_conflict],
            parent_snapshots=[branch_a, branch_b],
            merge_resolutions=resolutions,
        )
        return merged, branch_a, branch_b, status_conflict, decision_conflict

    def test_restricted_canonical_json_is_order_independent(self):
        self.assertEqual(canonical_json({"b": 2, "a": 1}), canonical_json({"a": 1, "b": 2}))
        with self.assertRaises(CanonicalizationError):
            canonical_json({"not_allowed": 1.5})

    def test_snapshot_root_is_record_order_independent(self):
        left = create_snapshot(claims=[self.routine, self.emergency], relations=[])
        right = create_snapshot(claims=[self.emergency, self.routine], relations=[])
        self.assertEqual(left["content_root"], right["content_root"])
        self.assertEqual(left["state_root"], right["state_root"])

    def test_exact_quote_anchor_passes(self):
        result = validate_snapshot(self.base, self.sources, parent_snapshots=[])
        self.assertTrue(result["valid"], result)
        self.assertEqual([], result["warnings"])

    def test_extracted_label_cannot_hide_a_paraphrase(self):
        anchor = provenance_anchor(
            self.policy_source,
            "Routine production changes require two approvals.",
            mode="QUOTE",
            asserted_by=ACTOR,
        )
        mislabeled = create_claim(
            kind="SOURCE_ASSERTION",
            text="Normal changes need a pair of approvals.",
            asserted_by=ACTOR,
            provenance=[anchor],
        )
        graph = create_snapshot(claims=[mislabeled], relations=[])
        result = validate_snapshot(graph, self.sources, parent_snapshots=[])
        self.assertFalse(result["valid"])
        self.assertTrue(any("quote_mode_text_mismatch" in item for item in result["errors"]))

    def test_paraphrase_and_inference_are_disclosed_as_unverified(self):
        inferred = self.inferred_claim(
            self.no_outage_source,
            "No outage has been declared.",
            "The routine approval rule applies.",
            slot="decision.rule",
            value="routine",
        )
        graph = create_snapshot(claims=[inferred], relations=[])
        result = validate_snapshot(graph, self.sources, parent_snapshots=[])
        self.assertTrue(result["valid"], result)
        self.assertTrue(any("semantic_mapping_unverified:inference" in item for item in result["warnings"]))

    def test_tampered_source_is_detected(self):
        tampered_sources = copy.deepcopy(self.sources)
        tampered_sources[self.policy_source["source_id"]]["content"] = "Routine changes require zero approvals."
        result = validate_snapshot(self.base, tampered_sources, parent_snapshots=[])
        self.assertFalse(result["valid"])
        self.assertTrue(any("source_hash_mismatch" in item for item in result["errors"]))

    def test_claim_mutation_breaks_content_identity_and_root(self):
        tampered = copy.deepcopy(self.base)
        tampered["claims"][0]["text"] = "Altered after commitment."
        result = validate_snapshot(tampered, self.sources, parent_snapshots=[])
        self.assertFalse(result["valid"])
        self.assertIn("content_root_mismatch", result["errors"])
        self.assertTrue(any("claim_id_mismatch" in item for item in result["errors"]))

    def test_dangling_relation_is_rejected(self):
        relation = create_relation(
            source_claim_id=self.routine["claim_id"],
            target_claim_id="claim:sha256:" + "0" * 64,
            relation="SUPPORTS",
            asserted_by=ACTOR,
        )
        graph = create_snapshot(claims=[self.routine], relations=[relation])
        result = validate_snapshot(graph, self.sources, parent_snapshots=[])
        self.assertFalse(result["valid"])
        self.assertTrue(any("relation_dangling" in item for item in result["errors"]))

    def test_signed_receipt_binds_snapshot_sources_and_receiver_pin(self):
        receipt = self.signed(self.base, [])
        result = verify_receipt(
            receipt,
            self.base,
            self.sources,
            pinned_public_key=self.pin,
            parent_snapshots=[],
        )
        self.assertTrue(result["valid"], result)
        self.assertNotIn("signer_key_not_receiver_pinned", result["warnings"])

    def test_unpinned_signature_is_not_silently_trusted(self):
        receipt = self.signed(self.base, [])
        result = verify_receipt(
            receipt,
            self.base,
            self.sources,
            pinned_public_key=None,
            parent_snapshots=[],
        )
        self.assertTrue(result["valid"], result)
        self.assertIn("signer_key_not_receiver_pinned", result["warnings"])

    def test_receipt_tampering_is_detected(self):
        receipt = self.signed(self.base, [])
        receipt["claim_count"] = 999
        result = verify_receipt(
            receipt,
            self.base,
            self.sources,
            pinned_public_key=self.pin,
            parent_snapshots=[],
        )
        self.assertFalse(result["valid"])
        self.assertIn("receipt_payload_hash_mismatch", result["errors"])

    def test_projection_inclusion_proofs_and_receiver_policy(self):
        projection = create_projection(
            self.base,
            claim_ids=[self.routine["claim_id"]],
            purpose="Determine the routine approval floor.",
            selected_by="fixture:selector",
        )
        accepted = verify_projection(
            projection,
            {
                "required_claim_ids": [self.routine["claim_id"]],
                "required_slots": ["policy.routine_approvals"],
                "allowed_provenance_modes": ["QUOTE"],
            },
        )
        self.assertTrue(accepted["valid"], accepted)
        self.assertEqual("ADMIT", accepted["disposition"])
        denied = verify_projection(
            projection,
            {"required_claim_ids": [self.emergency["claim_id"]]},
        )
        self.assertFalse(denied["valid"])
        self.assertEqual("DENY", denied["disposition"])

    def test_projection_tampering_breaks_proof(self):
        projection = create_projection(
            self.base,
            claim_ids=[self.routine["claim_id"]],
            purpose="Fixture",
            selected_by="fixture:selector",
        )
        projection["claims"][0]["record"]["text"] = "Tampered projection."
        result = verify_projection(projection)
        self.assertFalse(result["valid"])
        self.assertTrue(any("proof_invalid" in item for item in result["errors"]))

    def test_receipt_uses_fixed_source_manifest_and_projection_discloses_only_needed_source(self):
        receipt = self.signed(self.base, [])
        self.assertIn("source_manifest_root", receipt)
        self.assertNotIn("source_commitments", receipt)
        self.assertEqual(1, receipt["source_count"])
        projection = create_projection(
            self.base,
            claim_ids=[self.routine["claim_id"]],
            purpose="Routine approval check",
            selected_by="fixture:selector",
        )
        disclosure = create_source_disclosure(projection, self.base, receipt, self.sources)
        self.assertEqual(1, len(disclosure["sources"]))
        result = verify_source_disclosure(disclosure, projection, receipt)
        self.assertTrue(result["valid"], result)

    def test_source_disclosure_tampering_breaks_manifest_proof(self):
        receipt = self.signed(self.base, [])
        projection = create_projection(
            self.base,
            claim_ids=[self.routine["claim_id"]],
            purpose="Routine approval check",
            selected_by="fixture:selector",
        )
        disclosure = create_source_disclosure(projection, self.base, receipt, self.sources)
        disclosure["sources"][0]["commitment"]["byte_length"] += 1
        result = verify_source_disclosure(disclosure, projection, receipt)
        self.assertFalse(result["valid"])
        self.assertTrue(any("proof_invalid" in item for item in result["errors"]))

    def test_composed_bundle_requires_receiver_to_accept_bounded_projection(self):
        receipt = self.signed(self.base, [])
        projection = create_projection(
            self.base,
            claim_ids=[self.routine["claim_id"]],
            purpose="Routine approval check",
            selected_by="fixture:selector",
        )
        disclosure = create_source_disclosure(projection, self.base, receipt, self.sources)
        strict_policy = {
            "required_claim_ids": [self.routine["claim_id"]],
            "allowed_provenance_modes": ["QUOTE"],
        }
        denied = verify_bundle(
            snapshot=self.base,
            receipt=receipt,
            sources=self.sources,
            projection=projection,
            source_disclosure=disclosure,
            receiver_policy=strict_policy,
            pinned_public_key=self.pin,
            parent_snapshots=[],
        )
        self.assertEqual("DENY", denied["disposition"])
        strict_policy["accept_bounded_projection"] = True
        admitted = verify_bundle(
            snapshot=self.base,
            receipt=receipt,
            sources=self.sources,
            projection=projection,
            source_disclosure=disclosure,
            receiver_policy=strict_policy,
            pinned_public_key=self.pin,
            parent_snapshots=[],
        )
        self.assertEqual("ADMIT", admitted["disposition"])

    def test_projection_cannot_include_relation_without_both_endpoints(self):
        edge = create_relation(
            source_claim_id=self.routine["claim_id"],
            target_claim_id=self.emergency["claim_id"],
            relation="QUALIFIES",
            asserted_by=ACTOR,
        )
        graph = create_snapshot(claims=[self.routine, self.emergency], relations=[edge])
        with self.assertRaises(GraphValidationError):
            create_projection(
                graph,
                claim_ids=[self.routine["claim_id"]],
                relation_ids=[edge["relation_id"]],
                purpose="Invalid slice",
                selected_by="fixture:selector",
            )

    def test_parent_record_cannot_disappear_silently(self):
        with self.assertRaises(GraphValidationError):
            create_snapshot(claims=[self.routine], relations=[], parent_snapshots=[self.base])

    def test_merge_requires_explicit_resolution(self):
        branch_a, _, _ = self.branch(outage=False)
        branch_b, _, _ = self.branch(outage=True)
        claims = {item["claim_id"]: item for item in branch_a["claims"] + branch_b["claims"]}
        with self.assertRaises(GraphValidationError) as caught:
            create_snapshot(claims=claims.values(), relations=[], parent_snapshots=[branch_a, branch_b])
        self.assertIn("merge_conflict_unresolved", str(caught.exception))

    def test_merge_preserves_conflict_without_assuming_one_lca(self):
        merged, branch_a, branch_b, _, _ = self.merged()
        result = validate_snapshot(merged, self.sources, parent_snapshots=[branch_a, branch_b])
        self.assertTrue(result["valid"], result)
        self.assertEqual(
            sorted([branch_a["state_root"], branch_b["state_root"]]),
            merged["parent_state_roots"],
        )
        # Parent order is not a hidden tie-breaker.
        rebuilt = create_snapshot(
            claims=merged["claims"],
            relations=merged["relations"],
            parent_snapshots=[branch_b, branch_a],
            merge_resolutions=merged["merge_resolutions"],
        )
        self.assertEqual(merged["state_root"], rebuilt["state_root"])

    def test_structural_queries_expose_divergence_without_ranking_branches(self):
        merged, branch_a, branch_b, _, _ = self.merged()
        comparison = compare_snapshots(branch_a, branch_b)
        changed = {item["slot"] for item in comparison["changed_slots"]}
        self.assertEqual(
            {"environment.outage_declared", "decision.required_approvals"},
            changed,
        )
        self.assertNotIn("winner", comparison)
        report = disagreement_report(merged)
        self.assertEqual(2, len(report["disagreements"]))
        self.assertTrue(all(item["mapping_status"] == "EXPLICITLY_MAPPED" for item in report["disagreements"]))

    def test_wallet_rejects_orphans_and_accepts_a_branching_history(self):
        branch_a, _, _ = self.branch(outage=False)
        branch_b, _, _ = self.branch(outage=True)
        wallet = ClaimGraphWallet(issuer_pins={ISSUER: self.pin})
        orphan_receipt = self.signed(branch_a, [self.base])
        self.assertEqual("DENY", wallet.admit(branch_a, orphan_receipt, self.sources)["disposition"])

        base_receipt = self.signed(self.base, [])
        self.assertEqual("ADMIT", wallet.admit(self.base, base_receipt, self.sources)["disposition"])
        self.assertIn(
            wallet.admit(branch_a, orphan_receipt, self.sources)["disposition"],
            ("ADMIT", "ADMIT_WITH_WARNINGS"),
        )
        branch_b_receipt = self.signed(branch_b, [self.base])
        self.assertIn(
            wallet.admit(branch_b, branch_b_receipt, self.sources)["disposition"],
            ("ADMIT", "ADMIT_WITH_WARNINGS"),
        )
        self.assertEqual(2, len(wallet.heads))

        merged, merge_parent_a, merge_parent_b, _, _ = self.merged()
        merge_receipt = self.signed(merged, [merge_parent_a, merge_parent_b])
        self.assertIn(
            wallet.admit(merged, merge_receipt, self.sources)["disposition"],
            ("ADMIT", "ADMIT_WITH_WARNINGS"),
        )
        self.assertEqual((merged["state_root"],), wallet.heads)


if __name__ == "__main__":
    unittest.main()
