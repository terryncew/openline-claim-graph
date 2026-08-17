"""Three-way comparative benchmark for Evidence Recall.

This module evaluates a *frozen* Evidence Recall engine against two deliberately
simple baselines:

1. direct lookup: only the immediate dependents of an invalidated node;
2. naive transitive taint: every node reachable over every directed edge;
3. Evidence Recall: the shipped impact engine with receiver-owned hard,
   advisory, and unadmitted relation authority.

The benchmark is intentionally split into public inputs, receiver authority,
predictions, and external gold.  Gold is never required to produce predictions.
The module does not infer semantic dependencies from gold labels and does not
modify Evidence Recall semantics to fit an outcome.
"""

from __future__ import annotations

import csv
import io
import re
from collections import deque
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .canonical import content_id, hash_object, sha256_hex
from .graph import (
    build_source,
    create_claim,
    create_relation,
    create_snapshot,
    provenance_anchor,
)
from .impact import analyze_source_impact, create_impact_policy, create_source_status_event


COMPARATIVE_PACK_SCHEMA = "openline.evidence-recall-comparative-pack.v1"
COMPARATIVE_AUTHORITY_SCHEMA = "openline.evidence-recall-comparative-authority.v1"
COMPARATIVE_GOLD_SCHEMA = "openline.evidence-recall-comparative-gold.v1"
COMPARATIVE_PREDICTIONS_SCHEMA = "openline.evidence-recall-comparative-predictions.v1"
COMPARATIVE_SCORE_SCHEMA = "openline.evidence-recall-comparative-score.v1"
PUBLISHED_DIAGNOSTIC_SCHEMA = "openline.evidence-recall-published-diagnostic.v1"

SYSTEM_DIRECT = "DIRECT_LOOKUP"
SYSTEM_NAIVE = "NAIVE_TRANSITIVE_TAINT"
SYSTEM_EVIDENCE_RECALL = "EVIDENCE_RECALL"
SYSTEMS = (SYSTEM_DIRECT, SYSTEM_NAIVE, SYSTEM_EVIDENCE_RECALL)

AUTHORITIES = ("HARD", "ADVISORY", "UNADMITTED")
RELATIONS = ("SUPPORTS", "DEPENDS_ON", "DERIVED_FROM")
GOLD_OUTCOMES = ("EXPOSED", "NO_EXPOSURE", "UNASSESSED")
CLASSIFICATIONS = ("QUARANTINE", "SURVIVES", "AFFECTED_UNRESOLVED", "UNAFFECTED")

# These fields encode external answers or post-outcome judgments.  They may be
# present in the raw source importer, but never in the public benchmark pack.
RESERVED_PUBLIC_FIELD_FRAGMENTS = (
    "possible impact",
    "misinformation",
    "seriousness",
    "risk",
    "gold",
    "outcome",
)

SCHNEIDER_DATASET_DOI = "10.13012/B2IDB-3331845_V2"
SCHNEIDER_ARTICLE_DOI = "10.1007/s11192-020-03631-1"
VAN_DER_VET_ARTICLE_DOI = "10.1186/s41073-016-0008-5"
JAMA_ARTICLE_DOI = "10.1001/jamainternmed.2025.0256"


class ComparativeBenchmarkError(ValueError):
    """Raised when comparative benchmark inputs fail closed."""


def _without_id(record: Mapping[str, Any], id_field: str) -> dict[str, Any]:
    body = dict(record)
    body.pop(id_field, None)
    return body


