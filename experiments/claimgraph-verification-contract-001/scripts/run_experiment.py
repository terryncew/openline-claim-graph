from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from openline_claim_graph.decision_recall import _decision_recall_disposition

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
from verification_contract import evaluate_verification_contract  # noqa: E402

FIXTURE = HERE / "fixture.json"
RESULT = HERE / "artifacts" / "RESULT.json"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _manifest(fixture: dict[str, Any], role: str) -> dict[str, Any]:
    return next(row["manifest"] for row in fixture["decisions"] if row["role"] == role)


def _apply(
    *,
    manifest: dict[str, Any],
    contract: dict[str, Any],
    arm: dict[str, Any],
) -> dict[str, Any]:
    gate = evaluate_verification_contract(
        contract=contract,
        accepted_at=manifest["accepted_at"],
        evaluation_at=arm["evaluation_at"],
        verification_result=arm["verification_result"],
    )
    if gate["gate_disposition"] == "ESCALATE":
        return {"disposition": "ESCALATE", "witness": [contract["dependency_id"]], "reason": gate["reason"], "gate": gate}
    if gate["gate_disposition"] == "SURVIVE":
        return {"disposition": "SURVIVE", "witness": [], "reason": gate["reason"], "gate": gate}
    disposition, witness, reason = _decision_recall_disposition(manifest, gate["event"])
    return {"disposition": disposition, "witness": witness, "reason": reason, "gate": gate}


def run(fixture: dict[str, Any]) -> dict[str, Any]:
    target = _manifest(fixture, "TARGET")
    control = _manifest(fixture, "UNRELATED_CONTROL")
    contract = fixture["verification_contract"]

    target_before = sha256_obj(target)
    control_before = sha256_obj(control)

    rows = []
    for arm in fixture["arms"]:
        target_result = _apply(manifest=target, contract=contract, arm=arm)
        event = target_result["gate"].get("event")
        if event is None:
            control_result = {
                "disposition": "SURVIVE",
                "witness": [],
                "reason": "unrelated control has no verification contract event",
            }
        else:
            disposition, witness, reason = _decision_recall_disposition(control, event)
            control_result = {"disposition": disposition, "witness": witness, "reason": reason}

        rows.append({
            "arm": arm["arm"],
            "desired_target": arm["desired_target"],
            "target": target_result,
            "control": control_result,
            "target_hit": target_result["disposition"] == arm["desired_target"],
            "unrelated_preserved": control_result["disposition"] == "SURVIVE",
        })

    by_arm = {row["arm"]: row for row in rows}
    manifest_unchanged = target_before == sha256_obj(target) and control_before == sha256_obj(control)
    contract_present_before = contract["dependency_id"] in {
        item.get("basis_id") for item in target.get("basis", [])
    }
    post_outcome_dependency_added = not contract_present_before

    invalid_arms = [
        "UNADMITTED_FRESH_FAILURE",
        "UNRECOGNIZED_VERIFIER_FAILURE",
        "STALE_ADMITTED_FAILURE",
    ]
    invalid_reopens = sum(
        1 for name in invalid_arms
        if by_arm[name]["target"]["disposition"] == "REOPEN"
    )

    metrics = {
        "fresh_failure_reopen_recall": 1.0 if by_arm["FRESH_ADMITTED_FAILURE"]["target_hit"] else 0.0,
        "fresh_pass_survival": 1.0 if by_arm["FRESH_ADMITTED_PASS"]["target_hit"] else 0.0,
        "overdue_escalation_recall": 1.0 if by_arm["MISSED_DEADLINE_NO_RESULT"]["target_hit"] else 0.0,
        "invalid_verification_reopen_rate": invalid_reopens / len(invalid_arms),
        "unrelated_state_preservation": sum(1 for row in rows if row["unrelated_preserved"]) / len(rows),
        "prospective_contract_present_at_acceptance": contract_present_before,
        "frozen_manifests_unchanged": manifest_unchanged,
        "post_outcome_dependency_edges_added": 1 if post_outcome_dependency_added else 0,
    }

    passed = (
        all(row["target_hit"] for row in rows)
        and metrics["invalid_verification_reopen_rate"] == 0.0
        and metrics["unrelated_state_preservation"] == 1.0
        and metrics["prospective_contract_present_at_acceptance"]
        and metrics["frozen_manifests_unchanged"]
        and metrics["post_outcome_dependency_edges_added"] == 0
    )

    return {
        "schema": "openline.claimgraph-verification-contract-result.v1",
        "experiment": fixture["experiment"],
        "frozen_base_commit": fixture["frozen_base_commit"],
        "decision_recall_blob_sha": fixture["decision_recall_blob_sha"],
        "fixture_sha256": sha256_obj(fixture),
        "accepted_graph_anchor": fixture["accepted_graph_anchor"],
        "verification_contract": contract,
        "arms": rows,
        "metrics": metrics,
        "verdict": "CLAIMGRAPH_VERIFICATION_CONTRACT_PASS" if passed else "CLAIMGRAPH_VERIFICATION_CONTRACT_FALSIFIED",
        "earned_next_step": "PRODUCTION_INTEGRATION_CANDIDATE" if passed else "NONE",
        "production_semantics_changed": False,
        "claim_boundary": [
            "The pass, if earned, is limited to a prospectively declared verification obligation plus receiver-owned admission in this injected case.",
            "The live external state remains outside the accepted Claim Graph.",
            "No result self-authorizes; stale or inadmissible evidence escalates rather than reopening.",
            "The experiment does not establish hidden-dependency discovery, verifier truth, or polling infrastructure.",
        ],
    }


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = run(fixture)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": result["verdict"],
        "fresh_failure_reopen_recall": result["metrics"]["fresh_failure_reopen_recall"],
        "invalid_verification_reopen_rate": result["metrics"]["invalid_verification_reopen_rate"],
        "unrelated_state_preservation": result["metrics"]["unrelated_state_preservation"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
