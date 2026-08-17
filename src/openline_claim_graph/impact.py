"""Deterministic impact analysis for corrected or withdrawn evidence.

The guarantee in this module is deliberately conditional.  Given an admitted
graph, a receiver-owned edge policy, and a content-addressed source-status
event, it computes the exact downstream exposure implied by those inputs.  It
does not decide whether the graph edges are semantically true or whether a
correction makes a scientific conclusion false.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Iterable, Mapping, Sequence

from .canonical import content_id, hash_object, sha256_hex
from .graph import PROVENANCE_MODES, validate_snapshot, validate_sources
from .receipts import verify_receipt


SOURCE_STATUS_EVENT_SCHEMA = "openline.source-status-event.v1"
IMPACT_POLICY_SCHEMA = "openline.claim-impact-policy.v1"
IMPACT_REPORT_SCHEMA = "openline.claim-impact-report.v1"
ADJUDICATION_IMPACT_REPORT_SCHEMA = "openline.adjudication-impact-report.v1"

SOURCE_STATUSES = ("CORRECTED", "RETRACTED", "WITHDRAWN", "SUPERSEDED", "REVOKED")
IMPACT_RELATIONS = ("SUPPORTS", "DEPENDS_ON", "DERIVED_FROM")


class ImpactValidationError(ValueError):
    """Raised when impact inputs cannot be admitted fail-closed."""


def _without_id(record: Mapping[str, Any], id_field: str) -> dict[str, Any]:
    body = dict(record)
    body.pop(id_field, None)
    return body


def _normalize_spans(spans: Iterable[Mapping[str, Any]]) -> list[dict[str, int]]:
    return sorted(
        ({"start": int(item["start"]), "end": int(item["end"])} for item in spans),
        key=lambda item: (item["start"], item["end"]),
    )


def create_source_status_event(
    *,
    status: str,
    affected: Iterable[Mapping[str, Any]],
    evidence: Iterable[Mapping[str, Any]],
    asserted_by: str,
    effective_at: str,
    reason: str,
) -> dict[str, Any]:
    """Create a content-addressed source-status event.

    ``affected`` entries name a ``source_id`` and may carry exact byte spans.
    Omitting ``spans`` means the entire source is in scope.  The event's
    evidence anchors prove only which bytes were cited as the notice; the
    asserted mapping from notice to affected scope remains a human assertion.
    """

    affected_items = []
    for item in affected:
        normalized: dict[str, Any] = {"source_id": str(item["source_id"])}
        if "spans" in item:
            normalized["spans"] = _normalize_spans(item.get("spans", []))
        affected_items.append(normalized)
    body = {
        "schema": SOURCE_STATUS_EVENT_SCHEMA,
        "status": status.upper(),
        "affected": sorted(affected_items, key=lambda item: str(item["source_id"])),
        "evidence": sorted(
            (dict(item) for item in evidence),
            key=lambda item: (
                str(item.get("source_id", "")),
                int(dict(item.get("span", {})).get("start", -1)),
                int(dict(item.get("span", {})).get("end", -1)),
            ),
        ),
        "asserted_by": asserted_by,
        "effective_at": effective_at,
        "reason": reason,
    }
    return {"event_id": content_id("source-status-event", body), **body}


def create_impact_policy(
    snapshot: Mapping[str, Any],
    *,
    hard_relation_ids: Iterable[str],
    advisory_relation_ids: Iterable[str] = (),
    hard_provenance_modes: Iterable[str] = ("QUOTE",),
    decision_claim_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Create the receiver-owned authority policy for one accepted state."""

    body = {
        "schema": IMPACT_POLICY_SCHEMA,
        "accepted_state_root": str(snapshot["state_root"]),
        "hard_relation_ids": sorted(set(map(str, hard_relation_ids))),
        "advisory_relation_ids": sorted(set(map(str, advisory_relation_ids))),
        "hard_provenance_modes": sorted({str(item).upper() for item in hard_provenance_modes}),
        "decision_claim_ids": sorted(set(map(str, decision_claim_ids))),
    }
    return {"policy_id": content_id("claim-impact-policy", body), **body}


