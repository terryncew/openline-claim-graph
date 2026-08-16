"""Deterministic structural queries over admitted claim graphs.

These queries report graph structure.  They do not infer which branch is true.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping


def _claims(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item["claim_id"]): item for item in snapshot.get("claims", [])}


def _relations(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item["relation_id"]): item for item in snapshot.get("relations", [])}


def compare_snapshots(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_claims = _claims(left)
    right_claims = _claims(right)
    left_relations = _relations(left)
    right_relations = _relations(right)
    slots: dict[str, dict[str, list[str]]] = {}
    for side, claims in (("left", left_claims), ("right", right_claims)):
        for claim_id, claim in claims.items():
            if "slot" in claim:
                slots.setdefault(str(claim["slot"]), {"left": [], "right": []})[side].append(claim_id)
    changed_slots = []
    for slot, values in sorted(slots.items()):
        values = {side: sorted(ids) for side, ids in values.items()}
        if values["left"] != values["right"]:
            changed_slots.append({"slot": slot, **values})
    return {
        "schema": "openline.claim-graph.comparison.v1",
        "left_state_root": left.get("state_root"),
        "right_state_root": right.get("state_root"),
        "shared_claim_ids": sorted(set(left_claims) & set(right_claims)),
        "left_only_claim_ids": sorted(set(left_claims) - set(right_claims)),
        "right_only_claim_ids": sorted(set(right_claims) - set(left_claims)),
        "shared_relation_ids": sorted(set(left_relations) & set(right_relations)),
        "left_only_relation_ids": sorted(set(left_relations) - set(right_relations)),
        "right_only_relation_ids": sorted(set(right_relations) - set(left_relations)),
        "changed_slots": changed_slots,
        "claim_boundary": "Structural difference only; no branch is ranked or declared true.",
    }


def disagreement_report(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    claims = _claims(snapshot)
    relations = _relations(snapshot)
    by_slot: dict[str, list[str]] = {}
    for claim_id, claim in claims.items():
        if "slot" in claim:
            by_slot.setdefault(str(claim["slot"]), []).append(claim_id)
    disagreements = []
    for slot, claim_ids in sorted(by_slot.items()):
        value_groups: dict[str, list[str]] = {}
        for claim_id in claim_ids:
            value_groups.setdefault(repr(claims[claim_id].get("value")), []).append(claim_id)
        if len(value_groups) < 2:
            continue
        pairs = list(combinations(sorted(claim_ids), 2))
        mapped_pairs = []
        for left, right in pairs:
            matching = [
                relation_id
                for relation_id, relation in relations.items()
                if relation.get("relation") == "CONTRADICTS"
                and {relation.get("source_claim_id"), relation.get("target_claim_id")} == {left, right}
            ]
            if matching:
                mapped_pairs.append({"claim_ids": [left, right], "relation_ids": sorted(matching)})
        disagreements.append(
            {
                "slot": slot,
                "claim_ids": sorted(claim_ids),
                "variants": [
                    {
                        "claim_id": claim_id,
                        "value": claims[claim_id].get("value"),
                        "text": claims[claim_id].get("text"),
                        "source_ids": sorted(
                            {
                                str(anchor["source_id"])
                                for anchor in claims[claim_id].get("provenance", [])
                                if "source_id" in anchor
                            }
                        ),
                    }
                    for claim_id in sorted(claim_ids)
                ],
                "explicit_contradiction_pairs": mapped_pairs,
                "mapping_status": "EXPLICITLY_MAPPED" if len(mapped_pairs) == len(pairs) else "STRUCTURAL_VARIANCE_ONLY",
            }
        )
    return {
        "schema": "openline.claim-graph.disagreement-report.v1",
        "graph_state_root": snapshot.get("state_root"),
        "disagreements": disagreements,
        "claim_boundary": "Reports incompatible represented values; it does not adjudicate them.",
    }
