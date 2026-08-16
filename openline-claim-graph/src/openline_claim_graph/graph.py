"""Typed claim graphs, temporal state commitments, and bounded projections.

The module makes a deliberately narrow claim: it can preserve and verify the
identity, source anchors, lineage, and selected structure of an argument.  It
does not determine whether a claim or relation is true.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Iterable, Mapping, Sequence

from .canonical import PROFILE as CANONICAL_PROFILE
from .canonical import canonical_json, content_id, hash_object, sha256_hex
from .merkle import merkle_proof, merkle_root, verify_merkle_proof


GRAPH_SCHEMA = "openline.claim-graph.snapshot.v1"
CLAIM_SCHEMA = "openline.claim.v1"
EDGE_SCHEMA = "openline.claim-relation.v1"
SOURCE_SCHEMA = "openline.source.v1"
PROJECTION_SCHEMA = "openline.claim-graph.projection.v1"

CLAIM_KINDS = (
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
)
RELATIONS = (
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
)
PROVENANCE_MODES = ("QUOTE", "PARAPHRASE", "INFERENCE", "AMBIGUOUS")

CORE_PROFILE = {
    "schema": "openline.claim-graph.profile.v1",
    "profile_id": "openline.claim-graph.core.v1",
    "canonicalization": CANONICAL_PROFILE,
    "claim_kinds": list(CLAIM_KINDS),
    "relations": list(RELATIONS),
    "provenance_modes": list(PROVENANCE_MODES),
    "span_unit": "utf8_byte_offset_half_open",
    "claim_boundary": (
        "This profile preserves typed claims, relations, source anchors, and state lineage. "
        "It does not certify semantic fidelity, completeness, truth, or decision wisdom."
    ),
}
PROFILE_HASH = hash_object(CORE_PROFILE)


class GraphValidationError(ValueError):
    """Raised when a graph cannot be admitted under the core profile."""


def build_source(content: str, *, media_type: str = "text/plain", locator: str | None = None) -> dict[str, Any]:
    if not isinstance(content, str):
        raise TypeError("prototype sources must be UTF-8 text")
    encoded = content.encode("utf-8")
    source: dict[str, Any] = {
        "schema": SOURCE_SCHEMA,
        "source_id": f"source:sha256:{sha256_hex(encoded)}",
        "media_type": media_type,
        "encoding": "utf-8",
        "byte_length": len(encoded),
        "content": content,
    }
    if locator is not None:
        source["locator"] = locator
    return source


def source_commitment(source: Mapping[str, Any]) -> dict[str, Any]:
    """Return the portable commitment; raw source content intentionally stays out."""

    return {
        "source_id": source["source_id"],
        "media_type": source["media_type"],
        "encoding": source["encoding"],
        "byte_length": source["byte_length"],
        **({"locator": source["locator"]} if "locator" in source else {}),
    }


def source_span(source: Mapping[str, Any], quote: str, *, occurrence: int = 1) -> tuple[int, int]:
    if occurrence < 1:
        raise ValueError("occurrence must be at least 1")
    haystack = str(source["content"]).encode("utf-8")
    needle = quote.encode("utf-8")
    start = -1
    cursor = 0
    for _ in range(occurrence):
        start = haystack.find(needle, cursor)
        if start < 0:
            raise ValueError("quote not found in source")
        cursor = start + len(needle)
    return start, start + len(needle)


def provenance_anchor(
    source: Mapping[str, Any],
    quote: str,
    *,
    mode: str,
    asserted_by: str,
    occurrence: int = 1,
) -> dict[str, Any]:
    mode = mode.upper()
    if mode not in PROVENANCE_MODES:
        raise ValueError(f"unsupported provenance mode: {mode}")
    if not asserted_by:
        raise ValueError("asserted_by is required")
    start, end = source_span(source, quote, occurrence=occurrence)
    return {
        "mode": mode,
        "source_id": source["source_id"],
        "span": {"start": start, "end": end},
        "quote_sha256": sha256_hex(quote.encode("utf-8")),
        "asserted_by": asserted_by,
    }


def _sort_provenance(provenance: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (dict(item) for item in provenance),
        key=lambda item: (
            str(item.get("source_id", "")),
            int(dict(item.get("span", {})).get("start", -1)),
            int(dict(item.get("span", {})).get("end", -1)),
            str(item.get("mode", "")),
            str(item.get("asserted_by", "")),
        ),
    )


def create_claim(
    *,
    kind: str,
    text: str,
    asserted_by: str,
    provenance: Iterable[Mapping[str, Any]] = (),
    slot: str | None = None,
    value: Any | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": CLAIM_SCHEMA,
        "kind": kind.upper(),
        "text": text,
        "asserted_by": asserted_by,
        "provenance": _sort_provenance(provenance),
    }
    if (slot is None) != (value is None):
        raise ValueError("slot and value must either both be present or both be absent")
    if slot is not None:
        body["slot"] = slot
        body["value"] = value
    return {"claim_id": content_id("claim", body), **body}


def create_relation(
    *,
    source_claim_id: str,
    target_claim_id: str,
    relation: str,
    asserted_by: str,
    provenance: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    body = {
        "schema": EDGE_SCHEMA,
        "source_claim_id": source_claim_id,
        "target_claim_id": target_claim_id,
        "relation": relation.upper(),
        "asserted_by": asserted_by,
        "provenance": _sort_provenance(provenance),
    }
    return {"relation_id": content_id("relation", body), **body}


def _source_bytes(source: Mapping[str, Any]) -> bytes:
    if source.get("schema") != SOURCE_SCHEMA or source.get("encoding") != "utf-8":
        raise GraphValidationError("unsupported source schema or encoding")
    return str(source["content"]).encode("utf-8")


def validate_sources(sources: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    for key, source in sources.items():
        try:
            encoded = _source_bytes(source)
            expected = f"source:sha256:{sha256_hex(encoded)}"
            if key != source.get("source_id"):
                errors.append(f"source_store_key_mismatch:{key}")
            if source.get("source_id") != expected:
                errors.append(f"source_hash_mismatch:{key}")
            if source.get("byte_length") != len(encoded):
                errors.append(f"source_length_mismatch:{key}")
            if not isinstance(source.get("media_type"), str) or not source.get("media_type"):
                errors.append(f"source_media_type_invalid:{key}")
        except (KeyError, TypeError, GraphValidationError):
            errors.append(f"source_invalid:{key}")
    return sorted(set(errors))


def _verify_anchor(
    anchor: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    *,
    record_text: str | None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        mode = str(anchor["mode"]).upper()
        if mode not in PROVENANCE_MODES:
            errors.append("provenance_mode_invalid")
        if not str(anchor["asserted_by"]):
            errors.append("provenance_actor_missing")
        source_id = str(anchor["source_id"])
        source = sources[source_id]
        source_bytes = _source_bytes(source)
        span = dict(anchor["span"])
        start = int(span["start"])
        end = int(span["end"])
        if start < 0 or end < start or end > len(source_bytes):
            errors.append("provenance_span_invalid")
            return errors, warnings
        quote = source_bytes[start:end]
        if sha256_hex(quote) != anchor.get("quote_sha256"):
            errors.append("provenance_quote_hash_mismatch")
        if mode == "QUOTE":
            if record_text is None or record_text.encode("utf-8") != quote:
                errors.append("quote_mode_text_mismatch")
        else:
            warnings.append(f"semantic_mapping_unverified:{mode.lower()}")
    except KeyError as exc:
        errors.append(f"provenance_missing_field:{exc.args[0]}")
    except (TypeError, ValueError, UnicodeError, GraphValidationError):
        errors.append("provenance_invalid")
    return errors, warnings


def _record_body(record: Mapping[str, Any], id_field: str) -> dict[str, Any]:
    body = dict(record)
    body.pop(id_field, None)
    return body


def _validate_claim(
    claim: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    claim_id = str(claim.get("claim_id", ""))
    if claim.get("schema") != CLAIM_SCHEMA:
        errors.append(f"claim_schema_invalid:{claim_id}")
    if claim.get("kind") not in CLAIM_KINDS:
        errors.append(f"claim_kind_invalid:{claim_id}")
    if not isinstance(claim.get("text"), str) or not claim.get("text"):
        errors.append(f"claim_text_invalid:{claim_id}")
    if not isinstance(claim.get("asserted_by"), str) or not claim.get("asserted_by"):
        errors.append(f"claim_actor_missing:{claim_id}")
    if ("slot" in claim) != ("value" in claim):
        errors.append(f"claim_slot_value_incomplete:{claim_id}")
    expected = content_id("claim", _record_body(claim, "claim_id"))
    if claim_id != expected:
        errors.append(f"claim_id_mismatch:{claim_id}")
    provenance = claim.get("provenance")
    if not isinstance(provenance, list):
        errors.append(f"claim_provenance_invalid:{claim_id}")
    elif not provenance:
        warnings.append(f"claim_unanchored:{claim_id}")
    else:
        for anchor in provenance:
            if not isinstance(anchor, Mapping):
                errors.append(f"claim_provenance_invalid:{claim_id}")
                continue
            anchor_errors, anchor_warnings = _verify_anchor(anchor, sources, record_text=str(claim.get("text", "")))
            errors.extend(f"{item}:{claim_id}" for item in anchor_errors)
            warnings.extend(f"{item}:{claim_id}" for item in anchor_warnings)
    return errors, warnings


def _validate_relation(
    relation: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    claim_ids: set[str],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    relation_id = str(relation.get("relation_id", ""))
    if relation.get("schema") != EDGE_SCHEMA:
        errors.append(f"relation_schema_invalid:{relation_id}")
    if relation.get("relation") not in RELATIONS:
        errors.append(f"relation_type_invalid:{relation_id}")
    if relation.get("source_claim_id") not in claim_ids or relation.get("target_claim_id") not in claim_ids:
        errors.append(f"relation_dangling:{relation_id}")
    if not isinstance(relation.get("asserted_by"), str) or not relation.get("asserted_by"):
        errors.append(f"relation_actor_missing:{relation_id}")
    expected = content_id("relation", _record_body(relation, "relation_id"))
    if relation_id != expected:
        errors.append(f"relation_id_mismatch:{relation_id}")
    provenance = relation.get("provenance")
    if not isinstance(provenance, list):
        errors.append(f"relation_provenance_invalid:{relation_id}")
    elif not provenance:
        warnings.append(f"relation_unanchored:{relation_id}")
    else:
        for anchor in provenance:
            if not isinstance(anchor, Mapping):
                errors.append(f"relation_provenance_invalid:{relation_id}")
                continue
            anchor_errors, anchor_warnings = _verify_anchor(anchor, sources, record_text=None)
            errors.extend(f"{item}:{relation_id}" for item in anchor_errors)
            warnings.extend(f"{item}:{relation_id}" for item in anchor_warnings)
    return errors, warnings


def graph_leaves(snapshot: Mapping[str, Any]) -> list[tuple[str, Any]]:
    leaves: list[tuple[str, Any]] = [("profile", CORE_PROFILE)]
    leaves.extend((f"claim:{claim['claim_id']}", claim) for claim in snapshot.get("claims", []))
    leaves.extend((f"relation:{edge['relation_id']}", edge) for edge in snapshot.get("relations", []))
    return leaves


def _record_maps(snapshot: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    claims = {str(item["claim_id"]): dict(item) for item in snapshot.get("claims", [])}
    relations = {str(item["relation_id"]): dict(item) for item in snapshot.get("relations", [])}
    return claims, relations


def _union_parent_records(
    parent_snapshots: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    claims: dict[str, dict[str, Any]] = {}
    relations: dict[str, dict[str, Any]] = {}
    for parent in parent_snapshots:
        parent_claims, parent_relations = _record_maps(parent)
        claims.update(parent_claims)
        relations.update(parent_relations)
    return claims, relations


def _delta(
    claims: Mapping[str, Any],
    relations: Mapping[str, Any],
    parent_claims: Mapping[str, Any],
    parent_relations: Mapping[str, Any],
    removal_reasons: Mapping[str, str],
    *,
    genesis: bool,
) -> dict[str, Any]:
    removed = sorted((set(parent_claims) | set(parent_relations)) - (set(claims) | set(relations)))
    reasons = [{"record_id": item, "reason": removal_reasons[item]} for item in removed if item in removal_reasons]
    return {
        "schema": "openline.claim-graph.delta.v1",
        "basis": "genesis" if genesis else "union_of_named_parents",
        "added_claim_ids": sorted(set(claims) - set(parent_claims)),
        "removed_claim_ids": sorted(set(parent_claims) - set(claims)),
        "added_relation_ids": sorted(set(relations) - set(parent_relations)),
        "removed_relation_ids": sorted(set(parent_relations) - set(relations)),
        "removal_reasons": reasons,
    }


def _cross_parent_conflicts(parent_snapshots: Sequence[Mapping[str, Any]]) -> dict[str, set[str]]:
    if len(parent_snapshots) < 2:
        return {}
    slot_by_parent: list[dict[str, set[str]]] = []
    for parent in parent_snapshots:
        mapping: dict[str, set[str]] = {}
        for claim in parent.get("claims", []):
            if "slot" in claim:
                mapping.setdefault(str(claim["slot"]), set()).add(str(claim["claim_id"]))
        slot_by_parent.append(mapping)
    conflicts: dict[str, set[str]] = {}
    all_slots = set().union(*(set(mapping) for mapping in slot_by_parent))
    for slot in all_slots:
        variants = set().union(*(mapping.get(slot, set()) for mapping in slot_by_parent))
        carrying_parents = sum(1 for mapping in slot_by_parent if slot in mapping)
        if carrying_parents >= 2 and len(variants) > 1:
            conflicts[slot] = variants
    return conflicts


def _has_contradiction(relations: Mapping[str, Mapping[str, Any]], left: str, right: str) -> bool:
    return any(
        relation.get("relation") == "CONTRADICTS"
        and {relation.get("source_claim_id"), relation.get("target_claim_id")} == {left, right}
        for relation in relations.values()
    )


def _validate_merge(
    *,
    parent_snapshots: Sequence[Mapping[str, Any]],
    current_claims: Mapping[str, Mapping[str, Any]],
    current_relations: Mapping[str, Mapping[str, Any]],
    resolutions: Sequence[Mapping[str, Any]],
    removal_reasons: Mapping[str, str],
) -> list[str]:
    errors: list[str] = []
    conflicts = _cross_parent_conflicts(parent_snapshots)
    by_slot = {str(item.get("slot", "")): dict(item) for item in resolutions}
    if len(by_slot) != len(resolutions):
        errors.append("merge_resolution_duplicate_slot")
    if set(by_slot) != set(conflicts):
        for slot in sorted(set(conflicts) - set(by_slot)):
            errors.append(f"merge_conflict_unresolved:{slot}")
        for slot in sorted(set(by_slot) - set(conflicts)):
            errors.append(f"merge_resolution_without_conflict:{slot}")

    for slot, variants in conflicts.items():
        resolution = by_slot.get(slot)
        if not resolution:
            continue
        action = resolution.get("action")
        declared = set(map(str, resolution.get("parent_claim_ids", [])))
        if declared != variants:
            errors.append(f"merge_parent_claim_set_mismatch:{slot}")
            continue
        if not str(resolution.get("reason", "")):
            errors.append(f"merge_reason_missing:{slot}")
        if action == "PRESERVE_ALL":
            if not variants.issubset(current_claims):
                errors.append(f"merge_preserve_all_missing_claim:{slot}")
            for left, right in combinations(sorted(variants), 2):
                if not _has_contradiction(current_relations, left, right):
                    errors.append(f"merge_preserve_all_missing_contradiction:{slot}")
        elif action == "SELECT":
            selected = str(resolution.get("selected_claim_id", ""))
            if selected not in variants or selected not in current_claims:
                errors.append(f"merge_selected_claim_invalid:{slot}")
            for rejected in variants - {selected}:
                if rejected in current_claims:
                    errors.append(f"merge_rejected_claim_retained:{slot}")
                if rejected not in removal_reasons:
                    errors.append(f"merge_rejected_claim_reason_missing:{slot}")
        elif action == "SUPERSEDE":
            replacement = str(resolution.get("replacement_claim_id", ""))
            if replacement in variants or replacement not in current_claims:
                errors.append(f"merge_replacement_claim_invalid:{slot}")
            if variants & set(current_claims):
                errors.append(f"merge_superseded_parent_claim_retained:{slot}")
            for old in variants:
                if old not in removal_reasons:
                    errors.append(f"merge_superseded_claim_reason_missing:{slot}")
        else:
            errors.append(f"merge_action_invalid:{slot}")
    return errors


def create_snapshot(
    *,
    claims: Iterable[Mapping[str, Any]],
    relations: Iterable[Mapping[str, Any]],
    parent_snapshots: Sequence[Mapping[str, Any]] = (),
    merge_resolutions: Sequence[Mapping[str, Any]] = (),
    removal_reasons: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    removal_reasons = dict(removal_reasons or {})
    claim_list = sorted((dict(item) for item in claims), key=lambda item: str(item["claim_id"]))
    relation_list = sorted((dict(item) for item in relations), key=lambda item: str(item["relation_id"]))
    current_claims = {str(item["claim_id"]): item for item in claim_list}
    current_relations = {str(item["relation_id"]): item for item in relation_list}
    if len(current_claims) != len(claim_list) or len(current_relations) != len(relation_list):
        raise GraphValidationError("duplicate claim or relation id")

    parent_roots = sorted(str(item["state_root"]) for item in parent_snapshots)
    if len(parent_roots) != len(set(parent_roots)):
        raise GraphValidationError("duplicate parent state root")
    parent_claims, parent_relations = _union_parent_records(parent_snapshots)
    expected_removed = (set(parent_claims) | set(parent_relations)) - (set(current_claims) | set(current_relations))
    missing_reasons = expected_removed - set(removal_reasons)
    extra_reasons = set(removal_reasons) - expected_removed
    if missing_reasons:
        raise GraphValidationError(f"silent parent record removal: {sorted(missing_reasons)}")
    if extra_reasons:
        raise GraphValidationError(f"removal reason without removed record: {sorted(extra_reasons)}")
    if len(parent_snapshots) < 2 and merge_resolutions:
        raise GraphValidationError("merge resolutions require at least two parents")
    merge_errors = _validate_merge(
        parent_snapshots=parent_snapshots,
        current_claims=current_claims,
        current_relations=current_relations,
        resolutions=merge_resolutions,
        removal_reasons=removal_reasons,
    )
    if merge_errors:
        raise GraphValidationError("; ".join(merge_errors))

    provisional = {
        "schema": GRAPH_SCHEMA,
        "profile_hash": PROFILE_HASH,
        "parent_state_roots": parent_roots,
        "claims": claim_list,
        "relations": relation_list,
        "merge_resolutions": sorted((dict(item) for item in merge_resolutions), key=lambda item: str(item["slot"])),
    }
    content_root = merkle_root(graph_leaves(provisional))
    delta = _delta(
        current_claims,
        current_relations,
        parent_claims,
        parent_relations,
        removal_reasons,
        genesis=not parent_snapshots,
    )
    delta_root = hash_object(delta)
    state_descriptor = {
        "schema": "openline.claim-graph.state.v1",
        "profile_hash": PROFILE_HASH,
        "content_root": content_root,
        "parent_state_roots": parent_roots,
        "delta_root": delta_root,
        "merge_resolutions_root": hash_object(provisional["merge_resolutions"]),
    }
    return {
        **provisional,
        "content_root": content_root,
        "delta": delta,
        "delta_root": delta_root,
        "state_root": hash_object(state_descriptor),
    }


def validate_snapshot(
    snapshot: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    *,
    parent_snapshots: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    errors = validate_sources(sources)
    warnings: list[str] = []
    try:
        if snapshot.get("schema") != GRAPH_SCHEMA:
            errors.append("snapshot_schema_invalid")
        if snapshot.get("profile_hash") != PROFILE_HASH:
            errors.append("snapshot_profile_mismatch")
        claims, relations = _record_maps(snapshot)
        if len(claims) != len(snapshot.get("claims", [])):
            errors.append("duplicate_claim_id")
        if len(relations) != len(snapshot.get("relations", [])):
            errors.append("duplicate_relation_id")
        for claim in snapshot.get("claims", []):
            item_errors, item_warnings = _validate_claim(claim, sources)
            errors.extend(item_errors)
            warnings.extend(item_warnings)
        for relation in snapshot.get("relations", []):
            item_errors, item_warnings = _validate_relation(relation, sources, set(claims))
            errors.extend(item_errors)
            warnings.extend(item_warnings)
        expected_content_root = merkle_root(graph_leaves(snapshot))
        if snapshot.get("content_root") != expected_content_root:
            errors.append("content_root_mismatch")
        if snapshot.get("delta_root") != hash_object(snapshot.get("delta")):
            errors.append("delta_root_mismatch")
        descriptor = {
            "schema": "openline.claim-graph.state.v1",
            "profile_hash": PROFILE_HASH,
            "content_root": expected_content_root,
            "parent_state_roots": sorted(map(str, snapshot.get("parent_state_roots", []))),
            "delta_root": snapshot.get("delta_root"),
            "merge_resolutions_root": hash_object(snapshot.get("merge_resolutions", [])),
        }
        if snapshot.get("state_root") != hash_object(descriptor):
            errors.append("state_root_mismatch")

        if parent_snapshots is None:
            if snapshot.get("parent_state_roots"):
                warnings.append("lineage_not_reproduced_parent_snapshots_absent")
        else:
            reproduced = create_snapshot(
                claims=snapshot.get("claims", []),
                relations=snapshot.get("relations", []),
                parent_snapshots=parent_snapshots,
                merge_resolutions=snapshot.get("merge_resolutions", []),
                removal_reasons={
                    str(item["record_id"]): str(item["reason"])
                    for item in snapshot.get("delta", {}).get("removal_reasons", [])
                },
            )
            for field in ("parent_state_roots", "content_root", "delta", "delta_root", "state_root"):
                if snapshot.get(field) != reproduced.get(field):
                    errors.append(f"lineage_reproduction_mismatch:{field}")
    except (KeyError, TypeError, ValueError, GraphValidationError) as exc:
        errors.append(f"snapshot_invalid:{type(exc).__name__}")
    return {"valid": not errors, "errors": sorted(set(errors)), "warnings": sorted(set(warnings))}


def create_projection(
    snapshot: Mapping[str, Any],
    *,
    claim_ids: Iterable[str],
    relation_ids: Iterable[str] = (),
    purpose: str,
    selected_by: str,
) -> dict[str, Any]:
    claims, relations = _record_maps(snapshot)
    selected_claims = sorted(set(map(str, claim_ids)))
    selected_relations = sorted(set(map(str, relation_ids)))
    unknown = (set(selected_claims) - set(claims)) | (set(selected_relations) - set(relations))
    if unknown:
        raise GraphValidationError(f"projection references unknown records: {sorted(unknown)}")
    for relation_id in selected_relations:
        relation = relations[relation_id]
        endpoints = {str(relation["source_claim_id"]), str(relation["target_claim_id"])}
        if not endpoints.issubset(selected_claims):
            raise GraphValidationError(f"projection relation has omitted endpoint: {relation_id}")

    leaves = graph_leaves(snapshot)
    body = {
        "schema": PROJECTION_SCHEMA,
        "graph_content_root": snapshot["content_root"],
        "graph_state_root": snapshot["state_root"],
        "profile": {
            "record": CORE_PROFILE,
            "proof": merkle_proof(leaves, "profile"),
        },
        "claims": [
            {
                "record": claims[claim_id],
                "proof": merkle_proof(leaves, f"claim:{claim_id}"),
            }
            for claim_id in selected_claims
        ],
        "relations": [
            {
                "record": relations[relation_id],
                "proof": merkle_proof(leaves, f"relation:{relation_id}"),
            }
            for relation_id in selected_relations
        ],
        "purpose": purpose,
        "selected_by": selected_by,
        "omission_disclosure": "bounded_projection_not_a_completeness_proof",
    }
    return {"projection_id": content_id("projection", body), **body}


def verify_projection(projection: Mapping[str, Any], policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    policy = dict(policy or {})
    errors: list[str] = []
    warnings: list[str] = []
    try:
        if projection.get("schema") != PROJECTION_SCHEMA:
            errors.append("projection_schema_invalid")
        expected_id = content_id("projection", _record_body(projection, "projection_id"))
        if projection.get("projection_id") != expected_id:
            errors.append("projection_id_mismatch")
        root = str(projection["graph_content_root"])
        profile_entry = dict(projection["profile"])
        if profile_entry.get("record") != CORE_PROFILE:
            errors.append("projection_profile_mismatch")
        if not verify_merkle_proof("profile", profile_entry.get("record"), profile_entry.get("proof", []), root):
            errors.append("projection_profile_proof_invalid")

        claims: dict[str, Mapping[str, Any]] = {}
        for entry in projection.get("claims", []):
            record = dict(entry["record"])
            claim_id = str(record["claim_id"])
            if claim_id in claims:
                errors.append(f"projection_duplicate_claim:{claim_id}")
            claims[claim_id] = record
            if not verify_merkle_proof(f"claim:{claim_id}", record, entry.get("proof", []), root):
                errors.append(f"projection_claim_proof_invalid:{claim_id}")

        relations: dict[str, Mapping[str, Any]] = {}
        for entry in projection.get("relations", []):
            record = dict(entry["record"])
            relation_id = str(record["relation_id"])
            if relation_id in relations:
                errors.append(f"projection_duplicate_relation:{relation_id}")
            relations[relation_id] = record
            if not verify_merkle_proof(f"relation:{relation_id}", record, entry.get("proof", []), root):
                errors.append(f"projection_relation_proof_invalid:{relation_id}")
            endpoints = {str(record["source_claim_id"]), str(record["target_claim_id"])}
            if not endpoints.issubset(claims):
                errors.append(f"projection_relation_endpoint_missing:{relation_id}")

        required_ids = set(map(str, policy.get("required_claim_ids", [])))
        for missing in sorted(required_ids - set(claims)):
            errors.append(f"receiver_required_claim_missing:{missing}")
        required_slots = set(map(str, policy.get("required_slots", [])))
        present_slots = {str(claim["slot"]) for claim in claims.values() if "slot" in claim}
        for missing in sorted(required_slots - present_slots):
            errors.append(f"receiver_required_slot_missing:{missing}")
        required_relations = set(map(str, policy.get("required_relations", [])))
        present_relation_types = {str(item["relation"]) for item in relations.values()}
        for missing in sorted(required_relations - present_relation_types):
            errors.append(f"receiver_required_relation_missing:{missing}")
        if projection.get("omission_disclosure") != "bounded_projection_not_a_completeness_proof":
            errors.append("projection_omission_disclosure_missing")
        else:
            warnings.append("projection_does_not_prove_completeness")

        if policy.get("deny_unanchored_claims"):
            for claim_id, claim in claims.items():
                if not claim.get("provenance"):
                    errors.append(f"receiver_unanchored_claim_denied:{claim_id}")
        allowed_modes = set(map(str, policy.get("allowed_provenance_modes", PROVENANCE_MODES)))
        for claim_id, claim in claims.items():
            for anchor in claim.get("provenance", []):
                if anchor.get("mode") not in allowed_modes:
                    errors.append(f"receiver_provenance_mode_denied:{claim_id}:{anchor.get('mode')}")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"projection_invalid:{type(exc).__name__}")

    disposition = "DENY" if errors else ("QUARANTINE" if warnings and policy.get("quarantine_on_warnings") else "ADMIT")
    return {
        "valid": not errors,
        "disposition": disposition,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "claim_boundary": "Integrity and receiver-policy result only; no semantic truth or completeness claim.",
    }
