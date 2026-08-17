"""Temporal holdout benchmark for Evidence Recall.

The benchmark tests a narrower, prospective-style claim than the structural
comparative benchmark.  A public accepted state is frozen at ``t0``.  A single
triggering event that became available at ``t1`` is revealed.  Predictions are
produced without access to any later record.  Separately sealed records from
``t2 > t1`` provide external evidence about whether each target really
warranted reconsideration.

The shipped Evidence Recall engine is reused unchanged.  This module adds only
benchmark custody, a stronger reachability-review baseline, temporal leakage
checks, and scoring.  It does not add weighted support, new relation semantics,
AI edge discovery, generalized revocation, or product UI.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from .canonical import content_id, hash_object, sha256_hex
from .comparative_benchmark import (
    AUTHORITIES,
    RELATIONS,
    _materialize_evidence_recall,
)


TEMPORAL_PACK_SCHEMA = "openline.evidence-recall-temporal-pack.v1"
TEMPORAL_AUTHORITY_SCHEMA = "openline.evidence-recall-temporal-authority.v1"
TEMPORAL_FUTURE_SEAL_SCHEMA = "openline.evidence-recall-temporal-future-seal.v1"
TEMPORAL_GOLD_SCHEMA = "openline.evidence-recall-temporal-gold.v1"
TEMPORAL_PREDICTIONS_SCHEMA = "openline.evidence-recall-temporal-predictions.v1"
TEMPORAL_SCORE_SCHEMA = "openline.evidence-recall-temporal-score.v1"
TEMPORAL_PUBLISHED_DIAGNOSTIC_SCHEMA = "openline.evidence-recall-temporal-published-diagnostic.v1"

SYSTEM_DIRECT = "DIRECT_LOOKUP"
SYSTEM_REVIEW_ALL = "REVIEW_ALL_REACHABILITY"
SYSTEM_EVIDENCE_RECALL = "EVIDENCE_RECALL"
SYSTEM_NAIVE_DIAGNOSTIC = "NAIVE_TRANSITIVE_TAINT_DIAGNOSTIC"
SYSTEMS = (SYSTEM_DIRECT, SYSTEM_REVIEW_ALL, SYSTEM_EVIDENCE_RECALL)
SYSTEMS_WITH_DIAGNOSTIC = SYSTEMS + (SYSTEM_NAIVE_DIAGNOSTIC,)

GOLD_OUTCOMES = ("REOPEN", "NO_REOPEN", "UNASSESSED")
RAW_CLASSIFICATIONS = (
    "DIRECT_REVIEW",
    "REVIEW",
    "QUARANTINE",
    "SURVIVES",
    "AFFECTED_UNRESOLVED",
    "UNAFFECTED",
)

# These record types are evidence that a target warranted reconsideration even
# when the conclusion ultimately survived.  In particular, an explicit
# reanalysis that reports no change is still a REOPEN signal: someone had to
# revisit the accepted state to establish that result.
REOPEN_RECORD_TYPES = (
    "SYSTEMATIC_REVIEW_REVISED",
    "SYSTEMATIC_REVIEW_REANALYZED",
    "EXPLICIT_NO_CHANGE_AFTER_REANALYSIS",
    "GUIDELINE_RECOMMENDATION_CHANGED",
    "GUIDELINE_EXPLICITLY_RECONSIDERED",
    "DOWNSTREAM_CORRECTION",
    "DOWNSTREAM_WITHDRAWAL",
    "DOWNSTREAM_RETRACTION",
    "PREDECLARED_QUANTITATIVE_THRESHOLD_CROSSED",
    "REGULATORY_POSITION_CHANGED",
    "ACCEPTED_DECISION_FORMALLY_REOPENED",
    "INDEPENDENT_DEPENDENCY_AUDIT_RELIANCE",
)

# Negative gold must be affirmative evidence of non-reliance or scope, not the
# mere absence of a correction.  Silence is never converted into NO_REOPEN.
NO_REOPEN_RECORD_TYPES = (
    "INDEPENDENT_DEPENDENCY_AUDIT_NO_RELIANCE",
    "FORMAL_SCOPE_EXCLUSION",
    "INDEPENDENT_CITATION_CONTEXT_NO_RELIANCE",
)
FUTURE_RECORD_TYPES = tuple(sorted(set(REOPEN_RECORD_TYPES) | set(NO_REOPEN_RECORD_TYPES)))

# Answer-bearing keys are prohibited inside the pre-cutoff graph itself.  The
# temporal package necessarily contains a future-seal *commitment*, but not the
# sealed records or labels.
RESERVED_PRE_CUTOFF_KEY_FRAGMENTS = (
    "gold",
    "outcome",
    "reopen",
    "later result",
    "future result",
    "post event",
    "post-event",
)

KATAOKA_ARTICLE_DOI = "10.1016/j.jclinepi.2022.06.015"
JAMA_ARTICLE_DOI = "10.1001/jamainternmed.2025.0256"
VITALITY_ARTICLE_DOI = "10.1136/bmj-2024-082068"
COCHRANE_LETROZOLE_DOI = "10.1002/14651858.CD010287.pub3"


class TemporalHoldoutError(ValueError):
    """Raised when temporal benchmark inputs fail closed."""


def _without_id(record: Mapping[str, Any], field: str) -> dict[str, Any]:
    body = dict(record)
    body.pop(field, None)
    return body


def _token(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_time(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise TemporalHoldoutError("timestamp missing")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TemporalHoldoutError(f"timestamp invalid: {value}") from exc
    if parsed.tzinfo is None:
        raise TemporalHoldoutError(f"timestamp must include timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _normalized_time(value: Any) -> str:
    return _parse_time(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _edge_id(edge: Mapping[str, Any]) -> str:
    body = {
        "prerequisite_node_id": str(edge["prerequisite_node_id"]),
        "dependent_node_id": str(edge["dependent_node_id"]),
        "relation": str(edge["relation"]).upper(),
        "available_at": _normalized_time(edge["available_at"]),
        "evidence": sorted({_token(item) for item in edge.get("evidence", []) if _token(item)}),
    }
    return content_id("temporal-edge", body)


def create_future_record(
    *,
    episode_id: str,
    available_at: str,
    record_type: str,
    target_node_ids: Iterable[str],
    locator: str,
    evidence_sha256: str,
    description: str,
) -> dict[str, Any]:
    """Create one private, post-event record used only after predictions exist."""

    body = {
        "episode_id": str(episode_id),
        "available_at": _normalized_time(available_at),
        "record_type": str(record_type).upper(),
        "target_node_ids": sorted(set(map(str, target_node_ids))),
        "locator": _token(locator),
        "evidence_sha256": str(evidence_sha256).lower(),
        "description": _token(description),
    }
    return {"record_id": content_id("temporal-future-record", body), **body}


def create_future_seal(
    *,
    benchmark_id: str,
    scope_definition: str,
    retrieval_cutoff_at: str,
    records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Content-address the exact later-record corpus before it is used as gold."""

    normalized = sorted((dict(item) for item in records), key=lambda item: str(item["record_id"]))
    body = {
        "schema": TEMPORAL_FUTURE_SEAL_SCHEMA,
        "benchmark_id": _token(benchmark_id),
        "scope_definition": _token(scope_definition),
        "retrieval_cutoff_at": _normalized_time(retrieval_cutoff_at),
        "records": normalized,
    }
    return {"future_seal_id": content_id("evidence-recall-temporal-future-seal", body), **body}


