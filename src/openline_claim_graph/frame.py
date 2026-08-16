"""Receiver-owned framing-device ledger with deterministic admission.

This module deliberately separates three claims that are often collapsed:

* exact textual devices can be reproduced from exact source bytes;
* models may propose interpretations of those devices;
* a receiver policy decides which proposals, if any, are admitted.

The mechanical layer does not decide whether an article is fair, deceptive,
propaganda, or true.  The advisory layer cannot promote itself: model findings
need signed review by distinct receiver-pinned identities and model families.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .canonical import canonical_json, content_id, hash_object, sha256_hex
from .graph import validate_sources
from .receipts import public_key_hex


FRAME_FINDING_SCHEMA = "openline.frame-finding.v1"
FRAME_REVIEW_SCHEMA = "openline.frame-review.v1"
FRAME_ATTESTATION_SCHEMA = "openline.frame-attestation.v1"
FRAME_POLICY_SCHEMA = "openline.frame-policy.v1"
FRAME_REPORT_SCHEMA = "openline.frame-ledger-report.v1"

MECHANICAL_DEVICE_TYPES = (
    "EPISTEMIC_LEXEME",
    "CONTEXT_CUE",
    "ISSUE_FRAME_LEXEME",
    "LOCAL_ATTRIBUTION_PATTERN_ABSENCE",
    "DECLARED_TERM_SET_ABSENCE",
)
ADVISORY_DEVICE_TYPES = (
    "AGENCY_SUPPRESSION",
    "ASYMMETRIC_EVIDENCE_PRESENTATION",
    "CAUSAL_CONTEXT_IMPLICATION",
    "FACT_STATUS_OMISSION",
)
PROHIBITED_VERDICTS = (
    "BIAS_SCORE",
    "DECEPTION_INTENT",
    "FAIRNESS_VERDICT",
    "PROPAGANDA_VERDICT",
    "RATIONALIZATION_VERDICT",
    "TRUTH_VERDICT",
)
REVIEW_VERDICTS = ("CONFIRM", "CHALLENGE", "ABSTAIN")
HUMAN_MODES = ("OPTIONAL", "REQUIRED", "DISABLED")

FRAME_RULESET = {
    "schema": "openline.frame-mechanical-ruleset.v1",
    "ruleset_id": "openline.frame-mechanical-ruleset.v1",
    "span_unit": "utf8_byte_offset_half_open",
    "epistemic_lexemes": {
        "CONFLICT": ["contradict", "contradicted", "contradicting", "conflict", "conflicting", "inconsistent"],
        "FALSITY": ["false", "falsely", "inaccurate", "incorrect", "misleading"],
        "DECEPTION": ["deception", "lie", "lied", "lying"],
    },
    "context_cues": {
        "CAUSE": ["because", "because of", "due to"],
        "CONCESSION": ["despite", "although"],
        "CO_OCCURRENCE": ["amid", "as", "while"],
        "SEQUENCE": ["after", "before", "following"],
    },
    "issue_frame_lexemes": {
        "SECURITY_THREAT": ["danger", "security", "threat"],
        "SECRECY": ["covert", "secret", "secretly"],
    },
    "attribution_nouns": ["claim", "claims", "statement", "statements"],
    "attribution_grammar": ["possessive_before_noun", "by_or_from_after_noun"],
    "boundary": (
        "Rules report exact lexical or local grammatical patterns. A match is not a truth, intent, "
        "fairness, propaganda, or rationalization verdict. An absence is scoped only to the exact "
        "surface and declared term set recorded in the finding."
    ),
}
FRAME_RULESET_HASH = hash_object(FRAME_RULESET)


class FrameValidationError(ValueError):
    """Raised when a frame-ledger input cannot be admitted fail-closed."""


def _without_id(record: Mapping[str, Any], id_field: str) -> dict[str, Any]:
    body = dict(record)
    body.pop(id_field, None)
    return body


def _parse_timestamp(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")


def _byte_span(text: str, start: int, end: int) -> tuple[int, int]:
    return len(text[:start].encode("utf-8")), len(text[:end].encode("utf-8"))


def _anchor(source: Mapping[str, Any], start: int, end: int) -> dict[str, Any]:
    encoded = str(source["content"]).encode("utf-8")
    return {
        "source_id": str(source["source_id"]),
        "span": {"start": start, "end": end},
        "quote_sha256": sha256_hex(encoded[start:end]),
    }


def _word_matches(text: str, term: str) -> Iterable[re.Match[str]]:
    pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)
    return pattern.finditer(text)


def create_frame_finding(
    source: Mapping[str, Any],
    *,
    device_type: str,
    layer: str,
    observation: str,
    asserted_by: str,
    start: int,
    end: int,
    rule_id: str,
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a content-addressed finding anchored to exact source bytes."""

    encoded = str(source["content"]).encode("utf-8")
    if start < 0 or end <= start or end > len(encoded):
        raise ValueError("finding span is outside the source")
    body = {
        "schema": FRAME_FINDING_SCHEMA,
        "source_id": str(source["source_id"]),
        "device_type": device_type.upper(),
        "layer": layer.upper(),
        "observation": observation,
        "rule_id": rule_id,
        "ruleset_hash": FRAME_RULESET_HASH if layer.upper() == "MECHANICAL" else None,
        "parameters": dict(parameters or {}),
        "anchors": [_anchor(source, start, end)],
        "asserted_by": asserted_by,
    }
    return {"finding_id": content_id("frame-finding", body), **body}