def _canonical_token(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _edge_id(edge: Mapping[str, Any]) -> str:
    body = {
        "prerequisite_node_id": str(edge["prerequisite_node_id"]),
        "dependent_node_id": str(edge["dependent_node_id"]),
        "relation": str(edge["relation"]).upper(),
        "evidence": list(edge.get("evidence", [])),
    }
    return content_id("comparative-edge", body)


def _node_id(node: Mapping[str, Any]) -> str:
    body = {
        "label": _canonical_token(node.get("label", "")),
        "text": _canonical_token(node.get("text", "")),
        "locator": _canonical_token(node.get("locator", "")),
        "independent_basis": bool(node.get("independent_basis", False)),
    }
    return content_id("comparative-node", body)


def create_case(
    *,
    stratum: str,
    invalidated_node_id: str,
    target_node_id: str,
    nodes: Iterable[Mapping[str, Any]],
    edges: Iterable[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one public, gold-free benchmark case."""

    normalized_nodes = []
    seen_nodes: set[str] = set()
    for raw in nodes:
        item = {
            "node_id": str(raw["node_id"]),
            "label": _canonical_token(raw.get("label", raw["node_id"])),
            "text": _canonical_token(raw.get("text", raw.get("label", raw["node_id"]))),
            "locator": _canonical_token(raw.get("locator", "")),
            "independent_basis": bool(raw.get("independent_basis", False)),
        }
        if item["node_id"] in seen_nodes:
            raise ComparativeBenchmarkError(f"duplicate node id: {item['node_id']}")
        seen_nodes.add(item["node_id"])
        normalized_nodes.append(item)
    normalized_nodes.sort(key=lambda item: item["node_id"])

    normalized_edges = []
    seen_edges: set[str] = set()
    for raw in edges:
        item = {
            "prerequisite_node_id": str(raw["prerequisite_node_id"]),
            "dependent_node_id": str(raw["dependent_node_id"]),
            "relation": str(raw.get("relation", "DEPENDS_ON")).upper(),
            "evidence": sorted({_canonical_token(value) for value in raw.get("evidence", []) if _canonical_token(value)}),
        }
        item["edge_id"] = str(raw.get("edge_id") or _edge_id(item))
        if item["edge_id"] in seen_edges:
            raise ComparativeBenchmarkError(f"duplicate edge id: {item['edge_id']}")
        seen_edges.add(item["edge_id"])
        normalized_edges.append(item)
    normalized_edges.sort(key=lambda item: item["edge_id"])

    body: dict[str, Any] = {
        "stratum": _canonical_token(stratum),
        "invalidated_node_id": str(invalidated_node_id),
        "target_node_id": str(target_node_id),
        "nodes": normalized_nodes,
        "edges": normalized_edges,
        "metadata": dict(metadata or {}),
    }
    return {"case_id": content_id("comparative-case", body), **body}


def create_pack(
    *,
    benchmark_id: str,
    cases: Iterable[Mapping[str, Any]],
    source_manifest: Sequence[Mapping[str, Any]],
    construction_rule: str,
    status: str = "PUBLIC_INPUTS_FROZEN",
) -> dict[str, Any]:
    """Create a content-addressed public pack with no answer-bearing fields."""

    body = {
        "schema": COMPARATIVE_PACK_SCHEMA,
        "benchmark_id": _canonical_token(benchmark_id),
        "status": _canonical_token(status),
        "construction_rule": _canonical_token(construction_rule),
        "source_manifest": sorted((dict(item) for item in source_manifest), key=lambda x: (str(x.get("role", "")), str(x.get("identifier", "")))),
        "cases": sorted((dict(item) for item in cases), key=lambda item: str(item["case_id"])),
    }
    return {"pack_id": content_id("evidence-recall-comparative-pack", body), **body}


def create_authority(
    pack: Mapping[str, Any],
    *,
    edge_authority: Mapping[str, str],
    declared_by: str,
    construction_rule: str,
) -> dict[str, Any]:
    """Freeze receiver relation authority without access to gold."""

    entries = [
        {"edge_id": str(edge_id), "authority": str(authority).upper()}
        for edge_id, authority in edge_authority.items()
    ]
    entries.sort(key=lambda item: item["edge_id"])
    body = {
        "schema": COMPARATIVE_AUTHORITY_SCHEMA,
        "benchmark_id": str(pack["benchmark_id"]),
        "pack_id": str(pack["pack_id"]),
        "declared_by": _canonical_token(declared_by),
        "construction_rule": _canonical_token(construction_rule),
        "edge_authority": entries,
    }
    return {"authority_id": content_id("evidence-recall-comparative-authority", body), **body}


def create_gold(
    pack: Mapping[str, Any],
    labels: Mapping[str, str],
    *,
    source: str,
    label_definition: str,
) -> dict[str, Any]:
    """Bind external labels to an already frozen public pack."""

    entries = [
        {"case_id": str(case_id), "outcome": str(outcome).upper()}
        for case_id, outcome in labels.items()
    ]
    entries.sort(key=lambda item: item["case_id"])
    body = {
        "schema": COMPARATIVE_GOLD_SCHEMA,
        "benchmark_id": str(pack["benchmark_id"]),
        "pack_id": str(pack["pack_id"]),
        "source": _canonical_token(source),
        "label_definition": _canonical_token(label_definition),
        "labels": entries,
    }
    return {"gold_id": content_id("evidence-recall-comparative-gold", body), **body}


def _public_value_has_reserved_key(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = _header_key(str(raw_key))
            if any(fragment in key for fragment in RESERVED_PUBLIC_FIELD_FRAGMENTS):
                errors.append(f"reserved_public_key:{path}.{raw_key}")
            errors.extend(_public_value_has_reserved_key(child, f"{path}.{raw_key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_public_value_has_reserved_key(child, f"{path}[{index}]"))
    return errors


def validate_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        if pack.get("schema") != COMPARATIVE_PACK_SCHEMA:
            errors.append("pack_schema_invalid")
        if pack.get("pack_id") != content_id("evidence-recall-comparative-pack", _without_id(pack, "pack_id")):
            errors.append("pack_id_mismatch")
        if not str(pack.get("benchmark_id", "")):
            errors.append("benchmark_id_missing")
        cases = pack.get("cases")
        if not isinstance(cases, list) or not cases:
            errors.append("pack_cases_empty")
            cases = []
        case_ids: list[str] = []
        for case in cases:
            if not isinstance(case, Mapping):
                errors.append("case_invalid")
                continue
            case_id = str(case.get("case_id", ""))
            case_ids.append(case_id)
            expected_case = content_id("comparative-case", _without_id(case, "case_id"))
            if case_id != expected_case:
                errors.append(f"case_id_mismatch:{case_id}")
            nodes = case.get("nodes", [])
            edges = case.get("edges", [])
            if not isinstance(nodes, list) or not nodes:
                errors.append(f"case_nodes_empty:{case_id}")
                nodes = []
            if not isinstance(edges, list):
                errors.append(f"case_edges_invalid:{case_id}")
                edges = []
            node_ids = [str(item.get("node_id", "")) for item in nodes if isinstance(item, Mapping)]
            if node_ids != sorted(set(node_ids)):
                errors.append(f"case_nodes_not_canonical:{case_id}")
            if str(case.get("invalidated_node_id", "")) not in node_ids:
                errors.append(f"case_invalidated_node_unknown:{case_id}")
            if str(case.get("target_node_id", "")) not in node_ids:
                errors.append(f"case_target_node_unknown:{case_id}")
            edge_ids: list[str] = []
            for edge in edges:
                if not isinstance(edge, Mapping):
                    errors.append(f"case_edge_invalid:{case_id}")
                    continue
                edge_id = str(edge.get("edge_id", ""))
                edge_ids.append(edge_id)
                if edge_id != _edge_id(edge):
                    errors.append(f"case_edge_id_mismatch:{case_id}:{edge_id}")
                if edge.get("relation") not in RELATIONS:
                    errors.append(f"case_relation_invalid:{case_id}:{edge_id}")
                if str(edge.get("prerequisite_node_id", "")) not in node_ids:
                    errors.append(f"case_edge_prerequisite_unknown:{case_id}:{edge_id}")
                if str(edge.get("dependent_node_id", "")) not in node_ids:
                    errors.append(f"case_edge_dependent_unknown:{case_id}:{edge_id}")
            if edge_ids != sorted(set(edge_ids)):
                errors.append(f"case_edges_not_canonical:{case_id}")
            errors.extend(_public_value_has_reserved_key(case))
        if case_ids != sorted(set(case_ids)):
            errors.append("pack_cases_not_canonical")
    except (KeyError, TypeError, ValueError):
        errors.append("pack_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def validate_authority(authority: Mapping[str, Any], pack: Mapping[str, Any]) -> dict[str, Any]:
    errors = list(validate_pack(pack)["errors"])
    try:
        if authority.get("schema") != COMPARATIVE_AUTHORITY_SCHEMA:
            errors.append("authority_schema_invalid")
        if authority.get("authority_id") != content_id("evidence-recall-comparative-authority", _without_id(authority, "authority_id")):
            errors.append("authority_id_mismatch")
        if authority.get("benchmark_id") != pack.get("benchmark_id"):
            errors.append("authority_benchmark_mismatch")
        if authority.get("pack_id") != pack.get("pack_id"):
            errors.append("authority_pack_mismatch")
        all_edge_ids = {
            str(edge["edge_id"])
            for case in pack.get("cases", [])
            for edge in case.get("edges", [])
        }
        entries = authority.get("edge_authority")
        if not isinstance(entries, list):
            errors.append("authority_entries_invalid")
            entries = []
        ids: list[str] = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                errors.append("authority_entry_invalid")
                continue
            edge_id = str(entry.get("edge_id", ""))
            ids.append(edge_id)
            if edge_id not in all_edge_ids:
                errors.append(f"authority_edge_unknown:{edge_id}")
            if entry.get("authority") not in AUTHORITIES:
                errors.append(f"authority_value_invalid:{edge_id}")
        if ids != sorted(set(ids)):
            errors.append("authority_entries_not_canonical")
        if set(ids) != all_edge_ids:
            errors.append("authority_not_total_over_pack_edges")
    except (KeyError, TypeError, ValueError):
        errors.append("authority_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def validate_gold(gold: Mapping[str, Any], pack: Mapping[str, Any]) -> dict[str, Any]:
    errors = list(validate_pack(pack)["errors"])
    try:
        if gold.get("schema") != COMPARATIVE_GOLD_SCHEMA:
            errors.append("gold_schema_invalid")
        if gold.get("gold_id") != content_id("evidence-recall-comparative-gold", _without_id(gold, "gold_id")):
            errors.append("gold_id_mismatch")
        if gold.get("benchmark_id") != pack.get("benchmark_id"):
            errors.append("gold_benchmark_mismatch")
        if gold.get("pack_id") != pack.get("pack_id"):
            errors.append("gold_pack_mismatch")
        case_ids = {str(case["case_id"]) for case in pack.get("cases", [])}
        entries = gold.get("labels")
        if not isinstance(entries, list):
            errors.append("gold_labels_invalid")
            entries = []
        ids: list[str] = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                errors.append("gold_label_invalid")
                continue
            case_id = str(entry.get("case_id", ""))
            ids.append(case_id)
            if case_id not in case_ids:
                errors.append(f"gold_case_unknown:{case_id}")
            if entry.get("outcome") not in GOLD_OUTCOMES:
                errors.append(f"gold_outcome_invalid:{case_id}")
        if ids != sorted(set(ids)):
            errors.append("gold_labels_not_canonical")
        if set(ids) != case_ids:
            errors.append("gold_not_total_over_pack_cases")
    except (KeyError, TypeError, ValueError):
        errors.append("gold_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def _adjacency(case: Mapping[str, Any], *, admitted: set[str] | None = None) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}
    for edge in case.get("edges", []):
        if admitted is not None and str(edge["edge_id"]) not in admitted:
            continue
        prerequisite = str(edge["prerequisite_node_id"])
        dependent = str(edge["dependent_node_id"])
        adjacency.setdefault(prerequisite, []).append(dependent)
    for key in adjacency:
        adjacency[key] = sorted(set(adjacency[key]))
    return adjacency


def _reachable(origin: str, adjacency: Mapping[str, Sequence[str]]) -> set[str]:
    seen = {origin}
    queue = deque([origin])
    while queue:
        current = queue.popleft()
        for dependent in adjacency.get(current, []):
            if dependent not in seen:
                seen.add(dependent)
                queue.append(dependent)
    return seen


def _direct_prediction(case: Mapping[str, Any]) -> str:
    origin = str(case["invalidated_node_id"])
    target = str(case["target_node_id"])
    direct = {
        str(edge["dependent_node_id"])
        for edge in case.get("edges", [])
        if str(edge["prerequisite_node_id"]) == origin
    }
    return "QUARANTINE" if target in direct else "UNAFFECTED"


def _naive_prediction(case: Mapping[str, Any]) -> str:
    origin = str(case["invalidated_node_id"])
    target = str(case["target_node_id"])
    return "QUARANTINE" if target in (_reachable(origin, _adjacency(case)) - {origin}) else "UNAFFECTED"


def _materialize_evidence_recall(case: Mapping[str, Any], authority_by_edge: Mapping[str, str]) -> str:
    """Run the shipped Evidence Recall engine without modifying its semantics."""

    nodes = {str(node["node_id"]): node for node in case["nodes"]}
    origin_node_id = str(case["invalidated_node_id"])
    target_node_id = str(case["target_node_id"])

    sources: dict[str, dict[str, Any]] = {}
    claims: dict[str, dict[str, Any]] = {}
    claim_by_node: dict[str, str] = {}

    for node_id in sorted(nodes):
        node = nodes[node_id]
        text = str(node.get("text") or node.get("label") or node_id)
        provenance = []
        # The invalidated origin needs a real source anchor so the shipped source
        # event can originate exposure.  Optional independent bases are likewise
        # materialized as surviving source anchors.  Other bibliographic nodes
        # remain unanchored; their dependency standing comes from relations.
        if node_id == origin_node_id or bool(node.get("independent_basis", False)):
            source = build_source(
                text,
                locator=str(node.get("locator") or f"benchmark:{case['case_id']}:{node_id}"),
            )
            sources[source["source_id"]] = source
            provenance = [
                provenance_anchor(source, text, mode="QUOTE", asserted_by="comparative-benchmark")
            ]
        claim = create_claim(
            kind="OBSERVATION" if node_id == origin_node_id else "INFERENCE",
            text=text,
            asserted_by="comparative-benchmark",
            provenance=provenance,
        )
        claims[claim["claim_id"]] = claim
        claim_by_node[node_id] = claim["claim_id"]

    relations = []
    relation_by_edge: dict[str, str] = {}
    for edge in sorted(case["edges"], key=lambda item: str(item["edge_id"])):
        prerequisite = claim_by_node[str(edge["prerequisite_node_id"])]
        dependent = claim_by_node[str(edge["dependent_node_id"])]
        relation_type = str(edge["relation"])
        if relation_type == "SUPPORTS":
            source_claim_id, target_claim_id = prerequisite, dependent
        else:
            # DEPENDS_ON / DERIVED_FROM are stored dependent -> prerequisite in
            # Claim Graph; the impact engine reverses them for propagation.
            source_claim_id, target_claim_id = dependent, prerequisite
        relation = create_relation(
            source_claim_id=source_claim_id,
            target_claim_id=target_claim_id,
            relation=relation_type,
            asserted_by="comparative-benchmark",
        )
        relations.append(relation)
        relation_by_edge[str(edge["edge_id"])] = str(relation["relation_id"])

    snapshot = create_snapshot(claims=list(claims.values()), relations=relations)
    root_claim_id = claim_by_node[origin_node_id]
    root_claim = claims[root_claim_id]
    root_anchor = root_claim["provenance"][0]
    root_source_id = str(root_anchor["source_id"])

    notice_text = f"Benchmark invalidation event for {case['case_id']}"
    notice = build_source(notice_text, locator=f"benchmark-event:{case['case_id']}")
    sources[notice["source_id"]] = notice
    event = create_source_status_event(
        status="RETRACTED",
        affected=[{"source_id": root_source_id}],
        evidence=[provenance_anchor(notice, notice_text, mode="QUOTE", asserted_by="comparative-benchmark")],
        asserted_by="comparative-benchmark",
        effective_at="2000-01-01T00:00:00Z",
        reason="Frozen comparative benchmark invalidation event.",
    )

    hard_ids = [
        relation_by_edge[edge_id]
        for edge_id, value in authority_by_edge.items()
        if value == "HARD" and edge_id in relation_by_edge
    ]
    advisory_ids = [
        relation_by_edge[edge_id]
        for edge_id, value in authority_by_edge.items()
        if value == "ADVISORY" and edge_id in relation_by_edge
    ]
    policy = create_impact_policy(
        snapshot,
        hard_relation_ids=hard_ids,
        advisory_relation_ids=advisory_ids,
        hard_provenance_modes=["QUOTE"],
    )
    report = analyze_source_impact(snapshot, sources, event, policy)
    target_claim_id = claim_by_node[target_node_id]
    if any(item["claim_id"] == target_claim_id for item in report["classifications"]["quarantine"]):
        return "QUARANTINE"
    if any(item["claim_id"] == target_claim_id for item in report["classifications"]["survives"]):
        return "SURVIVES"
    if any(item["claim_id"] == target_claim_id for item in report["classifications"]["affected_unresolved"]):
        return "AFFECTED_UNRESOLVED"
    return "UNAFFECTED"


def run_comparative(pack: Mapping[str, Any], authority: Mapping[str, Any]) -> dict[str, Any]:
    """Emit predictions for all three systems without reading gold."""

    pack_check = validate_pack(pack)
    authority_check = validate_authority(authority, pack)
    errors = pack_check["errors"] + authority_check["errors"]
    if errors:
        raise ComparativeBenchmarkError("; ".join(sorted(set(errors))))
    authority_by_edge = {
        str(item["edge_id"]): str(item["authority"])
        for item in authority["edge_authority"]
    }
    rows = []
    for case in pack["cases"]:
        predictions = {
            SYSTEM_DIRECT: _direct_prediction(case),
            SYSTEM_NAIVE: _naive_prediction(case),
            SYSTEM_EVIDENCE_RECALL: _materialize_evidence_recall(case, authority_by_edge),
        }
        rows.append(
            {
                "case_id": str(case["case_id"]),
                "stratum": str(case["stratum"]),
                "predictions": predictions,
            }
        )
    rows.sort(key=lambda item: item["case_id"])
    body = {
        "schema": COMPARATIVE_PREDICTIONS_SCHEMA,
        "benchmark_id": str(pack["benchmark_id"]),
        "pack_id": str(pack["pack_id"]),
        "authority_id": str(authority["authority_id"]),
        "engine_contract": {
            "direct_lookup": "immediate dependent of invalidated node only",
            "naive_transitive_taint": "blind directed reachability over every edge",
            "evidence_recall": "shipped analyze_source_impact semantics; no benchmark-specific rescue logic",
        },
        "rows": rows,
    }
    return {"predictions_id": content_id("evidence-recall-comparative-predictions", body), **body}


def validate_predictions(
    predictions: Mapping[str, Any], pack: Mapping[str, Any], authority: Mapping[str, Any]
) -> dict[str, Any]:
    errors = list(validate_authority(authority, pack)["errors"])
    try:
        if predictions.get("schema") != COMPARATIVE_PREDICTIONS_SCHEMA:
            errors.append("predictions_schema_invalid")
        if predictions.get("predictions_id") != content_id("evidence-recall-comparative-predictions", _without_id(predictions, "predictions_id")):
            errors.append("predictions_id_mismatch")
        if predictions.get("benchmark_id") != pack.get("benchmark_id"):
            errors.append("predictions_benchmark_mismatch")
        if predictions.get("pack_id") != pack.get("pack_id"):
            errors.append("predictions_pack_mismatch")
        if predictions.get("authority_id") != authority.get("authority_id"):
            errors.append("predictions_authority_mismatch")
        case_ids = {str(case["case_id"]) for case in pack.get("cases", [])}
        rows = predictions.get("rows")
        if not isinstance(rows, list):
            errors.append("predictions_rows_invalid")
            rows = []
        ids: list[str] = []
        for row in rows:
            if not isinstance(row, Mapping):
                errors.append("prediction_row_invalid")
                continue
            case_id = str(row.get("case_id", ""))
            ids.append(case_id)
            if case_id not in case_ids:
                errors.append(f"prediction_case_unknown:{case_id}")
            values = row.get("predictions")
            if not isinstance(values, Mapping) or set(values) != set(SYSTEMS):
                errors.append(f"prediction_systems_invalid:{case_id}")
            else:
                for system, classification in values.items():
                    if classification not in CLASSIFICATIONS:
                        errors.append(f"prediction_classification_invalid:{case_id}:{system}")
        if ids != sorted(set(ids)) or set(ids) != case_ids:
            errors.append("predictions_cases_not_canonical_or_complete")
    except (KeyError, TypeError, ValueError):
        errors.append("predictions_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def verify_predictions(
    predictions: Mapping[str, Any], pack: Mapping[str, Any], authority: Mapping[str, Any]
) -> dict[str, Any]:
    """Recompute all three systems and require exact equality."""

    errors = list(validate_predictions(predictions, pack, authority)["errors"])
    if not errors:
        try:
            expected = run_comparative(pack, authority)
            if hash_object(expected) != hash_object(predictions):
                errors.append("predictions_reproduction_mismatch")
        except ComparativeBenchmarkError:
            errors.append("predictions_inputs_invalid")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "disposition": "ADMIT_PREDICTIONS" if not errors else "DENY_PREDICTIONS",
    }


def _empty_metrics() -> dict[str, int]:
    return {
        "scored_cases": 0,
        "gold_exposed": 0,
        "gold_no_exposure": 0,
        "missed_exposure": 0,
        "exposure_detected": 0,
        "exposure_reopened_or_reviewed": 0,
        "exposure_marked_survives": 0,
        "hard_false_quarantine": 0,
        "unnecessary_unresolved_review": 0,
        "total_hard_quarantine": 0,
        "total_unresolved_review": 0,
        "total_review_load": 0,
        "unnecessary_review_load": 0,
    }


def score_comparative(
    pack: Mapping[str, Any],
    authority: Mapping[str, Any],
    gold: Mapping[str, Any],
    predictions: Mapping[str, Any],
) -> dict[str, Any]:
    """Score visible error counts; no composite score or automatic promotion."""

    errors = list(validate_gold(gold, pack)["errors"])
    errors.extend(validate_predictions(predictions, pack, authority)["errors"])
    if errors:
        raise ComparativeBenchmarkError("; ".join(sorted(set(errors))))

    gold_by_case = {str(item["case_id"]): str(item["outcome"]) for item in gold["labels"]}
    prediction_by_case = {str(item["case_id"]): item for item in predictions["rows"]}
    case_by_id = {str(item["case_id"]): item for item in pack["cases"]}
    strata = sorted({str(case["stratum"]) for case in pack["cases"]})
    metrics: dict[str, dict[str, dict[str, int]]] = {
        "ALL": {system: _empty_metrics() for system in SYSTEMS},
        **{stratum: {system: _empty_metrics() for system in SYSTEMS} for stratum in strata},
    }

    scored_rows = []
    for case_id in sorted(case_by_id):
        outcome = gold_by_case[case_id]
        stratum = str(case_by_id[case_id]["stratum"])
        row_out = {"case_id": case_id, "stratum": stratum, "gold": outcome, "systems": {}}
        for system in SYSTEMS:
            classification = str(prediction_by_case[case_id]["predictions"][system])
            row_out["systems"][system] = classification
            if outcome == "UNASSESSED":
                continue
            for scope in ("ALL", stratum):
                bucket = metrics[scope][system]
                bucket["scored_cases"] += 1
                if outcome == "EXPOSED":
                    bucket["gold_exposed"] += 1
                    if classification == "UNAFFECTED":
                        bucket["missed_exposure"] += 1
                    else:
                        bucket["exposure_detected"] += 1
                    if classification in {"QUARANTINE", "AFFECTED_UNRESOLVED"}:
                        bucket["exposure_reopened_or_reviewed"] += 1
                    if classification == "SURVIVES":
                        bucket["exposure_marked_survives"] += 1
                else:
                    bucket["gold_no_exposure"] += 1
                    if classification == "QUARANTINE":
                        bucket["hard_false_quarantine"] += 1
                    if classification == "AFFECTED_UNRESOLVED":
                        bucket["unnecessary_unresolved_review"] += 1
                    if classification in {"QUARANTINE", "AFFECTED_UNRESOLVED"}:
                        bucket["unnecessary_review_load"] += 1
                if classification == "QUARANTINE":
                    bucket["total_hard_quarantine"] += 1
                if classification == "AFFECTED_UNRESOLVED":
                    bucket["total_unresolved_review"] += 1
                if classification in {"QUARANTINE", "AFFECTED_UNRESOLVED"}:
                    bucket["total_review_load"] += 1
        scored_rows.append(row_out)

    body = {
        "schema": COMPARATIVE_SCORE_SCHEMA,
        "benchmark_id": str(pack["benchmark_id"]),
        "pack_id": str(pack["pack_id"]),
        "authority_id": str(authority["authority_id"]),
        "gold_id": str(gold["gold_id"]),
        "predictions_id": str(predictions["predictions_id"]),
        "metrics": metrics,
        "rows": scored_rows,
        "claim_boundary": (
            "Scores external exposure labels against three frozen mechanisms. AFFECTED_UNRESOLVED "
            "counts as detected exposure but also consumes review load. SURVIVES counts as structurally "
            "touched without hard quarantine. No composite score or commercial-moat claim is derived."
        ),
    }
    return {"score_id": content_id("evidence-recall-comparative-score", body), **body}


def verify_score(
    score: Mapping[str, Any],
    pack: Mapping[str, Any],
    authority: Mapping[str, Any],
    gold: Mapping[str, Any],
    predictions: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        expected = score_comparative(pack, authority, gold, predictions)
        if score.get("schema") != COMPARATIVE_SCORE_SCHEMA:
            errors.append("score_schema_invalid")
        if score.get("score_id") != content_id("evidence-recall-comparative-score", _without_id(score, "score_id")):
            errors.append("score_id_mismatch")
        if hash_object(score) != hash_object(expected):
            errors.append("score_reproduction_mismatch")
    except (ComparativeBenchmarkError, KeyError, TypeError, ValueError):
        errors.append("score_inputs_invalid")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "disposition": "ADMIT_SCORE" if not errors else "DENY_SCORE",
    }


def _find_header(fieldnames: Sequence[str], aliases: Sequence[str], *, required: bool = True) -> str | None:
    by_key = {_header_key(name): name for name in fieldnames}
    for alias in aliases:
        if _header_key(alias) in by_key:
            return by_key[_header_key(alias)]
    if required:
        raise ComparativeBenchmarkError(f"required CSV column missing; expected one of: {aliases}")
    return None


def import_schneider_csv(
    path: str | Path,
    *,
    canonical_counts: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Split the Schneider V2 CSV into public pack, blind authority, and private gold.

    Authority is intentionally conservative and answer-independent:
    Matsuyama -> first generation is HARD because the corpus itself was selected
    for direct papers that discuss Matsuyama methods/results; first generation ->
    second generation is ADVISORY because citation/context alone is not promoted
    into required dependence.  The external ``Review possible impact overall?``
    field is used *only* for the private gold file.
    """

    source_path = Path(path)
    raw = source_path.read_bytes()
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ComparativeBenchmarkError("Schneider CSV has no header")
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ComparativeBenchmarkError("Schneider CSV has duplicate headers")
    fieldnames = list(reader.fieldnames)
    two_g = _find_header(fieldnames, ["2G article"])
    two_g_title = _find_header(fieldnames, ["2G Title", "2G Officially translated title"], required=False)
    two_g_url = _find_header(fieldnames, ["2G URL"], required=False)
    first_g = _find_header(fieldnames, ["FG in bibliography"])
    first_g_title = _find_header(fieldnames, ["FG Title", "FG Officially translated title"], required=False)
    no_access = _find_header(fieldnames, ["No access"], required=False)
    pending = _find_header(fieldnames, ["Annotation pending"], required=False)
    overall = _find_header(fieldnames, ["Review possible impact overall?"])
    two_g_is_fg = _find_header(fieldnames, ["2G is also FG"], required=False)

    rows = list(reader)
    cases = []
    raw_labels: dict[str, str] = {}
    edge_authority: dict[str, str] = {}
    accessible_rows = 0
    positive_rows = 0
    unassessed_rows = 0

    root_id = "publication:matsuyama-2005"
    for row_index, row in enumerate(rows, start=2):
        if no_access and _canonical_token(row.get(no_access, "")):
            continue
        if pending and _canonical_token(row.get(pending, "")).upper() == "Y":
            continue
        accessible_rows += 1
        two_g_id = _canonical_token(row.get(two_g, ""))
        first_g_id = _canonical_token(row.get(first_g, ""))
        if not two_g_id or not first_g_id:
            raise ComparativeBenchmarkError(f"row {row_index}: missing 2G or FG identifier")
        fg_node = f"publication:fg:{first_g_id}"
        two_g_node = f"publication:2g:{two_g_id}"
        nodes = [
            {
                "node_id": root_id,
                "label": "Matsuyama 2005 retracted clinical trial",
                "text": "Matsuyama 2005 retracted clinical trial",
                "locator": "doi:10.1378/chest.128.6.3817",
                "independent_basis": False,
            },
            {
                "node_id": fg_node,
                "label": _canonical_token(row.get(first_g_title, "")) if first_g_title else first_g_id,
                "text": _canonical_token(row.get(first_g_title, "")) if first_g_title else first_g_id,
                "locator": first_g_id,
                "independent_basis": False,
            },
            {
                "node_id": two_g_node,
                "label": _canonical_token(row.get(two_g_title, "")) if two_g_title else two_g_id,
                "text": _canonical_token(row.get(two_g_title, "")) if two_g_title else two_g_id,
                "locator": _canonical_token(row.get(two_g_url, "")) if two_g_url else two_g_id,
                "independent_basis": False,
            },
        ]
        first_edge = {
            "prerequisite_node_id": root_id,
            "dependent_node_id": fg_node,
            "relation": "DERIVED_FROM",
            "evidence": ["corpus selection: direct paper discusses Matsuyama methods/results"],
        }
        first_edge["edge_id"] = _edge_id(first_edge)
        second_edge = {
            "prerequisite_node_id": fg_node,
            "dependent_node_id": two_g_node,
            "relation": "DEPENDS_ON",
            "evidence": ["second-generation citation to first-generation paper"],
        }
        second_edge["edge_id"] = _edge_id(second_edge)
        # If a 2G item is itself also a direct citation, add the direct topology
        # edge using a public, non-gold column.  This prevents the direct baseline
        # from being artificially blinded to a real direct citation.
        edges = [first_edge, second_edge]
        if two_g_is_fg and _canonical_token(row.get(two_g_is_fg, "")).casefold() in {"y", "yes", "true", "1"}:
            direct_edge = {
                "prerequisite_node_id": root_id,
                "dependent_node_id": two_g_node,
                "relation": "DERIVED_FROM",
                "evidence": ["public dataset marks 2G item as also first-generation"],
            }
            direct_edge["edge_id"] = _edge_id(direct_edge)
            edges.append(direct_edge)
            edge_authority[direct_edge["edge_id"]] = "HARD"
        case = create_case(
            stratum="SCHNEIDER_SECOND_GENERATION",
            invalidated_node_id=root_id,
            target_node_id=two_g_node,
            nodes=nodes,
            edges=edges,
            metadata={
                "row_number": row_index,
                "second_generation_id": two_g_id,
                "first_generation_id": first_g_id,
            },
        )
        cases.append(case)
        edge_authority[first_edge["edge_id"]] = "HARD"
        edge_authority[second_edge["edge_id"]] = "ADVISORY"
        gold_value = _canonical_token(row.get(overall, ""))
        if gold_value.upper() == "Y":
            outcome = "EXPOSED"
            positive_rows += 1
        elif gold_value == "" or gold_value.upper() == "N" or "REMOVED AS NOT" in gold_value.upper():
            outcome = "NO_EXPOSURE"
        elif "NOT ASSESSED" in gold_value.upper():
            outcome = "UNASSESSED"
            unassessed_rows += 1
        else:
            raise ComparativeBenchmarkError(f"row {row_index}: unrecognized external gold value: {gold_value!r}")
        raw_labels[case["case_id"]] = outcome

    if canonical_counts:
        if accessible_rows != 152:
            raise ComparativeBenchmarkError(
                f"canonical Schneider V2 expected 152 accessible assessed rows after access/pending filtering; got {accessible_rows}"
            )
        if positive_rows != 23:
            raise ComparativeBenchmarkError(
                f"canonical Schneider V2 expected 23 possible-misinformation positives; got {positive_rows}"
            )

    manifest = [
        {
            "role": "external_case_and_gold_source",
            "identifier": f"doi:{SCHNEIDER_DATASET_DOI}",
            "sha256": sha256_hex(raw),
            "filename": source_path.name,
            "license": "CC0",
        },
        {
            "role": "published_method_and_counts",
            "identifier": f"doi:{SCHNEIDER_ARTICLE_DOI}",
        },
    ]
    pack = create_pack(
        benchmark_id="schneider-matsuyama-second-generation-v2",
        cases=cases,
        source_manifest=manifest,
        construction_rule=(
            "Exclude inaccessible and annotation-pending rows; construct citation topology and identifiers from public fields only; "
            "exclude answer-bearing annotation fields from the public pack."
        ),
    )
    authority = create_authority(
        pack,
        edge_authority=edge_authority,
        declared_by="benchmark-protocol",
        construction_rule=(
            "Matsuyama-to-selected-first-generation edges are HARD from the corpus selection rule; "
            "ordinary first-to-second-generation citation edges are ADVISORY; any public direct-overlap edge is HARD. "
            "No possible-impact label is consulted."
        ),
    )
    gold = create_gold(
        pack,
        raw_labels,
        source=f"Illinois Data Bank {SCHNEIDER_DATASET_DOI}",
        label_definition=(
            "EXPOSED iff Review possible impact overall? is Y; NO_EXPOSURE for assessed non-positive rows; "
            "UNASSESSED for explicit not-assessed rows. These are external annotations of possible misinformation diffusion, not truth labels."
        ),
    )
    import_report = {
        "valid": True,
        "source_sha256": sha256_hex(raw),
        "raw_rows": len(rows),
        "accessible_rows": accessible_rows,
        "positive_rows": positive_rows,
        "unassessed_rows": unassessed_rows,
        "pack_id": pack["pack_id"],
        "authority_id": authority["authority_id"],
        "gold_id": gold["gold_id"],
        "anti_leakage": "public pack contains no reserved gold-bearing fields; authority rule is label-independent",
    }
    return pack, authority, gold, import_report


def parse_dot_edges(text: str) -> list[tuple[str, str]]:
    """Parse simple directed DOT edges without executing Graphviz."""

    token = r'(?:"((?:\\.|[^"\\])*)"|([A-Za-z0-9_.:+/\-]+))'
    pattern = re.compile(token + r"\s*->\s*" + token)
    edges: list[tuple[str, str]] = []
    for match in pattern.finditer(text):
        left = match.group(1) if match.group(1) is not None else match.group(2)
        right = match.group(3) if match.group(3) is not None else match.group(4)
        if left is not None and right is not None:
            edges.append((left.replace('\\"', '"'), right.replace('\\"', '"')))
    return sorted(set(edges))



def import_van_der_vet_dot(
    path: str | Path,
    *,
    root_node_id: str,
    inspected_target_ids: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build the published van der Vet/Nijveen indirect-propagation negative control.

    The paper's DOT arrows point from citing -> cited.  Evidence-flow direction is
    therefore inverted before constructing cases.  ``inspected_target_ids`` must
    be the predeclared indirect candidates manually inspected by the authors; all
    receive NO_EXPOSURE gold because the published case study reports zero
    indirect propagation among those inspected candidates.
    """

    source_path = Path(path)
    raw = source_path.read_bytes()
    text = raw.decode("utf-8-sig")
    citation_edges = parse_dot_edges(text)
    if not citation_edges:
        raise ComparativeBenchmarkError("van der Vet DOT contains no directed edges")
    # DOT: citing -> cited. Benchmark dependency flow: cited -> citing.
    flow_edges = sorted({(cited, citing) for citing, cited in citation_edges})
    nodes_all = sorted({item for edge in flow_edges for item in edge})
    if root_node_id not in nodes_all:
        raise ComparativeBenchmarkError(f"van der Vet root node absent from DOT: {root_node_id}")
    adjacency: dict[str, list[str]] = {}
    for prerequisite, dependent in flow_edges:
        adjacency.setdefault(prerequisite, []).append(dependent)
    for key in adjacency:
        adjacency[key] = sorted(set(adjacency[key]))
    reachable = _reachable(root_node_id, adjacency)

    cases = []
    edge_authority: dict[str, str] = {}
    labels: dict[str, str] = {}
    for target in sorted(set(map(str, inspected_target_ids))):
        if target == root_node_id or target not in reachable:
            raise ComparativeBenchmarkError(f"inspected target is not an indirect reachable node: {target}")
        # Keep only nodes/edges that can sit on a root->target path.  Compute
        # descendants from root and ancestors of target in dependency direction.
        reverse: dict[str, list[str]] = {}
        for prerequisite, dependent in flow_edges:
            reverse.setdefault(dependent, []).append(prerequisite)
        ancestors = _reachable(target, reverse)
        path_nodes = reachable & ancestors
        if target not in path_nodes or root_node_id not in path_nodes:
            raise ComparativeBenchmarkError(f"no dependency path to inspected target: {target}")
        nodes = [
            {
                "node_id": item,
                "label": item,
                "text": item,
                "locator": item,
                "independent_basis": False,
            }
            for item in sorted(path_nodes)
        ]
        edges = []
        for prerequisite, dependent in flow_edges:
            if prerequisite not in path_nodes or dependent not in path_nodes:
                continue
            edge = {
                "prerequisite_node_id": prerequisite,
                "dependent_node_id": dependent,
                "relation": "DEPENDS_ON",
                "evidence": ["citation topology from published supplementary DOT"],
            }
            edge["edge_id"] = _edge_id(edge)
            edges.append(edge)
        case = create_case(
            stratum="VAN_DER_VET_NEGATIVE_CONTROL",
            invalidated_node_id=root_node_id,
            target_node_id=target,
            nodes=nodes,
            edges=edges,
            metadata={"inspected_target_id": target},
        )
        cases.append(case)
        labels[case["case_id"]] = "NO_EXPOSURE"
        # Direct root edges are mechanically established as direct citation
        # topology.  All later hops remain advisory because the negative-control
        # question is exactly whether indirect citation carried the result.
        for edge in case["edges"]:
            edge_authority[edge["edge_id"]] = (
                "HARD" if edge["prerequisite_node_id"] == root_node_id else "ADVISORY"
            )

    pack = create_pack(
        benchmark_id="van-der-vet-nijveen-indirect-negative-control",
        cases=cases,
        source_manifest=[
            {
                "role": "citation_network",
                "identifier": f"doi:{VAN_DER_VET_ARTICLE_DOI}",
                "filename": source_path.name,
                "sha256": sha256_hex(raw),
            }
        ],
        construction_rule=(
            "Invert supplementary DOT citing-to-cited arrows into evidence-flow direction; retain only root-to-inspected-target paths; "
            "target selection is the paper's predeclared manually inspected indirect candidate set."
        ),
    )
    authority = create_authority(
        pack,
        edge_authority=edge_authority,
        declared_by="benchmark-protocol",
        construction_rule="direct root citation edges HARD; all indirect citation edges ADVISORY; no inspection outcome consulted",
    )
    gold = create_gold(
        pack,
        labels,
        source=f"doi:{VAN_DER_VET_ARTICLE_DOI}",
        label_definition="NO_EXPOSURE for the paper's manually inspected indirect candidates; authors report no indirect propagation in this case study.",
    )
    report = {
        "valid": True,
        "source_sha256": sha256_hex(raw),
        "citation_edges": len(citation_edges),
        "reachable_nodes": len(reachable),
        "inspected_targets": len(cases),
        "pack_id": pack["pack_id"],
        "authority_id": authority["authority_id"],
        "gold_id": gold["gold_id"],
    }
    return pack, authority, gold, report

def build_published_diagnostic() -> dict[str, Any]:
    """Source-backed aggregate diagnostic when case-level raw bytes are absent.

    This is deliberately *not* labeled a case-level benchmark result.  It uses
    published aggregate counts and the predeclared conservative citation-only
    authority rule to expose what each system would do at that coarse level.
    """

    schneider = {
        "source": f"doi:{SCHNEIDER_ARTICLE_DOI}",
        "status": "PUBLISHED_AGGREGATE_DIAGNOSTIC",
        "accessible_second_generation": 152,
        "externally_annotated_possible_diffusion": 23,
        "not_marked_possible_diffusion_or_unassessed": 129,
        "second_generation_items_also_direct_in_full_161_network": 4,
        "systems": {
            SYSTEM_DIRECT: {
                "missed_exposure": 23,
                "note": "The published 23 positives are described as non-direct; exact nonpositive direct-overlap scoring awaits row-level bytes.",
            },
            SYSTEM_NAIVE: {
                "missed_exposure": 0,
                "hard_false_quarantine_lower_bound": 125,
                "total_review_load": 152,
                "note": "Lower bound excludes all four possible direct-overlap records from false-positive scoring because their accessible/assessment status is not recoverable from aggregate counts alone.",
            },
            SYSTEM_EVIDENCE_RECALL: {
                "missed_exposure": 0,
                "hard_false_quarantine": 0,
                "unnecessary_unresolved_review_lower_bound": 125,
                "total_review_load": 152,
                "note": "Under the predeclared citation-only policy, ordinary second-generation edges remain advisory; public direct-overlap edges would be hard. Exact split awaits row-level bytes.",
            },
        },
        "assumption": (
            "Ordinary first-to-second-generation citation edges remain ADVISORY until independently admitted; public direct-overlap edges are HARD. "
            "Aggregate counts alone cannot resolve which of the four direct-overlap records were among the 152 accessible cases, so over-taint counts are lower bounds."
        ),
        "diagnosis": (
            "Even under the favorable lower-bound treatment, conservative Evidence Recall converts much of naive hard over-taint into unresolved review but does not reduce total reviewer load. "
            "A case-level blind authority file is required to test selective precision."
        ),
    }
    van_der_vet = {
        "source": f"doi:{VAN_DER_VET_ARTICLE_DOI}",
        "status": "PUBLISHED_NEGATIVE_CONTROL_AGGREGATE",
        "indirect_candidates_manually_inspected": 10,
        "indirect_propagation_found": 0,
        "systems": {
            SYSTEM_DIRECT: {
                "hard_false_quarantine": 0,
                "unnecessary_unresolved_review": 0,
                "total_review_load": 0,
            },
            SYSTEM_NAIVE: {
                "hard_false_quarantine": 10,
                "unnecessary_unresolved_review": 0,
                "total_review_load": 10,
            },
            SYSTEM_EVIDENCE_RECALL: {
                "hard_false_quarantine": 0,
                "unnecessary_unresolved_review": 10,
                "total_review_load": 10,
            },
        },
        "assumption": "All indirect citation edges remain ADVISORY absent independently admitted semantic dependence.",
    }
    jama = {
        "source": f"doi:{JAMA_ARTICLE_DOI}",
        "status": "QUANTITATIVE_DEPENDENCY_STRESS_TEST_AGGREGATE",
        "meta_analyses_rerun": 166,
        "significance_changed": 18,
        "no_change_pooled_effect": 21,
        "effect_evolution_cases": 163,
        "effect_change_ge_10_percent": 57,
        "effect_change_ge_30_percent": 31,
        "effect_change_ge_50_percent": 23,
        "reviews": 50,
        "reviews_with_potentially_meaningful_abstract_interpretation_change": 7,
        "scoring_rule": (
            "Do not call unchanged recomputations false quarantine. Evidence Recall is a reconsideration detector, not a predictor "
            "that the recomputed numerical result must differ. These counts diagnose whether categorical dependency semantics are "
            "selective enough for quantitative aggregation."
        ),
    }
    body = {
        "schema": PUBLISHED_DIAGNOSTIC_SCHEMA,
        "status": "AGGREGATE_DIAGNOSTIC_ONLY_CASE_LEVEL_EMPIRICAL_PROMOTION_BLOCKED",
        "schneider": schneider,
        "van_der_vet": van_der_vet,
        "jama": jama,
        "claim_boundary": (
            "Published aggregate counts are independently grounded, but this report is not a substitute for the sealed case-level run. "
            "It cannot establish an Evidence Recall advantage from selective relation authority because no case-level blind authority "
            "file is evaluated here."
        ),
    }
    return {"diagnostic_id": content_id("evidence-recall-published-diagnostic", body), **body}


def verify_published_diagnostic(report: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_published_diagnostic()
    errors: list[str] = []
    if report.get("schema") != PUBLISHED_DIAGNOSTIC_SCHEMA:
        errors.append("published_diagnostic_schema_invalid")
    if report.get("diagnostic_id") != content_id("evidence-recall-published-diagnostic", _without_id(report, "diagnostic_id")):
        errors.append("published_diagnostic_id_mismatch")
    if hash_object(report) != hash_object(expected):
        errors.append("published_diagnostic_reproduction_mismatch")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "disposition": "ADMIT_AGGREGATE_DIAGNOSTIC" if not errors else "DENY_AGGREGATE_DIAGNOSTIC",
    }
