from __future__ import annotations

import copy
import unittest

from openline_claim_graph import (
    ReviewRenderError,
    build_source,
    create_claim,
    create_projection,
    create_relation,
    create_snapshot,
    create_source_disclosure,
    private_key_from_hex,
    provenance_anchor,
    public_key_hex,
    render_review,
    sign_snapshot,
)


ACTOR = "fixture:review-extractor"
ISSUER = "fixture:review-issuer"


class ReviewRenderTest(unittest.TestCase):
    def setUp(self):
        self.left_source = build_source(
            "The approved limit is 10 units.", locator="fixture://approved.txt"
        )
        self.right_source = build_source(
            "The proposed limit is <script>alert('x')</script> units.",
            locator="fixture://proposal.txt",
        )
        self.sources = {
            item["source_id"]: item for item in (self.left_source, self.right_source)
        }
        left_text = "The approved limit is 10 units."
        right_text = "The proposed limit is <script>alert('x')</script> units."
        self.left = create_claim(
            kind="SOURCE_ASSERTION",
            text=left_text,
            asserted_by=ACTOR,
            provenance=[provenance_anchor(self.left_source, left_text, mode="QUOTE", asserted_by=ACTOR)],
            slot="decision.limit",
            value=10,
        )
        self.right = create_claim(
            kind="SOURCE_ASSERTION",
            text=right_text,
            asserted_by=ACTOR,
            provenance=[provenance_anchor(self.right_source, right_text, mode="QUOTE", asserted_by=ACTOR)],
            slot="decision.limit",
            value="<script>alert('x')</script>",
        )
        self.conflict = create_relation(
            source_claim_id=self.left["claim_id"],
            target_claim_id=self.right["claim_id"],
            relation="CONTRADICTS",
            asserted_by=ACTOR,
        )
        self.snapshot = create_snapshot(claims=[self.left, self.right], relations=[self.conflict])
        self.key = private_key_from_hex("22" * 32)
        self.pin = public_key_hex(self.key)
        self.receipt = sign_snapshot(
            self.snapshot,
            self.sources,
            private_key=self.key,
            issuer=ISSUER,
            issued_at="2026-08-15T12:00:00Z",
            parent_snapshots=[],
        )
        self.projection = create_projection(
            self.snapshot,
            claim_ids=[self.left["claim_id"], self.right["claim_id"]],
            relation_ids=[self.conflict["relation_id"]],
            purpose="Review a proposed limit change.",
            selected_by="fixture:receiver",
        )
        self.disclosure = create_source_disclosure(
            self.projection, self.snapshot, self.receipt, self.sources
        )
        self.policy = {
            "required_slots": ["decision.limit"],
            "required_relations": ["CONTRADICTS"],
            "deny_unanchored_claims": True,
            "allow_unanchored_relations": True,
            "allowed_provenance_modes": ["QUOTE"],
            "accept_bounded_projection": True,
        }

    def render(self, **overrides):
        values = {
            "snapshot": self.snapshot,
            "receipt": self.receipt,
            "sources": self.sources,
            "projection": self.projection,
            "source_disclosure": self.disclosure,
            "receiver_policy": self.policy,
            "pinned_public_key": self.pin,
            "parent_snapshots": [],
            "title": "Limit review",
        }
        values.update(overrides)
        return render_review(**values)

    def test_review_is_static_deterministic_and_escapes_source_content(self):
        first = self.render()
        second = self.render()
        self.assertEqual(first, second)
        self.assertIn("Limit review", first)
        self.assertIn("ADMIT", first)
        self.assertIn("C1", first)
        self.assertIn("CONTRADICTS", first)
        self.assertNotIn("<script>alert('x')</script>", first)
        self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", first)

    def test_wrong_pin_fails_closed(self):
        with self.assertRaises(ReviewRenderError):
            self.render(pinned_public_key="00" * 32)

    def test_tampered_source_fails_closed(self):
        changed = copy.deepcopy(self.sources)
        changed[self.left_source["source_id"]]["content"] = "The approved limit is 999 units."
        with self.assertRaises(ReviewRenderError):
            self.render(sources=changed)


if __name__ == "__main__":
    unittest.main()