def create_advisory_finding(
    source: Mapping[str, Any],
    *,
    quote: str,
    device_type: str,
    observation: str,
    asserted_by: str,
    occurrence: int = 1,
) -> dict[str, Any]:
    """Create an exact-quote-anchored model proposal that remains semantic."""

    if device_type.upper() not in ADVISORY_DEVICE_TYPES:
        raise ValueError("advisory finding must use an allowed advisory device type")
    if occurrence < 1:
        raise ValueError("occurrence must be at least 1")
    text = str(source["content"])
    matches = list(_word_matches(text, quote)) if " " not in quote else []
    if matches:
        if occurrence > len(matches):
            raise ValueError("quote occurrence not found")
        char_start, char_end = matches[occurrence - 1].span()
    else:
        cursor = 0
        char_start = -1
        for _ in range(occurrence):
            char_start = text.find(quote, cursor)
            if char_start < 0:
                raise ValueError("quote not found in source")
            cursor = char_start + len(quote)
        char_end = char_start + len(quote)
    start, end = _byte_span(text, char_start, char_end)
    return create_frame_finding(
        source,
        device_type=device_type,
        layer="INFERRED",
        observation=observation,
        asserted_by=asserted_by,
        start=start,
        end=end,
        rule_id="MODEL_PROPOSAL.v1",
    )


