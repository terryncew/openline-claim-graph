"""Composed receiver verification for a graph receipt and bounded projection."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .graph import verify_projection
from .receipts import verify_receipt, verify_source_disclosure


def _warning_is_accepted(warning: str, policy: Mapping[str, Any]) -> bool:
    if warning == "projection_does_not_prove_completeness":
        return bool(policy.get("accept_bounded_projection"))
    if warning == "graph_state_receipt_authenticity_must_be_verified_separately":
        return True  # verify_receipt is executed in this composed path.
    if warning.startswith("semantic_mapping_unverified:"):
        mode = warning.split(":", 2)[1].upper()
        return mode in set(map(str, policy.get("allowed_provenance_modes", [])))
    if warning.startswith("relation_unanchored:"):
        return bool(policy.get("allow_unanchored_relations"))
    if warning.startswith("claim_unanchored:"):
        return bool(policy.get("allow_unanchored_claims"))
    return False


def verify_bundle(
    *,
    snapshot: Mapping[str, Any],
    receipt: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    projection: Mapping[str, Any],
    source_disclosure: Mapping[str, Any],
    receiver_policy: Mapping[str, Any],
    pinned_public_key: str,
    parent_snapshots: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify all layers before a receiver relies on a bounded graph slice."""

    receipt_result = verify_receipt(
        receipt,
        snapshot,
        sources,
        pinned_public_key=pinned_public_key,
        parent_snapshots=parent_snapshots,
    )
    projection_result = verify_projection(projection, receiver_policy)
    disclosure_result = verify_source_disclosure(source_disclosure, projection, receipt)
    errors = [f"receipt:{item}" for item in receipt_result["errors"]]
    errors.extend(f"projection:{item}" for item in projection_result["errors"])
    errors.extend(f"source_disclosure:{item}" for item in disclosure_result["errors"])
    warnings = list(receipt_result["warnings"])
    warnings.extend(projection_result["warnings"])
    warnings.extend(disclosure_result.get("warnings", []))

    bindings = {
        "snapshot_to_receipt_content": snapshot.get("content_root") == receipt.get("graph_content_root"),
        "snapshot_to_receipt_state": snapshot.get("state_root") == receipt.get("graph_state_root"),
        "projection_to_snapshot_content": projection.get("graph_content_root") == snapshot.get("content_root"),
        "projection_to_snapshot_state": projection.get("graph_state_root") == snapshot.get("state_root"),
        "disclosure_to_projection": source_disclosure.get("projection_id") == projection.get("projection_id"),
        "disclosure_to_receipt_sources": source_disclosure.get("source_manifest_root")
        == receipt.get("source_manifest_root"),
    }
    for name, matched in bindings.items():
        if not matched:
            errors.append(f"bundle_binding_failed:{name}")
    if not receiver_policy.get("accept_bounded_projection"):
        errors.append("receiver_policy_did_not_accept_bounded_projection")

    warnings = sorted(set(warnings))
    unaccepted = sorted(warning for warning in warnings if not _warning_is_accepted(warning, receiver_policy))
    if errors:
        disposition = "DENY"
    elif unaccepted:
        disposition = "QUARANTINE"
    else:
        disposition = "ADMIT"
    return {
        "valid": not errors,
        "disposition": disposition,
        "errors": sorted(set(errors)),
        "warnings": warnings,
        "unaccepted_warnings": unaccepted,
        "bindings": bindings,
        "layers": {
            "receipt": receipt_result,
            "projection": projection_result,
            "source_disclosure": disclosure_result,
        },
        "claim_boundary": (
            "Receiver-owned integrity and reliance-policy result. ADMIT means the declared policy accepted this "
            "bounded representation; it does not mean the represented claims are true or complete."
        ),
    }
