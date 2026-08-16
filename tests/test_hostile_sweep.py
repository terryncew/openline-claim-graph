from __future__ import annotations

import copy
import random
import unittest

from openline_claim_graph import (
    build_source,
    create_claim,
    create_snapshot,
    private_key_from_hex,
    provenance_anchor,
    public_key_hex,
    sign_snapshot,
    verify_receipt,
)


def flip_hex(value: str) -> str:
    replacement = "0" if value[0] != "0" else "1"
    return replacement + value[1:]


class HostileMutationSweep(unittest.TestCase):
    def setUp(self):
        self.source = build_source("The declared limit is three.", locator="fixture://limit.txt")
        self.sources = {self.source["source_id"]: self.source}
        self.claim = create_claim(
            kind="SOURCE_ASSERTION",
            text="The declared limit is three.",
            asserted_by="fixture:extractor",
            provenance=[
                provenance_anchor(
                    self.source,
                    "The declared limit is three.",
                    mode="QUOTE",
                    asserted_by="fixture:extractor",
                )
            ],
            slot="policy.limit",
            value=3,
        )
        self.snapshot = create_snapshot(claims=[self.claim], relations=[])
        self.key = private_key_from_hex("22" * 32)
        self.pin = public_key_hex(self.key)
        self.receipt = sign_snapshot(
            self.snapshot,
            self.sources,
            private_key=self.key,
            issuer="fixture:hostile-sweep",
            issued_at="2026-08-15T08:00:00Z",
            parent_snapshots=[],
        )

    def verify(self, receipt, snapshot, sources):
        return verify_receipt(
            receipt,
            snapshot,
            sources,
            pinned_public_key=self.pin,
            parent_snapshots=[],
        )

    def test_10000_deterministic_mutations_are_detected(self):
        rng = random.Random(20260815)
        mutation_names = (
            "claim_text",
            "claim_id",
            "anchor_start",
            "anchor_quote_hash",
            "content_root",
            "state_root",
            "delta_root",
            "delta_added_claim",
            "source_content",
            "source_length",
            "source_locator",
            "receipt_issuer",
            "receipt_timestamp",
            "receipt_claim_count",
            "receipt_manifest_root",
            "receipt_payload_hash",
            "receipt_signature",
            "receipt_public_key",
        )
        misses: list[tuple[int, str]] = []
        for index in range(10_000):
            receipt = copy.deepcopy(self.receipt)
            snapshot = copy.deepcopy(self.snapshot)
            sources = copy.deepcopy(self.sources)
            name = mutation_names[rng.randrange(len(mutation_names))]
            claim = snapshot["claims"][0]
            anchor = claim["provenance"][0]
            source = sources[self.source["source_id"]]

            if name == "claim_text":
                claim["text"] += " altered"
            elif name == "claim_id":
                claim["claim_id"] = flip_hex(claim["claim_id"])
            elif name == "anchor_start":
                anchor["span"]["start"] += 1
            elif name == "anchor_quote_hash":
                anchor["quote_sha256"] = flip_hex(anchor["quote_sha256"])
            elif name == "content_root":
                snapshot["content_root"] = flip_hex(snapshot["content_root"])
            elif name == "state_root":
                snapshot["state_root"] = flip_hex(snapshot["state_root"])
            elif name == "delta_root":
                snapshot["delta_root"] = flip_hex(snapshot["delta_root"])
            elif name == "delta_added_claim":
                snapshot["delta"]["added_claim_ids"] = []
            elif name == "source_content":
                source["content"] += " altered"
            elif name == "source_length":
                source["byte_length"] += 1
            elif name == "source_locator":
                source["locator"] = "fixture://swapped.txt"
            elif name == "receipt_issuer":
                receipt["issuer"] += ":altered"
            elif name == "receipt_timestamp":
                receipt["issued_at"] = "2026-08-16T08:00:00Z"
            elif name == "receipt_claim_count":
                receipt["claim_count"] += 1
            elif name == "receipt_manifest_root":
                receipt["source_manifest_root"] = flip_hex(receipt["source_manifest_root"])
            elif name == "receipt_payload_hash":
                receipt["payload_hash"] = flip_hex(receipt["payload_hash"])
            elif name == "receipt_signature":
                receipt["proof"]["signature"] = flip_hex(receipt["proof"]["signature"])
            elif name == "receipt_public_key":
                receipt["proof_options"]["public_key"] = flip_hex(receipt["proof_options"]["public_key"])

            result = self.verify(receipt, snapshot, sources)
            if result["valid"]:
                misses.append((index, name))
        self.assertEqual([], misses)


if __name__ == "__main__":
    unittest.main()
