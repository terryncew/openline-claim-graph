from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from openline_claim_graph.decision_recall import _decision_recall_disposition

HERE = Path(__file__).resolve().parents[1]
FIXTURE = HERE / "fixture.json"
RESULT = HERE / "artifacts" / "RESULT.json"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _manifest(fixture: dict[str, Any], role: str) -> dict[str, Any]:
    for row in fixture["decisions"]:
        if row["role"] == role:
            return row["manifest"]
    raise ValueError(f"missing role: {role}")


def _predict(manifest: dict[str, Any], basis_id: str, event_type: str) -> dict[str, Any]:
    disposition, witness, reason = _decision_recall_disposition(
        manifest,
        {"basis_id": basis_id, "event_type": event_type},
    )
    return {"disposition": disposition, "witness": witness, "reason": reason}


def run(fixture: dict[str, Any]) -> dict[str, Any]:
    target = _manifest(fixture, "TARGET")
    control = _manifest(fixture, "UNRELATED_CONTROL")
    external = fixture["external_state"]
    basis_id = external["basis_id"]

    target_before = sha256_obj(target)
    control_before = sha256_obj(control)

    # Graph-only has no observation to feed the disposition engine. The frozen
    # accepted state therefore remains closed by construction.
    graph_only_target = {
        "disposition": "SURVIVE",
        "witness": [],
        "reason": "external state is unobserved and absent from the frozen dependency record",
    }
    graph_only_control = {
        "disposition": "SURVIVE",
        "witness": [],
        "reason": "no observed event affects the unrelated control",
    }

    # Declared replay state exposes the previously unrepresented basis, but it
    # is not standing-changing verification. Current Decision Recall sees the
    # basis as absent and returns SURVIVE before event-type matching.
    replay_target = _predict(target, basis_id, "STATE_DIVERGENCE_DECLARED")
    replay_control = _predict(control, basis_id, "STATE_DIVERGENCE_DECLARED")

    # Fresh verification now says the unrepresented state lost standing and is
    # material to continued use. The basis remains absent from the frozen
    # manifest; current code still returns SURVIVE.
    verified_target = _predict(target, basis_id, "LOSS_OF_STANDING")
    verified_control = _predict(control, basis_id, "LOSS_OF_STANDING")

    arms = [
        {
            "arm": "GRAPH_ONLY",
            "target": graph_only_target,
            "control": graph_only_control,
            "desired_target": "AFFECTED_UNRESOLVED",
            "target_hit": False,
            "unrelated_preserved": graph_only_control["disposition"] == "SURVIVE",
        },
        {
            "arm": "GRAPH_PLUS_DECLARED_REPLAY_STATE",
            "target": replay_target,
            "control": replay_control,
            "desired_target": "ESCALATE",
            "target_hit": replay_target["disposition"] == "ESCALATE",
            "unrelated_preserved": replay_control["disposition"] == "SURVIVE",
        },
        {
            "arm": "GRAPH_PLUS_FRESH_VERIFICATION",
            "target": verified_target,
            "control": verified_control,
            "desired_target": "REOPEN",
            "target_hit": verified_target["disposition"] == "REOPEN",
            "unrelated_preserved": verified_control["disposition"] == "SURVIVE",
        },
    ]

    manifest_unchanged = target_before == sha256_obj(target) and control_before == sha256_obj(control)
    post_outcome_dependency_added = any(
        basis_id in {item.get("basis_id") for item in row["manifest"].get("basis", [])}
        or basis_id in {item.get("assumption_id") for item in row["manifest"].get("assumptions", [])}
        for row in fixture["decisions"]
    )
    falsifier = (
        verified_target["disposition"] == "SURVIVE"
        and external["materiality"] == "REQUIRED_FOR_CONTINUED_STANDING"
        and not external["represented_in_frozen_manifest"]
        and manifest_unchanged
        and not post_outcome_dependency_added
    )

    return {
        "schema": "openline.claimgraph-unobserved-state-result.v1",
        "experiment": fixture["experiment"],
        "frozen_base_commit": fixture["frozen_base_commit"],
        "decision_recall_blob_sha": fixture["decision_recall_blob_sha"],
        "fixture_sha256": sha256_obj(fixture),
        "accepted_graph_anchor": fixture["accepted_graph_anchor"],
        "external_state": external,
        "arms": arms,
        "metrics": {
            "declared_replay_unresolved_recall": 1.0 if arms[1]["target_hit"] else 0.0,
            "fresh_verification_reopen_recall": 1.0 if arms[2]["target_hit"] else 0.0,
            "unrelated_state_preservation": sum(1 for arm in arms if arm["unrelated_preserved"]) / len(arms),
            "post_outcome_dependency_edges_added": 1 if post_outcome_dependency_added else 0,
            "frozen_manifests_unchanged": manifest_unchanged,
        },
        "verdict": (
            "CLAIMGRAPH_UNOBSERVED_STATE_FALSIFIED"
            if falsifier
            else "FALSIFIER_NOT_TRIGGERED"
        ),
        "earned_next_primitive": (
            "PROSPECTIVE_VERIFICATION_DEPENDENCY_OR_REPLAY_CONTRACT"
            if falsifier
            else "NONE"
        ),
        "production_semantics_changed": False,
        "claim_boundary": [
            "This result tests current Decision Recall behavior when materially relevant external state was absent from the frozen accepted dependency record.",
            "It does not claim automatic discovery of hidden dependencies or authority for arbitrary verifier output.",
            "A falsifier trigger earns a contract-model gap, not a propagation patch.",
        ],
    }


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = run(fixture)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": result["verdict"],
        "declared_replay_unresolved_recall": result["metrics"]["declared_replay_unresolved_recall"],
        "fresh_verification_reopen_recall": result["metrics"]["fresh_verification_reopen_recall"],
        "unrelated_state_preservation": result["metrics"]["unrelated_state_preservation"],
        "production_semantics_changed": result["production_semantics_changed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