def _validate_anchor(anchor: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    try:
        if anchor.get("mode") != "QUOTE":
            errors.append("event_evidence_must_be_quote")
        if not str(anchor["asserted_by"]):
            errors.append("event_evidence_actor_missing")
        source = sources[str(anchor["source_id"])]
        encoded = str(source["content"]).encode("utf-8")
        span = dict(anchor["span"])
        start, end = int(span["start"]), int(span["end"])
        if start < 0 or end <= start or end > len(encoded):
            errors.append("event_evidence_span_invalid")
        elif sha256_hex(encoded[start:end]) != anchor.get("quote_sha256"):
            errors.append("event_evidence_quote_hash_mismatch")
    except (KeyError, TypeError, ValueError, UnicodeError):
        errors.append("event_evidence_invalid")
    return errors


def validate_source_status_event(
    event: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    errors = validate_sources(sources)
    warnings: list[str] = []
    try:
        if event.get("schema") != SOURCE_STATUS_EVENT_SCHEMA:
            errors.append("event_schema_invalid")
        expected_id = content_id("source-status-event", _without_id(event, "event_id"))
        if event.get("event_id") != expected_id:
            errors.append("event_id_mismatch")
        if event.get("status") not in SOURCE_STATUSES:
            errors.append("event_status_invalid")
        if not str(event.get("asserted_by", "")):
            errors.append("event_actor_missing")
        if not str(event.get("effective_at", "")):
            errors.append("event_effective_at_missing")
        if not str(event.get("reason", "")):
            errors.append("event_reason_missing")

        affected = event.get("affected")
        if not isinstance(affected, list) or not affected:
            errors.append("event_affected_empty")
            affected = []
        source_ids: list[str] = []
        for item in affected:
            if not isinstance(item, Mapping):
                errors.append("event_affected_invalid")
                continue
            source_id = str(item.get("source_id", ""))
            source_ids.append(source_id)
            if source_id not in sources:
                errors.append(f"event_affected_source_unknown:{source_id}")
                continue
            encoded = str(sources[source_id]["content"]).encode("utf-8")
            if "spans" in item:
                spans = item.get("spans")
                if not isinstance(spans, list) or not spans:
                    errors.append(f"event_affected_spans_empty:{source_id}")
                    continue
                normalized = _normalize_spans(spans)
                if list(spans) != normalized:
                    errors.append(f"event_affected_spans_not_canonical:{source_id}")
                for span in normalized:
                    if span["start"] < 0 or span["end"] <= span["start"] or span["end"] > len(encoded):
                        errors.append(f"event_affected_span_invalid:{source_id}")
        if len(source_ids) != len(set(source_ids)):
            errors.append("event_affected_source_duplicate")
        if source_ids != sorted(source_ids):
            errors.append("event_affected_not_canonical")

        evidence = event.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append("event_evidence_empty")
        else:
            for anchor in evidence:
                if not isinstance(anchor, Mapping):
                    errors.append("event_evidence_invalid")
                    continue
                errors.extend(_validate_anchor(anchor, sources))
        warnings.append("event_scope_mapping_asserted_not_mechanically_adjudicated")
    except (KeyError, TypeError, ValueError):
        errors.append("event_invalid")
    return {"valid": not errors, "errors": sorted(set(errors)), "warnings": sorted(set(warnings))}


def validate_impact_policy(policy: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        if policy.get("schema") != IMPACT_POLICY_SCHEMA:
            errors.append("impact_policy_schema_invalid")
        expected_id = content_id("claim-impact-policy", _without_id(policy, "policy_id"))
        if policy.get("policy_id") != expected_id:
            errors.append("impact_policy_id_mismatch")
        if policy.get("accepted_state_root") != snapshot.get("state_root"):
            errors.append("impact_policy_state_root_mismatch")

        relations = {str(item["relation_id"]): item for item in snapshot.get("relations", [])}
        claims = {str(item["claim_id"]): item for item in snapshot.get("claims", [])}
        hard = list(map(str, policy.get("hard_relation_ids", [])))
        advisory = list(map(str, policy.get("advisory_relation_ids", [])))
        decisions = list(map(str, policy.get("decision_claim_ids", [])))
        modes = list(map(str, policy.get("hard_provenance_modes", [])))
        for name, values in (("hard", hard), ("advisory", advisory), ("decision", decisions), ("mode", modes)):
            if values != sorted(set(values)):
                errors.append(f"impact_policy_{name}_not_canonical")
        if set(hard) & set(advisory):
            errors.append("impact_policy_relation_authority_overlap")
        for relation_id in hard + advisory:
            if relation_id not in relations:
                errors.append(f"impact_policy_relation_unknown:{relation_id}")
            elif relations[relation_id].get("relation") not in IMPACT_RELATIONS:
                errors.append(f"impact_policy_relation_semantics_unsupported:{relation_id}")
        for claim_id in decisions:
            if claim_id not in claims:
                errors.append(f"impact_policy_decision_unknown:{claim_id}")
        if not modes:
            errors.append("impact_policy_hard_provenance_modes_empty")
        for mode in modes:
            if mode not in PROVENANCE_MODES:
                errors.append(f"impact_policy_provenance_mode_invalid:{mode}")
        ignored = sorted(set(relations) - set(hard) - set(advisory))
        if ignored:
            warnings.append(f"impact_policy_relations_not_admitted:{len(ignored)}")
    except (KeyError, TypeError, ValueError):
        errors.append("impact_policy_invalid")
    return {"valid": not errors, "errors": sorted(set(errors)), "warnings": sorted(set(warnings))}


def _affected_ranges(event: Mapping[str, Any]) -> dict[str, list[tuple[int, int]] | None]:
    result: dict[str, list[tuple[int, int]] | None] = {}
    for item in event["affected"]:
        if "spans" not in item:
            result[str(item["source_id"])] = None
        else:
            result[str(item["source_id"])] = [
                (int(span["start"]), int(span["end"])) for span in item["spans"]
            ]
    return result


def _anchor_is_affected(anchor: Mapping[str, Any], ranges: Mapping[str, list[tuple[int, int]] | None]) -> bool:
    source_id = str(anchor.get("source_id", ""))
    if source_id not in ranges:
        return False
    scopes = ranges[source_id]
    if scopes is None:
        return True
    span = dict(anchor.get("span", {}))
    start, end = int(span.get("start", -1)), int(span.get("end", -1))
    return any(start < scope_end and scope_start < end for scope_start, scope_end in scopes)


def _dependency_direction(relation: Mapping[str, Any]) -> tuple[str, str]:
    relation_type = str(relation["relation"])
    source = str(relation["source_claim_id"])
    target = str(relation["target_claim_id"])
    if relation_type == "SUPPORTS":
        return source, target
    if relation_type in {"DEPENDS_ON", "DERIVED_FROM"}:
        return target, source
    raise ImpactValidationError(f"unsupported dependency semantics: {relation_type}")


def _reachable(
    origins: set[str], adjacency: Mapping[str, list[tuple[str, Mapping[str, Any]]]]
) -> set[str]:
    seen = set(origins)
    queue = deque(sorted(origins))
    while queue:
        current = queue.popleft()
        for dependent, _relation in adjacency.get(current, []):
            if dependent not in seen:
                seen.add(dependent)
                queue.append(dependent)
    return seen


def _advisory_reachable(
    origins: set[str],
    hard_adjacency: Mapping[str, list[tuple[str, Mapping[str, Any]]]],
    advisory_adjacency: Mapping[str, list[tuple[str, Mapping[str, Any]]]],
) -> set[str]:
    seen: set[tuple[str, bool]] = {(item, False) for item in origins}
    queue = deque(sorted(seen))
    advisory_nodes: set[str] = set()
    while queue:
        current, used_advisory = queue.popleft()
        for dependent, _relation in hard_adjacency.get(current, []):
            state = (dependent, used_advisory)
            if state not in seen:
                seen.add(state)
                queue.append(state)
                if used_advisory:
                    advisory_nodes.add(dependent)
        for dependent, _relation in advisory_adjacency.get(current, []):
            state = (dependent, True)
            if state not in seen:
                seen.add(state)
                queue.append(state)
            advisory_nodes.add(dependent)
    return advisory_nodes


def _shortest_path(
    origins: set[str],
    target: str,
    adjacency: Mapping[str, list[tuple[str, Mapping[str, Any]]]],
) -> dict[str, Any] | None:
    if target in origins:
        return {"origin_claim_id": target, "steps": []}
    queue = deque((origin, []) for origin in sorted(origins))
    seen = set(origins)
    while queue:
        current, steps = queue.popleft()
        for dependent, relation in adjacency.get(current, []):
            step = {
                "from_claim_id": current,
                "to_claim_id": dependent,
                "relation_id": str(relation["relation_id"]),
                "relation": str(relation["relation"]),
            }
            path = steps + [step]
            if dependent == target:
                return {"origin_claim_id": path[0]["from_claim_id"], "steps": path}
            if dependent not in seen:
                seen.add(dependent)
                queue.append((dependent, path))
    return None


def _shortest_advisory_path(
    origins: set[str],
    target: str,
    hard_adjacency: Mapping[str, list[tuple[str, Mapping[str, Any]]]],
    advisory_adjacency: Mapping[str, list[tuple[str, Mapping[str, Any]]]],
) -> dict[str, Any] | None:
    """Return a shortest witness that contains at least one advisory edge."""

    queue = deque((origin, False, []) for origin in sorted(origins))
    seen = {(origin, False) for origin in origins}
    while queue:
        current, used_advisory, steps = queue.popleft()
        for is_advisory, adjacency in ((False, hard_adjacency), (True, advisory_adjacency)):
            for dependent, relation in adjacency.get(current, []):
                next_used = used_advisory or is_advisory
                step = {
                    "from_claim_id": current,
                    "to_claim_id": dependent,
                    "relation_id": str(relation["relation_id"]),
                    "relation": str(relation["relation"]),
                    "authority": "ADVISORY" if is_advisory else "HARD",
                }
                path = steps + [step]
                if dependent == target and next_used:
                    return {"origin_claim_id": path[0]["from_claim_id"], "steps": path}
                state = (dependent, next_used)
                if state not in seen:
                    seen.add(state)
                    queue.append((dependent, next_used, path))
    return None


def _claim_entry(claim: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(claim["claim_id"]),
        "kind": str(claim["kind"]),
        "text": str(claim["text"]),
    }


def _classification_index(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Flatten an impact report into one deterministic classification per claim."""

    names = {
        "quarantine": "QUARANTINE",
        "survives": "SURVIVES",
        "affected_unresolved": "AFFECTED_UNRESOLVED",
        "unaffected": "UNAFFECTED",
    }
    result: dict[str, dict[str, Any]] = {}
    for bucket_name, classification in names.items():
        for raw in report.get("classifications", {}).get(bucket_name, []):
            item = dict(raw)
            claim_id = str(item["claim_id"])
            result[claim_id] = {
                "classification": str(item.get("classification", classification)),
                "reason": item.get("reason"),
            }
    return result


def analyze_source_impact(
    snapshot: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    event: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute deterministic blast radius under receiver-admitted semantics."""

    graph_check = validate_snapshot(snapshot, sources, parent_snapshots=None)
    event_check = validate_source_status_event(event, sources)
    policy_check = validate_impact_policy(policy, snapshot)
    errors = graph_check["errors"] + event_check["errors"] + policy_check["errors"]
    if errors:
        raise ImpactValidationError("; ".join(sorted(set(errors))))

    claims = {str(item["claim_id"]): item for item in snapshot.get("claims", [])}
    relations = {str(item["relation_id"]): item for item in snapshot.get("relations", [])}
    hard_ids = set(map(str, policy["hard_relation_ids"]))
    advisory_ids = set(map(str, policy["advisory_relation_ids"]))
    hard_modes = set(map(str, policy["hard_provenance_modes"]))
    ranges = _affected_ranges(event)

    affected_anchors: dict[str, list[dict[str, Any]]] = {}
    live_anchors: dict[str, list[dict[str, Any]]] = {}
    for claim_id, claim in claims.items():
        for raw_anchor in claim.get("provenance", []):
            anchor = dict(raw_anchor)
            if anchor.get("mode") not in hard_modes:
                continue
            (affected_anchors if _anchor_is_affected(anchor, ranges) else live_anchors).setdefault(
                claim_id, []
            ).append(anchor)

    source_exposed = set(affected_anchors)
    hard_adjacency: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    advisory_adjacency: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    required_by_dependent: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    supporters_by_dependent: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for relation_id, relation in relations.items():
        if relation_id not in hard_ids | advisory_ids:
            continue
        prerequisite, dependent = _dependency_direction(relation)
        adjacency = hard_adjacency if relation_id in hard_ids else advisory_adjacency
        adjacency.setdefault(prerequisite, []).append((dependent, relation))
        if relation_id in hard_ids:
            if relation["relation"] == "SUPPORTS":
                supporters_by_dependent.setdefault(dependent, []).append((prerequisite, relation))
            else:
                required_by_dependent.setdefault(dependent, []).append((prerequisite, relation))
    for adjacency in (hard_adjacency, advisory_adjacency):
        for prerequisite in adjacency:
            adjacency[prerequisite].sort(key=lambda item: (item[0], str(item[1]["relation_id"])))

    hard_touched = _reachable(source_exposed, hard_adjacency)

    # First compute the least fixed point of grounded admissible support,
    # independently of required-dependency edges.  A support cycle with no
    # surviving external basis must not keep itself alive.  A claim with no
    # declared supporters keeps its accepted basis unless this event directly
    # removed that basis.
    grounded: set[str] = set()
    changed = True
    while changed:
        changed = False
        for claim_id in sorted(claims):
            if claim_id in grounded:
                continue
            supporters = supporters_by_dependent.get(claim_id, [])
            own_basis = bool(live_anchors.get(claim_id)) or (
                claim_id not in source_exposed and not supporters
            )
            supported_basis = any(prerequisite in grounded for prerequisite, _relation in supporters)
            if own_basis or supported_basis:
                grounded.add(claim_id)
                changed = True

    # Then propagate loss across conjunctive required-dependency edges.  This
    # separate phase prevents a cycle of independently grounded required claims
    # from being rejected merely because a least fixed point started empty.
    invalid = set(claims) - grounded
    changed = True
    while changed:
        changed = False
        for claim_id in sorted(claims):
            if claim_id in invalid:
                continue
            if any(
                prerequisite in invalid
                for prerequisite, _relation in required_by_dependent.get(claim_id, [])
            ):
                invalid.add(claim_id)
                changed = True

    alive = set(claims) - invalid
    quarantine = hard_touched - alive
    advisory_touched = _advisory_reachable(source_exposed, hard_adjacency, advisory_adjacency)
    review = advisory_touched - quarantine
    survives = (hard_touched & alive) - review
    touched = quarantine | review | survives
    unaffected = set(claims) - touched

    direct_quarantine = source_exposed & quarantine
    causal_adjacency: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for prerequisite, outgoing in hard_adjacency.items():
        for dependent, relation in outgoing:
            if prerequisite not in quarantine or dependent not in quarantine:
                continue
            if relation["relation"] == "SUPPORTS":
                supporters = supporters_by_dependent.get(dependent, [])
                if not supporters or any(item[0] in alive for item in supporters):
                    continue
                if live_anchors.get(dependent):
                    continue
            causal_adjacency.setdefault(prerequisite, []).append((dependent, relation))
    for prerequisite in causal_adjacency:
        causal_adjacency[prerequisite].sort(key=lambda item: (item[0], str(item[1]["relation_id"])))

    quarantine_entries = []
    for claim_id in sorted(quarantine):
        entry = _claim_entry(claims[claim_id])
        entry["classification"] = "QUARANTINE"
        if claim_id in direct_quarantine:
            entry["reason"] = "SOURCE_BASIS_LOST"
        elif any(
            prerequisite in quarantine
            for prerequisite, _relation in required_by_dependent.get(claim_id, [])
        ):
            entry["reason"] = "REQUIRED_DEPENDENCY_LOST"
        else:
            entry["reason"] = "ALL_ADMITTED_SUPPORT_PATHS_LOST"
        entry["witness_path"] = _shortest_path(direct_quarantine, claim_id, causal_adjacency)
        quarantine_entries.append(entry)

    survive_entries = []
    for claim_id in sorted(survives):
        entry = _claim_entry(claims[claim_id])
        entry["classification"] = "SURVIVES"
        entry["reason"] = "ADMITTED_ALTERNATIVE_BASIS_REMAINS"
        entry["retained_source_ids"] = sorted(
            {str(anchor["source_id"]) for anchor in live_anchors.get(claim_id, [])}
        )
        entry["retained_support_claim_ids"] = sorted(
            prerequisite
            for prerequisite, _relation in supporters_by_dependent.get(claim_id, [])
            if prerequisite not in quarantine
        )
        survive_entries.append(entry)

    review_entries = []
    for claim_id in sorted(review):
        entry = _claim_entry(claims[claim_id])
        entry["classification"] = "AFFECTED_UNRESOLVED"
        entry["reason"] = "PATH_INCLUDES_ADVISORY_EDGE"
        entry["witness_path"] = _shortest_advisory_path(
            source_exposed, claim_id, hard_adjacency, advisory_adjacency
        )
        review_entries.append(entry)

    unaffected_entries = [_claim_entry(claims[item]) for item in sorted(unaffected)]
    decisions = set(map(str, policy.get("decision_claim_ids", [])))
    decision_claims_touched = sorted(decisions & touched)

    warnings = sorted(
        set(graph_check["warnings"] + event_check["warnings"] + policy_check["warnings"])
    )
    body: dict[str, Any] = {
        "schema": IMPACT_REPORT_SCHEMA,
        "status": "IMPACT_COMPUTED_CONDITIONALLY",
        "valid": True,
        "accepted_state_root": str(snapshot["state_root"]),
        "event_id": str(event["event_id"]),
        "policy_id": str(policy["policy_id"]),
        "source_exposed_claim_ids": sorted(source_exposed),
        "classifications": {
            "quarantine": quarantine_entries,
            "survives": survive_entries,
            "affected_unresolved": review_entries,
            "unaffected": unaffected_entries,
        },
        "decision_claim_ids_touched": decision_claims_touched,
        "ignored_relation_ids": sorted(set(relations) - hard_ids - advisory_ids),
        "summary": {
            "source_exposed": len(source_exposed),
            "quarantine": len(quarantine),
            "survives": len(survives),
            "affected_unresolved": len(review),
            "unaffected": len(unaffected),
            "decisions_touched": len(decision_claims_touched),
        },
        "warnings": warnings,
        "claim_boundary": (
            "Given this exact accepted graph, source-status event, and receiver-owned edge policy, "
            "these are the mechanically implied exposures. The report does not certify the semantic "
            "truth or completeness of any claim, edge, event scope, or source. It proposes review; it "
            "does not mutate the accepted graph."
        ),
    }
    return {"report_id": content_id("claim-impact-report", body), **body}


def analyze_adjudication_impact(
    snapshot: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    event: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute the marginal consequence of admitting each advisory relation.

    The function changes exactly one policy fact at a time: one currently
    advisory relation is promoted to hard authority, the existing source-impact
    engine is rerun, and accepted claim classifications are diffed against the
    unchanged baseline.  This determines the review surface mechanically; it
    does not decide whether any advisory relation is semantically correct or
    should be admitted.
    """

    baseline = analyze_source_impact(snapshot, sources, event, policy)
    claims = {str(item["claim_id"]): item for item in snapshot.get("claims", [])}
    relations = {str(item["relation_id"]): item for item in snapshot.get("relations", [])}
    advisory_ids = sorted(map(str, policy.get("advisory_relation_ids", [])))
    hard_ids = list(map(str, policy.get("hard_relation_ids", [])))
    decision_ids = set(map(str, policy.get("decision_claim_ids", [])))
    baseline_index = _classification_index(baseline)

    entries: list[dict[str, Any]] = []
    for relation_id in advisory_ids:
        promoted_policy = create_impact_policy(
            snapshot,
            hard_relation_ids=hard_ids + [relation_id],
            advisory_relation_ids=[item for item in advisory_ids if item != relation_id],
            hard_provenance_modes=policy.get("hard_provenance_modes", ()),
            decision_claim_ids=policy.get("decision_claim_ids", ()),
        )
        counterfactual = analyze_source_impact(snapshot, sources, event, promoted_policy)
        counterfactual_index = _classification_index(counterfactual)

        changed_claims: list[dict[str, Any]] = []
        for claim_id in sorted(baseline_index):
            before = baseline_index[claim_id]
            after = counterfactual_index[claim_id]
            if before["classification"] == after["classification"]:
                continue
            claim = claims[claim_id]
            changed_claims.append(
                {
                    "claim_id": claim_id,
                    "kind": str(claim["kind"]),
                    "text": str(claim["text"]),
                    "before": before["classification"],
                    "after": after["classification"],
                }
            )

        changed_claim_ids = {item["claim_id"] for item in changed_claims}
        changed_decisions = sorted(decision_ids & changed_claim_ids)
        relation = relations[relation_id]
        entries.append(
            {
                "relation_id": relation_id,
                "relation": str(relation["relation"]),
                "source_claim_id": str(relation["source_claim_id"]),
                "target_claim_id": str(relation["target_claim_id"]),
                "counterfactual_policy_id": str(promoted_policy["policy_id"]),
                "counterfactual_report_id": str(counterfactual["report_id"]),
                "changed_claims": changed_claims,
                "changed_decision_claim_ids": changed_decisions,
                "summary": {
                    "changed_claims": len(changed_claims),
                    "changed_decisions": len(changed_decisions),
                },
            }
        )

    # This ordering is intentionally mechanical rather than rhetorical.  It is
    # not a truth or importance score: receiver-declared decision claims are
    # surfaced first, then larger classification deltas, then stable relation ID.
    entries.sort(
        key=lambda item: (
            -int(item["summary"]["changed_decisions"]),
            -int(item["summary"]["changed_claims"]),
            str(item["relation_id"]),
        )
    )
    for index, item in enumerate(entries, start=1):
        item["review_order"] = index

    changed_claim_union = sorted(
        {claim["claim_id"] for item in entries for claim in item["changed_claims"]}
    )
    changed_decision_union = sorted(
        {claim_id for item in entries for claim_id in item["changed_decision_claim_ids"]}
    )
    body: dict[str, Any] = {
        "schema": ADJUDICATION_IMPACT_REPORT_SCHEMA,
        "status": "ADJUDICATION_COUNTERFACTUALS_COMPUTED_CONDITIONALLY",
        "valid": True,
        "accepted_state_root": str(snapshot["state_root"]),
        "event_id": str(event["event_id"]),
        "baseline_policy_id": str(policy["policy_id"]),
        "baseline_report_id": str(baseline["report_id"]),
        "queue_rule": (
            "changed receiver-declared decisions descending, then changed claim classifications "
            "descending, then relation_id ascending"
        ),
        "advisory_relations": entries,
        "summary": {
            "advisory_relations_evaluated": len(entries),
            "consequential_relations": sum(
                1 for item in entries if int(item["summary"]["changed_claims"]) > 0
            ),
            "distinct_changed_claims": len(changed_claim_union),
            "distinct_changed_decisions": len(changed_decision_union),
        },
        "warnings": list(baseline.get("warnings", [])),
        "claim_boundary": (
            "For each advisory relation in this exact accepted graph and receiver policy, the report "
            "changes only that relation's authority to hard, reruns the existing deterministic impact "
            "semantics, and reports classification deltas. It does not certify that an advisory relation "
            "is true, complete, important, or worthy of admission, and it does not mutate accepted state."
        ),
    }
    return {"report_id": content_id("adjudication-impact-report", body), **body}


def verify_adjudication_impact_report(
    report: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    event: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute the single-edge counterfactual queue and require exact equality."""

    errors: list[str] = []
    try:
        expected = analyze_adjudication_impact(snapshot, sources, event, policy)
        if report.get("schema") != ADJUDICATION_IMPACT_REPORT_SCHEMA:
            errors.append("adjudication_impact_report_schema_invalid")
        expected_id = content_id("adjudication-impact-report", _without_id(report, "report_id"))
        if report.get("report_id") != expected_id:
            errors.append("adjudication_impact_report_id_mismatch")
        if hash_object(report) != hash_object(expected):
            errors.append("adjudication_impact_report_reproduction_mismatch")
    except (ImpactValidationError, KeyError, TypeError, ValueError):
        errors.append("adjudication_impact_report_inputs_invalid")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "disposition": "ADMIT_ADJUDICATION_REVIEW" if not errors else "DENY_ADJUDICATION_REVIEW",
    }


def verify_impact_report(
    report: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    event: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute the report and require exact canonical equality."""

    errors: list[str] = []
    try:
        expected = analyze_source_impact(snapshot, sources, event, policy)
        if report.get("schema") != IMPACT_REPORT_SCHEMA:
            errors.append("impact_report_schema_invalid")
        expected_id = content_id("claim-impact-report", _without_id(report, "report_id"))
        if report.get("report_id") != expected_id:
            errors.append("impact_report_id_mismatch")
        if hash_object(report) != hash_object(expected):
            errors.append("impact_report_reproduction_mismatch")
    except (ImpactValidationError, KeyError, TypeError, ValueError):
        errors.append("impact_report_inputs_invalid")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "disposition": "ADMIT_REPORT" if not errors else "DENY_REPORT",
    }


def verify_impact_bundle(
    report: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    event: Mapping[str, Any],
    policy: Mapping[str, Any],
    accepted_receipt: Mapping[str, Any],
    *,
    pinned_public_key: str,
    parent_snapshots: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify accepted-state authenticity and impact reproduction together."""

    receipt_check = verify_receipt(
        accepted_receipt,
        snapshot,
        sources,
        pinned_public_key=pinned_public_key,
        parent_snapshots=parent_snapshots,
    )
    report_check = verify_impact_report(report, snapshot, sources, event, policy)
    errors = [f"accepted_receipt:{item}" for item in receipt_check["errors"]]
    errors.extend(f"impact_report:{item}" for item in report_check["errors"])
    warnings = [f"accepted_receipt:{item}" for item in receipt_check["warnings"]]
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "disposition": "ADMIT_IMPACT_REVIEW" if not errors else "DENY_IMPACT_REVIEW",
        "accepted_receipt": receipt_check,
        "impact_report": report_check,
        "claim_boundary": (
            "Authenticates the accepted state and reproduces impact under the declared event and policy. "
            "It does not certify truth, semantic completeness, or authority to mutate that state."
        ),
    }


def verify_adjudication_impact_bundle(
    report: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    event: Mapping[str, Any],
    policy: Mapping[str, Any],
    accepted_receipt: Mapping[str, Any],
    *,
    pinned_public_key: str,
    parent_snapshots: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Authenticate accepted state and reproduce adjudication counterfactuals."""

    receipt_check = verify_receipt(
        accepted_receipt,
        snapshot,
        sources,
        pinned_public_key=pinned_public_key,
        parent_snapshots=parent_snapshots,
    )
    report_check = verify_adjudication_impact_report(report, snapshot, sources, event, policy)
    errors = [f"accepted_receipt:{item}" for item in receipt_check["errors"]]
    errors.extend(f"adjudication_impact_report:{item}" for item in report_check["errors"])
    warnings = [f"accepted_receipt:{item}" for item in receipt_check["warnings"]]
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "disposition": "ADMIT_ADJUDICATION_REVIEW" if not errors else "DENY_ADJUDICATION_REVIEW",
        "accepted_receipt": receipt_check,
        "adjudication_impact_report": report_check,
        "claim_boundary": (
            "Authenticates the accepted state and reproduces the single-edge authority counterfactuals. "
            "It does not certify semantic correctness, materiality, or authority to admit any relation."
        ),
    }
