"""Prospective Decision Recall benchmark primitives.

This module tests the missing upstream assumption behind Evidence Recall:
whether a small dependency record can be frozen when a decision is accepted and
later support selective REOPEN / SURVIVE / ESCALATE dispositions when one
recorded basis loses standing.

The module is deliberately a benchmark/control layer.  It does not change the
frozen Evidence Recall inference semantics and it does not claim that a declared
dependency is causal truth.  A manifest is accepted operational state whose
quality is itself under test.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from .canonical import content_id, hash_object, sha256_hex


DECISION_MANIFEST_SCHEMA = "openline.decision-recall-manifest.v1"
DECISION_PRE_TRIGGER_RECORD_SCHEMA = "openline.decision-recall-pre-trigger-record.v1"
DECISION_STREAM_SEAL_SCHEMA = "openline.decision-recall-stream-seal.v2"
DECISION_REVOCATION_EVENT_SCHEMA = "openline.decision-recall-revocation-event.v1"
DECISION_PREDICTIONS_SCHEMA = "openline.decision-recall-predictions.v1"
DECISION_ADJUDICATION_PACKET_SCHEMA = "openline.decision-recall-adjudication-packet.v1"
DECISION_GOLD_SCHEMA = "openline.decision-recall-gold.v1"
DECISION_REVIEW_PACKET_SCHEMA = "openline.decision-recall-review-packet.v1"
DECISION_REVIEW_OUTCOME_SCHEMA = "openline.decision-recall-review-outcome.v1"
DECISION_REVIEW_TIMES_SCHEMA = "openline.decision-recall-review-times.v1"
DECISION_SCORE_SCHEMA = "openline.decision-recall-score.v1"
DECISION_PROMOTION_POLICY_SCHEMA = "openline.decision-recall-promotion-policy.v1"
DECISION_PROMOTION_RESULT_SCHEMA = "openline.decision-recall-promotion-result.v1"
DECISION_STANDING_STATE_SCHEMA = "openline.decision-recall-standing-state.v1"
DECISION_STANDING_EVENT_SCHEMA = "openline.decision-recall-standing-event.v1"
DECISION_GAIN_REPORT_SCHEMA = "openline.decision-recall-gain-report.v1"

SYSTEM_FULL_HISTORY = "FULL_HISTORY_REVIEW"
SYSTEM_FLAT_SEARCH = "FLAT_LOG_SEARCH"
SYSTEM_DECISION_RECALL = "DECISION_RECALL"
SYSTEMS = (SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH, SYSTEM_DECISION_RECALL)

GOLD_LABELS = ("REOPEN", "SURVIVE", "ESCALATE")
DECISION_RECALL_DISPOSITIONS = GOLD_LABELS
BASELINE_DISPOSITIONS = ("REVIEW", "SURVIVE")
BASIS_ROLES = ("REQUIRED", "ALTERNATIVE", "CONTEXT", "AMBIGUOUS")
EVENT_TYPES = ("LOSS_OF_STANDING", "GAIN_OF_STANDING")


class DecisionRecallError(ValueError):
    """Raised when a prospective Decision Recall artifact fails closed."""


def _token(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_time(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise DecisionRecallError("timestamp missing")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise DecisionRecallError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise DecisionRecallError(f"timestamp must include timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _time(value: Any) -> str:
    return _parse_time(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _without(record: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = dict(record)
    result.pop(field, None)
    return result


def _basis_item(raw: Mapping[str, Any]) -> dict[str, Any]:
    role = str(raw.get("role", "CONTEXT")).upper()
    if role not in BASIS_ROLES:
        raise DecisionRecallError(f"unknown basis role: {role}")
    basis_id = _token(raw.get("basis_id"))
    if not basis_id:
        raise DecisionRecallError("basis_id missing")
    evidence_sha256 = str(raw.get("evidence_sha256", "")).lower().strip()
    if evidence_sha256 and (len(evidence_sha256) != 64 or any(c not in "0123456789abcdef" for c in evidence_sha256)):
        raise DecisionRecallError(f"invalid evidence_sha256 for {basis_id}")
    return {
        "basis_id": basis_id,
        "kind": _token(raw.get("kind", "OTHER")).upper(),
        "statement": _token(raw.get("statement")),
        "locator": _token(raw.get("locator")),
        "evidence_sha256": evidence_sha256,
        "role": role,
        "alternative_group": _token(raw.get("alternative_group")) if role == "ALTERNATIVE" else "",
    }


def _assumption_item(raw: Mapping[str, Any]) -> dict[str, Any]:
    assumption_id = _token(raw.get("assumption_id"))
    if not assumption_id:
        raise DecisionRecallError("assumption_id missing")
    role = str(raw.get("role", "REQUIRED")).upper()
    if role not in ("REQUIRED", "AMBIGUOUS", "CONTEXT"):
        raise DecisionRecallError(f"assumption {assumption_id}: role must be REQUIRED, AMBIGUOUS, or CONTEXT")
    return {
        "assumption_id": assumption_id,
        "statement": _token(raw.get("statement")),
        "role": role,
    }


def create_manifest(
    *,
    decision_id: str,
    accepted_at: str,
    decision: str,
    basis: Iterable[Mapping[str, Any]],
    required_dependencies: Iterable[str],
    alternative_support: Iterable[Mapping[str, Any]],
    assumptions: Iterable[Mapping[str, Any]],
    invalidation_conditions: Iterable[Mapping[str, Any]],
    resulting_artifact: Mapping[str, Any],
    capture: Mapping[str, Any],
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one content-addressed decision-time dependency record."""

    normalized_basis = sorted((_basis_item(item) for item in basis), key=lambda item: item["basis_id"])
    basis_ids = [item["basis_id"] for item in normalized_basis]
    if len(set(basis_ids)) != len(basis_ids):
        raise DecisionRecallError("duplicate basis_id")

    normalized_assumptions = sorted((_assumption_item(item) for item in assumptions), key=lambda item: item["assumption_id"])
    assumption_ids = [item["assumption_id"] for item in normalized_assumptions]
    if len(set(assumption_ids)) != len(assumption_ids):
        raise DecisionRecallError("duplicate assumption_id")

    all_dependency_ids = set(basis_ids) | set(assumption_ids)
    required = sorted(set(map(str, required_dependencies)))
    missing_required = sorted(set(required) - all_dependency_ids)
    if missing_required:
        raise DecisionRecallError(f"required dependencies missing from basis/assumptions: {missing_required}")
    roles = {item["basis_id"]: item["role"] for item in normalized_basis}
    roles.update({item["assumption_id"]: item["role"] for item in normalized_assumptions})
    bad_required = sorted(item for item in required if roles.get(item) != "REQUIRED")
    if bad_required:
        raise DecisionRecallError(f"required_dependencies must reference REQUIRED items: {bad_required}")

    alternatives = []
    seen_groups: set[str] = set()
    for raw in alternative_support:
        group_id = _token(raw.get("group_id"))
        dependencies = sorted(set(map(str, raw.get("dependency_ids", []))))
        if not group_id or not dependencies:
            raise DecisionRecallError("alternative support group requires group_id and dependency_ids")
        if group_id in seen_groups:
            raise DecisionRecallError(f"duplicate alternative support group: {group_id}")
        missing = sorted(set(dependencies) - all_dependency_ids)
        if missing:
            raise DecisionRecallError(f"alternative group {group_id} references missing dependencies: {missing}")
        bad_alternatives = sorted(item for item in dependencies if roles.get(item) != "ALTERNATIVE")
        if bad_alternatives:
            raise DecisionRecallError(f"alternative group {group_id} must reference ALTERNATIVE items: {bad_alternatives}")
        for dependency_id in dependencies:
            basis_entry = next((item for item in normalized_basis if item["basis_id"] == dependency_id), None)
            if basis_entry is not None and basis_entry.get("alternative_group") and basis_entry["alternative_group"] != group_id:
                raise DecisionRecallError(f"alternative basis {dependency_id} declares group {basis_entry['alternative_group']} but is assigned to {group_id}")
        seen_groups.add(group_id)
        alternatives.append({"group_id": group_id, "dependency_ids": dependencies})
    alternatives.sort(key=lambda item: item["group_id"])
    grouped = {dependency_id for group in alternatives for dependency_id in group["dependency_ids"]}
    orphaned_alternatives = sorted(item["basis_id"] for item in normalized_basis if item["role"] == "ALTERNATIVE" and item["basis_id"] not in grouped)
    if orphaned_alternatives:
        raise DecisionRecallError(f"ALTERNATIVE basis items must belong to a sufficient alternative group: {orphaned_alternatives}")

    conditions = []
    seen_conditions: set[str] = set()
    for raw in invalidation_conditions:
        condition_id = _token(raw.get("condition_id"))
        dependency_id = _token(raw.get("dependency_id"))
        event_types = sorted(set(str(item).upper() for item in raw.get("event_types", [])))
        if not condition_id or not dependency_id or not event_types:
            raise DecisionRecallError("invalidation condition requires condition_id, dependency_id, and event_types")
        if condition_id in seen_conditions:
            raise DecisionRecallError(f"duplicate invalidation condition: {condition_id}")
        if dependency_id not in all_dependency_ids:
            raise DecisionRecallError(f"condition {condition_id} references unknown dependency {dependency_id}")
        unknown_events = sorted(set(event_types) - set(EVENT_TYPES))
        if unknown_events:
            raise DecisionRecallError(f"condition {condition_id} has unsupported event types: {unknown_events}")
        seen_conditions.add(condition_id)
        conditions.append({
            "condition_id": condition_id,
            "dependency_id": dependency_id,
            "event_types": event_types,
            "note": _token(raw.get("note")),
        })
    conditions.sort(key=lambda item: item["condition_id"])

    capture_started = _time(capture.get("started_at"))
    capture_confirmed = _time(capture.get("confirmed_at"))
    started = _parse_time(capture_started)
    confirmed = _parse_time(capture_confirmed)
    if confirmed < started:
        raise DecisionRecallError("capture confirmed_at precedes started_at")
    measured_ms = int((confirmed - started).total_seconds() * 1000)
    human_ms = int(capture.get("human_capture_milliseconds", measured_ms))
    if human_ms < 0:
        raise DecisionRecallError("human_capture_milliseconds must be non-negative")
    correction_count = int(capture.get("correction_count", 0))
    if correction_count < 0:
        raise DecisionRecallError("correction_count must be non-negative")

    artifact = {
        "kind": _token(resulting_artifact.get("kind", "ARTIFACT")).upper(),
        "locator": _token(resulting_artifact.get("locator")),
        "sha256": str(resulting_artifact.get("sha256", "")).lower().strip(),
    }
    if artifact["sha256"] and (len(artifact["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in artifact["sha256"])):
        raise DecisionRecallError("resulting artifact sha256 invalid")

    body = {
        "schema": DECISION_MANIFEST_SCHEMA,
        "decision_id": _token(decision_id),
        "accepted_at": _time(accepted_at),
        "decision": _token(decision),
        "basis": normalized_basis,
        "required_dependencies": required,
        "alternative_support": alternatives,
        "assumptions": normalized_assumptions,
        "invalidation_conditions": conditions,
        "resulting_artifact": artifact,
        "capture": {
            "started_at": capture_started,
            "confirmed_at": capture_confirmed,
            "human_capture_milliseconds": human_ms,
            "drafted_by": _token(capture.get("drafted_by", "UNKNOWN")),
            "confirmed_by": _token(capture.get("confirmed_by", "RECEIVER")),
            "correction_count": correction_count,
            "accepted_without_correction": correction_count == 0,
            "timing_source": _token(capture.get("timing_source", "DECLARED")).upper(),
        },
        "metadata": dict(sorted((metadata or {}).items())),
    }
    return {"manifest_id": content_id("decision-recall-manifest", body), **body}


def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        rebuilt = create_manifest(
            decision_id=manifest["decision_id"],
            accepted_at=manifest["accepted_at"],
            decision=manifest["decision"],
            basis=manifest.get("basis", []),
            required_dependencies=manifest.get("required_dependencies", []),
            alternative_support=manifest.get("alternative_support", []),
            assumptions=manifest.get("assumptions", []),
            invalidation_conditions=manifest.get("invalidation_conditions", []),
            resulting_artifact=manifest.get("resulting_artifact", {}),
            capture=manifest.get("capture", {}),
            metadata=manifest.get("metadata", {}),
        )
        if manifest.get("schema") != DECISION_MANIFEST_SCHEMA:
            errors.append("schema mismatch")
        if rebuilt["manifest_id"] != manifest.get("manifest_id"):
            errors.append("manifest_id mismatch")
    except (KeyError, TypeError, ValueError, DecisionRecallError) as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors}


def create_pre_trigger_record(*, decision_id: str, decision: str, available_at: str, materials: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Bind the conventional full pre-trigger decision record used by blind gold and baselines."""

    normalized = []
    seen: set[str] = set()
    for raw in materials:
        material_id = _token(raw.get("material_id"))
        if not material_id or material_id in seen:
            raise DecisionRecallError("pre-trigger materials require unique material_id")
        seen.add(material_id)
        evidence = str(raw.get("sha256", "")).lower().strip()
        text = str(raw.get("text", ""))
        if evidence and (len(evidence) != 64 or any(c not in "0123456789abcdef" for c in evidence)):
            raise DecisionRecallError(f"material {material_id}: invalid sha256")
        if not evidence:
            evidence = sha256_hex(text.encode("utf-8"))
        normalized.append({
            "material_id": material_id,
            "kind": _token(raw.get("kind", "OTHER")).upper(),
            "locator": _token(raw.get("locator")),
            "sha256": evidence,
            "text": text,
        })
    normalized.sort(key=lambda item: item["material_id"])
    body = {
        "schema": DECISION_PRE_TRIGGER_RECORD_SCHEMA,
        "decision_id": _token(decision_id),
        "decision": _token(decision),
        "available_at": _time(available_at),
        "materials": normalized,
    }
    return {"pre_trigger_record_id": content_id("decision-recall-pre-trigger-record", body), **body}


def _eligible_basis(raw: Mapping[str, Any], record_ids: set[str]) -> dict[str, Any]:
    basis_id = _token(raw.get("basis_id"))
    if not basis_id:
        raise DecisionRecallError("eligible basis_id missing")
    mentions = sorted(set(map(str, raw.get("mentioned_record_ids", []))))
    missing = sorted(set(mentions) - record_ids)
    if missing:
        raise DecisionRecallError(f"eligible basis {basis_id} references unknown pre-trigger records: {missing}")
    if not mentions:
        raise DecisionRecallError(f"eligible basis {basis_id} must be observed in at least one pre-trigger record")
    evidence = str(raw.get("evidence_sha256", "")).lower().strip()
    if evidence and (len(evidence) != 64 or any(c not in "0123456789abcdef" for c in evidence)):
        raise DecisionRecallError(f"eligible basis {basis_id}: invalid evidence_sha256")
    return {
        "basis_id": basis_id,
        "kind": _token(raw.get("kind", "OTHER")).upper(),
        "locator": _token(raw.get("locator")),
        "evidence_sha256": evidence,
        "mentioned_record_ids": mentions,
    }


def create_stream_seal(
    *,
    benchmark_id: str,
    sealed_at: str,
    manifests: Sequence[Mapping[str, Any]],
    pre_trigger_records: Sequence[Mapping[str, Any]],
    eligible_bases: Sequence[Mapping[str, Any]],
    eligible_basis_catalog_custody: Mapping[str, Any],
    protocol_id: str,
) -> dict[str, Any]:
    """Seal manifests plus an independent full-history/basis universe before any trigger."""

    normalized = sorted((dict(item) for item in manifests), key=lambda item: str(item.get("decision_id")))
    seen_manifests: set[str] = set()
    seen_decisions: set[str] = set()
    for item in normalized:
        result = validate_manifest(item)
        if not result["valid"]:
            raise DecisionRecallError(f"invalid manifest {item.get('manifest_id')}: {result['errors']}")
        if item["manifest_id"] in seen_manifests:
            raise DecisionRecallError(f"duplicate manifest_id: {item['manifest_id']}")
        if item["decision_id"] in seen_decisions:
            raise DecisionRecallError(f"duplicate decision_id: {item['decision_id']}")
        seen_manifests.add(item["manifest_id"])
        seen_decisions.add(item["decision_id"])
        if _parse_time(item["accepted_at"]) > _parse_time(sealed_at):
            raise DecisionRecallError(f"manifest accepted after stream seal: {item['manifest_id']}")

    records = sorted((dict(item) for item in pre_trigger_records), key=lambda item: str(item.get("pre_trigger_record_id")))
    record_ids: set[str] = set()
    manifest_decisions = {item["decision_id"]: item["decision"] for item in normalized}
    records_by_decision: dict[str, list[str]] = {decision_id: [] for decision_id in seen_decisions}
    for record in records:
        expected = create_pre_trigger_record(
            decision_id=record["decision_id"],
            decision=record["decision"],
            available_at=record["available_at"],
            materials=record.get("materials", []),
        )
        if expected != record:
            raise DecisionRecallError(f"pre-trigger record does not reproduce: {record.get('pre_trigger_record_id')}")
        if record["pre_trigger_record_id"] in record_ids:
            raise DecisionRecallError(f"duplicate pre-trigger record: {record['pre_trigger_record_id']}")
        if record["decision_id"] not in seen_decisions:
            raise DecisionRecallError(f"pre-trigger record references unknown decision: {record['decision_id']}")
        if record["decision"] != manifest_decisions[record["decision_id"]]:
            raise DecisionRecallError(f"pre-trigger record decision text does not match accepted decision: {record['decision_id']}")
        if _parse_time(record["available_at"]) > _parse_time(sealed_at):
            raise DecisionRecallError(f"pre-trigger record became available after stream seal: {record['pre_trigger_record_id']}")
        record_ids.add(record["pre_trigger_record_id"])
        records_by_decision[record["decision_id"]].append(record["pre_trigger_record_id"])
    missing_records = sorted(decision_id for decision_id, ids in records_by_decision.items() if not ids)
    if missing_records:
        raise DecisionRecallError(f"every decision requires at least one complete pre-trigger record: {missing_records}")

    catalog = sorted((_eligible_basis(item, record_ids) for item in eligible_bases), key=lambda item: item["basis_id"])
    catalog_ids = [item["basis_id"] for item in catalog]
    if len(set(catalog_ids)) != len(catalog_ids):
        raise DecisionRecallError("duplicate eligible basis_id")
    catalog_set = set(catalog_ids)
    declared_ids = {
        item["basis_id"]
        for manifest in normalized
        for item in manifest.get("basis", [])
    } | {
        item["assumption_id"]
        for manifest in normalized
        for item in manifest.get("assumptions", [])
    }
    missing_catalog = sorted(declared_ids - catalog_set)
    if missing_catalog:
        raise DecisionRecallError(f"manifest dependencies absent from independent eligible-basis catalog: {missing_catalog}")

    catalog_built_at = _time(eligible_basis_catalog_custody.get("built_at"))
    catalog_builder_id = _token(eligible_basis_catalog_custody.get("builder_id"))
    catalog_method = _token(eligible_basis_catalog_custody.get("method")).upper()
    source_scope = _token(eligible_basis_catalog_custody.get("source_scope")).upper()
    manifest_visible = bool(eligible_basis_catalog_custody.get("manifest_visible", True))
    if not catalog_builder_id:
        raise DecisionRecallError("eligible-basis catalog builder_id missing")
    if _parse_time(catalog_built_at) > _parse_time(sealed_at):
        raise DecisionRecallError("eligible-basis catalog was built after the stream seal")
    latest_record_time = max((_parse_time(item["available_at"]) for item in records), default=_parse_time(catalog_built_at))
    if _parse_time(catalog_built_at) < latest_record_time:
        raise DecisionRecallError("eligible-basis catalog was built before all bound pre-trigger records were available")
    catalog_custody = {
        "built_at": catalog_built_at,
        "builder_id": catalog_builder_id,
        "method": catalog_method,
        "source_scope": source_scope,
        "manifest_visible": manifest_visible,
    }

    manifest_ids = [item["manifest_id"] for item in normalized]
    decision_ids = [item["decision_id"] for item in normalized]
    pre_trigger_ids = [item["pre_trigger_record_id"] for item in records]
    body = {
        "schema": DECISION_STREAM_SEAL_SCHEMA,
        "benchmark_id": _token(benchmark_id),
        "protocol_id": _token(protocol_id),
        "sealed_at": _time(sealed_at),
        "manifest_count": len(normalized),
        "decision_ids": decision_ids,
        "manifest_ids": manifest_ids,
        "manifests_root": sha256_hex("\n".join(manifest_ids).encode("utf-8")),
        "pre_trigger_record_ids": pre_trigger_ids,
        "pre_trigger_records_root": sha256_hex("\n".join(pre_trigger_ids).encode("utf-8")),
        "eligible_basis_ids": catalog_ids,
        "eligible_bases_root": sha256_hex("\n".join(catalog_ids).encode("utf-8")),
        "eligible_basis_catalog_custody": catalog_custody,
        "manifests": normalized,
        "pre_trigger_records": records,
        "eligible_bases": catalog,
    }
    return {"stream_seal_id": content_id("decision-recall-stream-seal", body), **body}

def validate_stream_seal(seal: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        rebuilt = create_stream_seal(
            benchmark_id=seal["benchmark_id"],
            sealed_at=seal["sealed_at"],
            manifests=seal.get("manifests", []),
            pre_trigger_records=seal.get("pre_trigger_records", []),
            eligible_bases=seal.get("eligible_bases", []),
            eligible_basis_catalog_custody=seal.get("eligible_basis_catalog_custody", {}),
            protocol_id=seal["protocol_id"],
        )
        if seal.get("schema") != DECISION_STREAM_SEAL_SCHEMA:
            errors.append("schema mismatch")
        if rebuilt["stream_seal_id"] != seal.get("stream_seal_id"):
            errors.append("stream_seal_id mismatch")
    except (KeyError, TypeError, ValueError, DecisionRecallError) as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors}


def _controlled_selection_proof(*, stream_seal: Mapping[str, Any], basis_id: str, raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {}
    seed_hex = str(raw.get("seed_hex", "")).strip().lower()
    try:
        seed = bytes.fromhex(seed_hex)
    except ValueError as exc:
        raise DecisionRecallError("controlled selection seed_hex invalid") from exc
    if not seed:
        raise DecisionRecallError("controlled selection seed is empty")
    selection_at = _time(raw.get("selection_at"))
    if _parse_time(selection_at) <= _parse_time(stream_seal["sealed_at"]):
        raise DecisionRecallError("controlled selection must occur after stream seal")
    method = _token(raw.get("selection_method"))
    if method != "sha256_rank(seed || stream_seal_id || basis_id)":
        raise DecisionRecallError("unsupported controlled selection method")
    candidates = sorted(item["basis_id"] for item in stream_seal.get("eligible_bases", []))
    selected_count = int(raw.get("selected_count", 0))
    if selected_count < 1 or selected_count > len(candidates):
        raise DecisionRecallError("controlled selection selected_count invalid")
    ranked = sorted(
        candidates,
        key=lambda candidate: hashlib.sha256(seed + b"\0" + stream_seal["stream_seal_id"].encode() + b"\0" + candidate.encode()).digest(),
    )
    if basis_id not in ranked[:selected_count]:
        raise DecisionRecallError("basis is not selected by the committed controlled-selection seed")
    rank = ranked.index(basis_id)
    declared_rank = int(raw.get("rank", rank))
    if declared_rank != rank:
        raise DecisionRecallError("controlled selection rank mismatch")
    return {
        "selection_at": selection_at,
        "selection_method": method,
        "seed_hex": seed.hex(),
        "seed_sha256": hashlib.sha256(seed).hexdigest(),
        "candidate_basis_count": len(candidates),
        "selected_count": selected_count,
        "rank": rank,
    }


def create_revocation_event(*, stream_seal: Mapping[str, Any], basis_id: str, event_at: str, reason: str, locator: str = "", evidence_sha256: str = "", stratum: str = "CONTROLLED", selection_proof: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not validate_stream_seal(stream_seal)["valid"]:
        raise DecisionRecallError("stream seal invalid")
    if _parse_time(event_at) <= _parse_time(stream_seal["sealed_at"]):
        raise DecisionRecallError("revocation event must occur after stream seal")
    normalized_stratum = _token(stratum).upper()
    if normalized_stratum not in {"CONTROLLED", "NATURAL"}:
        raise DecisionRecallError(f"unsupported revocation stratum: {normalized_stratum}")
    eligible = {item["basis_id"] for item in stream_seal.get("eligible_bases", [])}
    if normalized_stratum == "CONTROLLED" and basis_id not in eligible:
        raise DecisionRecallError(f"controlled basis not present in independently sealed eligible-basis catalog: {basis_id}")
    evidence = str(evidence_sha256).lower().strip()
    if evidence and (len(evidence) != 64 or any(c not in "0123456789abcdef" for c in evidence)):
        raise DecisionRecallError("revocation evidence_sha256 invalid")
    proof = _controlled_selection_proof(stream_seal=stream_seal, basis_id=_token(basis_id), raw=selection_proof) if normalized_stratum == "CONTROLLED" else {}
    if proof and _parse_time(event_at) < _parse_time(proof["selection_at"]):
        raise DecisionRecallError("controlled revocation event cannot precede its selection")
    body = {
        "schema": DECISION_REVOCATION_EVENT_SCHEMA,
        "stream_seal_id": stream_seal["stream_seal_id"],
        "event_at": _time(event_at),
        "event_type": "LOSS_OF_STANDING",
        "basis_id": _token(basis_id),
        "stratum": normalized_stratum,
        "selection_proof": proof,
        "reason": _token(reason),
        "locator": _token(locator),
        "evidence_sha256": evidence,
    }
    return {"event_id": content_id("decision-recall-revocation-event", body), **body}


def validate_revocation_event(event: Mapping[str, Any], seal: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        rebuilt = create_revocation_event(
            stream_seal=seal,
            basis_id=event["basis_id"],
            event_at=event["event_at"],
            reason=event.get("reason", ""),
            locator=event.get("locator", ""),
            evidence_sha256=event.get("evidence_sha256", ""),
            stratum=event.get("stratum", "CONTROLLED"),
            selection_proof=event.get("selection_proof", {}),
        )
        if event.get("schema") != DECISION_REVOCATION_EVENT_SCHEMA:
            errors.append("schema mismatch")
        if rebuilt["event_id"] != event.get("event_id"):
            errors.append("event_id mismatch")
    except (KeyError, TypeError, ValueError, DecisionRecallError) as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors}


def _dependency_roles(manifest: Mapping[str, Any]) -> dict[str, str]:
    result = {item["basis_id"]: item["role"] for item in manifest.get("basis", [])}
    result.update({item["assumption_id"]: item["role"] for item in manifest.get("assumptions", [])})
    return result


def _flat_mentions(seal: Mapping[str, Any], decision_id: str, basis_id: str) -> bool:
    record_ids = {
        item["pre_trigger_record_id"]
        for item in seal.get("pre_trigger_records", [])
        if item.get("decision_id") == decision_id
    }
    basis = next((item for item in seal.get("eligible_bases", []) if item.get("basis_id") == basis_id), None)
    if basis is not None:
        return bool(record_ids & set(basis.get("mentioned_record_ids", [])))
    # Natural revocations may expose a basis the independent controlled catalog
    # omitted.  Flat search then falls back to an exact lexical search over the
    # sealed conventional records rather than inheriting the catalog miss.
    needle = str(basis_id).casefold()
    for record in seal.get("pre_trigger_records", []):
        if record.get("pre_trigger_record_id") not in record_ids:
            continue
        for material in record.get("materials", []):
            haystack = " ".join([str(material.get("material_id", "")), str(material.get("locator", "")), str(material.get("text", ""))]).casefold()
            if needle and needle in haystack:
                return True
    return False

def _matching_condition(manifest: Mapping[str, Any], basis_id: str, event_type: str) -> bool:
    return any(
        item.get("dependency_id") == basis_id and event_type in item.get("event_types", [])
        for item in manifest.get("invalidation_conditions", [])
    )


def _decision_recall_disposition(manifest: Mapping[str, Any], event: Mapping[str, Any]) -> tuple[str, list[str], str]:
    basis_id = event["basis_id"]
    event_type = event["event_type"]
    roles = _dependency_roles(manifest)
    if basis_id not in roles:
        return "SURVIVE", [], "revoked basis is absent from the accepted dependency record"

    role = roles[basis_id]
    if role == "CONTEXT":
        return "SURVIVE", [basis_id], "basis was recorded as contextual rather than material"
    if role == "AMBIGUOUS":
        return "ESCALATE", [basis_id], "accepted record declared materiality ambiguous"

    if not _matching_condition(manifest, basis_id, event_type):
        return "ESCALATE", [basis_id], "material dependency lost standing without a matching predeclared invalidation condition"

    required = set(manifest.get("required_dependencies", []))
    alternatives = [set(item.get("dependency_ids", [])) for item in manifest.get("alternative_support", []) if item.get("dependency_ids")]
    support_sets = ([required] if required else []) + alternatives
    containing = [group for group in support_sets if basis_id in group]
    if not containing:
        # A material-looking item that is not actually part of any declared
        # sufficient support set is a malformed/incomplete contract.  Fail to
        # human review rather than silently inventing semantics.
        return "ESCALATE", [basis_id], "material basis is not assigned to any declared sufficient support set"

    standing_sets = [group for group in support_sets if basis_id not in group]
    if standing_sets:
        witness = sorted(min(standing_sets, key=lambda group: (len(group), sorted(group))))
        return "SURVIVE", witness, "an independently declared sufficient support set remains standing"

    # Every declared sufficient support path included the revoked basis.
    # Reopening is therefore the smallest consequence earned by the frozen
    # operational contract.  It is not a claim that the real-world decision is
    # false.
    witness = sorted({item for group in containing for item in group})
    return "REOPEN", witness, "every predeclared sufficient support path depends on the basis that lost standing"


def run_predictions(*, seal: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    if not validate_stream_seal(seal)["valid"]:
        raise DecisionRecallError("stream seal invalid")
    event_check = validate_revocation_event(event, seal)
    if not event_check["valid"]:
        raise DecisionRecallError(f"revocation event invalid: {event_check['errors']}")

    rows = []
    for manifest in seal["manifests"]:
        flat = "REVIEW" if _flat_mentions(seal, manifest["decision_id"], event["basis_id"]) else "SURVIVE"
        disposition, witness, reason = _decision_recall_disposition(manifest, event)
        rows.append({
            "decision_id": manifest["decision_id"],
            "decision": manifest["decision"],
            SYSTEM_FULL_HISTORY: {"disposition": "REVIEW", "witness": []},
            SYSTEM_FLAT_SEARCH: {
                "disposition": flat,
                "witness": [event["basis_id"]] if flat == "REVIEW" else [],
            },
            SYSTEM_DECISION_RECALL: {
                "disposition": disposition,
                "witness": witness,
                "reason": reason,
            },
        })
    body = {
        "schema": DECISION_PREDICTIONS_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "event_id": event["event_id"],
        "rows": rows,
    }
    return {"predictions_id": content_id("decision-recall-predictions", body), **body}


def validate_predictions(predictions: Mapping[str, Any], seal: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        rebuilt = run_predictions(seal=seal, event=event)
        if predictions.get("schema") != DECISION_PREDICTIONS_SCHEMA:
            errors.append("schema mismatch")
        if rebuilt != dict(predictions):
            errors.append("predictions do not reproduce from sealed pre-event state and event")
    except (KeyError, TypeError, ValueError, DecisionRecallError) as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors}


def create_adjudication_packet(*, seal: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    """Create a prediction-blind packet for independent gold adjudication."""

    if not validate_stream_seal(seal)["valid"]:
        raise DecisionRecallError("stream seal invalid")
    if not validate_revocation_event(event, seal)["valid"]:
        raise DecisionRecallError("revocation event invalid")
    rows = []
    for manifest in seal["manifests"]:
        records = [
            item for item in seal.get("pre_trigger_records", [])
            if item.get("decision_id") == manifest["decision_id"]
        ]
        if not records:
            raise DecisionRecallError(f"no conventional pre-trigger record for decision {manifest['decision_id']}")
        rows.append({
            "decision_id": manifest["decision_id"],
            "decision": records[0]["decision"],
            "complete_pre_trigger_records": records,
        })
    body = {
        "schema": DECISION_ADJUDICATION_PACKET_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "event": dict(event),
        "instructions": "Using only the conventional complete pre-trigger record and the new revocation event, label each accepted decision REOPEN, SURVIVE, or ESCALATE. Do not inspect the prospective dependency manifest or any system prediction.",
        "rows": rows,
    }
    return {"adjudication_packet_id": content_id("decision-recall-adjudication-packet", body), **body}


def create_gold(*, adjudication_packet: Mapping[str, Any], adjudicated_at: str, adjudicator_id: str, labels: Sequence[Mapping[str, Any]], method: str = "INDEPENDENT_BLINDED_REVIEW") -> dict[str, Any]:
    packet_ids = {item["decision_id"] for item in adjudication_packet.get("rows", [])}
    normalized = []
    seen: set[str] = set()
    for raw in labels:
        decision_id = str(raw["decision_id"])
        label = str(raw["label"]).upper()
        if decision_id not in packet_ids:
            raise DecisionRecallError(f"gold references unknown decision: {decision_id}")
        if decision_id in seen:
            raise DecisionRecallError(f"duplicate gold label: {decision_id}")
        if label not in GOLD_LABELS:
            raise DecisionRecallError(f"invalid gold label {label}")
        seen.add(decision_id)
        normalized.append({
            "decision_id": decision_id,
            "label": label,
            "rationale": _token(raw.get("rationale")),
        })
    if seen != packet_ids:
        raise DecisionRecallError(f"gold does not cover every packet row; missing={sorted(packet_ids - seen)}")
    normalized.sort(key=lambda item: item["decision_id"])
    adjudicated = _time(adjudicated_at)
    if _parse_time(adjudicated) <= _parse_time(adjudication_packet["event"]["event_at"]):
        raise DecisionRecallError("gold adjudication must occur after the revocation event")
    body = {
        "schema": DECISION_GOLD_SCHEMA,
        "adjudication_packet_id": adjudication_packet["adjudication_packet_id"],
        "stream_seal_id": adjudication_packet["stream_seal_id"],
        "event_id": adjudication_packet["event"]["event_id"],
        "adjudicated_at": adjudicated,
        "adjudicator_id": _token(adjudicator_id),
        "method": _token(method).upper(),
        "labels": normalized,
    }
    return {"gold_id": content_id("decision-recall-gold", body), **body}


def validate_gold(gold: Mapping[str, Any], seal: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        expected_packet = create_adjudication_packet(seal=seal, event=event)
        if gold.get("schema") != DECISION_GOLD_SCHEMA:
            errors.append("schema mismatch")
        if gold.get("adjudication_packet_id") != expected_packet["adjudication_packet_id"]:
            errors.append("gold is not bound to the manifest-blind adjudication packet for this sealed state/event")
        if gold.get("stream_seal_id") != seal.get("stream_seal_id") or gold.get("event_id") != event.get("event_id"):
            errors.append("gold binding mismatch")
        if _parse_time(gold.get("adjudicated_at")) <= _parse_time(event.get("event_at")):
            errors.append("gold adjudication does not postdate event")
        decision_ids = {item["decision_id"] for item in seal.get("manifests", [])}
        labels = list(gold.get("labels", []))
        label_ids = [str(item.get("decision_id")) for item in labels]
        if len(set(label_ids)) != len(label_ids) or set(label_ids) != decision_ids:
            errors.append("gold coverage mismatch")
        if any(str(item.get("label", "")).upper() not in GOLD_LABELS for item in labels):
            errors.append("gold contains invalid label")
        expected_id = content_id("decision-recall-gold", _without(gold, "gold_id"))
        if expected_id != gold.get("gold_id"):
            errors.append("gold_id mismatch")
    except (KeyError, TypeError, ValueError, DecisionRecallError) as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors}


def create_review_packet(*, seal: Mapping[str, Any], event: Mapping[str, Any], predictions: Mapping[str, Any], system: str) -> dict[str, Any]:
    """Build the exact post-trigger human workload for one comparison system.

    The packet contains no gold. Full History exposes every accepted decision;
    Flat Search exposes only lexical/index hits; Decision Recall exposes only
    REOPEN/ESCALATE rows and carries its frozen witness/reason projection.
    """

    pred_check = validate_predictions(predictions, seal, event)
    if not pred_check["valid"]:
        raise DecisionRecallError(f"invalid predictions: {pred_check['errors']}")
    normalized_system = str(system).upper()
    if normalized_system not in SYSTEMS:
        raise DecisionRecallError(f"unknown review-packet system: {normalized_system}")
    rows = []
    for prediction_row in predictions.get("rows", []):
        disposition = prediction_row[normalized_system]["disposition"]
        include = (
            normalized_system == SYSTEM_FULL_HISTORY
            or (normalized_system == SYSTEM_FLAT_SEARCH and disposition == "REVIEW")
            or (normalized_system == SYSTEM_DECISION_RECALL and disposition in {"REOPEN", "ESCALATE"})
        )
        if not include:
            continue
        records = [
            item for item in seal.get("pre_trigger_records", [])
            if item.get("decision_id") == prediction_row["decision_id"]
        ]
        if not records:
            raise DecisionRecallError(f"no conventional pre-trigger record for decision {prediction_row['decision_id']}")
        rows.append({
            "decision_id": prediction_row["decision_id"],
            "decision": records[0]["decision"],
            "system_projection": dict(prediction_row[normalized_system]),
            "complete_pre_trigger_records": records,
        })
    body = {
        "schema": DECISION_REVIEW_PACKET_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "event_id": event["event_id"],
        "system": normalized_system,
        "event": dict(event),
        "review_row_count": len(rows),
        "instructions": "Review only the surfaced rows using the pre-trigger record and revocation event. Produce the operational disposition required by the condition. Gold is intentionally absent.",
        "rows": rows,
    }
    return {"review_packet_id": content_id("decision-recall-review-packet", body), **body}


def create_review_outcome(*, review_packet: Mapping[str, Any], reviewed_at: str, reviewer_id: str, labels: Sequence[Mapping[str, Any]], method: str = "BLINDED_BASELINE_REVIEW") -> dict[str, Any]:
    """Bind a human baseline review result to the exact review packet.

    Full History and Flat Search are baselines, not gold. Their reviewers can
    make mistakes. Recording those labels separately lets independent gold
    reveal a baseline miss instead of defining Full History as an oracle.
    """

    system = _token(review_packet.get("system")).upper()
    if system not in {SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH}:
        raise DecisionRecallError("review outcomes are only defined for human baseline systems")
    packet_ids = {str(item.get("decision_id")) for item in review_packet.get("rows", [])}
    normalized = []
    seen: set[str] = set()
    for raw in labels:
        decision_id = _token(raw.get("decision_id"))
        label = _token(raw.get("label")).upper()
        if decision_id not in packet_ids:
            raise DecisionRecallError(f"review outcome references unsurfaced decision: {decision_id}")
        if decision_id in seen:
            raise DecisionRecallError(f"duplicate review outcome: {decision_id}")
        if label not in GOLD_LABELS:
            raise DecisionRecallError(f"invalid review outcome label: {label}")
        seen.add(decision_id)
        normalized.append({
            "decision_id": decision_id,
            "label": label,
            "rationale": _token(raw.get("rationale")),
        })
    if seen != packet_ids:
        raise DecisionRecallError(f"review outcome must cover every surfaced row; missing={sorted(packet_ids - seen)}")
    normalized.sort(key=lambda item: item["decision_id"])
    reviewed = _time(reviewed_at)
    if _parse_time(reviewed) <= _parse_time(review_packet.get("event", {}).get("event_at")):
        raise DecisionRecallError("baseline review must occur after the revocation event")
    body = {
        "schema": DECISION_REVIEW_OUTCOME_SCHEMA,
        "review_packet_id": review_packet["review_packet_id"],
        "stream_seal_id": review_packet["stream_seal_id"],
        "event_id": review_packet["event_id"],
        "system": system,
        "reviewed_at": reviewed,
        "reviewer_id": _token(reviewer_id),
        "method": _token(method).upper(),
        "labels": normalized,
    }
    if not body["reviewer_id"]:
        raise DecisionRecallError("baseline reviewer_id missing")
    return {"review_outcome_id": content_id("decision-recall-review-outcome", body), **body}


def validate_review_outcome(review_outcome: Mapping[str, Any], *, seal: Mapping[str, Any], event: Mapping[str, Any], predictions: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        system = str(review_outcome.get("system", "")).upper()
        if system not in {SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH}:
            errors.append("unsupported baseline review system")
        else:
            packet = create_review_packet(seal=seal, event=event, predictions=predictions, system=system)
            if review_outcome.get("review_packet_id") != packet.get("review_packet_id"):
                errors.append("review outcome packet binding mismatch")
            packet_ids = {str(item.get("decision_id")) for item in packet.get("rows", [])}
            labels = list(review_outcome.get("labels", []))
            label_ids = [str(item.get("decision_id")) for item in labels]
            if len(set(label_ids)) != len(label_ids) or set(label_ids) != packet_ids:
                errors.append("review outcome coverage mismatch")
            if any(str(item.get("label", "")).upper() not in GOLD_LABELS for item in labels):
                errors.append("review outcome contains invalid label")
        if review_outcome.get("schema") != DECISION_REVIEW_OUTCOME_SCHEMA:
            errors.append("schema mismatch")
        if review_outcome.get("stream_seal_id") != seal.get("stream_seal_id") or review_outcome.get("event_id") != event.get("event_id"):
            errors.append("review outcome event/stream binding mismatch")
        if str(review_outcome.get("method", "")).upper() != "BLINDED_BASELINE_REVIEW":
            errors.append("review outcome method is not blinded baseline review")
        if not str(review_outcome.get("reviewer_id", "")).strip():
            errors.append("reviewer_id missing")
        if _parse_time(review_outcome.get("reviewed_at")) <= _parse_time(event.get("event_at")):
            errors.append("review outcome does not postdate event")
        expected_id = content_id("decision-recall-review-outcome", _without(review_outcome, "review_outcome_id"))
        if expected_id != review_outcome.get("review_outcome_id"):
            errors.append("review_outcome_id mismatch")
    except (KeyError, TypeError, ValueError, DecisionRecallError) as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors}


def create_review_times(*, seal: Mapping[str, Any], event: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = []
    for raw in records:
        system = str(raw["system"]).upper()
        if system not in SYSTEMS:
            raise DecisionRecallError(f"unknown review-time system: {system}")
        elapsed = int(raw["review_milliseconds"])
        if elapsed < 0:
            raise DecisionRecallError("review_milliseconds must be non-negative")
        packet_id = _token(raw.get("review_packet_id"))
        if packet_id and not packet_id.startswith("decision-recall-review-packet:sha256:"):
            raise DecisionRecallError("review_packet_id has wrong namespace")
        normalized.append({
            "system": system,
            "reviewer_id": _token(raw.get("reviewer_id")),
            "review_packet_id": packet_id,
            "review_milliseconds": elapsed,
            "timing_source": _token(raw.get("timing_source", "DECLARED")).upper(),
            "notes": _token(raw.get("notes")),
        })
    normalized.sort(key=lambda item: (item["system"], item["reviewer_id"], item["review_milliseconds"]))
    body = {
        "schema": DECISION_REVIEW_TIMES_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "event_id": event["event_id"],
        "records": normalized,
    }
    return {"review_times_id": content_id("decision-recall-review-times", body), **body}


def validate_review_times(review_times: Mapping[str, Any], seal: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        if review_times.get("schema") != DECISION_REVIEW_TIMES_SCHEMA:
            errors.append("schema mismatch")
        if review_times.get("stream_seal_id") != seal.get("stream_seal_id") or review_times.get("event_id") != event.get("event_id"):
            errors.append("review-time binding mismatch")
        for item in review_times.get("records", []):
            if item.get("system") not in SYSTEMS:
                errors.append(f"unknown review-time system: {item.get('system')}")
            if int(item.get("review_milliseconds", -1)) < 0:
                errors.append("negative review time")
            packet_id = str(item.get("review_packet_id", ""))
            if packet_id and not packet_id.startswith("decision-recall-review-packet:sha256:"):
                errors.append("invalid review packet namespace")
        expected_id = content_id("decision-recall-review-times", _without(review_times, "review_times_id"))
        if expected_id != review_times.get("review_times_id"):
            errors.append("review_times_id mismatch")
    except (KeyError, TypeError, ValueError, DecisionRecallError) as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors}


def _is_review(disposition: str) -> bool:
    return disposition in {"REVIEW", "REOPEN", "ESCALATE"}


def score_predictions(*, seal: Mapping[str, Any], event: Mapping[str, Any], predictions: Mapping[str, Any], gold: Mapping[str, Any], review_times: Mapping[str, Any] | None = None, review_outcomes: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    pred_check = validate_predictions(predictions, seal, event)
    if not pred_check["valid"]:
        raise DecisionRecallError(f"invalid predictions: {pred_check['errors']}")
    gold_check = validate_gold(gold, seal, event)
    if not gold_check["valid"]:
        raise DecisionRecallError(f"invalid gold: {gold_check['errors']}")
    gold_map = {item["decision_id"]: item["label"] for item in gold.get("labels", [])}
    decision_ids = {item["decision_id"] for item in seal["manifests"]}
    if set(gold_map) != decision_ids:
        raise DecisionRecallError("gold coverage mismatch")

    outcome_by_system: dict[str, Mapping[str, Any]] = {}
    if review_outcomes is not None:
        for outcome in review_outcomes:
            check = validate_review_outcome(outcome, seal=seal, event=event, predictions=predictions)
            if not check["valid"]:
                raise DecisionRecallError(f"invalid baseline review outcome: {check['errors']}")
            system = str(outcome["system"]).upper()
            if system in outcome_by_system:
                raise DecisionRecallError(f"duplicate baseline review outcome for {system}")
            outcome_by_system[system] = outcome
    baseline_review_outcomes_verified = set(outcome_by_system) == {SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH}
    baseline_reviewer_ids = {
        system: str(outcome_by_system[system]["reviewer_id"])
        for system in sorted(outcome_by_system)
    }
    outcome_labels = {
        system: {item["decision_id"]: item["label"] for item in outcome.get("labels", [])}
        for system, outcome in outcome_by_system.items()
    }

    gold_label_counts = {label: sum(1 for value in gold_map.values() if value == label) for label in GOLD_LABELS}

    metrics: dict[str, dict[str, Any]] = {}
    for system in SYSTEMS:
        review_load = 0
        missed_reopenings = 0
        unnecessary_reviews = 0
        gold_escalations = 0
        surfaced_escalations = 0
        exact = 0
        silent_ambiguous_survivals = 0
        ambiguous_overreach = 0
        final_disposition_errors = 0
        baseline_labels_bound = system in outcome_by_system
        for row in predictions["rows"]:
            triage = row[system]["disposition"]
            target = gold_map[row["decision_id"]]
            if _is_review(triage):
                review_load += 1
            effective = triage
            if system in {SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH}:
                if triage == "SURVIVE":
                    effective = "SURVIVE"
                elif baseline_labels_bound:
                    effective = outcome_labels[system][row["decision_id"]]
            if target == "REOPEN" and effective == "SURVIVE":
                missed_reopenings += 1
            if target == "SURVIVE" and _is_review(triage):
                unnecessary_reviews += 1
            if target == "ESCALATE":
                gold_escalations += 1
                if _is_review(triage):
                    surfaced_escalations += 1
                if effective == "SURVIVE":
                    silent_ambiguous_survivals += 1
                if system == SYSTEM_DECISION_RECALL and effective == "REOPEN":
                    ambiguous_overreach += 1
            if system == SYSTEM_DECISION_RECALL:
                if effective == target:
                    exact += 1
                else:
                    final_disposition_errors += 1
            elif baseline_labels_bound:
                if effective == target:
                    exact += 1
                else:
                    final_disposition_errors += 1
            else:
                # Without human baseline outcomes, retain triage-only behavior
                # for mechanics/debugging. Promotion requires the outcomes.
                if (target == "SURVIVE" and triage == "SURVIVE") or (target != "SURVIVE" and triage == "REVIEW"):
                    exact += 1
        count = len(predictions["rows"])
        metrics[system] = {
            "decision_count": count,
            "review_load": review_load,
            "review_load_reduction_basis_points_vs_full_history": 0,
            "missed_reopenings": missed_reopenings,
            "unnecessary_reviews": unnecessary_reviews,
            "gold_escalations": gold_escalations,
            "surfaced_escalations": surfaced_escalations,
            "silent_ambiguous_survivals": silent_ambiguous_survivals,
            "ambiguous_overreach": ambiguous_overreach,
            "baseline_review_outcome_bound": baseline_labels_bound,
            "final_disposition_errors": final_disposition_errors if (system == SYSTEM_DECISION_RECALL or baseline_labels_bound) else None,
            "exact_or_correct_triage": exact,
            "exact_or_correct_triage_basis_points": (exact * 10000 // count) if count else 0,
        }
    full_load = metrics[SYSTEM_FULL_HISTORY]["review_load"]
    for system in SYSTEMS:
        load = metrics[system]["review_load"]
        metrics[system]["review_load_reduction_basis_points_vs_full_history"] = (
            (full_load - load) * 10000 // full_load if full_load else 0
        )

    capture_values = [int(item["capture"]["human_capture_milliseconds"]) for item in seal["manifests"]]
    capture_total = sum(capture_values)
    capture_median = int(median(capture_values)) if capture_values else 0
    no_correction = sum(1 for item in seal["manifests"] if item["capture"].get("accepted_without_correction"))

    economics: dict[str, Any] = {
        "capture_total_milliseconds": capture_total,
        "capture_median_milliseconds": capture_median,
        "accepted_without_correction": no_correction,
        "accepted_without_correction_basis_points": (no_correction * 10000 // len(capture_values)) if capture_values else 0,
        "review_time_measurements_present": review_times is not None,
        "review_packet_bindings_valid": False,
        "review_outcome_timing_bindings_valid": False,
        "review_timing_instrumented": False,
        "conditional_attention_saved_milliseconds": None,
        "break_even_meaningful_revocations": None,
        "annual_roi_inferred": False,
    }
    if review_times is not None:
        review_check = validate_review_times(review_times, seal, event)
        if not review_check["valid"]:
            raise DecisionRecallError(f"invalid review times: {review_check['errors']}")
        by_system: dict[str, list[int]] = {system: [] for system in SYSTEMS}
        reviewer_ids_by_system: dict[str, set[str]] = {system: set() for system in SYSTEMS}
        review_sources = []
        packet_bindings_ok = True
        expected_packets = {
            system: create_review_packet(seal=seal, event=event, predictions=predictions, system=system)["review_packet_id"]
            for system in SYSTEMS
        }
        for item in review_times.get("records", []):
            if item["system"] in by_system:
                by_system[item["system"]].append(int(item["review_milliseconds"]))
                reviewer_ids_by_system[item["system"]].add(str(item.get("reviewer_id", "")))
                review_sources.append(str(item.get("timing_source", "DECLARED")).upper())
                if str(item.get("review_packet_id", "")) != expected_packets[item["system"]]:
                    packet_bindings_ok = False
        outcome_timing_ok = baseline_review_outcomes_verified and all(
            baseline_reviewer_ids[system] in reviewer_ids_by_system[system]
            for system in (SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH)
        )
        economics["review_packet_bindings_valid"] = packet_bindings_ok and bool(review_sources)
        economics["review_outcome_timing_bindings_valid"] = outcome_timing_ok
        economics["review_timing_instrumented"] = bool(review_sources) and packet_bindings_ok and outcome_timing_ok and all(source in {"MONOTONIC_CLI", "MONOTONIC_UI"} for source in review_sources)
        if by_system[SYSTEM_FULL_HISTORY] and by_system[SYSTEM_DECISION_RECALL]:
            full_median = int(median(by_system[SYSTEM_FULL_HISTORY]))
            recall_median = int(median(by_system[SYSTEM_DECISION_RECALL]))
            saved = full_median - recall_median
            economics.update({
                "full_history_review_median_milliseconds": full_median,
                "decision_recall_review_median_milliseconds": recall_median,
                "conditional_attention_saved_milliseconds": saved,
                "break_even_meaningful_revocations": (
                    (capture_total + saved - 1) // saved if saved > 0 else None
                ),
            })

    body = {
        "schema": DECISION_SCORE_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "event_id": event["event_id"],
        "predictions_id": predictions["predictions_id"],
        "gold_id": gold["gold_id"],
        "gold_method": gold.get("method", ""),
        "gold_adjudicator_id": gold.get("adjudicator_id", ""),
        "baseline_review_outcomes_verified": baseline_review_outcomes_verified,
        "baseline_review_outcome_ids": sorted(str(item["review_outcome_id"]) for item in outcome_by_system.values()),
        "baseline_reviewer_ids": baseline_reviewer_ids,
        "event_stratum": event.get("stratum", ""),
        "controlled_selection_verified": bool(event.get("selection_proof")) if str(event.get("stratum", "")).upper() == "CONTROLLED" else None,
        "gold_label_counts": gold_label_counts,
        "metrics": metrics,
        "economics": economics,
        "claim_boundary": "Controlled revocations estimate conditional performance when a recorded basis loses standing. Human Full History and Flat Search outcomes are baselines, not gold. Controlled events do not estimate how often real revocations occur, annual customer ROI, or whether the decision-time manifest captured causal truth.",
    }
    return {"score_id": content_id("decision-recall-score", body), **body}


def create_standing_state(*, stream_seal: Mapping[str, Any], standing_basis_ids: Sequence[str], unresolved_blockers: Mapping[str, Sequence[str]] | None = None, recorded_at: str) -> dict[str, Any]:
    """Bind receiver-owned runtime standing/blocker state for gain-side recomputation."""
    if not validate_stream_seal(stream_seal)["valid"]:
        raise DecisionRecallError("stream seal invalid")
    universe = sorted({item["basis_id"] for item in stream_seal.get("eligible_bases", [])})
    standing = sorted(set(map(str, standing_basis_ids)))
    unknown = sorted(set(standing) - set(universe))
    if unknown:
        raise DecisionRecallError(f"standing state references unknown bases: {unknown}")
    decision_ids = {item["decision_id"] for item in stream_seal.get("manifests", [])}
    blockers = {}
    for decision_id, values in sorted((unresolved_blockers or {}).items()):
        if decision_id not in decision_ids:
            raise DecisionRecallError(f"standing state blocker references unknown decision: {decision_id}")
        normalized = sorted(set(map(str, values)))
        if normalized:
            blockers[str(decision_id)] = normalized
    body = {
        "schema": DECISION_STANDING_STATE_SCHEMA,
        "stream_seal_id": stream_seal["stream_seal_id"],
        "recorded_at": _time(recorded_at),
        "basis_universe_ids": universe,
        "standing_basis_ids": standing,
        "unresolved_blockers": blockers,
    }
    return {"standing_state_id": content_id("decision-recall-standing-state", body), **body}


def validate_standing_state(state: Mapping[str, Any], seal: Mapping[str, Any]) -> dict[str, Any]:
    errors = []
    try:
        rebuilt = create_standing_state(
            stream_seal=seal,
            standing_basis_ids=state.get("standing_basis_ids", []),
            unresolved_blockers=state.get("unresolved_blockers", {}),
            recorded_at=state["recorded_at"],
        )
        if state.get("schema") != DECISION_STANDING_STATE_SCHEMA:
            errors.append("schema mismatch")
        if rebuilt != dict(state):
            errors.append("standing state does not reproduce")
    except (KeyError, TypeError, ValueError, DecisionRecallError) as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors}


def create_standing_event(*, state: Mapping[str, Any], seal: Mapping[str, Any], basis_id: str, event_type: str, event_at: str, asserted_by: str, reason: str) -> dict[str, Any]:
    if not validate_standing_state(state, seal)["valid"]:
        raise DecisionRecallError("standing state invalid")
    event_type = str(event_type).upper()
    if event_type not in EVENT_TYPES:
        raise DecisionRecallError(f"unsupported standing event type: {event_type}")
    basis_id = _token(basis_id)
    universe = set(state.get("basis_universe_ids", []))
    if basis_id not in universe:
        raise DecisionRecallError(f"standing event basis unknown: {basis_id}")
    standing = set(state.get("standing_basis_ids", []))
    if event_type == "GAIN_OF_STANDING" and basis_id in standing:
        transition = "NO_CHANGE"
    elif event_type == "LOSS_OF_STANDING" and basis_id not in standing:
        transition = "NO_CHANGE"
    else:
        transition = "CHANGE"
    body = {
        "schema": DECISION_STANDING_EVENT_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "pre_state_id": state["standing_state_id"],
        "event_type": event_type,
        "basis_id": basis_id,
        "event_at": _time(event_at),
        "asserted_by": _token(asserted_by),
        "reason": _token(reason),
        "transition": transition,
    }
    return {"event_id": content_id("decision-recall-standing-event", body), **body}


def _support_sets(manifest: Mapping[str, Any]) -> list[set[str]]:
    required = set(map(str, manifest.get("required_dependencies", [])))
    groups = [set(map(str, item.get("dependency_ids", []))) for item in manifest.get("alternative_support", []) if item.get("dependency_ids")]
    return ([required] if required else []) + groups


def analyze_gain_of_standing(*, seal: Mapping[str, Any], state: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    """Compute the review-only delta caused by one bound GAIN_OF_STANDING event."""
    check = validate_standing_state(state, seal)
    if not check["valid"]:
        raise DecisionRecallError(f"standing state invalid: {check['errors']}")
    if event.get("schema") != DECISION_STANDING_EVENT_SCHEMA or event.get("event_type") != "GAIN_OF_STANDING":
        raise DecisionRecallError("gain analysis requires GAIN_OF_STANDING event")
    if event.get("stream_seal_id") != seal.get("stream_seal_id") or event.get("pre_state_id") != state.get("standing_state_id"):
        raise DecisionRecallError("gain event state/stream binding mismatch")
    expected = create_standing_event(state=state, seal=seal, basis_id=event["basis_id"], event_type=event["event_type"], event_at=event["event_at"], asserted_by=event.get("asserted_by", ""), reason=event.get("reason", ""))
    if expected != dict(event):
        raise DecisionRecallError("gain event does not reproduce")
    basis = event["basis_id"]
    before_standing = set(state.get("standing_basis_ids", []))
    after_standing = set(before_standing)
    after_standing.add(basis)
    rows = []
    if event.get("transition") == "CHANGE":
        for manifest in seal.get("manifests", []):
            support_sets = _support_sets(manifest)
            if not any(basis in group for group in support_sets):
                continue
            before_complete = [sorted(group) for group in support_sets if group <= before_standing]
            after_complete = [sorted(group) for group in support_sets if group <= after_standing]
            blockers = sorted(set(state.get("unresolved_blockers", {}).get(manifest["decision_id"], [])))
            before_cls = "BLOCKED" if not before_complete else ("AFFECTED_UNRESOLVED" if blockers else "SUPPORTED")
            after_cls = "BLOCKED" if not after_complete else ("AFFECTED_UNRESOLVED" if blockers else "RECONSIDERABLE")
            if before_complete == after_complete and before_cls == after_cls:
                continue
            # Existing support before the event means the restoration did not create the option.
            if before_complete and not blockers:
                continue
            rows.append({
                "decision_id": manifest["decision_id"],
                "decision": manifest["decision"],
                "before": before_cls,
                "classification": after_cls,
                "complete_support_sets_before": before_complete,
                "complete_support_sets_after": after_complete,
                "unresolved_blockers": blockers,
            })
    rows.sort(key=lambda item: item["decision_id"])
    body = {
        "schema": DECISION_GAIN_REPORT_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "pre_state_id": state["standing_state_id"],
        "event_id": event["event_id"],
        "basis_id": basis,
        "classifications": rows,
        "summary": {
            "reconsiderable": sum(1 for item in rows if item["classification"] == "RECONSIDERABLE"),
            "affected_unresolved": sum(1 for item in rows if item["classification"] == "AFFECTED_UNRESOLVED"),
            "blocked": sum(1 for item in rows if item["classification"] == "BLOCKED"),
        },
        "claim_boundary": "RECONSIDERABLE is a receiver review projection only. This report does not restore accepted state, certify truth, clear independent blockers, or confer execution authority.",
    }
    return {"report_id": content_id("decision-recall-gain-report", body), **body}


def verify_gain_report(report: Mapping[str, Any], *, seal: Mapping[str, Any], state: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    errors = []
    try:
        expected = analyze_gain_of_standing(seal=seal, state=state, event=event)
        if report.get("schema") != DECISION_GAIN_REPORT_SCHEMA:
            errors.append("schema mismatch")
        if expected != dict(report):
            errors.append("gain report reproduction mismatch")
    except (KeyError, TypeError, ValueError, DecisionRecallError) as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors, "disposition": "ADMIT_GAIN_REVIEW" if not errors else "DENY_GAIN_REVIEW"}

def create_promotion_policy(
    *,
    declared_at: str,
    minimum_decisions: int = 30,
    minimum_controlled_revocations: int = 10,
    maximum_additional_missed_reopenings_vs_full_history: int = 0,
    minimum_review_load_reduction_basis_points: int = 4000,
    maximum_median_capture_milliseconds: int = 60000,
    maximum_silent_ambiguous_survivals: int = 0,
    maximum_ambiguous_overreach: int = 0,
    minimum_review_load_reduction_vs_flat_search_basis_points: int = 1000,
    minimum_timed_revocations: int = 3,
    require_positive_conditional_attention_savings: bool = True,
    require_instrumented_capture: bool = True,
    acceptable_capture_timing_sources: Sequence[str] = ("MONOTONIC_CLI", "MONOTONIC_UI"),
    require_outperform_flat_search: bool = True,
    minimum_mixed_gold_revocations: int = 3,
    require_adjudicator_role_separation: bool = True,
    require_verified_controlled_selection: bool = True,
    require_instrumented_review_timing: bool = True,
    require_verified_score_artifacts: bool = True,
    require_manifest_blind_basis_catalog: bool = True,
    require_catalog_role_separation: bool = True,
    require_baseline_review_outcomes: bool = True,
    require_baseline_reviewer_role_separation: bool = True,
    require_policy_predeclared_before_capture: bool = True,
) -> dict[str, Any]:
    body = {
        "schema": DECISION_PROMOTION_POLICY_SCHEMA,
        "declared_at": _time(declared_at),
        "minimum_decisions": int(minimum_decisions),
        "minimum_controlled_revocations": int(minimum_controlled_revocations),
        "maximum_additional_missed_reopenings_vs_full_history": int(maximum_additional_missed_reopenings_vs_full_history),
        "minimum_review_load_reduction_basis_points": int(minimum_review_load_reduction_basis_points),
        "maximum_median_capture_milliseconds": int(maximum_median_capture_milliseconds),
        "maximum_silent_ambiguous_survivals": int(maximum_silent_ambiguous_survivals),
        "maximum_ambiguous_overreach": int(maximum_ambiguous_overreach),
        "minimum_review_load_reduction_vs_flat_search_basis_points": int(minimum_review_load_reduction_vs_flat_search_basis_points),
        "minimum_timed_revocations": int(minimum_timed_revocations),
        "require_positive_conditional_attention_savings": bool(require_positive_conditional_attention_savings),
        "require_instrumented_capture": bool(require_instrumented_capture),
        "acceptable_capture_timing_sources": sorted(set(str(item).upper() for item in acceptable_capture_timing_sources)),
        "require_outperform_flat_search": bool(require_outperform_flat_search),
        "minimum_mixed_gold_revocations": int(minimum_mixed_gold_revocations),
        "require_adjudicator_role_separation": bool(require_adjudicator_role_separation),
        "require_verified_controlled_selection": bool(require_verified_controlled_selection),
        "require_instrumented_review_timing": bool(require_instrumented_review_timing),
        "require_verified_score_artifacts": bool(require_verified_score_artifacts),
        "require_manifest_blind_basis_catalog": bool(require_manifest_blind_basis_catalog),
        "require_catalog_role_separation": bool(require_catalog_role_separation),
        "require_baseline_review_outcomes": bool(require_baseline_review_outcomes),
        "require_baseline_reviewer_role_separation": bool(require_baseline_reviewer_role_separation),
        "require_policy_predeclared_before_capture": bool(require_policy_predeclared_before_capture),
        "rule": "Promotion requires the policy to be frozen before the first accepted decision, a prospectively frozen decision stream, a manifest-blind independently enumerated eligible-basis catalog, future-blind controlled revocations selected by a post-seal committed random seed, independently reproducible event/prediction/gold/timing/score bundles, human Full History and Flat Search baseline outcomes bound to their blinded review packets, independent manifest-blind gold from an adjudicator outside capture/baseline-review roles, zero additional missed warranted reopenings versus the actual Full History reviewer baseline, >=40% review-load reduction, <60s median instrumented human capture, no silent survival or forced reopening of gold-ambiguous cases, >=10% review-load reduction versus flat history/search, at least three controlled revocations containing both REOPEN and SURVIVE gold, and positive instrumented conditional attention savings on at least three revocations. Controlled revocations do not estimate natural revocation frequency or annual ROI.",
    }
    return {"promotion_policy_id": content_id("decision-recall-promotion-policy", body), **body}


def aggregate_scores(*, seal: Mapping[str, Any], scores: Sequence[Mapping[str, Any]], policy: Mapping[str, Any], score_artifacts: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    seal_validation = validate_stream_seal(seal)
    if not seal_validation["valid"]:
        raise DecisionRecallError(f"stream seal invalid: {seal_validation['errors']}")
    expected_policy_id = content_id("decision-recall-promotion-policy", _without(policy, "promotion_policy_id"))
    if expected_policy_id != policy.get("promotion_policy_id"):
        raise DecisionRecallError("promotion policy content id mismatch")
    if not scores:
        raise DecisionRecallError("at least one score required")

    normalized_scores = [dict(item) for item in scores]
    seen_scores: set[str] = set()
    seen_events: set[str] = set()
    for item in normalized_scores:
        expected_score_id = content_id("decision-recall-score", _without(item, "score_id"))
        if expected_score_id != item.get("score_id"):
            raise DecisionRecallError("score content id mismatch")
        if item.get("stream_seal_id") != seal.get("stream_seal_id"):
            raise DecisionRecallError("score stream-seal binding mismatch")
        score_id = str(item.get("score_id"))
        event_id = str(item.get("event_id"))
        if score_id in seen_scores:
            raise DecisionRecallError(f"duplicate score: {score_id}")
        if event_id in seen_events:
            raise DecisionRecallError(f"duplicate revocation event: {event_id}")
        seen_scores.add(score_id)
        seen_events.add(event_id)
        if str(item.get("event_stratum", "")).upper() not in {"CONTROLLED", "NATURAL"}:
            raise DecisionRecallError(f"unknown score event stratum: {item.get('event_stratum')}")

    verified_score_artifacts = False
    if score_artifacts is not None:
        bundle_by_score: dict[str, Mapping[str, Any]] = {}
        for bundle in score_artifacts:
            score_value = bundle.get("score")
            if not isinstance(score_value, Mapping):
                raise DecisionRecallError("score artifact bundle missing score")
            score_id = str(score_value.get("score_id", ""))
            if score_id in bundle_by_score:
                raise DecisionRecallError(f"duplicate score artifact bundle: {score_id}")
            bundle_by_score[score_id] = bundle
        expected_ids = {str(item["score_id"]) for item in normalized_scores}
        if set(bundle_by_score) != expected_ids:
            raise DecisionRecallError("score artifact bundles do not exactly cover aggregated scores")
        for score_value in normalized_scores:
            bundle = bundle_by_score[str(score_value["score_id"])]
            event = bundle.get("event")
            predictions = bundle.get("predictions")
            gold = bundle.get("gold")
            review_times = bundle.get("review_times")
            review_outcomes = bundle.get("review_outcomes")
            if not isinstance(event, Mapping) or not isinstance(predictions, Mapping) or not isinstance(gold, Mapping):
                raise DecisionRecallError("score artifact bundle missing event/predictions/gold")
            rebuilt = score_predictions(
                seal=seal,
                event=event,
                predictions=predictions,
                gold=gold,
                review_times=review_times if isinstance(review_times, Mapping) else None,
                review_outcomes=review_outcomes if isinstance(review_outcomes, Sequence) and not isinstance(review_outcomes, (str, bytes, bytearray)) else None,
            )
            if rebuilt != score_value:
                raise DecisionRecallError(f"score artifact bundle does not reproduce: {score_value.get('score_id')}")
        verified_score_artifacts = True

    controlled = [item for item in normalized_scores if str(item.get("event_stratum", "")).upper() == "CONTROLLED"]
    natural = [item for item in normalized_scores if str(item.get("event_stratum", "")).upper() == "NATURAL"]

    # Promotion is graded on the independently randomized controlled stratum.
    # Natural failures are stronger external evidence when they occur, but they
    # must not silently substitute for the predeclared controlled sample size.
    graded = controlled
    dr_missed = sum(int(item["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"]) for item in graded)
    full_missed = sum(int(item["metrics"][SYSTEM_FULL_HISTORY]["missed_reopenings"]) for item in graded)
    dr_review = sum(int(item["metrics"][SYSTEM_DECISION_RECALL]["review_load"]) for item in graded)
    full_review = sum(int(item["metrics"][SYSTEM_FULL_HISTORY]["review_load"]) for item in graded)
    flat_review = sum(int(item["metrics"][SYSTEM_FLAT_SEARCH]["review_load"]) for item in graded)
    silent = sum(int(item["metrics"][SYSTEM_DECISION_RECALL]["silent_ambiguous_survivals"]) for item in graded)
    ambiguous_overreach = sum(int(item["metrics"][SYSTEM_DECISION_RECALL].get("ambiguous_overreach", 0)) for item in graded)
    reduction_bps = ((full_review - dr_review) * 10000 // full_review) if full_review else 0
    flat_reduction_bps = ((flat_review - dr_review) * 10000 // flat_review) if flat_review else 0

    capture_values = [int(item["capture"]["human_capture_milliseconds"]) for item in seal["manifests"]]
    capture_total = sum(capture_values)
    capture_median = int(median(capture_values)) if capture_values else 0
    capture_sources = [str(item["capture"].get("timing_source", "DECLARED")).upper() for item in seal["manifests"]]
    acceptable_sources = set(str(item).upper() for item in policy.get("acceptable_capture_timing_sources", []))
    instrumented_capture = all(source in acceptable_sources for source in capture_sources) if capture_sources else False

    timed_savings = [
        int(item["economics"]["conditional_attention_saved_milliseconds"])
        for item in graded
        if item.get("economics", {}).get("conditional_attention_saved_milliseconds") is not None
    ]
    timed_revocations = len(timed_savings)
    instrumented_review_timing = bool(graded) and all(
        item.get("economics", {}).get("conditional_attention_saved_milliseconds") is None
        or item.get("economics", {}).get("review_timing_instrumented") is True
        for item in graded
    ) and timed_revocations > 0
    mean_saved = (sum(timed_savings) // timed_revocations) if timed_revocations else None
    median_saved = int(median(timed_savings)) if timed_savings else None
    break_even = ((capture_total + mean_saved - 1) // mean_saved) if mean_saved is not None and mean_saved > 0 else None

    blind_gold = bool(graded) and all(str(item.get("gold_method", "")).upper() == "INDEPENDENT_BLINDED_REVIEW" for item in graded)
    capture_actors = {
        str(value).strip()
        for manifest in seal.get("manifests", [])
        for value in (manifest.get("capture", {}).get("drafted_by", ""), manifest.get("capture", {}).get("confirmed_by", ""))
        if str(value).strip()
    }
    catalog_custody = seal.get("eligible_basis_catalog_custody", {})
    catalog_builder = str(catalog_custody.get("builder_id", "")).strip()
    manifest_blind_basis_catalog = (
        str(catalog_custody.get("method", "")).upper() == "MANIFEST_BLIND_RECORD_ENUMERATION"
        and str(catalog_custody.get("source_scope", "")).upper() == "CONVENTIONAL_PRE_TRIGGER_RECORDS_ONLY"
        and catalog_custody.get("manifest_visible") is False
        and bool(catalog_builder)
    )
    catalog_role_separation = bool(catalog_builder) and catalog_builder not in capture_actors
    adjudicators = {str(item.get("gold_adjudicator_id", "")).strip() for item in graded if str(item.get("gold_adjudicator_id", "")).strip()}
    baseline_review_outcomes_verified = bool(graded) and all(item.get("baseline_review_outcomes_verified") is True for item in graded)
    baseline_reviewers = {
        str(reviewer).strip()
        for item in graded
        for reviewer in item.get("baseline_reviewer_ids", {}).values()
        if str(reviewer).strip()
    }
    adjudicator_role_separation = bool(graded) and len(adjudicators) > 0 and not bool(adjudicators & capture_actors) and not bool(adjudicators & baseline_reviewers)
    baseline_reviewer_role_separation = bool(graded) and bool(baseline_reviewers) and not bool(baseline_reviewers & capture_actors) and not bool(baseline_reviewers & adjudicators)
    earliest_acceptance = min((_parse_time(item["accepted_at"]) for item in seal.get("manifests", [])), default=_parse_time(policy["declared_at"]))
    policy_predeclared_before_capture = _parse_time(policy["declared_at"]) <= earliest_acceptance
    mixed_gold_revocations = sum(
        1
        for item in graded
        if int(item.get("gold_label_counts", {}).get("REOPEN", 0)) > 0
        and int(item.get("gold_label_counts", {}).get("SURVIVE", 0)) > 0
    )
    verified_controlled_selection = bool(graded) and all(item.get("controlled_selection_verified") is True for item in graded)

    conditions = {
        "minimum_decisions": int(seal["manifest_count"]) >= int(policy["minimum_decisions"]),
        "minimum_controlled_revocations": len(controlled) >= int(policy["minimum_controlled_revocations"]),
        "maximum_additional_missed_reopenings": (dr_missed - full_missed) <= int(policy["maximum_additional_missed_reopenings_vs_full_history"]),
        "minimum_review_load_reduction": reduction_bps >= int(policy["minimum_review_load_reduction_basis_points"]),
        "maximum_median_capture": capture_median < int(policy["maximum_median_capture_milliseconds"]),
        "maximum_silent_ambiguous_survivals": silent <= int(policy["maximum_silent_ambiguous_survivals"]),
        "maximum_ambiguous_overreach": ambiguous_overreach <= int(policy.get("maximum_ambiguous_overreach", 0)),
        "outperform_flat_search": (flat_reduction_bps >= int(policy.get("minimum_review_load_reduction_vs_flat_search_basis_points", 0))) if policy.get("require_outperform_flat_search") else True,
        "instrumented_capture": instrumented_capture if policy.get("require_instrumented_capture") else True,
        "independent_manifest_blind_gold": blind_gold,
        "verified_controlled_selection": verified_controlled_selection if policy.get("require_verified_controlled_selection") else True,
        "verified_score_artifacts": verified_score_artifacts if policy.get("require_verified_score_artifacts") else True,
        "manifest_blind_basis_catalog": manifest_blind_basis_catalog if policy.get("require_manifest_blind_basis_catalog") else True,
        "catalog_role_separation": catalog_role_separation if policy.get("require_catalog_role_separation") else True,
        "baseline_review_outcomes_verified": baseline_review_outcomes_verified if policy.get("require_baseline_review_outcomes") else True,
        "baseline_reviewer_role_separation": baseline_reviewer_role_separation if policy.get("require_baseline_reviewer_role_separation") else True,
        "policy_predeclared_before_capture": policy_predeclared_before_capture if policy.get("require_policy_predeclared_before_capture") else True,
        "adjudicator_role_separation": adjudicator_role_separation if policy.get("require_adjudicator_role_separation") else True,
        "minimum_mixed_gold_revocations": mixed_gold_revocations >= int(policy.get("minimum_mixed_gold_revocations", 0)),
        "minimum_timed_revocations": timed_revocations >= int(policy.get("minimum_timed_revocations", 0)),
        "instrumented_review_timing": instrumented_review_timing if policy.get("require_instrumented_review_timing") else True,
        "positive_conditional_attention_savings": (mean_saved is not None and mean_saved > 0) if policy.get("require_positive_conditional_attention_savings") else True,
    }
    failed = [key for key, value in conditions.items() if not value]
    body = {
        "schema": DECISION_PROMOTION_RESULT_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "promotion_policy_id": policy["promotion_policy_id"],
        "score_ids": [item["score_id"] for item in normalized_scores],
        "conditions": conditions,
        "failed_conditions": failed,
        "observed": {
            "decisions": int(seal["manifest_count"]),
            "controlled_revocations": len(controlled),
            "natural_revocations": len(natural),
            "decision_recall_missed_reopenings": dr_missed,
            "additional_missed_reopenings_vs_full_history": dr_missed - full_missed,
            "decision_recall_review_load": dr_review,
            "full_history_review_load": full_review,
            "flat_search_review_load": flat_review,
            "review_load_reduction_basis_points_vs_full_history": reduction_bps,
            "review_load_reduction_basis_points_vs_flat_search": flat_reduction_bps,
            "median_capture_milliseconds": capture_median,
            "silent_ambiguous_survivals": silent,
            "ambiguous_overreach": ambiguous_overreach,
            "instrumented_capture": instrumented_capture,
            "independent_manifest_blind_gold": blind_gold,
            "verified_controlled_selection": verified_controlled_selection,
            "verified_score_artifacts": verified_score_artifacts,
            "manifest_blind_basis_catalog": manifest_blind_basis_catalog,
            "catalog_role_separation": catalog_role_separation,
            "catalog_builder_id": catalog_builder,
            "baseline_review_outcomes_verified": baseline_review_outcomes_verified,
            "baseline_reviewer_role_separation": baseline_reviewer_role_separation,
            "baseline_reviewer_count": len(baseline_reviewers),
            "policy_predeclared_before_capture": policy_predeclared_before_capture,
            "policy_declared_at": policy.get("declared_at"),
            "adjudicator_role_separation": adjudicator_role_separation,
            "adjudicator_count": len(adjudicators),
            "mixed_gold_revocations": mixed_gold_revocations,
            "timed_revocations": timed_revocations,
            "instrumented_review_timing": instrumented_review_timing,
            "mean_conditional_attention_saved_milliseconds": mean_saved,
            "median_conditional_attention_saved_milliseconds": median_saved,
            "break_even_meaningful_revocations": break_even,
            "annual_roi_inferred": False,
        },
        "verdict": "PROMOTION" if not failed else "NO_PROMOTION",
        "claim_boundary": "A PROMOTION here would establish only prospective conditional decision-recall performance under the frozen protocol. It would not establish natural revocation frequency, annual ROI, cross-domain transport, or completeness of all real-world dependencies.",
    }
    return {"promotion_result_id": content_id("decision-recall-promotion-result", body), **body}
