"""Independent verifier for the checked-in one-headline Frame Ledger specimen.

This script intentionally does not import ``openline_claim_graph.frame`` or its
renderer.  It rechecks content identities, byte anchors, the seven expected
mechanical observations, policy/report bindings, and rendered-output hash with
stdlib-only code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


HEADLINE = (
    "Contradicting public statements, Trump took secret flight from Turkey amid Iranian threat"
)
EXPECTED_TYPES = {
    "CONTEXT_CUE": 1,
    "DECLARED_TERM_SET_ABSENCE": 2,
    "EPISTEMIC_LEXEME": 1,
    "ISSUE_FRAME_LEXEME": 2,
    "LOCAL_ATTRIBUTION_PATTERN_ABSENCE": 1,
}


def canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        raise ValueError("floats forbidden")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", key): canonical_value(item) for key, item in value.items()}
    raise ValueError("unsupported canonical value")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_object(value: Any) -> str:
    return digest(
        json.dumps(
            canonical_value(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )


def content_id(namespace: str, value: Any) -> str:
    return f"{namespace}:sha256:{hash_object(value)}"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def body(record: dict, field: str) -> dict:
    result = dict(record)
    result.pop(field)
    return result


def run(artifact: Path) -> dict[str, Any]:
    source = read(artifact / "source.json")
    findings = read(artifact / "findings.json")["findings"]
    policy = read(artifact / "policy.json")
    ruleset = read(artifact / "ruleset.json")
    report = read(artifact / "report.json")
    verification = read(artifact / "verification.json")
    specimen = read(artifact / "REPORT.json")
    source_bytes = source["content"].encode("utf-8")
    ruleset_hash = hash_object(ruleset)

    checks: dict[str, bool] = {}
    checks["headline_exact"] = source["content"] == HEADLINE
    checks["source_content_address"] = source["source_id"] == f"source:sha256:{digest(source_bytes)}"
    checks["source_length"] = source["byte_length"] == len(source_bytes)
    checks["ruleset_hash_bound"] = (
        policy["ruleset_hash"] == ruleset_hash
        and report["ruleset_hash"] == ruleset_hash
        and all(item["ruleset_hash"] == ruleset_hash for item in findings)
    )
    checks["policy_content_address"] = policy["policy_id"] == content_id("frame-policy", body(policy, "policy_id"))
    checks["report_content_address"] = report["report_id"] == content_id(
        "frame-ledger-report", body(report, "report_id")
    )
    checks["finding_content_addresses"] = all(
        item["finding_id"] == content_id("frame-finding", body(item, "finding_id")) for item in findings
    )
    checks["anchors_exact"] = all(
        item["anchors"][0]["source_id"] == source["source_id"]
        and 0 <= int(item["anchors"][0]["span"]["start"])
        < int(item["anchors"][0]["span"]["end"])
        <= len(source_bytes)
        and item["anchors"][0]["quote_sha256"]
        == digest(
            source_bytes[
                int(item["anchors"][0]["span"]["start"]):int(item["anchors"][0]["span"]["end"])
            ]
        )
        for item in findings
    )

    counts: dict[str, int] = {}
    for item in findings:
        counts[item["device_type"]] = counts.get(item["device_type"], 0) + 1
    checks["device_counts"] = counts == EXPECTED_TYPES
    checks["conflict_lexeme"] = any(
        item["device_type"] == "EPISTEMIC_LEXEME"
        and item["parameters"] == {"category": "CONFLICT", "term": "contradicting"}
        for item in findings
    )
    checks["co_occurrence_cue"] = any(
        item["device_type"] == "CONTEXT_CUE"
        and item["parameters"] == {"category": "CO_OCCURRENCE", "term": "amid"}
        for item in findings
    )
    issue_pairs = {
        (item["parameters"].get("category"), item["parameters"].get("term"))
        for item in findings
        if item["device_type"] == "ISSUE_FRAME_LEXEME"
    }
    checks["issue_lexemes"] = issue_pairs == {("SECRECY", "secret"), ("SECURITY_THREAT", "threat")}

    clause = HEADLINE.split(",", 1)[0]
    attribution_pattern = re.compile(
        r"\b[A-Z][\w'’.-]*(?:\s+[A-Z][\w'’.-]*){0,3}['’]s\s+(?:public\s+)?statements?"
        r"|(?:public\s+)?statements?\s+(?:by|from)\s+[A-Z][\w'’.-]*",
        re.IGNORECASE,
    )
    checks["local_attribution_pattern_absent"] = (
        "public statements" in clause.lower() and attribution_pattern.search(clause) is None
    )

    absence_findings = [item for item in findings if item["device_type"] == "DECLARED_TERM_SET_ABSENCE"]
    checks["declared_absences_reproduced"] = len(absence_findings) == 2 and all(
        all(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", HEADLINE, re.IGNORECASE) is None for term in item["parameters"]["terms"])
        for item in absence_findings
    )
    checks["no_prohibited_verdict"] = not {
        "BIAS_SCORE",
        "DECEPTION_INTENT",
        "FAIRNESS_VERDICT",
        "PROPAGANDA_VERDICT",
        "RATIONALIZATION_VERDICT",
        "TRUTH_VERDICT",
    } & {item["device_type"] for item in findings}
    checks["receiver_policy_autonomy"] = (
        policy["mechanical_auto_admit"] is True
        and policy["advisory_min_confirmations"] == 2
        and policy["advisory_min_distinct_families"] == 2
        and policy["challenge_blocks"] is True
        and policy["human_mode"] == "OPTIONAL"
    )
    established_ids = sorted(item["finding_id"] for item in findings)
    checks["report_exact_set"] = (
        report["finding_ids"] == established_ids
        and sorted(item["finding_id"] for item in report["classifications"]["established"])
        == established_ids
        and report["summary"] == {"advisory": 0, "blocked": 0, "established": 7, "unadmitted": 0}
    )
    checks["checked_in_verification_passes"] = verification["valid"] is True and not verification["errors"]
    review_bytes = (artifact / "review.html").read_bytes()
    checks["review_hash"] = digest(review_bytes) == specimen["review_sha256"]
    checks["no_model_result_claimed"] = (
        specimen["frontier_or_open_model_calls_run"] == 0
        and specimen["incremental_api_spend_usd"] == 0
    )

    failures = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema": "openline.frame-ledger-independent-verification.v1",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "check_count": len(checks),
        "failures": failures,
        "claim_boundary": (
            "This independently reproduces the checked-in one-headline mechanical specimen. It does "
            "not validate the general ruleset, model performance, article fairness, truth, intent, "
            "rationalization, propaganda, or effects on readers."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.artifact)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
