from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _time(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _sha256(value: Any) -> bool:
    text = str(value or "").lower().strip()
    return len(text) == 64 and all(c in "0123456789abcdef" for c in text)


def evaluate_verification_contract(
    *,
    contract: Mapping[str, Any],
    accepted_at: str,
    evaluation_at: str,
    verification_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    evaluation = _time(evaluation_at)
    accepted = _time(accepted_at)
    freshness = int(contract["freshness_seconds"])

    if verification_result is None:
        age = int((evaluation - accepted).total_seconds())
        if age <= freshness:
            return {
                "gate_disposition": "SURVIVE",
                "event": None,
                "reason": "verification budget remains open; no polling result is required yet",
            }
        return {
            "gate_disposition": "ESCALATE",
            "event": None,
            "reason": "verification freshness budget expired without admissible evidence",
        }

    result = dict(verification_result)
    checks = [
        (result.get("contract_id") == contract.get("contract_id"), "verification contract binding mismatch"),
        (result.get("subject_id") == contract.get("subject_id"), "verification subject binding mismatch"),
        (result.get("verifier_id") == contract.get("recognized_verifier_id"), "verifier is not receiver-recognized"),
        (bool(result.get("receiver_admitted")) is True, "verification was not admitted by the receiver"),
        (_sha256(result.get("evidence_sha256")), "verification evidence hash is invalid"),
    ]
    for passed, reason in checks:
        if not passed:
            return {"gate_disposition": "ESCALATE", "event": None, "reason": reason}

    observed = _time(result["observed_at"])
    admitted = _time(result["admitted_at"])
    if admitted < observed:
        return {"gate_disposition": "ESCALATE", "event": None, "reason": "receiver admission predates observation"}
    if admitted > evaluation:
        return {"gate_disposition": "ESCALATE", "event": None, "reason": "receiver admission postdates evaluation boundary"}
    if int((evaluation - observed).total_seconds()) > freshness:
        return {"gate_disposition": "ESCALATE", "event": None, "reason": "verification result is stale at evaluation boundary"}

    if result.get("observed_value") == contract.get("required_value"):
        return {
            "gate_disposition": "SURVIVE",
            "event": None,
            "reason": "fresh receiver-admitted verification satisfies the prospective predicate",
        }

    return {
        "gate_disposition": "EVENT",
        "event": {
            "basis_id": contract["dependency_id"],
            "event_type": "LOSS_OF_STANDING",
        },
        "reason": "fresh receiver-admitted verification falsifies the prospective predicate",
    }
