from __future__ import annotations

"""Module-free verifier for the prospective Decision Recall conformance fixture.

This script intentionally imports only the Python standard library.  It does not
import ``openline_claim_graph`` and it independently re-implements the restricted
canonical JSON profile, content IDs, Decision Recall reference dispositions,
flat-search baseline, blind-adjudication packet, and score arithmetic.

Passing this verifier establishes deterministic custody/mechanics for the authored
conformance fixture only.  It is not empirical evidence that prospective capture
is usable or that Decision Recall earns promotion.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import unicodedata
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]

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

SYSTEM_FULL_HISTORY = "FULL_HISTORY_REVIEW"
SYSTEM_FLAT_SEARCH = "FLAT_LOG_SEARCH"
SYSTEM_DECISION_RECALL = "DECISION_RECALL"
SYSTEMS = (SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH, SYSTEM_DECISION_RECALL)
GOLD_LABELS = ("REOPEN", "SURVIVE", "ESCALATE")
BASIS_ROLES = ("REQUIRED", "ALTERNATIVE", "CONTEXT", "AMBIGUOUS")

SCORE_CLAIM_BOUNDARY = (
    "Controlled revocations estimate conditional performance when a recorded basis loses standing. "
    "Human Full History and Flat Search outcomes are baselines, not gold. Controlled events do not "
    "estimate how often real revocations occur, annual customer ROI, or whether the decision-time "
    "manifest captured causal truth."
)
PACKET_INSTRUCTIONS = (
    "Using only the conventional complete pre-trigger record and the new revocation event, label each "
    "accepted decision REOPEN, SURVIVE, or ESCALATE. Do not inspect the prospective dependency manifest "
    "or any system prediction."
)
REVIEW_PACKET_INSTRUCTIONS = (
    "Review only the surfaced rows using the pre-trigger record and revocation event. Produce the operational "
    "disposition required by the condition. Gold is intentionally absent."
)
VERIFY_CLAIM_BOUNDARY = (
    "This module-free verifier independently reproduces content-addressed custody, reference dispositions, "
    "blind adjudication packets, and score arithmetic for the authored conformance fixture. It does not "
    "turn the fixture into prospective human evidence, validate capture usability, estimate natural "
    "revocation frequency, or establish product promotion."
)

FROZEN_ENGINE_SHA256 = {
    "src/openline_claim_graph/temporal_holdout.py": "bc8f0011d65cb1c2c728ef374ebb82b86c3c08657e9919427ff5d80b2707886a",
    "src/openline_claim_graph/comparative_benchmark.py": "6c04e9e021cbc1c01aae78606acc6cd41393c99673185e1e8e3ee4ccaa06e4b1",
    "src/openline_claim_graph/impact.py": "1757340f69e919ff68d3cdfe4265fc1ac330bc99ff5bcd20b69058fa846905a2",
}

EXPECTED_POLICY = {
    "declared_at": "2026-08-18T00:00:00Z",
    "minimum_decisions": 30,
    "minimum_controlled_revocations": 10,
    "maximum_additional_missed_reopenings_vs_full_history": 0,
    "minimum_review_load_reduction_basis_points": 4000,
    "maximum_median_capture_milliseconds": 60000,
    "maximum_silent_ambiguous_survivals": 0,
    "maximum_ambiguous_overreach": 0,
    "minimum_review_load_reduction_vs_flat_search_basis_points": 1000,
    "minimum_timed_revocations": 3,
    "require_positive_conditional_attention_savings": True,
    "require_instrumented_capture": True,
    "acceptable_capture_timing_sources": ["MONOTONIC_CLI", "MONOTONIC_UI"],
    "require_outperform_flat_search": True,
    "minimum_mixed_gold_revocations": 3,
    "require_adjudicator_role_separation": True,
    "require_verified_controlled_selection": True,
    "require_instrumented_review_timing": True,
    "require_verified_score_artifacts": True,
    "require_manifest_blind_basis_catalog": True,
    "require_catalog_role_separation": True,
    "require_baseline_review_outcomes": True,
    "require_baseline_reviewer_role_separation": True,
    "require_policy_predeclared_before_capture": True,
}


class VerificationError(ValueError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize(value: Any, path: str = "$") -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise VerificationError(f"{path}: float forbidden by restricted canonical JSON")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalize(item, f"{path}[{i}]") for i, item in enumerate(value)]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                raise VerificationError(f"{path}: object key must be string")
            key = unicodedata.normalize("NFC", raw_key)
            if key in out:
                raise VerificationError(f"{path}: duplicate key after NFC: {key!r}")
            out[key] = _normalize(raw_value, f"{path}.{key}")
        return out
    raise VerificationError(f"{path}: unsupported type {type(value).__name__}")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_id(namespace: str, value: Any) -> str:
    if not namespace or ":" in namespace:
        raise VerificationError("invalid content-id namespace")
    return f"{namespace}:sha256:{hashlib.sha256(canonical_json(value)).hexdigest()}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def without(record: Mapping[str, Any], key: str) -> dict[str, Any]:
    out = dict(record)
    out.pop(key, None)
    return out


def parse_time(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise VerificationError("timestamp missing")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise VerificationError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def median_int(values: Sequence[int]) -> int:
    if not values:
        raise VerificationError("median of empty sequence")
    ordered = sorted(int(v) for v in values)
    n = len(ordered)
    if n % 2:
        return ordered[n // 2]
    return (ordered[n // 2 - 1] + ordered[n // 2]) // 2


def validate_manifest(manifest: Mapping[str, Any], sealed_at: str) -> list[str]:
    errors: list[str] = []
    try:
        if manifest.get("schema") != DECISION_MANIFEST_SCHEMA:
            errors.append("schema")
        if content_id("decision-recall-manifest", without(manifest, "manifest_id")) != manifest.get("manifest_id"):
            errors.append("content_id")
        if not str(manifest.get("decision_id", "")).strip():
            errors.append("decision_id")
        if parse_time(manifest.get("accepted_at")) > parse_time(sealed_at):
            errors.append("accepted_after_seal")

        basis = list(manifest.get("basis", []))
        assumptions = list(manifest.get("assumptions", []))
        basis_ids = [str(item.get("basis_id", "")) for item in basis]
        assumption_ids = [str(item.get("assumption_id", "")) for item in assumptions]
        dep_ids = set(basis_ids) | set(assumption_ids)
        if "" in dep_ids or len(basis_ids) != len(set(basis_ids)) or len(assumption_ids) != len(set(assumption_ids)):
            errors.append("dependency_ids")
        roles = {str(item.get("basis_id")): str(item.get("role")) for item in basis}
        roles.update({str(item.get("assumption_id")): str(item.get("role")) for item in assumptions})
        if any(role not in BASIS_ROLES for role in roles.values()):
            errors.append("dependency_role")
        required = set(map(str, manifest.get("required_dependencies", [])))
        if not required <= dep_ids or any(roles.get(item) != "REQUIRED" for item in required):
            errors.append("required_dependencies")

        alternative_ids: set[str] = set()
        group_ids: set[str] = set()
        for group in manifest.get("alternative_support", []):
            gid = str(group.get("group_id", ""))
            members = set(map(str, group.get("dependency_ids", [])))
            if not gid or gid in group_ids or not members or not members <= dep_ids:
                errors.append("alternative_group")
            if any(roles.get(item) != "ALTERNATIVE" for item in members):
                errors.append("alternative_role")
            group_ids.add(gid)
            alternative_ids |= members
        declared_alternatives = {item for item, role in roles.items() if role == "ALTERNATIVE"}
        if declared_alternatives != alternative_ids:
            errors.append("alternative_coverage")

        condition_ids: set[str] = set()
        for condition in manifest.get("invalidation_conditions", []):
            cid = str(condition.get("condition_id", ""))
            did = str(condition.get("dependency_id", ""))
            event_types = list(condition.get("event_types", []))
            if not cid or cid in condition_ids or did not in dep_ids or not event_types:
                errors.append("invalidation_condition")
            if any(str(item) != "LOSS_OF_STANDING" for item in event_types):
                errors.append("invalidation_event_type")
            condition_ids.add(cid)

        capture = manifest.get("capture", {})
        if parse_time(capture.get("confirmed_at")) < parse_time(capture.get("started_at")):
            errors.append("capture_time_order")
        human_ms = int(capture.get("human_capture_milliseconds", -1))
        correction_count = int(capture.get("correction_count", -1))
        if human_ms < 0 or correction_count < 0:
            errors.append("capture_metrics")
        if bool(capture.get("accepted_without_correction")) != (correction_count == 0):
            errors.append("capture_correction_flag")
    except Exception as exc:  # verifier records malformed artifacts rather than crashing
        errors.append(f"exception:{type(exc).__name__}:{exc}")
    return errors


def validate_pre_trigger_record(record: Mapping[str, Any], sealed_at: str) -> list[str]:
    errors: list[str] = []
    try:
        if record.get("schema") != DECISION_PRE_TRIGGER_RECORD_SCHEMA:
            errors.append("schema")
        if content_id("decision-recall-pre-trigger-record", without(record, "pre_trigger_record_id")) != record.get("pre_trigger_record_id"):
            errors.append("content_id")
        if parse_time(record.get("available_at")) > parse_time(sealed_at):
            errors.append("available_after_seal")
        material_ids: set[str] = set()
        for material in record.get("materials", []):
            mid = str(material.get("material_id", ""))
            if not mid or mid in material_ids:
                errors.append("material_id")
            material_ids.add(mid)
            evidence = str(material.get("sha256", ""))
            if evidence != sha256_text(str(material.get("text", ""))):
                # Fixture records omit externally supplied bytes, so their SHA is
                # expected to bind the included text directly.
                errors.append("material_sha256")
    except Exception as exc:
        errors.append(f"exception:{type(exc).__name__}:{exc}")
    return errors


def validate_seal(seal: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        if seal.get("schema") != DECISION_STREAM_SEAL_SCHEMA:
            errors.append("schema")
        if content_id("decision-recall-stream-seal", without(seal, "stream_seal_id")) != seal.get("stream_seal_id"):
            errors.append("content_id")
        manifests = list(seal.get("manifests", []))
        records = list(seal.get("pre_trigger_records", []))
        catalog = list(seal.get("eligible_bases", []))
        if int(seal.get("manifest_count", -1)) != len(manifests):
            errors.append("manifest_count")
        decision_ids = [str(item.get("decision_id")) for item in manifests]
        manifest_ids = [str(item.get("manifest_id")) for item in manifests]
        if len(set(decision_ids)) != len(decision_ids) or len(set(manifest_ids)) != len(manifest_ids):
            errors.append("duplicate_manifest_or_decision")
        if seal.get("decision_ids") != decision_ids:
            errors.append("decision_ids")
        if seal.get("manifest_ids") != manifest_ids:
            errors.append("manifest_ids")
        if seal.get("manifests_root") != sha256_text("\n".join(manifest_ids)):
            errors.append("manifests_root")
        for manifest in manifests:
            if validate_manifest(manifest, str(seal.get("sealed_at"))):
                errors.append(f"manifest:{manifest.get('decision_id')}")

        record_ids = [str(item.get("pre_trigger_record_id")) for item in records]
        if len(set(record_ids)) != len(record_ids):
            errors.append("duplicate_pre_trigger_record")
        if seal.get("pre_trigger_record_ids") != record_ids:
            errors.append("pre_trigger_record_ids")
        if seal.get("pre_trigger_records_root") != sha256_text("\n".join(record_ids)):
            errors.append("pre_trigger_records_root")
        manifest_decisions = {str(item.get("decision_id")): str(item.get("decision")) for item in manifests}
        records_by_decision: dict[str, int] = {did: 0 for did in decision_ids}
        for record in records:
            if validate_pre_trigger_record(record, str(seal.get("sealed_at"))):
                errors.append(f"pre_trigger_record:{record.get('pre_trigger_record_id')}")
            did = str(record.get("decision_id"))
            if did not in records_by_decision:
                errors.append("record_unknown_decision")
            else:
                records_by_decision[did] += 1
                if str(record.get("decision")) != manifest_decisions[did]:
                    errors.append("record_decision_text_mismatch")
        if any(count < 1 for count in records_by_decision.values()):
            errors.append("decision_missing_record")

        basis_ids = [str(item.get("basis_id")) for item in catalog]
        if basis_ids != sorted(basis_ids) or len(set(basis_ids)) != len(basis_ids):
            errors.append("eligible_basis_ids_order_or_duplicate")
        if seal.get("eligible_basis_ids") != basis_ids:
            errors.append("eligible_basis_ids")
        if seal.get("eligible_bases_root") != sha256_text("\n".join(basis_ids)):
            errors.append("eligible_bases_root")
        record_id_set = set(record_ids)
        for basis in catalog:
            mentions = list(basis.get("mentioned_record_ids", []))
            if not mentions or not set(map(str, mentions)) <= record_id_set:
                errors.append(f"eligible_basis_mentions:{basis.get('basis_id')}")
        declared = {
            str(item.get("basis_id"))
            for manifest in manifests
            for item in manifest.get("basis", [])
        } | {
            str(item.get("assumption_id"))
            for manifest in manifests
            for item in manifest.get("assumptions", [])
        }
        if not declared <= set(basis_ids):
            errors.append("declared_dependency_missing_from_catalog")

        custody = seal.get("eligible_basis_catalog_custody", {})
        if str(custody.get("method", "")).upper() != "MANIFEST_BLIND_RECORD_ENUMERATION":
            errors.append("catalog_custody_method")
        if str(custody.get("source_scope", "")).upper() != "CONVENTIONAL_PRE_TRIGGER_RECORDS_ONLY":
            errors.append("catalog_custody_source_scope")
        if custody.get("manifest_visible") is not False:
            errors.append("catalog_manifest_visible")
        if not str(custody.get("builder_id", "")).strip():
            errors.append("catalog_builder_id")
        built_at = parse_time(custody.get("built_at"))
        if built_at > parse_time(seal.get("sealed_at")):
            errors.append("catalog_built_after_seal")
        latest_record = max((parse_time(record.get("available_at")) for record in records), default=built_at)
        if built_at < latest_record:
            errors.append("catalog_built_before_complete_record_scope")
        capture_actors = {
            str(value).strip()
            for manifest in manifests
            for value in (manifest.get("capture", {}).get("drafted_by", ""), manifest.get("capture", {}).get("confirmed_by", ""))
            if str(value).strip()
        }
        if str(custody.get("builder_id", "")).strip() in capture_actors:
            errors.append("catalog_builder_not_role_separated")
    except Exception as exc:
        errors.append(f"exception:{type(exc).__name__}:{exc}")
    return errors


def validate_selection_proof(seal: Mapping[str, Any], event: Mapping[str, Any]) -> list[str]:
    proof = event.get("selection_proof") or {}
    if not proof:
        return []
    errors: list[str] = []
    try:
        seed = bytes.fromhex(str(proof.get("seed_hex", "")))
        if not seed:
            errors.append("empty_seed")
            return errors
        if hashlib.sha256(seed).hexdigest() != proof.get("seed_sha256"):
            errors.append("seed_sha256")
        if parse_time(proof.get("selection_at")) <= parse_time(seal.get("sealed_at")):
            errors.append("selection_not_post_seal")
        method = "sha256_rank(seed || stream_seal_id || basis_id)"
        if proof.get("selection_method") != method:
            errors.append("method")
        candidates = sorted(str(item.get("basis_id")) for item in seal.get("eligible_bases", []))
        selected_count = int(proof.get("selected_count", 0))
        if int(proof.get("candidate_basis_count", -1)) != len(candidates):
            errors.append("candidate_count")
        if selected_count < 1 or selected_count > len(candidates):
            errors.append("selected_count")
            return errors
        ranked = sorted(
            candidates,
            key=lambda candidate: hashlib.sha256(
                seed + b"\0" + str(seal["stream_seal_id"]).encode() + b"\0" + candidate.encode()
            ).digest(),
        )
        basis_id = str(event.get("basis_id"))
        if basis_id not in ranked[:selected_count]:
            errors.append("basis_not_selected")
        elif int(proof.get("rank", -1)) != ranked.index(basis_id):
            errors.append("rank")
    except Exception as exc:
        errors.append(f"exception:{type(exc).__name__}:{exc}")
    return errors


def validate_event(event: Mapping[str, Any], seal: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        if event.get("schema") != DECISION_REVOCATION_EVENT_SCHEMA:
            errors.append("schema")
        if content_id("decision-recall-revocation-event", without(event, "event_id")) != event.get("event_id"):
            errors.append("content_id")
        if event.get("stream_seal_id") != seal.get("stream_seal_id"):
            errors.append("stream_seal_binding")
        if event.get("event_type") != "LOSS_OF_STANDING":
            errors.append("event_type")
        if parse_time(event.get("event_at")) <= parse_time(seal.get("sealed_at")):
            errors.append("event_not_post_seal")
        stratum = str(event.get("stratum", "")).upper()
        if stratum not in {"CONTROLLED", "NATURAL"}:
            errors.append("stratum")
        if stratum == "CONTROLLED":
            eligible = {str(item.get("basis_id")) for item in seal.get("eligible_bases", [])}
            if str(event.get("basis_id")) not in eligible:
                errors.append("controlled_basis_not_eligible")
            errors.extend(validate_selection_proof(seal, event))
            proof = event.get("selection_proof") or {}
            if proof and parse_time(event.get("event_at")) < parse_time(proof.get("selection_at")):
                errors.append("event_precedes_selection")
    except Exception as exc:
        errors.append(f"exception:{type(exc).__name__}:{exc}")
    return errors


def flat_mentions(seal: Mapping[str, Any], decision_id: str, basis_id: str) -> bool:
    record_ids = {
        str(item.get("pre_trigger_record_id"))
        for item in seal.get("pre_trigger_records", [])
        if str(item.get("decision_id")) == decision_id
    }
    basis = next((item for item in seal.get("eligible_bases", []) if str(item.get("basis_id")) == basis_id), None)
    if basis is not None:
        return bool(record_ids & set(map(str, basis.get("mentioned_record_ids", []))))
    needle = basis_id.casefold()
    for record in seal.get("pre_trigger_records", []):
        if str(record.get("pre_trigger_record_id")) not in record_ids:
            continue
        for material in record.get("materials", []):
            haystack = " ".join(
                [str(material.get("material_id", "")), str(material.get("locator", "")), str(material.get("text", ""))]
            ).casefold()
            if needle and needle in haystack:
                return True
    return False


def reference_disposition(manifest: Mapping[str, Any], event: Mapping[str, Any]) -> tuple[str, list[str], str]:
    basis_id = str(event["basis_id"])
    roles = {str(item.get("basis_id")): str(item.get("role")) for item in manifest.get("basis", [])}
    roles.update({str(item.get("assumption_id")): str(item.get("role")) for item in manifest.get("assumptions", [])})
    if basis_id not in roles:
        return "SURVIVE", [], "revoked basis is absent from the accepted dependency record"
    role = roles[basis_id]
    if role == "CONTEXT":
        return "SURVIVE", [basis_id], "basis was recorded as contextual rather than material"
    if role == "AMBIGUOUS":
        return "ESCALATE", [basis_id], "accepted record declared materiality ambiguous"
    matching_condition = any(
        str(item.get("dependency_id")) == basis_id and str(event.get("event_type")) in item.get("event_types", [])
        for item in manifest.get("invalidation_conditions", [])
    )
    if not matching_condition:
        return "ESCALATE", [basis_id], "material dependency lost standing without a matching predeclared invalidation condition"
    required = set(map(str, manifest.get("required_dependencies", [])))
    alternatives = [set(map(str, item.get("dependency_ids", []))) for item in manifest.get("alternative_support", []) if item.get("dependency_ids")]
    support_sets = ([required] if required else []) + alternatives
    containing = [group for group in support_sets if basis_id in group]
    if not containing:
        return "ESCALATE", [basis_id], "material basis is not assigned to any declared sufficient support set"
    standing = [group for group in support_sets if basis_id not in group]
    if standing:
        chosen = min(standing, key=lambda group: (len(group), sorted(group)))
        return "SURVIVE", sorted(chosen), "an independently declared sufficient support set remains standing"
    witness = sorted({item for group in containing for item in group})
    return "REOPEN", witness, "every predeclared sufficient support path depends on the basis that lost standing"


def rebuild_predictions(seal: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for manifest in seal.get("manifests", []):
        basis_id = str(event.get("basis_id"))
        flat = "REVIEW" if flat_mentions(seal, str(manifest.get("decision_id")), basis_id) else "SURVIVE"
        disposition, witness, reason = reference_disposition(manifest, event)
        rows.append({
            "decision_id": manifest["decision_id"],
            "decision": manifest["decision"],
            SYSTEM_FULL_HISTORY: {"disposition": "REVIEW", "witness": []},
            SYSTEM_FLAT_SEARCH: {"disposition": flat, "witness": [basis_id] if flat == "REVIEW" else []},
            SYSTEM_DECISION_RECALL: {"disposition": disposition, "witness": witness, "reason": reason},
        })
    body = {
        "schema": DECISION_PREDICTIONS_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "event_id": event["event_id"],
        "rows": rows,
    }
    return {"predictions_id": content_id("decision-recall-predictions", body), **body}


def rebuild_packet(seal: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for manifest in seal.get("manifests", []):
        records = [
            item for item in seal.get("pre_trigger_records", [])
            if str(item.get("decision_id")) == str(manifest.get("decision_id"))
        ]
        if not records:
            raise VerificationError(f"no conventional record for {manifest['decision_id']}")
        rows.append({
            "decision_id": manifest["decision_id"],
            "decision": records[0]["decision"],
            "complete_pre_trigger_records": records,
        })
    body = {
        "schema": DECISION_ADJUDICATION_PACKET_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "event": dict(event),
        "instructions": PACKET_INSTRUCTIONS,
        "rows": rows,
    }
    return {"adjudication_packet_id": content_id("decision-recall-adjudication-packet", body), **body}


def rebuild_review_packet(seal: Mapping[str, Any], event: Mapping[str, Any], predictions: Mapping[str, Any], system: str) -> dict[str, Any]:
    rows = []
    for prediction_row in predictions.get("rows", []):
        disposition = str(prediction_row[system]["disposition"])
        include = (
            system == SYSTEM_FULL_HISTORY
            or (system == SYSTEM_FLAT_SEARCH and disposition == "REVIEW")
            or (system == SYSTEM_DECISION_RECALL and disposition in {"REOPEN", "ESCALATE"})
        )
        if not include:
            continue
        records = [
            item for item in seal.get("pre_trigger_records", [])
            if str(item.get("decision_id")) == str(prediction_row.get("decision_id"))
        ]
        if not records:
            raise VerificationError(f"no conventional record for {prediction_row['decision_id']}")
        rows.append({
            "decision_id": prediction_row["decision_id"],
            "decision": records[0]["decision"],
            "system_projection": dict(prediction_row[system]),
            "complete_pre_trigger_records": records,
        })
    body = {
        "schema": DECISION_REVIEW_PACKET_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "event_id": event["event_id"],
        "system": system,
        "event": dict(event),
        "review_row_count": len(rows),
        "instructions": REVIEW_PACKET_INSTRUCTIONS,
        "rows": rows,
    }
    return {"review_packet_id": content_id("decision-recall-review-packet", body), **body}


def validate_gold(gold: Mapping[str, Any], packet: Mapping[str, Any], event: Mapping[str, Any], seal: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        if gold.get("schema") != DECISION_GOLD_SCHEMA:
            errors.append("schema")
        if content_id("decision-recall-gold", without(gold, "gold_id")) != gold.get("gold_id"):
            errors.append("content_id")
        if gold.get("adjudication_packet_id") != packet.get("adjudication_packet_id"):
            errors.append("packet_binding")
        if gold.get("stream_seal_id") != seal.get("stream_seal_id") or gold.get("event_id") != event.get("event_id"):
            errors.append("event_or_seal_binding")
        if parse_time(gold.get("adjudicated_at")) <= parse_time(event.get("event_at")):
            errors.append("adjudication_not_post_event")
        ids = [str(item.get("decision_id")) for item in gold.get("labels", [])]
        expected = [str(item.get("decision_id")) for item in packet.get("rows", [])]
        if len(ids) != len(set(ids)) or set(ids) != set(expected):
            errors.append("coverage")
        if any(str(item.get("label", "")).upper() not in GOLD_LABELS for item in gold.get("labels", [])):
            errors.append("label")
    except Exception as exc:
        errors.append(f"exception:{type(exc).__name__}:{exc}")
    return errors


def validate_review_outcome(review_outcome: Mapping[str, Any], seal: Mapping[str, Any], event: Mapping[str, Any], predictions: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        system = str(review_outcome.get("system", "")).upper()
        if system not in {SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH}:
            errors.append("system")
        else:
            packet = rebuild_review_packet(seal, event, predictions, system)
            if review_outcome.get("review_packet_id") != packet.get("review_packet_id"):
                errors.append("packet_binding")
            expected_ids = {str(item.get("decision_id")) for item in packet.get("rows", [])}
            ids = [str(item.get("decision_id")) for item in review_outcome.get("labels", [])]
            if len(ids) != len(set(ids)) or set(ids) != expected_ids:
                errors.append("coverage")
            if any(str(item.get("label", "")).upper() not in GOLD_LABELS for item in review_outcome.get("labels", [])):
                errors.append("label")
        if review_outcome.get("schema") != DECISION_REVIEW_OUTCOME_SCHEMA:
            errors.append("schema")
        if content_id("decision-recall-review-outcome", without(review_outcome, "review_outcome_id")) != review_outcome.get("review_outcome_id"):
            errors.append("content_id")
        if review_outcome.get("stream_seal_id") != seal.get("stream_seal_id") or review_outcome.get("event_id") != event.get("event_id"):
            errors.append("event_or_seal_binding")
        if str(review_outcome.get("method", "")).upper() != "BLINDED_BASELINE_REVIEW":
            errors.append("method")
        if not str(review_outcome.get("reviewer_id", "")).strip():
            errors.append("reviewer_id")
        if parse_time(review_outcome.get("reviewed_at")) <= parse_time(event.get("event_at")):
            errors.append("reviewed_not_post_event")
    except Exception as exc:
        errors.append(f"exception:{type(exc).__name__}:{exc}")
    return errors


def validate_review_times(review_times: Mapping[str, Any], seal: Mapping[str, Any], event: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        if review_times.get("schema") != DECISION_REVIEW_TIMES_SCHEMA:
            errors.append("schema")
        if content_id("decision-recall-review-times", without(review_times, "review_times_id")) != review_times.get("review_times_id"):
            errors.append("content_id")
        if review_times.get("stream_seal_id") != seal.get("stream_seal_id") or review_times.get("event_id") != event.get("event_id"):
            errors.append("binding")
        for row in review_times.get("records", []):
            if row.get("system") not in SYSTEMS:
                errors.append("system")
            if int(row.get("review_milliseconds", -1)) < 0:
                errors.append("negative_time")
            packet_id = str(row.get("review_packet_id", ""))
            if packet_id and not packet_id.startswith("decision-recall-review-packet:sha256:"):
                errors.append("review_packet_namespace")
    except Exception as exc:
        errors.append(f"exception:{type(exc).__name__}:{exc}")
    return errors


def is_review(disposition: str) -> bool:
    return disposition in {"REVIEW", "REOPEN", "ESCALATE"}


def rebuild_score(
    seal: Mapping[str, Any],
    event: Mapping[str, Any],
    predictions: Mapping[str, Any],
    gold: Mapping[str, Any],
    review_times: Mapping[str, Any] | None,
    review_outcomes: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    gold_map = {str(item["decision_id"]): str(item["label"]).upper() for item in gold.get("labels", [])}
    counts = {label: sum(1 for value in gold_map.values() if value == label) for label in GOLD_LABELS}

    outcome_by_system: dict[str, Mapping[str, Any]] = {}
    for outcome in review_outcomes or []:
        system = str(outcome.get("system", "")).upper()
        if system in outcome_by_system:
            raise VerificationError(f"duplicate review outcome {system}")
        outcome_by_system[system] = outcome
    baseline_verified = set(outcome_by_system) == {SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH}
    baseline_reviewer_ids = {
        system: str(outcome_by_system[system].get("reviewer_id", ""))
        for system in sorted(outcome_by_system)
    }
    outcome_labels = {
        system: {str(item["decision_id"]): str(item["label"]).upper() for item in outcome.get("labels", [])}
        for system, outcome in outcome_by_system.items()
    }

    metrics: dict[str, dict[str, Any]] = {}
    for system in SYSTEMS:
        review_load = missed = unnecessary = gold_escalations = surfaced = exact = silent = overreach = final_errors = 0
        baseline_bound = system in outcome_by_system
        for row in predictions.get("rows", []):
            triage = str(row[system]["disposition"])
            target = gold_map[str(row["decision_id"])]
            if is_review(triage):
                review_load += 1
            effective = triage
            if system in {SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH}:
                if triage == "SURVIVE":
                    effective = "SURVIVE"
                elif baseline_bound:
                    effective = outcome_labels[system][str(row["decision_id"])]
            if target == "REOPEN" and effective == "SURVIVE":
                missed += 1
            if target == "SURVIVE" and is_review(triage):
                unnecessary += 1
            if target == "ESCALATE":
                gold_escalations += 1
                if is_review(triage):
                    surfaced += 1
                if effective == "SURVIVE":
                    silent += 1
                if system == SYSTEM_DECISION_RECALL and effective == "REOPEN":
                    overreach += 1
            if system == SYSTEM_DECISION_RECALL or baseline_bound:
                if effective == target:
                    exact += 1
                else:
                    final_errors += 1
            elif (target == "SURVIVE" and triage == "SURVIVE") or (target != "SURVIVE" and triage == "REVIEW"):
                exact += 1
        count = len(predictions.get("rows", []))
        metrics[system] = {
            "decision_count": count,
            "review_load": review_load,
            "review_load_reduction_basis_points_vs_full_history": 0,
            "missed_reopenings": missed,
            "unnecessary_reviews": unnecessary,
            "gold_escalations": gold_escalations,
            "surfaced_escalations": surfaced,
            "silent_ambiguous_survivals": silent,
            "ambiguous_overreach": overreach,
            "baseline_review_outcome_bound": baseline_bound,
            "final_disposition_errors": final_errors if (system == SYSTEM_DECISION_RECALL or baseline_bound) else None,
            "exact_or_correct_triage": exact,
            "exact_or_correct_triage_basis_points": (exact * 10000 // count) if count else 0,
        }
    full_load = metrics[SYSTEM_FULL_HISTORY]["review_load"]
    for system in SYSTEMS:
        load = metrics[system]["review_load"]
        metrics[system]["review_load_reduction_basis_points_vs_full_history"] = (
            (full_load - load) * 10000 // full_load if full_load else 0
        )

    capture_values = [int(item["capture"]["human_capture_milliseconds"]) for item in seal.get("manifests", [])]
    capture_total = sum(capture_values)
    capture_median = median_int(capture_values) if capture_values else 0
    no_correction = sum(1 for item in seal.get("manifests", []) if item.get("capture", {}).get("accepted_without_correction"))
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
        by_system: dict[str, list[int]] = {system: [] for system in SYSTEMS}
        reviewer_ids_by_system: dict[str, set[str]] = {system: set() for system in SYSTEMS}
        sources: list[str] = []
        packet_bindings_ok = True
        expected_packets = {
            system: rebuild_review_packet(seal, event, predictions, system)["review_packet_id"]
            for system in SYSTEMS
        }
        for item in review_times.get("records", []):
            system = str(item.get("system"))
            if system in by_system:
                by_system[system].append(int(item["review_milliseconds"]))
                reviewer_ids_by_system[system].add(str(item.get("reviewer_id", "")))
                sources.append(str(item.get("timing_source", "DECLARED")).upper())
                if str(item.get("review_packet_id", "")) != expected_packets[system]:
                    packet_bindings_ok = False
        outcome_timing_ok = baseline_verified and all(
            baseline_reviewer_ids[system] in reviewer_ids_by_system[system]
            for system in (SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH)
        )
        economics["review_packet_bindings_valid"] = packet_bindings_ok and bool(sources)
        economics["review_outcome_timing_bindings_valid"] = outcome_timing_ok
        economics["review_timing_instrumented"] = bool(sources) and packet_bindings_ok and outcome_timing_ok and all(
            source in {"MONOTONIC_CLI", "MONOTONIC_UI"} for source in sources
        )
        if by_system[SYSTEM_FULL_HISTORY] and by_system[SYSTEM_DECISION_RECALL]:
            full_median = median_int(by_system[SYSTEM_FULL_HISTORY])
            recall_median = median_int(by_system[SYSTEM_DECISION_RECALL])
            saved = full_median - recall_median
            economics.update({
                "full_history_review_median_milliseconds": full_median,
                "decision_recall_review_median_milliseconds": recall_median,
                "conditional_attention_saved_milliseconds": saved,
                "break_even_meaningful_revocations": (capture_total + saved - 1) // saved if saved > 0 else None,
            })

    body = {
        "schema": DECISION_SCORE_SCHEMA,
        "stream_seal_id": seal["stream_seal_id"],
        "event_id": event["event_id"],
        "predictions_id": predictions["predictions_id"],
        "gold_id": gold["gold_id"],
        "gold_method": gold.get("method", ""),
        "gold_adjudicator_id": gold.get("adjudicator_id", ""),
        "baseline_review_outcomes_verified": baseline_verified,
        "baseline_review_outcome_ids": sorted(str(item["review_outcome_id"]) for item in outcome_by_system.values()),
        "baseline_reviewer_ids": baseline_reviewer_ids,
        "event_stratum": event.get("stratum", ""),
        "controlled_selection_verified": bool(event.get("selection_proof")) if str(event.get("stratum", "")).upper() == "CONTROLLED" else None,
        "gold_label_counts": counts,
        "metrics": metrics,
        "economics": economics,
        "claim_boundary": SCORE_CLAIM_BOUNDARY,
    }
    return {"score_id": content_id("decision-recall-score", body), **body}

def main() -> int:
    parser = argparse.ArgumentParser(description="Module-free verifier for the prospective Decision Recall mechanics fixture")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    base = Path(args.artifact)
    checks: list[dict[str, Any]] = []

    def check(name: str, value: Any, detail: Any = None) -> None:
        checks.append({"name": name, "pass": bool(value), "detail": detail})

    try:
        seal = load(base / "stream-seal.json")
        policy = load(base / "promotion-policy.json")
        report = load(base / "REPORT.json")
    except Exception as exc:
        output = {
            "schema": "openline.decision-recall-prospective-conformance-verification.v2",
            "module_free": True,
            "check_count": 1,
            "failed_count": 1,
            "checks": [{"name": "fixture_load", "pass": False, "detail": str(exc)}],
            "disposition": "FAIL",
            "valid": False,
            "claim_boundary": VERIFY_CLAIM_BOUNDARY,
        }
        if args.output:
            Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(output, indent=2, sort_keys=True))
        return 1

    seal_errors = validate_seal(seal)
    check("stream_seal_valid_independent", not seal_errors, seal_errors)
    check("stream_seal_schema", seal.get("schema") == DECISION_STREAM_SEAL_SCHEMA, seal.get("schema"))
    check("eight_fixture_decisions", seal.get("manifest_count") == 8, seal.get("manifest_count"))
    check("protocol_id", seal.get("protocol_id") == "decision-recall-prospective-001-v1", seal.get("protocol_id"))
    custody = seal.get("eligible_basis_catalog_custody", {})
    check("catalog_manifest_blind_method", custody.get("method") == "MANIFEST_BLIND_RECORD_ENUMERATION", custody)
    check("catalog_conventional_record_scope", custody.get("source_scope") == "CONVENTIONAL_PRE_TRIGGER_RECORDS_ONLY", custody)
    check("catalog_manifest_not_visible", custody.get("manifest_visible") is False, custody.get("manifest_visible"))
    capture_actors = {
        str(value).strip()
        for manifest in seal.get("manifests", [])
        for value in (manifest.get("capture", {}).get("drafted_by", ""), manifest.get("capture", {}).get("confirmed_by", ""))
        if str(value).strip()
    }
    check("catalog_builder_role_separated", str(custody.get("builder_id", "")).strip() not in capture_actors, custody.get("builder_id"))

    check("promotion_policy_schema", policy.get("schema") == DECISION_PROMOTION_POLICY_SCHEMA, policy.get("schema"))
    check(
        "promotion_policy_content_id",
        content_id("decision-recall-promotion-policy", without(policy, "promotion_policy_id")) == policy.get("promotion_policy_id"),
        policy.get("promotion_policy_id"),
    )
    for key, expected in EXPECTED_POLICY.items():
        check(f"promotion_policy:{key}", policy.get(key) == expected, policy.get(key))

    check("mechanics_only_status", report.get("status") == "MECHANICS_ONLY_NOT_PRODUCT_EVIDENCE", report.get("status"))
    check("promotion_not_claimed", report.get("promotion_eligible") is False, report.get("promotion_eligible"))
    check("report_benchmark_binding", report.get("benchmark_id") == seal.get("benchmark_id"), report.get("benchmark_id"))
    check("report_manifest_count", report.get("manifest_count") == seal.get("manifest_count"), report.get("manifest_count"))
    check("report_policy_binding", report.get("promotion_policy_id") == policy.get("promotion_policy_id"), report.get("promotion_policy_id"))
    why_not = list(report.get("why_not", []))
    check("report_explicitly_disclaims_authored_fixture", any("authored calibration" in str(item) for item in why_not), why_not)
    check("report_explicitly_disclaims_empirical_gold", any("pre-authored" in str(item) for item in why_not), why_not)
    check("report_explicitly_disclaims_attention_economics", any("synthetic" in str(item) for item in why_not), why_not)

    for rel, expected in FROZEN_ENGINE_SHA256.items():
        actual = file_sha256(ROOT / rel)
        check(f"frozen_engine:{rel}", actual == expected, actual)

    event_dirs = sorted(path for path in base.iterdir() if path.is_dir() and path.name.startswith("event-"))
    check("five_fixture_events", len(event_dirs) == 5, len(event_dirs))
    check("report_event_count", report.get("event_count") == len(event_dirs), report.get("event_count"))
    report_events = {str(item.get("event_id")): item for item in report.get("events", [])}
    check("report_event_summary_count", len(report_events) == len(event_dirs), len(report_events))

    omission_seen = False
    ambiguity_seen = False
    negative_control_seen = False
    full_history_error_control_seen = False
    for event_dir in event_dirs:
        try:
            event = load(event_dir / "event.json")
            predictions = load(event_dir / "predictions.json")
            packet = load(event_dir / "adjudication-packet.json")
            gold = load(event_dir / "gold.private.json")
            review_times = load(event_dir / "review-times.fixture.json")
            review_outcomes = [
                load(event_dir / "review-outcome.full-history.fixture.json"),
                load(event_dir / "review-outcome.flat-search.fixture.json"),
            ]
            score = load(event_dir / "score.json")
            stored_review_packets = {
                SYSTEM_FULL_HISTORY: load(event_dir / "review-packet.full-history.json"),
                SYSTEM_FLAT_SEARCH: load(event_dir / "review-packet.flat-search.json"),
                SYSTEM_DECISION_RECALL: load(event_dir / "review-packet.decision-recall.json"),
            }
        except Exception as exc:
            check(f"{event_dir.name}:load", False, str(exc))
            continue

        event_errors = validate_event(event, seal)
        check(f"{event_dir.name}:event_valid_independent", not event_errors, event_errors)
        check(f"{event_dir.name}:controlled_stratum", event.get("stratum") == "CONTROLLED", event.get("stratum"))
        check(
            f"{event_dir.name}:fixture_does_not_fake_random_selection",
            event.get("selection_proof") == {},
            event.get("selection_proof"),
        )

        rebuilt_predictions = rebuild_predictions(seal, event)
        check(f"{event_dir.name}:predictions_reproduce_independently", rebuilt_predictions == predictions)
        check(
            f"{event_dir.name}:predictions_content_id",
            content_id("decision-recall-predictions", without(predictions, "predictions_id")) == predictions.get("predictions_id"),
            predictions.get("predictions_id"),
        )

        rebuilt_packet = rebuild_packet(seal, event)
        check(f"{event_dir.name}:blind_packet_reproduces_independently", rebuilt_packet == packet)
        check(
            f"{event_dir.name}:packet_content_id",
            content_id("decision-recall-adjudication-packet", without(packet, "adjudication_packet_id")) == packet.get("adjudication_packet_id"),
            packet.get("adjudication_packet_id"),
        )
        packet_text = json.dumps(packet, sort_keys=True).lower()
        check(f"{event_dir.name}:packet_hides_predictions", '"decision_recall"' not in packet_text and "predictions_id" not in packet_text)
        check(f"{event_dir.name}:packet_hides_manifest_contract", "manifest_id" not in packet_text and DECISION_MANIFEST_SCHEMA.lower() not in packet_text)

        for system in SYSTEMS:
            rebuilt_review = rebuild_review_packet(seal, event, predictions, system)
            stored_review = stored_review_packets[system]
            check(f"{event_dir.name}:review_packet:{system}:reproduces_independently", rebuilt_review == stored_review)
            check(
                f"{event_dir.name}:review_packet:{system}:content_id",
                content_id("decision-recall-review-packet", without(stored_review, "review_packet_id")) == stored_review.get("review_packet_id"),
                stored_review.get("review_packet_id"),
            )
            review_text = json.dumps(stored_review, sort_keys=True).lower()
            check(f"{event_dir.name}:review_packet:{system}:hides_gold", "gold_id" not in review_text and '"labels"' not in review_text)

        gold_errors = validate_gold(gold, rebuilt_packet, event, seal)
        check(f"{event_dir.name}:gold_valid_independent", not gold_errors, gold_errors)
        check(f"{event_dir.name}:fixture_gold_not_misrepresented", gold.get("method") == "CONFORMANCE_FIXTURE_NOT_EMPIRICAL_GOLD", gold.get("method"))
        check(f"{event_dir.name}:fixture_adjudicator_not_human", gold.get("adjudicator_id") == "fixture-not-human", gold.get("adjudicator_id"))

        outcome_by_system = {str(item.get("system")): item for item in review_outcomes}
        check(f"{event_dir.name}:two_baseline_review_outcomes", set(outcome_by_system) == {SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH}, sorted(outcome_by_system))
        for system in (SYSTEM_FULL_HISTORY, SYSTEM_FLAT_SEARCH):
            outcome_errors = validate_review_outcome(outcome_by_system.get(system, {}), seal, event, predictions)
            check(f"{event_dir.name}:review_outcome:{system}:valid_independent", not outcome_errors, outcome_errors)
            check(f"{event_dir.name}:review_outcome:{system}:method", outcome_by_system.get(system, {}).get("method") == "BLINDED_BASELINE_REVIEW", outcome_by_system.get(system, {}).get("method"))

        review_errors = validate_review_times(review_times, seal, event)
        check(f"{event_dir.name}:review_times_valid_independent", not review_errors, review_errors)
        review_sources = {str(item.get("timing_source", "")) for item in review_times.get("records", [])}
        check(f"{event_dir.name}:review_times_declared_synthetic", review_sources == {"SYNTHETIC_FIXTURE"}, sorted(review_sources))

        expected_packet_ids = {system: stored_review_packets[system]["review_packet_id"] for system in SYSTEMS}
        timing_packet_ids = {str(item.get("system")): str(item.get("review_packet_id")) for item in review_times.get("records", [])}
        check(f"{event_dir.name}:review_times_bind_exact_workloads", timing_packet_ids == expected_packet_ids, timing_packet_ids)

        rebuilt_score = rebuild_score(seal, event, predictions, gold, review_times, review_outcomes)
        check(f"{event_dir.name}:score_reproduces_independently", rebuilt_score == score)
        check(
            f"{event_dir.name}:score_content_id",
            content_id("decision-recall-score", without(score, "score_id")) == score.get("score_id"),
            score.get("score_id"),
        )
        check(f"{event_dir.name}:annual_roi_not_inferred", score.get("economics", {}).get("annual_roi_inferred") is False)
        check(f"{event_dir.name}:review_timing_not_empirical", score.get("economics", {}).get("review_timing_instrumented") is False)
        check(f"{event_dir.name}:review_packet_bindings_valid", score.get("economics", {}).get("review_packet_bindings_valid") is True)
        check(f"{event_dir.name}:review_outcome_timing_bindings_valid", score.get("economics", {}).get("review_outcome_timing_bindings_valid") is True)
        check(f"{event_dir.name}:baseline_review_outcomes_verified", score.get("baseline_review_outcomes_verified") is True)
        check(f"{event_dir.name}:controlled_selection_not_verified", score.get("controlled_selection_verified") is False)

        summary = report_events.get(str(event.get("event_id")))
        check(f"{event_dir.name}:report_summary_present", summary is not None, event.get("event_id"))
        if summary is not None:
            check(f"{event_dir.name}:report_basis", summary.get("basis_id") == event.get("basis_id"), summary.get("basis_id"))
            check(
                f"{event_dir.name}:report_review_load",
                summary.get("decision_recall_review_load") == score["metrics"][SYSTEM_DECISION_RECALL]["review_load"],
                summary.get("decision_recall_review_load"),
            )
            check(
                f"{event_dir.name}:report_missed_reopens",
                summary.get("decision_recall_missed_reopenings") == score["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"],
                summary.get("decision_recall_missed_reopenings"),
            )
            check(
                f"{event_dir.name}:report_full_history_reviewer_misses",
                summary.get("full_history_reviewer_missed_reopenings") == score["metrics"][SYSTEM_FULL_HISTORY]["missed_reopenings"],
                summary.get("full_history_reviewer_missed_reopenings"),
            )

        if event_dir.name == "event-01":
            full_history_error_control_seen = score["metrics"][SYSTEM_FULL_HISTORY]["missed_reopenings"] == 1 and score["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"] == 0
            check(f"{event_dir.name}:full_history_is_not_gold_oracle", full_history_error_control_seen, {
                "full_history": score["metrics"][SYSTEM_FULL_HISTORY]["missed_reopenings"],
                "decision_recall": score["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"],
            })

        basis_id = str(event.get("basis_id"))
        if basis_id == "hidden-5":
            omission_seen = True
            check(
                f"{event_dir.name}:omitted_dependency_punishes_decision_recall",
                score["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"] == 1,
                score["metrics"][SYSTEM_DECISION_RECALL],
            )
            check(
                f"{event_dir.name}:flat_search_catches_omitted_dependency",
                score["metrics"][SYSTEM_FLAT_SEARCH]["missed_reopenings"] == 0,
                score["metrics"][SYSTEM_FLAT_SEARCH],
            )
        else:
            check(
                f"{event_dir.name}:non_omission_no_dr_miss",
                score["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"] == 0,
                score["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"],
            )
        if basis_id == "dep-4":
            ambiguity_seen = True
            target = next(row for row in predictions["rows"] if row["decision_id"] == "decision-4")
            check(f"{event_dir.name}:ambiguous_dependency_escalates", target[SYSTEM_DECISION_RECALL]["disposition"] == "ESCALATE", target[SYSTEM_DECISION_RECALL])
            check(f"{event_dir.name}:no_ambiguous_overreach", score["metrics"][SYSTEM_DECISION_RECALL]["ambiguous_overreach"] == 0)
        if basis_id == "shared-context":
            negative_control_seen = True
            check(f"{event_dir.name}:negative_control_has_zero_dr_review", score["metrics"][SYSTEM_DECISION_RECALL]["review_load"] == 0)

    check("hostile_omission_control_present", omission_seen)
    check("full_history_reviewer_error_control_present", full_history_error_control_seen)
    check("ambiguity_control_present", ambiguity_seen)
    check("negative_control_present", negative_control_seen)

    valid = all(item["pass"] for item in checks)
    output = {
        "schema": "openline.decision-recall-prospective-conformance-verification.v2",
        "module_free": True,
        "check_count": len(checks),
        "failed_count": sum(1 for item in checks if not item["pass"]),
        "checks": checks,
        "disposition": "PASS" if valid else "FAIL",
        "valid": valid,
        "claim_boundary": VERIFY_CLAIM_BOUNDARY,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