def _future_commitment(seal: Mapping[str, Any]) -> dict[str, Any]:
    records = list(seal.get("records", []))
    return {
        "future_seal_id": str(seal["future_seal_id"]),
        "record_count": len(records),
        "records_root": sha256_hex(
            "\n".join(str(item["record_id"]) for item in records).encode("utf-8")
        ),
        "scope_sha256": sha256_hex(str(seal["scope_definition"]).encode("utf-8")),
        "retrieval_cutoff_at": str(seal["retrieval_cutoff_at"]),
    }


def create_episode(
    *,
    episode_name: str,
    cutoff_at: str,
    event_at: str,
    invalidated_node_id: str,
    target_node_ids: Iterable[str],
    nodes: Iterable[Mapping[str, Any]],
    edges: Iterable[Mapping[str, Any]],
    event: Mapping[str, Any],
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one public historical episode from information available by t0 plus the t1 event."""

    normalized_nodes = []
    seen_nodes: set[str] = set()
    for raw in nodes:
        item = {
            "node_id": str(raw["node_id"]),
            "label": _token(raw.get("label", raw["node_id"])),
            "text": _token(raw.get("text", raw.get("label", raw["node_id"]))),
            "locator": _token(raw.get("locator", "")),
            "available_at": _normalized_time(raw["available_at"]),
            "independent_basis": bool(raw.get("independent_basis", False)),
        }
        if item["node_id"] in seen_nodes:
            raise TemporalHoldoutError(f"duplicate node id: {item['node_id']}")
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
            "available_at": _normalized_time(raw["available_at"]),
            "evidence": sorted({_token(value) for value in raw.get("evidence", []) if _token(value)}),
        }
        item["edge_id"] = str(raw.get("edge_id") or _edge_id(item))
        if item["edge_id"] in seen_edges:
            raise TemporalHoldoutError(f"duplicate edge id: {item['edge_id']}")
        seen_edges.add(item["edge_id"])
        normalized_edges.append(item)
    normalized_edges.sort(key=lambda item: item["edge_id"])

    event_body = {
        "status": str(event.get("status", "RETRACTED")).upper(),
        "identifier": _token(event.get("identifier", "")),
        "locator": _token(event.get("locator", "")),
        "reason": _token(event.get("reason", "")),
        "available_at": _normalized_time(event.get("available_at", event_at)),
        "evidence_sha256": str(event.get("evidence_sha256", "")).lower(),
    }
    body = {
        "episode_name": _token(episode_name),
        "cutoff_at": _normalized_time(cutoff_at),
        "event_at": _normalized_time(event_at),
        "invalidated_node_id": str(invalidated_node_id),
        "target_node_ids": sorted(set(map(str, target_node_ids))),
        "nodes": normalized_nodes,
        "edges": normalized_edges,
        "event": event_body,
        "metadata": dict(metadata or {}),
    }
    return {"episode_id": content_id("temporal-holdout-episode", body), **body}


def create_pack(
    *,
    benchmark_id: str,
    episodes: Iterable[Mapping[str, Any]],
    source_manifest: Sequence[Mapping[str, Any]],
    construction_rule: str,
    future_seal: Mapping[str, Any],
    status: str = "TEMPORAL_INPUTS_FROZEN",
) -> dict[str, Any]:
    """Create the prediction-visible pack while exposing only a commitment to future records."""

    body = {
        "schema": TEMPORAL_PACK_SCHEMA,
        "benchmark_id": _token(benchmark_id),
        "status": _token(status),
        "construction_rule": _token(construction_rule),
        "source_manifest": sorted(
            (dict(item) for item in source_manifest),
            key=lambda item: (str(item.get("role", "")), str(item.get("identifier", ""))),
        ),
        "future_seal_commitment": _future_commitment(future_seal),
        "episodes": sorted((dict(item) for item in episodes), key=lambda item: str(item["episode_id"])),
    }
    return {"pack_id": content_id("evidence-recall-temporal-pack", body), **body}


def create_authority(
    pack: Mapping[str, Any],
    *,
    edge_authority: Mapping[str, str] | Iterable[Mapping[str, Any]],
    declared_by: str,
    construction_rule: str,
) -> dict[str, Any]:
    """Freeze episode-scoped receiver authority without access to later gold.

    A simple ``edge_id -> authority`` mapping is accepted when the same policy
    applies wherever an identical edge appears.  An iterable of explicit
    ``episode_id`` / ``edge_id`` / ``authority`` records supports different
    historical receiver policies for otherwise identical edges.
    """

    if isinstance(edge_authority, Mapping):
        entries = []
        for episode in pack.get("episodes", []):
            for edge in episode.get("edges", []):
                edge_id = str(edge["edge_id"])
                if edge_id in edge_authority:
                    entries.append(
                        {
                            "episode_id": str(episode["episode_id"]),
                            "edge_id": edge_id,
                            "authority": str(edge_authority[edge_id]).upper(),
                        }
                    )
    else:
        entries = [
            {
                "episode_id": str(item["episode_id"]),
                "edge_id": str(item["edge_id"]),
                "authority": str(item["authority"]).upper(),
            }
            for item in edge_authority
        ]
    entries.sort(key=lambda item: (item["episode_id"], item["edge_id"]))
    body = {
        "schema": TEMPORAL_AUTHORITY_SCHEMA,
        "benchmark_id": str(pack["benchmark_id"]),
        "pack_id": str(pack["pack_id"]),
        "declared_by": _token(declared_by),
        "construction_rule": _token(construction_rule),
        "edge_authority": entries,
    }
    return {"authority_id": content_id("evidence-recall-temporal-authority", body), **body}


def create_gold(
    pack: Mapping[str, Any],
    future_seal: Mapping[str, Any],
    labels: Iterable[Mapping[str, Any]],
    *,
    label_definition: str,
) -> dict[str, Any]:
    entries = []
    for raw in labels:
        entries.append(
            {
                "episode_id": str(raw["episode_id"]),
                "target_node_id": str(raw["target_node_id"]),
                "outcome": str(raw["outcome"]).upper(),
                "future_record_ids": sorted(set(map(str, raw.get("future_record_ids", [])))),
            }
        )
    entries.sort(key=lambda item: (item["episode_id"], item["target_node_id"]))
    body = {
        "schema": TEMPORAL_GOLD_SCHEMA,
        "benchmark_id": str(pack["benchmark_id"]),
        "pack_id": str(pack["pack_id"]),
        "future_seal_id": str(future_seal["future_seal_id"]),
        "label_definition": _token(label_definition),
        "labels": entries,
    }
    return {"gold_id": content_id("evidence-recall-temporal-gold", body), **body}


def _reserved_keys(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = " ".join(str(raw_key).casefold().replace("_", " ").replace("-", " ").split())
            if any(fragment in key for fragment in RESERVED_PRE_CUTOFF_KEY_FRAGMENTS):
                errors.append(f"answer_bearing_pre_cutoff_key:{path}.{raw_key}")
            errors.extend(_reserved_keys(child, f"{path}.{raw_key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_reserved_keys(child, f"{path}[{index}]"))
    return errors


def validate_future_seal(seal: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        if seal.get("schema") != TEMPORAL_FUTURE_SEAL_SCHEMA:
            errors.append("future_seal_schema_invalid")
        if seal.get("future_seal_id") != content_id(
            "evidence-recall-temporal-future-seal", _without_id(seal, "future_seal_id")
        ):
            errors.append("future_seal_id_mismatch")
        retrieval_cutoff = _parse_time(seal.get("retrieval_cutoff_at"))
        records = seal.get("records")
        if not isinstance(records, list):
            errors.append("future_seal_records_invalid")
            records = []
        ids: list[str] = []
        for record in records:
            if not isinstance(record, Mapping):
                errors.append("future_record_invalid")
                continue
            record_id = str(record.get("record_id", ""))
            ids.append(record_id)
            if record_id != content_id("temporal-future-record", _without_id(record, "record_id")):
                errors.append(f"future_record_id_mismatch:{record_id}")
            if record.get("record_type") not in FUTURE_RECORD_TYPES:
                errors.append(f"future_record_type_invalid:{record_id}")
            available_at = _parse_time(record.get("available_at"))
            if available_at > retrieval_cutoff:
                errors.append(f"future_record_after_retrieval_cutoff:{record_id}")
            targets = record.get("target_node_ids")
            if not isinstance(targets, list) or targets != sorted(set(map(str, targets))):
                errors.append(f"future_record_targets_not_canonical:{record_id}")
            digest = str(record.get("evidence_sha256", ""))
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                errors.append(f"future_record_digest_invalid:{record_id}")
        if ids != sorted(set(ids)):
            errors.append("future_records_not_canonical_or_unique")
    except (KeyError, TypeError, ValueError, TemporalHoldoutError):
        errors.append("future_seal_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def validate_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = [
        "temporal_separation_does_not_prove_graph_constructor_ignored_future_knowledge",
        "historical_reconstruction_procedure_must_be_frozen_and_auditable",
    ]
    try:
        if pack.get("schema") != TEMPORAL_PACK_SCHEMA:
            errors.append("pack_schema_invalid")
        if pack.get("pack_id") != content_id("evidence-recall-temporal-pack", _without_id(pack, "pack_id")):
            errors.append("pack_id_mismatch")
        source_manifest = pack.get("source_manifest", [])
        if not isinstance(source_manifest, list):
            errors.append("source_manifest_invalid")
            source_manifest = []
        errors.extend(_reserved_keys(source_manifest, "$.source_manifest"))
        episodes = pack.get("episodes")
        if not isinstance(episodes, list) or not episodes:
            errors.append("pack_episodes_empty")
            episodes = []
        commitment = pack.get("future_seal_commitment")
        if not isinstance(commitment, Mapping):
            errors.append("future_seal_commitment_missing")
        else:
            if not str(commitment.get("future_seal_id", "")):
                errors.append("future_seal_commitment_id_missing")
            if int(commitment.get("record_count", -1)) < 0:
                errors.append("future_seal_commitment_count_invalid")
            for name in ("records_root", "scope_sha256"):
                digest = str(commitment.get(name, ""))
                if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                    errors.append(f"future_seal_commitment_{name}_invalid")
            _parse_time(commitment.get("retrieval_cutoff_at"))

        episode_ids: list[str] = []
        all_edge_ids: set[str] = set()
        for episode in episodes:
            if not isinstance(episode, Mapping):
                errors.append("episode_invalid")
                continue
            episode_id = str(episode.get("episode_id", ""))
            episode_ids.append(episode_id)
            if episode_id != content_id("temporal-holdout-episode", _without_id(episode, "episode_id")):
                errors.append(f"episode_id_mismatch:{episode_id}")
            cutoff = _parse_time(episode.get("cutoff_at"))
            event_at = _parse_time(episode.get("event_at"))
            if not cutoff < event_at:
                errors.append(f"episode_time_order_invalid:{episode_id}")
            nodes = episode.get("nodes")
            edges = episode.get("edges")
            targets = list(map(str, episode.get("target_node_ids", [])))
            if not isinstance(nodes, list) or not nodes:
                errors.append(f"episode_nodes_empty:{episode_id}")
                nodes = []
            if not isinstance(edges, list):
                errors.append(f"episode_edges_invalid:{episode_id}")
                edges = []
            node_ids = [str(item.get("node_id", "")) for item in nodes if isinstance(item, Mapping)]
            if node_ids != sorted(set(node_ids)):
                errors.append(f"episode_nodes_not_canonical:{episode_id}")
            node_set = set(node_ids)
            if str(episode.get("invalidated_node_id", "")) not in node_set:
                errors.append(f"episode_origin_unknown:{episode_id}")
            if targets != sorted(set(targets)) or not targets:
                errors.append(f"episode_targets_invalid:{episode_id}")
            for target in targets:
                if target not in node_set:
                    errors.append(f"episode_target_unknown:{episode_id}:{target}")
            for node in nodes:
                if _parse_time(node.get("available_at")) > cutoff:
                    errors.append(f"node_after_cutoff:{episode_id}:{node.get('node_id')}")
                errors.extend(_reserved_keys(node, f"episode[{episode_id}].node[{node.get('node_id')}]") )
            edge_ids: list[str] = []
            for edge in edges:
                edge_id = str(edge.get("edge_id", ""))
                edge_ids.append(edge_id)
                all_edge_ids.add(edge_id)
                if edge_id != _edge_id(edge):
                    errors.append(f"edge_id_mismatch:{episode_id}:{edge_id}")
                if edge.get("relation") not in RELATIONS:
                    errors.append(f"edge_relation_invalid:{episode_id}:{edge_id}")
                if str(edge.get("prerequisite_node_id", "")) not in node_set or str(edge.get("dependent_node_id", "")) not in node_set:
                    errors.append(f"edge_node_unknown:{episode_id}:{edge_id}")
                if _parse_time(edge.get("available_at")) > cutoff:
                    errors.append(f"edge_after_cutoff:{episode_id}:{edge_id}")
                errors.extend(_reserved_keys(edge, f"episode[{episode_id}].edge[{edge_id}]") )
            if edge_ids != sorted(set(edge_ids)):
                errors.append(f"episode_edges_not_canonical:{episode_id}")
            event = episode.get("event")
            if not isinstance(event, Mapping):
                errors.append(f"episode_event_invalid:{episode_id}")
            else:
                event_available = _parse_time(event.get("available_at"))
                if not cutoff < event_available <= event_at:
                    errors.append(f"episode_event_availability_invalid:{episode_id}")
                if not str(event.get("identifier", "")):
                    errors.append(f"episode_event_identifier_missing:{episode_id}")
                digest = str(event.get("evidence_sha256", ""))
                if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                    errors.append(f"episode_event_digest_invalid:{episode_id}")
            errors.extend(_reserved_keys(episode.get("metadata", {}), f"episode[{episode_id}].metadata"))
        if episode_ids != sorted(set(episode_ids)):
            errors.append("episodes_not_canonical_or_unique")
        if not all_edge_ids and episodes:
            warnings.append("temporal_pack_contains_no_dependency_edges")
    except (KeyError, TypeError, ValueError, TemporalHoldoutError):
        errors.append("pack_invalid")
    return {"valid": not errors, "errors": sorted(set(errors)), "warnings": sorted(set(warnings))}


def validate_authority(authority: Mapping[str, Any], pack: Mapping[str, Any]) -> dict[str, Any]:
    errors = list(validate_pack(pack)["errors"])
    try:
        if authority.get("schema") != TEMPORAL_AUTHORITY_SCHEMA:
            errors.append("authority_schema_invalid")
        if authority.get("authority_id") != content_id(
            "evidence-recall-temporal-authority", _without_id(authority, "authority_id")
        ):
            errors.append("authority_id_mismatch")
        if authority.get("benchmark_id") != pack.get("benchmark_id") or authority.get("pack_id") != pack.get("pack_id"):
            errors.append("authority_pack_binding_mismatch")
        known = {
            (str(episode["episode_id"]), str(edge["edge_id"]))
            for episode in pack.get("episodes", [])
            for edge in episode.get("edges", [])
        }
        entries = authority.get("edge_authority")
        if not isinstance(entries, list):
            errors.append("authority_entries_invalid")
            entries = []
        keys: list[tuple[str, str]] = []
        for entry in entries:
            key = (str(entry.get("episode_id", "")), str(entry.get("edge_id", "")))
            keys.append(key)
            if key not in known:
                errors.append(f"authority_edge_unknown:{key[0]}:{key[1]}")
            if entry.get("authority") not in AUTHORITIES:
                errors.append(f"authority_value_invalid:{key[0]}:{key[1]}")
        if keys != sorted(set(keys)) or set(keys) != known:
            errors.append("authority_edges_not_canonical_or_complete")
    except (KeyError, TypeError, ValueError):
        errors.append("authority_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def validate_future_seal_for_pack(seal: Mapping[str, Any], pack: Mapping[str, Any]) -> dict[str, Any]:
    errors = list(validate_future_seal(seal)["errors"])
    errors.extend(validate_pack(pack)["errors"])
    try:
        commitment = _future_commitment(seal)
        if hash_object(commitment) != hash_object(pack.get("future_seal_commitment", {})):
            errors.append("future_seal_commitment_mismatch")
        if seal.get("benchmark_id") != pack.get("benchmark_id"):
            errors.append("future_seal_benchmark_mismatch")
        episodes = {str(item["episode_id"]): item for item in pack.get("episodes", [])}
        for record in seal.get("records", []):
            episode_id = str(record.get("episode_id", ""))
            episode = episodes.get(episode_id)
            if episode is None:
                errors.append(f"future_record_episode_unknown:{record.get('record_id')}:{episode_id}")
                continue
            known_targets = set(map(str, episode.get("target_node_ids", [])))
            for target in record.get("target_node_ids", []):
                target = str(target)
                if target not in known_targets:
                    errors.append(f"future_record_target_unknown:{record.get('record_id')}:{target}")
                elif _parse_time(record["available_at"]) <= _parse_time(episode["event_at"]):
                    errors.append(f"future_record_not_after_event:{record.get('record_id')}:{target}")
    except (KeyError, TypeError, ValueError, TemporalHoldoutError):
        errors.append("future_seal_pack_binding_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def validate_gold(gold: Mapping[str, Any], pack: Mapping[str, Any], future_seal: Mapping[str, Any]) -> dict[str, Any]:
    errors = list(validate_future_seal_for_pack(future_seal, pack)["errors"])
    try:
        if gold.get("schema") != TEMPORAL_GOLD_SCHEMA:
            errors.append("gold_schema_invalid")
        if gold.get("gold_id") != content_id("evidence-recall-temporal-gold", _without_id(gold, "gold_id")):
            errors.append("gold_id_mismatch")
        if gold.get("benchmark_id") != pack.get("benchmark_id") or gold.get("pack_id") != pack.get("pack_id"):
            errors.append("gold_pack_binding_mismatch")
        if gold.get("future_seal_id") != future_seal.get("future_seal_id"):
            errors.append("gold_future_seal_binding_mismatch")
        expected = {
            (str(episode["episode_id"]), str(target))
            for episode in pack.get("episodes", [])
            for target in episode.get("target_node_ids", [])
        }
        records = {str(item["record_id"]): item for item in future_seal.get("records", [])}
        entries = gold.get("labels")
        if not isinstance(entries, list):
            errors.append("gold_labels_invalid")
            entries = []
        keys: list[tuple[str, str]] = []
        for entry in entries:
            key = (str(entry.get("episode_id", "")), str(entry.get("target_node_id", "")))
            keys.append(key)
            if key not in expected:
                errors.append(f"gold_target_unknown:{key[0]}:{key[1]}")
            outcome = str(entry.get("outcome", ""))
            if outcome not in GOLD_OUTCOMES:
                errors.append(f"gold_outcome_invalid:{key[0]}:{key[1]}")
            record_ids = list(map(str, entry.get("future_record_ids", [])))
            if record_ids != sorted(set(record_ids)):
                errors.append(f"gold_record_ids_not_canonical:{key[0]}:{key[1]}")
            if outcome == "UNASSESSED":
                if record_ids:
                    errors.append(f"gold_unassessed_has_evidence:{key[0]}:{key[1]}")
                continue
            if not record_ids:
                errors.append(f"gold_assessed_missing_evidence:{key[0]}:{key[1]}")
                continue
            allowed_types = set(REOPEN_RECORD_TYPES if outcome == "REOPEN" else NO_REOPEN_RECORD_TYPES)
            matching = False
            for record_id in record_ids:
                record = records.get(record_id)
                if record is None:
                    errors.append(f"gold_future_record_unknown:{record_id}")
                    continue
                if str(record.get("episode_id", "")) != key[0]:
                    errors.append(f"gold_future_record_episode_mismatch:{record_id}:{key[0]}")
                if key[1] not in set(map(str, record.get("target_node_ids", []))):
                    errors.append(f"gold_future_record_target_mismatch:{record_id}:{key[1]}")
                if record.get("record_type") in allowed_types:
                    matching = True
            if not matching:
                errors.append(f"gold_evidence_polarity_mismatch:{key[0]}:{key[1]}")
        if keys != sorted(set(keys)) or set(keys) != expected:
            errors.append("gold_labels_not_canonical_or_complete")
    except (KeyError, TypeError, ValueError):
        errors.append("gold_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def _adjacency(episode: Mapping[str, Any]) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}
    for edge in episode.get("edges", []):
        prerequisite = str(edge["prerequisite_node_id"])
        dependent = str(edge["dependent_node_id"])
        adjacency.setdefault(prerequisite, []).append(dependent)
    for node in adjacency:
        adjacency[node] = sorted(set(adjacency[node]))
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


def _comparative_case(episode: Mapping[str, Any], target: str) -> dict[str, Any]:
    # _materialize_evidence_recall reads only these fields.  The temporal
    # timestamps remain bound by the parent episode and are intentionally not
    # fed into the frozen impact engine, whose semantics are unchanged.
    return {
        "case_id": f"temporal:{episode['episode_id']}:{target}",
        "invalidated_node_id": str(episode["invalidated_node_id"]),
        "target_node_id": str(target),
        "nodes": [
            {
                "node_id": str(node["node_id"]),
                "label": str(node["label"]),
                "text": str(node["text"]),
                "locator": str(node.get("locator", "")),
                "independent_basis": bool(node.get("independent_basis", False)),
            }
            for node in episode["nodes"]
        ],
        "edges": [
            {
                "edge_id": str(edge["edge_id"]),
                "prerequisite_node_id": str(edge["prerequisite_node_id"]),
                "dependent_node_id": str(edge["dependent_node_id"]),
                "relation": str(edge["relation"]),
                "evidence": list(edge.get("evidence", [])),
            }
            for edge in episode["edges"]
        ],
    }


def _prediction(raw: str, review: bool) -> dict[str, Any]:
    return {"classification": raw, "review": bool(review)}


def run_temporal(
    pack: Mapping[str, Any],
    authority: Mapping[str, Any],
    *,
    include_naive_diagnostic: bool = True,
) -> dict[str, Any]:
    """Run all systems with no future seal or gold object in scope."""

    errors = validate_authority(authority, pack)["errors"]
    if errors:
        raise TemporalHoldoutError("; ".join(errors))
    authority_by_episode: dict[str, dict[str, str]] = {}
    for item in authority["edge_authority"]:
        authority_by_episode.setdefault(str(item["episode_id"]), {})[str(item["edge_id"])] = str(item["authority"])
    rows = []
    for episode in pack["episodes"]:
        origin = str(episode["invalidated_node_id"])
        adjacency = _adjacency(episode)
        reachable = _reachable(origin, adjacency) - {origin}
        direct = {
            str(edge["dependent_node_id"])
            for edge in episode.get("edges", [])
            if str(edge["prerequisite_node_id"]) == origin
        }
        for target in episode["target_node_ids"]:
            target = str(target)
            er_raw = _materialize_evidence_recall(
                _comparative_case(episode, target),
                authority_by_episode[str(episode["episode_id"])],
            )
            predictions: dict[str, Any] = {
                SYSTEM_DIRECT: _prediction("DIRECT_REVIEW" if target in direct else "UNAFFECTED", target in direct),
                SYSTEM_REVIEW_ALL: _prediction("REVIEW" if target in reachable else "UNAFFECTED", target in reachable),
                SYSTEM_EVIDENCE_RECALL: _prediction(
                    er_raw,
                    er_raw in {"QUARANTINE", "AFFECTED_UNRESOLVED"},
                ),
            }
            if include_naive_diagnostic:
                predictions[SYSTEM_NAIVE_DIAGNOSTIC] = _prediction(
                    "QUARANTINE" if target in reachable else "UNAFFECTED",
                    target in reachable,
                )
            rows.append(
                {
                    "episode_id": str(episode["episode_id"]),
                    "target_node_id": target,
                    "predictions": predictions,
                }
            )
    rows.sort(key=lambda item: (item["episode_id"], item["target_node_id"]))
    body = {
        "schema": TEMPORAL_PREDICTIONS_SCHEMA,
        "benchmark_id": str(pack["benchmark_id"]),
        "pack_id": str(pack["pack_id"]),
        "authority_id": str(authority["authority_id"]),
        "future_seal_id": str(pack["future_seal_commitment"]["future_seal_id"]),
        "systems": list(SYSTEMS_WITH_DIAGNOSTIC if include_naive_diagnostic else SYSTEMS),
        "engine_contract": {
            "direct_lookup": "review only immediate dependents of the invalidated node",
            "review_all_reachability": "review every target reachable over any directed edge",
            "evidence_recall": "frozen shipped Evidence Recall semantics; QUARANTINE and AFFECTED_UNRESOLVED require review, SURVIVES and UNAFFECTED do not",
            "naive_transitive_taint_diagnostic": "optional diagnostic: hard quarantine every reachable target",
        },
        "rows": rows,
    }
    return {"predictions_id": content_id("evidence-recall-temporal-predictions", body), **body}


def validate_predictions(
    predictions: Mapping[str, Any], pack: Mapping[str, Any], authority: Mapping[str, Any]
) -> dict[str, Any]:
    errors = list(validate_authority(authority, pack)["errors"])
    try:
        if predictions.get("schema") != TEMPORAL_PREDICTIONS_SCHEMA:
            errors.append("predictions_schema_invalid")
        if predictions.get("predictions_id") != content_id(
            "evidence-recall-temporal-predictions", _without_id(predictions, "predictions_id")
        ):
            errors.append("predictions_id_mismatch")
        if predictions.get("benchmark_id") != pack.get("benchmark_id") or predictions.get("pack_id") != pack.get("pack_id"):
            errors.append("predictions_pack_binding_mismatch")
        if predictions.get("authority_id") != authority.get("authority_id"):
            errors.append("predictions_authority_binding_mismatch")
        if predictions.get("future_seal_id") != pack.get("future_seal_commitment", {}).get("future_seal_id"):
            errors.append("predictions_future_seal_binding_mismatch")
        systems = tuple(predictions.get("systems", []))
        if systems not in (SYSTEMS, SYSTEMS_WITH_DIAGNOSTIC):
            errors.append("predictions_systems_invalid")
        expected = {
            (str(episode["episode_id"]), str(target))
            for episode in pack.get("episodes", [])
            for target in episode.get("target_node_ids", [])
        }
        rows = predictions.get("rows")
        if not isinstance(rows, list):
            errors.append("predictions_rows_invalid")
            rows = []
        keys: list[tuple[str, str]] = []
        for row in rows:
            key = (str(row.get("episode_id", "")), str(row.get("target_node_id", "")))
            keys.append(key)
            if key not in expected:
                errors.append(f"prediction_target_unknown:{key[0]}:{key[1]}")
            values = row.get("predictions")
            if not isinstance(values, Mapping) or set(values) != set(systems):
                errors.append(f"prediction_systems_invalid:{key[0]}:{key[1]}")
                continue
            for system, result in values.items():
                if not isinstance(result, Mapping):
                    errors.append(f"prediction_result_invalid:{key[0]}:{key[1]}:{system}")
                    continue
                if result.get("classification") not in RAW_CLASSIFICATIONS:
                    errors.append(f"prediction_classification_invalid:{key[0]}:{key[1]}:{system}")
                if not isinstance(result.get("review"), bool):
                    errors.append(f"prediction_review_invalid:{key[0]}:{key[1]}:{system}")
        if keys != sorted(set(keys)) or set(keys) != expected:
            errors.append("predictions_rows_not_canonical_or_complete")
    except (KeyError, TypeError, ValueError):
        errors.append("predictions_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def verify_predictions(
    predictions: Mapping[str, Any], pack: Mapping[str, Any], authority: Mapping[str, Any]
) -> dict[str, Any]:
    errors = list(validate_predictions(predictions, pack, authority)["errors"])
    if not errors:
        try:
            expected = run_temporal(
                pack,
                authority,
                include_naive_diagnostic=SYSTEM_NAIVE_DIAGNOSTIC in predictions.get("systems", []),
            )
            if hash_object(expected) != hash_object(predictions):
                errors.append("predictions_reproduction_mismatch")
        except TemporalHoldoutError:
            errors.append("predictions_reproduction_failed")
    return {"valid": not errors, "errors": sorted(set(errors))}


def _rate(numerator: int, denominator: int) -> dict[str, int] | None:
    """Return an exact integer-backed rate compatible with canonical JSON."""

    if denominator == 0:
        return None
    return {
        "numerator": numerator,
        "denominator": denominator,
        "basis_points": (numerator * 10_000) // denominator,
    }


def _ratio(numerator: int, denominator: int) -> dict[str, int] | None:
    """Return an exact ratio without introducing forbidden floating point."""

    if denominator == 0:
        return None
    return {"numerator": numerator, "denominator": denominator}


def score_temporal(
    pack: Mapping[str, Any],
    authority: Mapping[str, Any],
    future_seal: Mapping[str, Any],
    gold: Mapping[str, Any],
    predictions: Mapping[str, Any],
) -> dict[str, Any]:
    """Score reconsideration precision/recall and human-review burden without a composite score."""

    errors = []
    errors.extend(validate_gold(gold, pack, future_seal)["errors"])
    errors.extend(verify_predictions(predictions, pack, authority)["errors"])
    if errors:
        raise TemporalHoldoutError("; ".join(sorted(set(errors))))

    gold_by_key = {
        (str(item["episode_id"]), str(item["target_node_id"])): str(item["outcome"])
        for item in gold["labels"]
    }
    systems = tuple(predictions["systems"])
    counts = {
        system: {
            "scored_cases": 0,
            "reopen_gold": 0,
            "no_reopen_gold": 0,
            "true_reopen_reviews": 0,
            "missed_reopenings": 0,
            "unnecessary_reviews": 0,
            "correct_nonreviews": 0,
            "total_review_load": 0,
            "unresolved_review_load": 0,
            "hard_quarantine_load": 0,
        }
        for system in systems
    }
    episode_counts: dict[str, dict[str, dict[str, int]]] = {}

    for row in predictions["rows"]:
        key = (str(row["episode_id"]), str(row["target_node_id"]))
        outcome = gold_by_key[key]
        if outcome == "UNASSESSED":
            continue
        per_episode = episode_counts.setdefault(
            key[0],
            {
                system: {
                    "scored_cases": 0,
                    "true_reopen_reviews": 0,
                    "missed_reopenings": 0,
                    "unnecessary_reviews": 0,
                    "total_review_load": 0,
                }
                for system in systems
            },
        )
        for system in systems:
            prediction = row["predictions"][system]
            review = bool(prediction["review"])
            raw = str(prediction["classification"])
            metric = counts[system]
            episode_metric = per_episode[system]
            metric["scored_cases"] += 1
            episode_metric["scored_cases"] += 1
            if review:
                metric["total_review_load"] += 1
                episode_metric["total_review_load"] += 1
            if raw == "AFFECTED_UNRESOLVED":
                metric["unresolved_review_load"] += 1
            if raw == "QUARANTINE":
                metric["hard_quarantine_load"] += 1
            if outcome == "REOPEN":
                metric["reopen_gold"] += 1
                if review:
                    metric["true_reopen_reviews"] += 1
                    episode_metric["true_reopen_reviews"] += 1
                else:
                    metric["missed_reopenings"] += 1
                    episode_metric["missed_reopenings"] += 1
            elif outcome == "NO_REOPEN":
                metric["no_reopen_gold"] += 1
                if review:
                    metric["unnecessary_reviews"] += 1
                    episode_metric["unnecessary_reviews"] += 1
                else:
                    metric["correct_nonreviews"] += 1

    metrics: dict[str, Any] = {}
    for system, metric in counts.items():
        derived = dict(metric)
        derived["reconsideration_precision"] = _rate(
            metric["true_reopen_reviews"],
            metric["true_reopen_reviews"] + metric["unnecessary_reviews"],
        )
        derived["reconsideration_recall"] = _rate(
            metric["true_reopen_reviews"], metric["reopen_gold"]
        )
        derived["review_burden"] = _rate(metric["total_review_load"], metric["scored_cases"])
        derived["unnecessary_review_rate"] = _rate(
            metric["unnecessary_reviews"], metric["no_reopen_gold"]
        )
        derived["relevant_reopenings_caught_per_unnecessary_review"] = _ratio(
            metric["true_reopen_reviews"], metric["unnecessary_reviews"]
        )
        metrics[system] = derived

    baseline = metrics[SYSTEM_REVIEW_ALL]
    comparisons: dict[str, Any] = {}
    for system in systems:
        current = metrics[system]
        comparisons[system] = {
            "reviewer_savings_vs_review_all": baseline["total_review_load"] - current["total_review_load"],
            "unnecessary_review_savings_vs_review_all": baseline["unnecessary_reviews"] - current["unnecessary_reviews"],
            "additional_missed_reopenings_vs_review_all": current["missed_reopenings"] - baseline["missed_reopenings"],
        }

    body = {
        "schema": TEMPORAL_SCORE_SCHEMA,
        "benchmark_id": str(pack["benchmark_id"]),
        "pack_id": str(pack["pack_id"]),
        "authority_id": str(authority["authority_id"]),
        "future_seal_id": str(future_seal["future_seal_id"]),
        "gold_id": str(gold["gold_id"]),
        "predictions_id": str(predictions["predictions_id"]),
        "metrics": metrics,
        "comparisons_vs_review_all": comparisons,
        "episode_counts": episode_counts,
        "primary_question": (
            "When a new event arrives, does frozen Evidence Recall catch later independently recorded "
            "reopenings while waking fewer targets than review-all reachability?"
        ),
        "claim_boundary": (
            "Gold measures independently recorded later reconsideration, not eventual falsity. "
            "No absence of correction is treated as NO_REOPEN. No composite score or automatic "
            "promotion threshold is computed."
        ),
    }
    return {"score_id": content_id("evidence-recall-temporal-score", body), **body}


def verify_score(
    score: Mapping[str, Any],
    pack: Mapping[str, Any],
    authority: Mapping[str, Any],
    future_seal: Mapping[str, Any],
    gold: Mapping[str, Any],
    predictions: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        if score.get("schema") != TEMPORAL_SCORE_SCHEMA:
            errors.append("score_schema_invalid")
        if score.get("score_id") != content_id("evidence-recall-temporal-score", _without_id(score, "score_id")):
            errors.append("score_id_mismatch")
        expected = score_temporal(pack, authority, future_seal, gold, predictions)
        if hash_object(expected) != hash_object(score):
            errors.append("score_reproduction_mismatch")
    except (TemporalHoldoutError, KeyError, TypeError, ValueError):
        errors.append("score_inputs_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def build_published_diagnostic() -> dict[str, Any]:
    """Record source-backed corpus candidates without pretending a temporal run occurred."""

    body = {
        "schema": TEMPORAL_PUBLISHED_DIAGNOSTIC_SCHEMA,
        "status": "TEMPORAL_CORPUS_CANDIDATES_VERIFIED_CASE_LEVEL_HOLDOUT_NOT_YET_RUN",
        "benchmark_claim": (
            "The promotion question is temporal selectivity: after a new event, catch later independently "
            "recorded reconsiderations with less human review than review-all reachability."
        ),
        "candidate_corpora": {
            "kataoka_2022": {
                "doi": KATAOKA_ARTICLE_DOI,
                "published_facts": {
                    "articles_citing_retracted_rcts": 587,
                    "published_before_retraction": 335,
                    "published_after_retraction": 252,
                    "pre_retraction_articles_using_rct_in_evidence_synthesis": 239,
                    "systematic_reviews_using_rct": 196,
                    "clinical_practice_guidelines_using_rct": 43,
                    "systematic_reviews_later_corrected_or_retracted": 9,
                    "clinical_practice_guidelines_later_corrected": 2,
                },
                "benchmark_role": "candidate temporal cohort; absence of later correction is not negative gold",
            },
            "jama_2025": {
                "doi": JAMA_ARTICLE_DOI,
                "published_facts": {
                    "meta_analyses_recomputed": 166,
                    "statistical_significance_changed": 18,
                    "meta_analyses_with_no_pooled_estimate_change": 21,
                },
                "benchmark_role": "quantitative abstraction stress asset, not automatic NO_REOPEN gold",
            },
            "vitality_2025": {
                "doi": VITALITY_ARTICLE_DOI,
                "published_facts": {
                    "retracted_rcts": 1330,
                    "systematic_reviews_quantitatively_synthesizing_retracted_trials": 847,
                    "meta_analyses_replicated": 3902,
                    "meta_analyses_substantially_impacted": 218,
                    "systematic_reviews_with_substantially_impacted_meta_analyses": 68,
                    "guideline_documents_using_impacted_evidence": 157,
                },
                "benchmark_role": "candidate independently recomputed downstream-outcome substrate",
            },
            "cochrane_letrozole_2021": {
                "doi": COCHRANE_LETROZOLE_DOI,
                "published_fact": (
                    "review update excluded prior studies because of validity/retraction concerns while reporting that conclusions did not change"
                ),
                "benchmark_role": "positive example: warranted reconsideration can end in survival",
            },
        },
        "not_present": [
            "case-level temporal predictions",
            "case-level temporal gold",
            "empirical Evidence Recall temporal advantage",
            "commercial moat evidence",
        ],
    }
    return {"diagnostic_id": content_id("evidence-recall-temporal-published-diagnostic", body), **body}


def verify_published_diagnostic(report: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        if report.get("schema") != TEMPORAL_PUBLISHED_DIAGNOSTIC_SCHEMA:
            errors.append("diagnostic_schema_invalid")
        if report.get("diagnostic_id") != content_id(
            "evidence-recall-temporal-published-diagnostic", _without_id(report, "diagnostic_id")
        ):
            errors.append("diagnostic_id_mismatch")
        if report.get("status") != "TEMPORAL_CORPUS_CANDIDATES_VERIFIED_CASE_LEVEL_HOLDOUT_NOT_YET_RUN":
            errors.append("diagnostic_status_invalid")
    except (KeyError, TypeError, ValueError):
        errors.append("diagnostic_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}
