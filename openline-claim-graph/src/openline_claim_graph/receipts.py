"""Ed25519 receipts for claim-graph states.

Signatures prove that one key signed one exact state commitment.  Identity and
trust remain receiver-owned; callers should pass a pinned public key whenever
the receipt will influence a consequential decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .canonical import PROFILE as CANONICAL_PROFILE
from .canonical import canonical_json, content_id, sha256_hex
from .graph import PROFILE_HASH, source_commitment, validate_snapshot
from .merkle import merkle_proof, merkle_root, verify_merkle_proof


RECEIPT_SCHEMA = "openline.claim-graph.receipt.v1"


def private_key_from_hex(value: str) -> Ed25519PrivateKey:
    raw = bytes.fromhex(value)
    if len(raw) != 32:
        raise ValueError("Ed25519 private key must contain exactly 32 bytes")
    return Ed25519PrivateKey.from_private_bytes(raw)


def public_key_hex(private_key: Ed25519PrivateKey) -> str:
    return private_key.public_key().public_bytes_raw().hex()


def _referenced_source_ids(snapshot: Mapping[str, Any]) -> set[str]:
    source_ids: set[str] = set()
    for collection in (snapshot.get("claims", []), snapshot.get("relations", [])):
        for record in collection:
            for anchor in record.get("provenance", []):
                if "source_id" in anchor:
                    source_ids.add(str(anchor["source_id"]))
    return source_ids


def _source_manifest_leaves(
    snapshot: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]
) -> list[tuple[str, dict[str, Any]]]:
    referenced = _referenced_source_ids(snapshot)
    return sorted(
        ((f"source:{source_id}", source_commitment(sources[source_id])) for source_id in referenced),
        key=lambda item: item[0],
    )


def _receipt_body(receipt: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(receipt)
    body.pop("payload_hash", None)
    body.pop("proof", None)
    return body


def _warning_commitment(warnings: Sequence[str]) -> dict[str, Any]:
    ordered = sorted(set(map(str, warnings)))
    leaves = [(f"warning:{sha256_hex(item.encode('utf-8'))}", {"warning": item}) for item in ordered]
    categories: dict[str, int] = {}
    for warning in ordered:
        parts = warning.split(":")
        category = ":".join(parts[:2]) if warning.startswith("semantic_mapping_unverified:") else parts[0]
        categories[category] = categories.get(category, 0) + 1
    return {
        "validation_warning_root": merkle_root(leaves),
        "validation_warning_count": len(ordered),
        "validation_warning_categories": dict(sorted(categories.items())),
    }


def _parse_timestamp(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")


def sign_snapshot(
    snapshot: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    *,
    private_key: Ed25519PrivateKey,
    issuer: str,
    issued_at: str,
    parent_snapshots: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    _parse_timestamp(issued_at)
    verification = validate_snapshot(snapshot, sources, parent_snapshots=parent_snapshots)
    if not verification["valid"]:
        raise ValueError(f"cannot sign invalid snapshot: {verification['errors']}")
    referenced = _referenced_source_ids(snapshot)
    missing = referenced - set(sources)
    if missing:
        raise ValueError(f"referenced sources missing: {sorted(missing)}")
    source_leaves = _source_manifest_leaves(snapshot, sources)
    signer_public_key = public_key_hex(private_key)
    body = {
        "schema": RECEIPT_SCHEMA,
        "issuer": issuer,
        "issued_at": issued_at,
        "canonicalization": CANONICAL_PROFILE,
        "profile_hash": PROFILE_HASH,
        "graph_content_root": snapshot["content_root"],
        "graph_state_root": snapshot["state_root"],
        "parent_state_roots": snapshot["parent_state_roots"],
        "delta_root": snapshot["delta_root"],
        "claim_count": len(snapshot.get("claims", [])),
        "relation_count": len(snapshot.get("relations", [])),
        "source_manifest_root": merkle_root(source_leaves),
        "source_count": len(source_leaves),
        **_warning_commitment(verification["warnings"]),
        "proof_options": {
            "algorithm": "Ed25519",
            "public_key": signer_public_key,
            "trust": "receiver_must_pin_or_resolve_public_key",
        },
        "claim_boundary": (
            "The signer commits to this graph state and its declared source anchors. "
            "The receipt does not certify truth, semantic fidelity, completeness, or signer identity."
        ),
    }
    encoded = canonical_json(body)
    return {
        **body,
        "payload_hash": sha256_hex(encoded),
        "proof": {
            "signature": private_key.sign(encoded).hex(),
        },
    }


def verify_receipt(
    receipt: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    *,
    pinned_public_key: str | None,
    parent_snapshots: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        if receipt.get("schema") != RECEIPT_SCHEMA:
            errors.append("receipt_schema_invalid")
        body = _receipt_body(receipt)
        encoded = canonical_json(body)
        if receipt.get("payload_hash") != sha256_hex(encoded):
            errors.append("receipt_payload_hash_mismatch")
        proof = dict(receipt["proof"])
        proof_options = dict(receipt["proof_options"])
        if proof_options.get("algorithm") != "Ed25519":
            errors.append("receipt_signature_algorithm_invalid")
        public = str(proof_options["public_key"])
        if pinned_public_key is None:
            warnings.append("signer_key_not_receiver_pinned")
        elif public != pinned_public_key:
            errors.append("signer_key_pin_mismatch")
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public)).verify(bytes.fromhex(str(proof["signature"])), encoded)
        _parse_timestamp(str(receipt["issued_at"]))

        graph_verification = validate_snapshot(snapshot, sources, parent_snapshots=parent_snapshots)
        errors.extend(graph_verification["errors"])
        warnings.extend(graph_verification["warnings"])
        expected_fields = {
            "canonicalization": CANONICAL_PROFILE,
            "profile_hash": PROFILE_HASH,
            "graph_content_root": snapshot.get("content_root"),
            "graph_state_root": snapshot.get("state_root"),
            "parent_state_roots": snapshot.get("parent_state_roots"),
            "delta_root": snapshot.get("delta_root"),
            "claim_count": len(snapshot.get("claims", [])),
            "relation_count": len(snapshot.get("relations", [])),
            **_warning_commitment(graph_verification["warnings"]),
        }
        for field, expected in expected_fields.items():
            if receipt.get(field) != expected:
                errors.append(f"receipt_snapshot_binding_mismatch:{field}")
        source_leaves = _source_manifest_leaves(snapshot, sources)
        if receipt.get("source_manifest_root") != merkle_root(source_leaves):
            errors.append("receipt_source_manifest_root_mismatch")
        if receipt.get("source_count") != len(source_leaves):
            errors.append("receipt_source_count_mismatch")
    except InvalidSignature:
        errors.append("receipt_signature_invalid")
    except (KeyError, TypeError, ValueError, UnicodeError):
        errors.append("receipt_invalid")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "claim_boundary": "Authenticity, integrity, anchor, and lineage checks only; no truth claim.",
    }


def create_source_disclosure(
    projection: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    receipt: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Disclose only projection-relevant source commitments with inclusion proofs."""

    if projection.get("graph_state_root") != snapshot.get("state_root"):
        raise ValueError("projection and snapshot state roots differ")
    if receipt.get("graph_state_root") != snapshot.get("state_root"):
        raise ValueError("receipt and snapshot state roots differ")
    selected_source_ids: set[str] = set()
    for collection in (projection.get("claims", []), projection.get("relations", [])):
        for entry in collection:
            for anchor in entry.get("record", {}).get("provenance", []):
                if "source_id" in anchor:
                    selected_source_ids.add(str(anchor["source_id"]))
    all_leaves = _source_manifest_leaves(snapshot, sources)
    entries = []
    for source_id in sorted(selected_source_ids):
        key = f"source:{source_id}"
        entries.append(
            {
                "commitment": source_commitment(sources[source_id]),
                "proof": merkle_proof(all_leaves, key),
            }
        )
    body = {
        "schema": "openline.claim-graph.source-disclosure.v1",
        "projection_id": projection["projection_id"],
        "graph_state_root": snapshot["state_root"],
        "source_manifest_root": receipt["source_manifest_root"],
        "sources": entries,
        "omission_disclosure": "only_sources_referenced_by_the_bounded_projection_are_disclosed",
    }
    return {"disclosure_id": content_id("source-disclosure", body), **body}


