"""Independent verifier for the PLOS evidence-recall specimen.

This file intentionally does not import the candidate impact implementation.
It reimplements canonical hashing, graph exposure semantics, and receipt
signature verification so a shared bug is less likely to rubber-stamp the
checked-in result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from collections import deque
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


CORRECTION_ANCHOR = (
    "In the Results subsection of the Abstract. there are numbers reported which are "
    "inconsistent with those of the main text."
)
ORIGINAL_DOI = "10.1371/journal.pone.0223255"
CORRECTION_DOI = "10.1371/journal.pone.0249731"
CANONICAL_PROFILE = "openline.restricted-canonical-json.v1"
EMPTY_ROOT = hashlib.sha256(b"openline.claim-graph.merkle.empty.v1").hexdigest()
CORE_PROFILE = {
    "schema": "openline.claim-graph.profile.v1",
    "profile_id": "openline.claim-graph.core.v1",
    "canonicalization": CANONICAL_PROFILE,
    "claim_kinds": [
        "OBSERVATION",
        "MEASUREMENT",
        "SOURCE_ASSERTION",
        "DEFINITION",
        "ASSUMPTION",
        "INFERENCE",
        "CAUSAL_HYPOTHESIS",
        "PREDICTION",
        "VALUE_JUDGMENT",
        "ADJUDICATION",
        "OUTCOME",
        "UNRESOLVED_QUESTION",
    ],
    "relations": [
        "SUPPORTS",
        "CONTRADICTS",
        "DEPENDS_ON",
        "DEFINES",
        "DERIVED_FROM",
        "PREDICTS",
        "SUPERSEDES",
        "QUALIFIES",
        "ADJUDICATED_BY",
        "UNRESOLVED_BY",
    ],
    "provenance_modes": ["QUOTE", "PARAPHRASE", "INFERENCE", "AMBIGUOUS"],
    "span_unit": "utf8_byte_offset_half_open",
    "claim_boundary": (
        "This profile preserves typed claims, relations, source anchors, and state lineage. "
        "It does not certify semantic fidelity, completeness, truth, or decision wisdom."
    ),
}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        raise ValueError("floats forbidden")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", key): _normalize(item) for key, item in value.items()}
    raise ValueError(f"unsupported canonical type: {type(value).__name__}")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        _normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _content_id(namespace: str, value: Any) -> str:
    return f"{namespace}:sha256:{_hash(value)}"


def _leaf_hash(key: str, record: Any) -> bytes:
    return hashlib.sha256(b"leaf\x00" + key.encode() + b"\x00" + _canonical(record)).digest()


def _merkle_root(leaves: list[tuple[str, Any]]) -> str:
    if not leaves:
        return EMPTY_ROOT
    ordered = sorted(leaves, key=lambda item: item[0])
    if len({key for key, _record in ordered}) != len(ordered):
        raise ValueError("duplicate Merkle key")
    level = [_leaf_hash(key, record) for key, record in ordered]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256(b"node\x00" + level[index] + level[index + 1]).digest()
            for index in range(0, len(level), 2)
        ]
    return level[0].hex()


def _body(record: dict, id_field: str) -> dict:
    result = dict(record)
    result.pop(id_field, None)
    return result


def _verify_sources(sources: dict[str, dict]) -> bool:
    for source_id, source in sources.items():
        encoded = source["content"].encode("utf-8")
        if source_id != source["source_id"]:
            return False
        if source_id != f"source:sha256:{hashlib.sha256(encoded).hexdigest()}":
            return False
        if source["byte_length"] != len(encoded):
            return False
    return True


def _verify_snapshot(snapshot: dict, sources: dict[str, dict]) -> bool:
    claim_ids = set()
    for claim in snapshot["claims"]:
        if claim["claim_id"] != _content_id("claim", _body(claim, "claim_id")):
            return False
        claim_ids.add(claim["claim_id"])
        for anchor in claim.get("provenance", []):
            source = sources.get(anchor["source_id"])
            if source is None:
                return False
            encoded = source["content"].encode("utf-8")
            start, end = anchor["span"]["start"], anchor["span"]["end"]
            if start < 0 or end <= start or end > len(encoded):
                return False
            quote = encoded[start:end]
            if hashlib.sha256(quote).hexdigest() != anchor["quote_sha256"]:
                return False
            if anchor["mode"] == "QUOTE" and quote != claim["text"].encode("utf-8"):
                return False
    for relation in snapshot["relations"]:
        if relation["relation_id"] != _content_id("relation", _body(relation, "relation_id")):
            return False
        if relation["source_claim_id"] not in claim_ids or relation["target_claim_id"] not in claim_ids:
            return False

    leaves = [("profile", CORE_PROFILE)]
    leaves += [(f"claim:{item['claim_id']}", item) for item in snapshot["claims"]]
    leaves += [(f"relation:{item['relation_id']}", item) for item in snapshot["relations"]]
    content_root = _merkle_root(leaves)
    if snapshot["content_root"] != content_root:
        return False
    if snapshot["profile_hash"] != _hash(CORE_PROFILE):
        return False
    if snapshot["delta_root"] != _hash(snapshot["delta"]):
        return False
    descriptor = {
        "schema": "openline.claim-graph.state.v1",
        "profile_hash": _hash(CORE_PROFILE),
        "content_root": content_root,
        "parent_state_roots": sorted(snapshot["parent_state_roots"]),
        "delta_root": snapshot["delta_root"],
        "merge_resolutions_root": _hash(snapshot["merge_resolutions"]),
    }
    return snapshot["state_root"] == _hash(descriptor)


def _verify_receipt(receipt: dict, snapshot: dict, sources: dict[str, dict], pin: str) -> bool:
    body = dict(receipt)
    body.pop("payload_hash", None)
    body.pop("proof", None)
    encoded = _canonical(body)
    if receipt["payload_hash"] != hashlib.sha256(encoded).hexdigest():
        return False
    if receipt["proof_options"]["public_key"] != pin:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pin)).verify(
            bytes.fromhex(receipt["proof"]["signature"]), encoded
        )
    except (InvalidSignature, ValueError):
        return False
    if receipt["graph_state_root"] != snapshot["state_root"]:
        return False
    if receipt["graph_content_root"] != snapshot["content_root"]:
        return False
    if receipt["claim_count"] != len(snapshot["claims"]):
        return False
    if receipt["relation_count"] != len(snapshot["relations"]):
        return False

    referenced = {
        anchor["source_id"]
        for collection in (snapshot["claims"], snapshot["relations"])
        for record in collection
        for anchor in record.get("provenance", [])
    }
    leaves = []
    for source_id in sorted(referenced):
        source = sources[source_id]
        commitment = {
            "source_id": source_id,
            "media_type": source["media_type"],
            "encoding": source["encoding"],
            "byte_length": source["byte_length"],
            **({"locator": source["locator"]} if "locator" in source else {}),
        }
        leaves.append((f"source:{source_id}", commitment))
    return receipt["source_manifest_root"] == _merkle_root(leaves) and receipt["source_count"] == len(leaves)


def _overlaps(anchor: dict, scopes: dict[str, list[tuple[int, int]] | None]) -> bool:
    if anchor["source_id"] not in scopes:
        return False
    if scopes[anchor["source_id"]] is None:
        return True
    start, end = anchor["span"]["start"], anchor["span"]["end"]
    return any(start < right and left < end for left, right in scopes[anchor["source_id"]])


def _direction(relation: dict) -> tuple[str, str]:
    if relation["relation"] == "SUPPORTS":
        return relation["source_claim_id"], relation["target_claim_id"]
    if relation["relation"] in {"DEPENDS_ON", "DERIVED_FROM"}:
        return relation["target_claim_id"], relation["source_claim_id"]
    raise ValueError("unsupported admitted relation")


def _reach(origins: set[str], adjacency: dict[str, list[tuple[str, str]]]) -> set[str]:
    found = set(origins)
    queue = deque(origins)
    while queue:
        current = queue.popleft()
        for dependent, _relation_id in adjacency.get(current, []):
            if dependent not in found:
                found.add(dependent)
                queue.append(dependent)
    return found


def _oracle(snapshot: dict, event: dict, policy: dict) -> dict[str, set[str]]:
    claims = {item["claim_id"]: item for item in snapshot["claims"]}
    relations = {item["relation_id"]: item for item in snapshot["relations"]}
    hard_ids = set(policy["hard_relation_ids"])
    advisory_ids = set(policy["advisory_relation_ids"])
    modes = set(policy["hard_provenance_modes"])
    scopes = {
        item["source_id"]: (
            [(span["start"], span["end"]) for span in item["spans"]]
            if "spans" in item
            else None
        )
        for item in event["affected"]
    }
    affected_anchors: dict[str, list[dict]] = {}
    live_anchors: dict[str, list[dict]] = {}
    for claim_id, claim in claims.items():
        for anchor in claim.get("provenance", []):
            if anchor["mode"] not in modes:
                continue
            destination = affected_anchors if _overlaps(anchor, scopes) else live_anchors
            destination.setdefault(claim_id, []).append(anchor)
    exposed = set(affected_anchors)
    hard: dict[str, list[tuple[str, str]]] = {}
    advisory: dict[str, list[tuple[str, str]]] = {}
    requirements: dict[str, list[str]] = {}
    supporters: dict[str, list[str]] = {}
    for relation_id in hard_ids | advisory_ids:
        relation = relations[relation_id]
        prerequisite, dependent = _direction(relation)
        (hard if relation_id in hard_ids else advisory).setdefault(prerequisite, []).append(
            (dependent, relation_id)
        )
        if relation_id in hard_ids:
            if relation["relation"] == "SUPPORTS":
                supporters.setdefault(dependent, []).append(prerequisite)
            else:
                requirements.setdefault(dependent, []).append(prerequisite)

    hard_touched = _reach(exposed, hard)
    grounded: set[str] = set()
    while True:
        previous = set(grounded)
        for claim_id in claims:
            if claim_id in grounded:
                continue
            claim_supporters = supporters.get(claim_id, [])
            own_basis = claim_id in live_anchors or (claim_id not in exposed and not claim_supporters)
            supported_basis = any(item in grounded for item in claim_supporters)
            if own_basis or supported_basis:
                grounded.add(claim_id)
        if grounded == previous:
            break

    invalid = set(claims) - grounded
    while True:
        previous = set(invalid)
        for claim_id in claims:
            if any(item in invalid for item in requirements.get(claim_id, [])):
                invalid.add(claim_id)
        if invalid == previous:
            break
    alive = set(claims) - invalid

    quarantine = hard_touched - alive
    states = {(origin, False) for origin in exposed}
    queue = deque(states)
    advisory_touched: set[str] = set()
    while queue:
        current, used = queue.popleft()
        for is_advisory, adjacency in ((False, hard), (True, advisory)):
            for dependent, _relation_id in adjacency.get(current, []):
                next_used = used or is_advisory
                state = (dependent, next_used)
                if state not in states:
                    states.add(state)
                    queue.append(state)
                if next_used:
                    advisory_touched.add(dependent)
    review = advisory_touched - quarantine
    survives = (hard_touched & alive) - review
    unaffected = set(claims) - quarantine - survives - review
    return {
        "source_exposed": exposed,
        "quarantine": quarantine,
        "survives": survives,
        "affected_unresolved": review,
        "unaffected": unaffected,
        "decisions_touched": set(policy["decision_claim_ids"]) & (quarantine | survives | review),
    }


def verify(directory: Path) -> dict:
    snapshot = _read(directory / "accepted.snapshot.json")
    accepted_sources_list = _read(directory / "accepted-sources.json")["sources"]
    all_sources_list = _read(directory / "sources.json")["sources"]
    accepted_sources = {item["source_id"]: item for item in accepted_sources_list}
    all_sources = {item["source_id"]: item for item in all_sources_list}
    receipt = _read(directory / "accepted.receipt.json")
    pin = _read(directory / "public-key.json")["public_key"]
    event = _read(directory / "source-status-event.json")
    policy = _read(directory / "impact-policy.json")
    report = _read(directory / "impact-report.json")
    expected = _read(directory / "expected.json")
    baseline = _read(directory / "direct-only-baseline.json")
    specimen_report = _read(directory / "report.json")
    upstream_verification = _read(directory / "upstream-verification.json")

    correction_sources = [
        item for item in all_sources_list if item.get("locator") == f"https://doi.org/{CORRECTION_DOI}"
    ]
    anchor_exact = len(correction_sources) == 1 and correction_sources[0]["content"] == CORRECTION_ANCHOR
    evidence_exact = False
    if anchor_exact and len(event.get("evidence", [])) == 1:
        anchor = event["evidence"][0]
        source = all_sources.get(anchor.get("source_id"))
        if source:
            encoded = source["content"].encode("utf-8")
            start, end = anchor["span"]["start"], anchor["span"]["end"]
            evidence_exact = (
                encoded[start:end].decode("utf-8") == CORRECTION_ANCHOR
                and hashlib.sha256(encoded[start:end]).hexdigest() == anchor["quote_sha256"]
            )

    event_id_valid = event["event_id"] == _content_id("source-status-event", _body(event, "event_id"))
    policy_id_valid = policy["policy_id"] == _content_id("claim-impact-policy", _body(policy, "policy_id"))
    report_id_valid = report["report_id"] == _content_id("claim-impact-report", _body(report, "report_id"))
    oracle = _oracle(snapshot, event, policy)
    reported = {
        name: {item["claim_id"] for item in report["classifications"][name]}
        for name in ("quarantine", "survives", "affected_unresolved", "unaffected")
    }
    reported["source_exposed"] = set(report["source_exposed_claim_ids"])
    reported["decisions_touched"] = set(report["decision_claim_ids_touched"])
    classifications_match = all(reported[name] == oracle[name] for name in oracle)

    expected_sets = {name: set(values) for name, values in expected["expected"].items()}
    expected_match = (
        oracle["quarantine"] == expected_sets["quarantine"]
        and oracle["survives"] == expected_sets["survives"]
        and oracle["affected_unresolved"] == expected_sets["affected_unresolved"]
        and oracle["decisions_touched"] == expected_sets["decision_claim_ids_touched"]
    )
    direct_only_match = (
        set(baseline["direct_claim_ids"]) == oracle["source_exposed"]
        and set(baseline["transitive_quarantine_claim_ids_missed"])
        == oracle["quarantine"] - oracle["source_exposed"]
        and baseline["transitive_quarantine_missed"] == 2
    )
    summary_match = report["summary"] == {
        "source_exposed": len(oracle["source_exposed"]),
        "quarantine": len(oracle["quarantine"]),
        "survives": len(oracle["survives"]),
        "affected_unresolved": len(oracle["affected_unresolved"]),
        "unaffected": len(oracle["unaffected"]),
        "decisions_touched": len(oracle["decisions_touched"]),
    }
    witness_paths_valid = True
    hard_ids = set(policy["hard_relation_ids"])
    advisory_ids = set(policy["advisory_relation_ids"])
    relation_ids = {item["relation_id"] for item in snapshot["relations"]}
    for name in ("quarantine", "affected_unresolved"):
        for item in report["classifications"][name]:
            path = item.get("witness_path")
            if path is None:
                witness_paths_valid = False
                continue
            current = path["origin_claim_id"]
            advisory_seen = False
            for step in path["steps"]:
                if step["relation_id"] not in relation_ids or step["from_claim_id"] != current:
                    witness_paths_valid = False
                current = step["to_claim_id"]
                if step["relation_id"] in advisory_ids:
                    advisory_seen = True
                elif step["relation_id"] not in hard_ids:
                    witness_paths_valid = False
            if current != item["claim_id"]:
                witness_paths_valid = False
            if name == "affected_unresolved" and not advisory_seen:
                witness_paths_valid = False

    checks = {
        "all_sources_content_addressed": _verify_sources(all_sources),
        "accepted_snapshot_reproduced": _verify_snapshot(snapshot, accepted_sources),
        "accepted_receipt_signature_and_binding": _verify_receipt(
            receipt, snapshot, accepted_sources, pin
        ),
        "accepted_state_root_bound_by_policy": policy["accepted_state_root"] == snapshot["state_root"],
        "event_id_reproduced": event_id_valid,
        "policy_id_reproduced": policy_id_valid,
        "report_id_reproduced": report_id_valid,
        "rendered_review_hash_bound": hashlib.sha256(
            (directory / "review.html").read_bytes()
        ).hexdigest()
        == specimen_report["review_sha256"],
        "real_correction_anchor_exact": anchor_exact,
        "current_plos_api_excerpt_check": upstream_verification["exact_match"],
        "event_evidence_span_exact": evidence_exact,
        "original_doi_present": any(ORIGINAL_DOI in str(item.get("locator", "")) for item in accepted_sources_list),
        "oracle_matches_report": classifications_match,
        "oracle_matches_predeclared_specimen_expectation": expected_match,
        "summary_matches_oracle": summary_match,
        "witness_paths_valid": witness_paths_valid,
        "direct_only_baseline_reproduced": direct_only_match,
        "two_transitive_claims_found_beyond_direct_lookup": len(oracle["quarantine"] - oracle["source_exposed"]) == 2,
        "independent_support_prevents_over_quarantine": len(oracle["survives"]) == 1,
        "advisory_edge_yields_review_not_quarantine": len(oracle["affected_unresolved"]) == 1,
        "exactly_one_accepted_decision_reopened": len(oracle["decisions_touched"]) == 1,
    }
    return {
        "schema": "openline.claim-impact.independent-verification.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "summary": report["summary"],
        "claim_boundary": (
            "Independent code reproduced the conditional graph result and cryptographic bindings. "
            "It does not independently validate the authored dependency edges, extraction completeness, "
            "scientific truth, or market value."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, default=Path("artifacts/plos-correction-impact"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.artifact)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
