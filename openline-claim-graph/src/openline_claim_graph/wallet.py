"""Append-only custody for branching claim-graph receipts."""

from __future__ import annotations

from typing import Any, Mapping

from .receipts import verify_receipt


class ClaimGraphWallet:
    """A small receipt wallet; not an identity wallet and not a truth ledger."""

    def __init__(self, *, issuer_pins: Mapping[str, str]):
        self.issuer_pins = dict(issuer_pins)
        self._entries: dict[str, dict[str, Any]] = {}

    @property
    def state_roots(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    @property
    def heads(self) -> tuple[str, ...]:
        parents = {
            parent
            for entry in self._entries.values()
            for parent in entry["snapshot"].get("parent_state_roots", [])
        }
        return tuple(sorted(set(self._entries) - parents))

    def admit(
        self,
        snapshot: Mapping[str, Any],
        receipt: Mapping[str, Any],
        sources: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        state_root = str(snapshot.get("state_root", ""))
        if not state_root:
            return {"disposition": "DENY", "errors": ["wallet_state_root_missing"], "warnings": []}
        if state_root in self._entries:
            return {"disposition": "DENY", "errors": ["wallet_duplicate_state"], "warnings": []}
        parent_roots = list(map(str, snapshot.get("parent_state_roots", [])))
        missing = sorted(set(parent_roots) - set(self._entries))
        if missing:
            return {
                "disposition": "DENY",
                "errors": [f"wallet_unknown_parent:{item}" for item in missing],
                "warnings": [],
            }
        issuer = str(receipt.get("issuer", ""))
        pin = self.issuer_pins.get(issuer)
        if pin is None:
            return {"disposition": "DENY", "errors": ["wallet_issuer_not_pinned"], "warnings": []}
        parents = [self._entries[root]["snapshot"] for root in parent_roots]
        verification = verify_receipt(
            receipt,
            snapshot,
            sources,
            pinned_public_key=pin,
            parent_snapshots=parents,
        )
        if not verification["valid"]:
            return {"disposition": "DENY", **verification}
        self._entries[state_root] = {
            "snapshot": dict(snapshot),
            "receipt": dict(receipt),
            "source_manifest_root": receipt["source_manifest_root"],
            "source_count": receipt["source_count"],
        }
        disposition = "ADMIT_WITH_WARNINGS" if verification["warnings"] else "ADMIT"
        return {"disposition": disposition, **verification}

    def export(self) -> dict[str, Any]:
        return {
            "schema": "openline.claim-graph.wallet.v1",
            "claim_boundary": "Append-only custody of signed graph states; not a truth or reputation ledger.",
            "issuer_pins": dict(sorted(self.issuer_pins.items())),
            "heads": list(self.heads),
            "entries": [
                {
                    "state_root": root,
                    "parent_state_roots": entry["snapshot"].get("parent_state_roots", []),
                    "content_root": entry["snapshot"].get("content_root"),
                    "receipt_payload_hash": entry["receipt"].get("payload_hash"),
                    "issuer": entry["receipt"].get("issuer"),
                    "issued_at": entry["receipt"].get("issued_at"),
                    "source_manifest_root": entry["source_manifest_root"],
                    "source_count": entry["source_count"],
                }
                for root, entry in sorted(self._entries.items())
            ],
        }