def _mechanical_finding(
    source: Mapping[str, Any],
    *,
    asserted_by: str,
    device_type: str,
    observation: str,
    rule_id: str,
    char_start: int,
    char_end: int,
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    start, end = _byte_span(str(source["content"]), char_start, char_end)
    return create_frame_finding(
        source,
        device_type=device_type,
        layer="MECHANICAL",
        observation=observation,
        asserted_by=asserted_by,
        start=start,
        end=end,
        rule_id=rule_id,
        parameters=parameters,
    )


def detect_mechanical_frame_devices(
    source: Mapping[str, Any],
    *,
    asserted_by: str = "openline:frame-ruleset-v1",
    absence_sets: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Reproduce narrowly defined textual devices without model judgment."""

    text = str(source["content"])
    findings: list[dict[str, Any]] = []

    for category, terms in FRAME_RULESET["epistemic_lexemes"].items():
        for term in terms:
            for match in _word_matches(text, term):
                findings.append(
                    _mechanical_finding(
                        source,
                        asserted_by=asserted_by,
                        device_type="EPISTEMIC_LEXEME",
                        observation=f"{category} lexeme present in the audited surface.",
                        rule_id="LEXICAL_EPISTEMIC_MARKER.v1",
                        char_start=match.start(),
                        char_end=match.end(),
                        parameters={"category": category, "term": term},
                    )
                )

    for category, terms in FRAME_RULESET["context_cues"].items():
        for term in terms:
            for match in _word_matches(text, term):
                findings.append(
                    _mechanical_finding(
                        source,
                        asserted_by=asserted_by,
                        device_type="CONTEXT_CUE",
                        observation=(
                            f"{category} context cue present. The token does not by itself establish causation."
                        ),
                        rule_id="LEXICAL_CONTEXT_CUE.v1",
                        char_start=match.start(),
                        char_end=match.end(),
                        parameters={"category": category, "term": term},
                    )
                )

    for category, terms in FRAME_RULESET["issue_frame_lexemes"].items():
        for term in terms:
            for match in _word_matches(text, term):
                findings.append(
                    _mechanical_finding(
                        source,
                        asserted_by=asserted_by,
                        device_type="ISSUE_FRAME_LEXEME",
                        observation=(
                            f"{category} lexeme present. One lexeme is not a complete frame classification."
                        ),
                        rule_id="DECLARED_ISSUE_FRAME_LEXICON.v1",
                        char_start=match.start(),
                        char_end=match.end(),
                        parameters={"category": category, "term": term},
                    )
                )

    noun_pattern = re.compile(
        r"(?<!\w)(?:public\s+)?(?:" + "|".join(FRAME_RULESET["attribution_nouns"]) + r")(?!\w)",
        re.IGNORECASE,
    )
    for match in noun_pattern.finditer(text):
        left_boundary = max(text.rfind(",", 0, match.start()), text.rfind(";", 0, match.start())) + 1
        right_candidates = [position for position in (text.find(",", match.end()), text.find(";", match.end())) if position >= 0]
        right_boundary = min(right_candidates) if right_candidates else len(text)
        raw_clause = text[left_boundary:right_boundary]
        leading = len(raw_clause) - len(raw_clause.lstrip())
        trailing = len(raw_clause.rstrip())
        clause_start = left_boundary + leading
        clause_end = left_boundary + trailing
        clause = text[clause_start:clause_end]
        noun = match.group(0)
        escaped = re.escape(noun)
        possessive = re.search(r"\b[A-Z][\w'’.-]*(?:\s+[A-Z][\w'’.-]*){0,3}['’]s\s+" + escaped, clause)
        after = re.search(escaped + r"\s+(?:by|from)\s+[A-Z][\w'’.-]*", clause, re.IGNORECASE)
        if not possessive and not after:
            findings.append(
                _mechanical_finding(
                    source,
                    asserted_by=asserted_by,
                    device_type="LOCAL_ATTRIBUTION_PATTERN_ABSENCE",
                    observation=(
                        "No explicit speaker matched the declared possessive/by/from grammar inside "
                        "the local comma-delimited clause. This says nothing about the full article."
                    ),
                    rule_id="LOCAL_ATTRIBUTION_GRAMMAR.v1",
                    char_start=clause_start,
                    char_end=clause_end,
                    parameters={"attribution_noun": noun.casefold()},
                )
            )

    for raw_set in absence_sets:
        set_id = str(raw_set.get("set_id", ""))
        terms = sorted({str(term) for term in raw_set.get("terms", [])}, key=str.casefold)
        if not set_id or not terms or any(not term or len(term) > 80 for term in terms):
            raise ValueError("absence sets require a set_id and non-empty terms of at most 80 characters")
        present = [term for term in terms if any(True for _ in _word_matches(text, term))]
        if not present:
            findings.append(
                _mechanical_finding(
                    source,
                    asserted_by=asserted_by,
                    device_type="DECLARED_TERM_SET_ABSENCE",
                    observation=(
                        "None of the receiver-declared terms appears in the exact audited surface. "
                        "Absence does not establish motive, falsity, or omission from a larger document."
                    ),
                    rule_id="DECLARED_TERM_SET_ABSENCE.v1",
                    char_start=0,
                    char_end=len(text),
                    parameters={"set_id": set_id, "terms": terms},
                )
            )

    return sorted(findings, key=lambda item: str(item["finding_id"]))


def _validate_anchor(anchor: Mapping[str, Any], source: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        if anchor.get("source_id") != source.get("source_id"):
            errors.append("frame_anchor_source_mismatch")
        encoded = str(source["content"]).encode("utf-8")
        span = dict(anchor["span"])
        start, end = int(span["start"]), int(span["end"])
        if start < 0 or end <= start or end > len(encoded):
            errors.append("frame_anchor_span_invalid")
        elif sha256_hex(encoded[start:end]) != anchor.get("quote_sha256"):
            errors.append("frame_anchor_quote_hash_mismatch")
    except (KeyError, TypeError, ValueError, UnicodeError):
        errors.append("frame_anchor_invalid")
    return errors


def validate_frame_finding(finding: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        if finding.get("schema") != FRAME_FINDING_SCHEMA:
            errors.append("frame_finding_schema_invalid")
        expected_id = content_id("frame-finding", _without_id(finding, "finding_id"))
        if finding.get("finding_id") != expected_id:
            errors.append("frame_finding_id_mismatch")
        if finding.get("source_id") != source.get("source_id"):
            errors.append("frame_finding_source_mismatch")
        if not str(finding.get("asserted_by", "")):
            errors.append("frame_finding_actor_missing")
        if not str(finding.get("observation", "")):
            errors.append("frame_finding_observation_missing")
        layer = str(finding.get("layer", ""))
        device = str(finding.get("device_type", ""))
        if device in PROHIBITED_VERDICTS:
            errors.append(f"frame_finding_prohibited_verdict:{device}")
        if layer == "MECHANICAL":
            if device not in MECHANICAL_DEVICE_TYPES:
                errors.append("frame_finding_mechanical_device_invalid")
            if finding.get("ruleset_hash") != FRAME_RULESET_HASH:
                errors.append("frame_finding_ruleset_mismatch")
        elif layer == "INFERRED":
            if device not in ADVISORY_DEVICE_TYPES:
                errors.append("frame_finding_advisory_device_invalid")
            if finding.get("rule_id") != "MODEL_PROPOSAL.v1":
                errors.append("frame_finding_advisory_rule_invalid")
            if finding.get("ruleset_hash") is not None:
                errors.append("frame_finding_advisory_ruleset_must_be_null")
            warnings.append("frame_finding_semantics_unverified")
        else:
            errors.append("frame_finding_layer_invalid")
        anchors = finding.get("anchors")
        if not isinstance(anchors, list) or len(anchors) != 1:
            errors.append("frame_finding_requires_one_anchor")
        else:
            errors.extend(_validate_anchor(anchors[0], source))

        if layer == "MECHANICAL" and not errors:
            absence_sets: list[Mapping[str, Any]] = []
            if device == "DECLARED_TERM_SET_ABSENCE":
                parameters = dict(finding.get("parameters", {}))
                absence_sets = [{"set_id": parameters.get("set_id"), "terms": parameters.get("terms", [])}]
            reproduced = detect_mechanical_frame_devices(
                source,
                asserted_by=str(finding["asserted_by"]),
                absence_sets=absence_sets,
            )
            if dict(finding) not in reproduced:
                errors.append("frame_finding_mechanical_reproduction_failed")
    except (KeyError, TypeError, ValueError):
        errors.append("frame_finding_invalid")
    return {"valid": not errors, "errors": sorted(set(errors)), "warnings": sorted(set(warnings))}


def sign_frame_record(
    record: Mapping[str, Any],
    *,
    record_type: str,
    record_id: str,
    signer_id: str,
    private_key: Ed25519PrivateKey,
    issued_at: str,
) -> dict[str, Any]:
    """Sign one finding or review under a pinned execution identity."""

    _parse_timestamp(issued_at)
    if record.get(record_type + "_id") != record_id:
        raise ValueError("record id does not match record")
    body = {
        "schema": FRAME_ATTESTATION_SCHEMA,
        "record_type": record_type,
        "record_id": record_id,
        "record_hash": hash_object(record),
        "signer_id": signer_id,
        "issued_at": issued_at,
        "public_key": public_key_hex(private_key),
    }
    payload = canonical_json(body)
    attestation = {
        **body,
        "payload_hash": sha256_hex(payload),
        "proof": {"type": "Ed25519", "signature": private_key.sign(payload).hex()},
    }
    return {"attestation_id": content_id("frame-attestation", attestation), **attestation}


def verify_frame_attestation(
    attestation: Mapping[str, Any],
    record: Mapping[str, Any],
    *,
    expected_public_key: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        expected_id = content_id("frame-attestation", _without_id(attestation, "attestation_id"))
        if attestation.get("attestation_id") != expected_id:
            errors.append("frame_attestation_id_mismatch")
        if attestation.get("schema") != FRAME_ATTESTATION_SCHEMA:
            errors.append("frame_attestation_schema_invalid")
        record_type = str(attestation["record_type"])
        record_id = str(attestation["record_id"])
        if record.get(record_type + "_id") != record_id:
            errors.append("frame_attestation_record_id_mismatch")
        if attestation.get("record_hash") != hash_object(record):
            errors.append("frame_attestation_record_hash_mismatch")
        _parse_timestamp(str(attestation["issued_at"]))
        if expected_public_key is not None and attestation.get("public_key") != expected_public_key:
            errors.append("frame_attestation_public_key_mismatch")
        body = {
            key: attestation[key]
            for key in (
                "schema",
                "record_type",
                "record_id",
                "record_hash",
                "signer_id",
                "issued_at",
                "public_key",
            )
        }
        payload = canonical_json(body)
        if attestation.get("payload_hash") != sha256_hex(payload):
            errors.append("frame_attestation_payload_hash_mismatch")
        if dict(attestation.get("proof", {})).get("type") != "Ed25519":
            errors.append("frame_attestation_proof_type_invalid")
        public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(str(attestation["public_key"])))
        public.verify(bytes.fromhex(str(dict(attestation["proof"])["signature"])), payload)
    except InvalidSignature:
        errors.append("frame_attestation_signature_invalid")
    except (KeyError, TypeError, ValueError):
        errors.append("frame_attestation_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def create_frame_review(
    *,
    finding_id: str,
    reviewer_id: str,
    verdict: str,
    rationale: str,
    evidence_anchors: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    verdict = verdict.upper()
    if verdict not in REVIEW_VERDICTS:
        raise ValueError("unsupported frame-review verdict")
    body = {
        "schema": FRAME_REVIEW_SCHEMA,
        "finding_id": finding_id,
        "reviewer_id": reviewer_id,
        "verdict": verdict,
        "rationale": rationale,
        "evidence_anchors": sorted(
            (dict(item) for item in evidence_anchors),
            key=lambda item: (
                str(item.get("source_id", "")),
                int(dict(item.get("span", {})).get("start", -1)),
                int(dict(item.get("span", {})).get("end", -1)),
            ),
        ),
    }
    return {"review_id": content_id("frame-review", body), **body}


def create_frame_policy(
    *,
    mechanical_auto_admit: bool = True,
    advisory_min_confirmations: int = 2,
    advisory_min_distinct_families: int = 2,
    challenge_blocks: bool = True,
    human_mode: str = "OPTIONAL",
    proposers: Sequence[Mapping[str, Any]] = (),
    reviewers: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Create the explicit receiver policy controlling autonomous admission."""

    def normalize(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            (
                {
                    "actor_id": str(item["actor_id"]),
                    "model_id": str(item["model_id"]),
                    "family": str(item["family"]),
                    "kind": str(item.get("kind", "AI")).upper(),
                    "public_key": str(item["public_key"]),
                }
                for item in entries
            ),
            key=lambda item: item["actor_id"],
        )

    body = {
        "schema": FRAME_POLICY_SCHEMA,
        "ruleset_hash": FRAME_RULESET_HASH,
        "mechanical_auto_admit": bool(mechanical_auto_admit),
        "advisory_min_confirmations": int(advisory_min_confirmations),
        "advisory_min_distinct_families": int(advisory_min_distinct_families),
        "challenge_blocks": bool(challenge_blocks),
        "human_mode": human_mode.upper(),
        "proposers": normalize(proposers),
        "reviewers": normalize(reviewers),
    }
    return {"policy_id": content_id("frame-policy", body), **body}


def validate_frame_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        if policy.get("schema") != FRAME_POLICY_SCHEMA:
            errors.append("frame_policy_schema_invalid")
        if policy.get("policy_id") != content_id("frame-policy", _without_id(policy, "policy_id")):
            errors.append("frame_policy_id_mismatch")
        if policy.get("ruleset_hash") != FRAME_RULESET_HASH:
            errors.append("frame_policy_ruleset_mismatch")
        if not isinstance(policy.get("mechanical_auto_admit"), bool):
            errors.append("frame_policy_mechanical_auto_admit_invalid")
        if not isinstance(policy.get("challenge_blocks"), bool):
            errors.append("frame_policy_challenge_blocks_invalid")
        if policy.get("human_mode") not in HUMAN_MODES:
            errors.append("frame_policy_human_mode_invalid")
        raw_minimum = policy.get("advisory_min_confirmations", 0)
        raw_families = policy.get("advisory_min_distinct_families", 0)
        if isinstance(raw_minimum, bool) or not isinstance(raw_minimum, int):
            errors.append("frame_policy_confirmation_minimum_invalid")
        if isinstance(raw_families, bool) or not isinstance(raw_families, int):
            errors.append("frame_policy_family_minimum_invalid")
        minimum = int(raw_minimum)
        families = int(raw_families)
        if minimum < 1 or families < 1 or families > minimum:
            errors.append("frame_policy_quorum_invalid")
        all_ids: list[str] = []
        for role in ("proposers", "reviewers"):
            entries = policy.get(role)
            if not isinstance(entries, list):
                errors.append(f"frame_policy_{role}_invalid")
                continue
            actor_ids = [str(item.get("actor_id", "")) for item in entries]
            if actor_ids != sorted(actor_ids) or len(actor_ids) != len(set(actor_ids)):
                errors.append(f"frame_policy_{role}_not_canonical")
            for item in entries:
                actor_id = str(item.get("actor_id", ""))
                all_ids.append(actor_id)
                if not actor_id or not str(item.get("model_id", "")) or not str(item.get("family", "")):
                    errors.append(f"frame_policy_actor_invalid:{actor_id}")
                if item.get("kind") not in {"AI", "HUMAN"}:
                    errors.append(f"frame_policy_actor_kind_invalid:{actor_id}")
                try:
                    key = bytes.fromhex(str(item.get("public_key", "")))
                    if len(key) != 32:
                        raise ValueError
                except ValueError:
                    errors.append(f"frame_policy_actor_key_invalid:{actor_id}")
        if set(str(item.get("actor_id")) for item in policy.get("proposers", [])) & set(
            str(item.get("actor_id")) for item in policy.get("reviewers", [])
        ):
            warnings.append("frame_policy_actor_has_multiple_roles")
        warnings.append("model_family_independence_is_receiver_declared_not_mechanically_proven")
    except (TypeError, ValueError):
        errors.append("frame_policy_invalid")
    return {"valid": not errors, "errors": sorted(set(errors)), "warnings": sorted(set(warnings))}


def _validate_review(review: Mapping[str, Any], finding: Mapping[str, Any], source: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        if review.get("schema") != FRAME_REVIEW_SCHEMA:
            errors.append("frame_review_schema_invalid")
        if review.get("review_id") != content_id("frame-review", _without_id(review, "review_id")):
            errors.append("frame_review_id_mismatch")
        if review.get("finding_id") != finding.get("finding_id"):
            errors.append("frame_review_finding_mismatch")
        if review.get("verdict") not in REVIEW_VERDICTS:
            errors.append("frame_review_verdict_invalid")
        if not str(review.get("reviewer_id", "")) or not str(review.get("rationale", "")):
            errors.append("frame_review_fields_missing")
        for anchor in review.get("evidence_anchors", []):
            errors.extend(_validate_anchor(anchor, source))
    except (TypeError, ValueError):
        errors.append("frame_review_invalid")
    return errors


def evaluate_frame_ledger(
    source: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    *,
    finding_attestations: Sequence[Mapping[str, Any]] = (),
    reviews: Sequence[Mapping[str, Any]] = (),
    review_attestations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Apply receiver policy without allowing a model to approve itself."""

    source_errors = validate_sources({str(source.get("source_id", "")): source})
    policy_check = validate_frame_policy(policy)
    if source_errors or not policy_check["valid"]:
        raise FrameValidationError(", ".join(source_errors + policy_check["errors"]))

    finding_map: dict[str, Mapping[str, Any]] = {}
    for finding in findings:
        check = validate_frame_finding(finding, source)
        if not check["valid"]:
            raise FrameValidationError(", ".join(check["errors"]))
        finding_id = str(finding["finding_id"])
        if finding_id in finding_map:
            raise FrameValidationError(f"duplicate finding: {finding_id}")
        finding_map[finding_id] = finding

    proposer_registry = {str(item["actor_id"]): item for item in policy["proposers"]}
    reviewer_registry = {str(item["actor_id"]): item for item in policy["reviewers"]}
    finding_attestation_map: dict[str, Mapping[str, Any]] = {}
    for attestation in finding_attestations:
        record_id = str(attestation.get("record_id", ""))
        if record_id in finding_attestation_map:
            raise FrameValidationError(f"duplicate finding attestation: {record_id}")
        finding_attestation_map[record_id] = attestation
    orphan_finding_attestations = set(finding_attestation_map) - set(finding_map)
    if orphan_finding_attestations:
        raise FrameValidationError(
            f"orphan finding attestations: {sorted(orphan_finding_attestations)}"
        )

    review_attestation_map: dict[str, Mapping[str, Any]] = {}
    for attestation in review_attestations:
        record_id = str(attestation.get("record_id", ""))
        if record_id in review_attestation_map:
            raise FrameValidationError(f"duplicate review attestation: {record_id}")
        review_attestation_map[record_id] = attestation

    reviews_by_finding: dict[str, list[Mapping[str, Any]]] = {key: [] for key in finding_map}
    seen_reviewers: set[tuple[str, str]] = set()
    for review in reviews:
        finding_id = str(review.get("finding_id", ""))
        if finding_id not in finding_map:
            raise FrameValidationError(f"review references unknown finding: {finding_id}")
        finding = finding_map[finding_id]
        review_errors = _validate_review(review, finding, source)
        reviewer_id = str(review.get("reviewer_id", ""))
        registry = reviewer_registry.get(reviewer_id)
        if registry is None:
            review_errors.append(f"frame_review_reviewer_not_pinned:{reviewer_id}")
        if reviewer_id == finding.get("asserted_by"):
            review_errors.append("frame_review_self_approval_forbidden")
        key = (finding_id, reviewer_id)
        if key in seen_reviewers:
            review_errors.append("frame_review_duplicate_reviewer")
        seen_reviewers.add(key)
        attestation = review_attestation_map.get(str(review.get("review_id", "")))
        if attestation is None:
            review_errors.append("frame_review_attestation_missing")
        elif registry is not None:
            check = verify_frame_attestation(
                attestation,
                review,
                expected_public_key=str(registry["public_key"]),
            )
            review_errors.extend(check["errors"])
            if attestation.get("signer_id") != reviewer_id:
                review_errors.append("frame_review_signer_mismatch")
        if review_errors:
            raise FrameValidationError(", ".join(sorted(set(review_errors))))
        reviews_by_finding[finding_id].append(review)
    known_review_ids = {str(review["review_id"]) for review in reviews}
    orphan_review_attestations = set(review_attestation_map) - known_review_ids
    if orphan_review_attestations:
        raise FrameValidationError(
            f"orphan review attestations: {sorted(orphan_review_attestations)}"
        )

    classifications = {"established": [], "advisory": [], "blocked": [], "unadmitted": []}
    for finding_id, finding in sorted(finding_map.items()):
        layer = str(finding["layer"])
        if layer == "MECHANICAL":
            if policy["mechanical_auto_admit"]:
                classifications["established"].append(
                    {
                        "finding_id": finding_id,
                        "disposition": "ESTABLISHED_MECHANICAL",
                        "reason": "The finding reproduced from exact source bytes under the pinned ruleset.",
                    }
                )
            else:
                classifications["unadmitted"].append(
                    {
                        "finding_id": finding_id,
                        "disposition": "UNADMITTED",
                        "reason": "Receiver policy disables automatic admission of mechanical findings.",
                    }
                )
            continue

        proposer_id = str(finding["asserted_by"])
        proposer = proposer_registry.get(proposer_id)
        proposal_errors: list[str] = []
        if proposer is None:
            proposal_errors.append("frame_finding_proposer_not_pinned")
        attestation = finding_attestation_map.get(finding_id)
        if attestation is None:
            proposal_errors.append("frame_finding_attestation_missing")
        elif proposer is not None:
            check = verify_frame_attestation(
                attestation,
                finding,
                expected_public_key=str(proposer["public_key"]),
            )
            proposal_errors.extend(check["errors"])
            if attestation.get("signer_id") != proposer_id:
                proposal_errors.append("frame_finding_signer_mismatch")
        if proposal_errors:
            raise FrameValidationError(", ".join(sorted(set(proposal_errors))))

        finding_reviews = reviews_by_finding[finding_id]
        confirmations = [review for review in finding_reviews if review["verdict"] == "CONFIRM"]
        challenges = [review for review in finding_reviews if review["verdict"] == "CHALLENGE"]
        confirming_families = {
            str(reviewer_registry[str(review["reviewer_id"])]["family"])
            for review in confirmations
        }
        human_confirmed = any(
            reviewer_registry[str(review["reviewer_id"])]["kind"] == "HUMAN"
            for review in confirmations
        )
        quorum = (
            len(confirmations) >= int(policy["advisory_min_confirmations"])
            and len(confirming_families) >= int(policy["advisory_min_distinct_families"])
        )
        if policy["human_mode"] == "REQUIRED" and not human_confirmed:
            quorum = False
        if challenges and policy["challenge_blocks"]:
            classifications["blocked"].append(
                {
                    "finding_id": finding_id,
                    "disposition": "BLOCKED_BY_CHALLENGE",
                    "reason": "At least one pinned reviewer challenged the proposal.",
                    "confirmations": len(confirmations),
                    "challenges": len(challenges),
                    "distinct_confirming_families": len(confirming_families),
                }
            )
        elif quorum:
            classifications["advisory"].append(
                {
                    "finding_id": finding_id,
                    "disposition": "ADVISORY_ADMITTED",
                    "reason": "The receiver's signed heterogeneous-review quorum was satisfied.",
                    "confirmations": len(confirmations),
                    "challenges": len(challenges),
                    "distinct_confirming_families": len(confirming_families),
                }
            )
        else:
            classifications["unadmitted"].append(
                {
                    "finding_id": finding_id,
                    "disposition": "UNADMITTED",
                    "reason": "The receiver's signed review quorum was not satisfied.",
                    "confirmations": len(confirmations),
                    "challenges": len(challenges),
                    "distinct_confirming_families": len(confirming_families),
                }
            )

    body = {
        "schema": FRAME_REPORT_SCHEMA,
        "source_id": str(source["source_id"]),
        "ruleset_hash": FRAME_RULESET_HASH,
        "policy_id": str(policy["policy_id"]),
        "finding_ids": sorted(finding_map),
        "classifications": classifications,
        "summary": {name: len(items) for name, items in classifications.items()},
        "human_mode": str(policy["human_mode"]),
        "claim_boundary": (
            "Mechanical findings reproduce declared textual patterns. Advisory findings record a "
            "receiver-policy admission by pinned reviewers. Neither layer establishes truth, intent, "
            "fairness, propaganda, rationalization, completeness, or causal effect on readers."
        ),
    }
    return {"report_id": content_id("frame-ledger-report", body), **body}


def verify_frame_report(
    report: Mapping[str, Any],
    source: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    *,
    finding_attestations: Sequence[Mapping[str, Any]] = (),
    reviews: Sequence[Mapping[str, Any]] = (),
    review_attestations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        expected = evaluate_frame_ledger(
            source,
            findings,
            policy,
            finding_attestations=finding_attestations,
            reviews=reviews,
            review_attestations=review_attestations,
        )
        if dict(report) != expected:
            errors.append("frame_report_reproduction_mismatch")
        if report.get("schema") != FRAME_REPORT_SCHEMA:
            errors.append("frame_report_schema_invalid")
        if report.get("report_id") != content_id("frame-ledger-report", _without_id(report, "report_id")):
            errors.append("frame_report_id_mismatch")
    except FrameValidationError as exc:
        errors.append(f"frame_report_input_invalid:{exc}")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "warnings": [
            "semantic_device_interpretation_not_mechanically_verified",
            "reviewer_family_independence_is_receiver_declared",
        ],
    }