def verify_source_disclosure(
    disclosure: Mapping[str, Any],
    projection: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        if disclosure.get("schema") != "openline.claim-graph.source-disclosure.v1":
            errors.append("source_disclosure_schema_invalid")
        body = dict(disclosure)
        body.pop("disclosure_id", None)
        expected_id = content_id("source-disclosure", body)
        if disclosure.get("disclosure_id") != expected_id:
            errors.append("source_disclosure_id_mismatch")
        if disclosure.get("projection_id") != projection.get("projection_id"):
            errors.append("source_disclosure_projection_mismatch")
        if disclosure.get("graph_state_root") != receipt.get("graph_state_root"):
            errors.append("source_disclosure_state_mismatch")
        root = str(receipt["source_manifest_root"])
        if disclosure.get("source_manifest_root") != root:
            errors.append("source_disclosure_manifest_mismatch")

        disclosed_ids: set[str] = set()
        for entry in disclosure.get("sources", []):
            commitment = dict(entry["commitment"])
            source_id = str(commitment["source_id"])
            if source_id in disclosed_ids:
                errors.append(f"source_disclosure_duplicate:{source_id}")
            disclosed_ids.add(source_id)
            if not verify_merkle_proof(
                f"source:{source_id}", commitment, entry.get("proof", []), root
            ):
                errors.append(f"source_disclosure_proof_invalid:{source_id}")

        required_ids = {
            str(anchor["source_id"])
            for collection in (projection.get("claims", []), projection.get("relations", []))
            for entry in collection
            for anchor in entry.get("record", {}).get("provenance", [])
            if "source_id" in anchor
        }
        for missing in sorted(required_ids - disclosed_ids):
            errors.append(f"projection_source_not_disclosed:{missing}")
        for extra in sorted(disclosed_ids - required_ids):
            errors.append(f"unreferenced_source_disclosed:{extra}")
        if disclosure.get("omission_disclosure") != "only_sources_referenced_by_the_bounded_projection_are_disclosed":
            errors.append("source_disclosure_omission_notice_missing")
    except (KeyError, TypeError, ValueError):
        errors.append("source_disclosure_invalid")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "warnings": ["graph_state_receipt_authenticity_must_be_verified_separately"],
        "claim_boundary": "Source-manifest inclusion relative to a separately verified receipt; source availability and semantic support remain separate.",
    }
