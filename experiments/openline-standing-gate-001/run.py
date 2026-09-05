#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import traceback
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from openline_claim_graph.decision_recall import (
    _decision_recall_disposition,
    create_manifest,
    validate_manifest,
)
from openline_claim_graph.verification_contract import (
    create_receiver_admission,
    create_verification_contract,
    create_verification_result,
    decision_recall_binding,
    evaluate_verification_contract,
)
from olp_gate.authority_link import canonical_hash
from olp_gate.crypto import public_key_hex, sign_olp_body
from olp_gate.standing import (
    ReceiverStandingView,
    STANDING_PROJECTION_SCHEMA,
    standing_action_hash,
    standing_action_hash_from_call,
    standing_requirement_source,
    support_receipt_hash,
)
from olp_gate.tool_adapter import (
    AuthorizationBlocked,
    AuthorizedValue,
    EvidenceAssertion,
    authorize,
)


CLAIM_GRAPH_BASE_SHA = "e868fcfc1a392ec9d1e38edbd3629aea3ec576d6"
CLAIM_GRAPH_SRC_TREE = "7187fb74c57764a9ef1a3aad385dda7b00e4d57a"
RECEIPT_GATE_SHA = "3ae2918d59125e13cf8f58147e482ebb940b6da6"
RECEIPT_GATE_STANDING_BLOB = "bb73267c9a67e26ee40f6914bc75e7c8f97532ed"
RECEIPT_GATE_ADAPTER_BLOB = "8fc200e8ad44e461b50cef90426ad141bdb8238b"
PREREG_SCHEMA = "openline.openline-standing-gate-001.prereg.v1"

TARGET_DECISION = "decision-standing-gate-target"
CONTROL_DECISION = "decision-standing-gate-control"
TOOL = "apply_decision"
TARGET_URI = "runtime://standing-gate-consequence"


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()


def _manifest(
    *,
    decision_id: str,
    accepted_at: str,
    basis: list[Mapping[str, Any]],
    required_dependencies: list[str],
    invalidation_conditions: list[Mapping[str, Any]],
    locator: str,
) -> dict[str, Any]:
    manifest = create_manifest(
        decision_id=decision_id,
        accepted_at=accepted_at,
        decision="ACCEPT",
        basis=basis,
        required_dependencies=required_dependencies,
        alternative_support=[],
        assumptions=[],
        invalidation_conditions=invalidation_conditions,
        resulting_artifact={
            "kind": "CONSEQUENCE_AUTHORIZATION",
            "locator": locator,
            "sha256": "",
        },
        capture={
            "started_at": accepted_at,
            "confirmed_at": accepted_at,
            "human_capture_milliseconds": 0,
            "drafted_by": "OPENLINE-STANDING-GATE-001",
            "confirmed_by": "RECEIVER",
            "correction_count": 0,
            "timing_source": "HARNESS",
        },
        metadata={"experiment": "OPENLINE-STANDING-GATE-001"},
    )
    check = validate_manifest(manifest)
    if check["valid"] is not True:
        raise RuntimeError(f"fixture invalid: manifest failed validation: {check}")
    return manifest


class GateHarness:
    def __init__(
        self,
        *,
        target_manifest: Mapping[str, Any],
        control_manifest: Mapping[str, Any],
        runtime_dir: Path,
    ) -> None:
        self.target_manifest = dict(target_manifest)
        self.control_manifest = dict(control_manifest)
        self.supports = {
            TARGET_DECISION: self.target_manifest,
            CONTROL_DECISION: self.control_manifest,
        }

        self.standing_key = Ed25519PrivateKey.generate()
        self.standing_issuer = "receiver:standing-gate-bridge:v1"
        self.view = ReceiverStandingView(
            {self.standing_issuer: public_key_hex(self.standing_key)}
        )
        self.presented: dict[tuple[str, str], dict[str, Any]] = {}
        self.effects: list[str] = []
        self.bridge_calls = 0
        self.bridge_calls_before_loss = 0
        self.bridge_receipts: list[dict[str, Any]] = []

        self.bundle = {
            "schema": "openline.authorized_tool_policy.v1",
            "mandate": {
                "profile": "principal_mandate/v1",
                "mandate_id": "standing-gate-001-mandate",
                "principal_id": "receiver-owner",
                "agent_id": "standing-gate-agent",
                "purpose": "execute only receiver-authorized standing-gate fixture actions",
                "allowed_action_types": ["inspect"],
                "allowed_targets": [TARGET_URI],
                "allowed_disclosure_classes": [],
                "forbidden_disclosure_classes": [],
                "max_settlement_cents": 0,
                "max_payment_cents": 0,
                "delegation_allowed": False,
                "expires_at": _iso(
                    datetime.now(timezone.utc) + timedelta(hours=6)
                ),
                "version": "1",
            },
            "permission_policy": {
                "profile": "decision_permission_policy/v1",
                "policy_id": "standing-gate-001-policy",
                "version": "1",
                "routes": [
                    {
                        "route_id": "apply-decision",
                        "tool": TOOL,
                        "target": TARGET_URI,
                        "requirements": [
                            {
                                "requirement_id": "decision_authority",
                                "kind": "authority",
                                "accepted_issuers": ["decision_authority"],
                                "max_age_seconds": 300,
                                "independent_from_producer": True,
                            },
                            {
                                "requirement_id": "decision_standing",
                                "kind": "evidence",
                                "accepted_issuers": ["receiver_standing"],
                                "max_age_seconds": 300,
                                "independent_from_producer": True,
                            },
                        ],
                        "unknown_behavior": "QUARANTINE",
                        "max_authorization_ttl_seconds": 120,
                    }
                ],
            },
        }

        self._standing_provider = standing_requirement_source(
            self.view,
            support_source=self._support_for_call,
            projection_source=self._projection_for_call,
            action_hash_source=standing_action_hash_from_call,
            evidence_issuer_id="receiver_standing",
            max_assertion_ttl_seconds=60,
            now_source=lambda: datetime.now(timezone.utc),
        )

        @authorize(
            policy=self.bundle,
            tool=TOOL,
            target=TARGET_URI,
            semantics=self._semantics,
            state_source=self._state,
            evidence_sources={
                "decision_authority": self._authority_for_call,
                "decision_standing": self._standing_provider,
            },
            producer_model="standing-gate-integration-fixture",
            objective="exercise the frozen Claim Graph to Receipt Gate standing seam",
            runtime_dir=runtime_dir,
            return_receipt=True,
        )
        def apply_decision(decision_id: str, payload: str):
            self.effects.append(decision_id)
            return {
                "applied": True,
                "decision_id": decision_id,
                "payload": payload,
            }

        self.apply_decision = apply_decision

    @staticmethod
    def _semantics(call):
        return {
            "action_type": "inspect",
            "disclosures": [],
            "value_cents": 0,
            "delegatee": None,
        }

    @staticmethod
    def _state(call):
        return {
            "decision_id": call.arguments["decision_id"],
            "payload": call.arguments["payload"],
        }

    @staticmethod
    def action_hash(decision_id: str, payload: str) -> str:
        return standing_action_hash(
            tool=TOOL,
            target=TARGET_URI,
            arguments={"decision_id": decision_id, "payload": payload},
        )

    def _support_for_call(self, call):
        return self.supports.get(str(call.arguments.get("decision_id")))

    def _projection_for_call(self, call):
        support = self._support_for_call(call)
        if support is None:
            return None
        key = (
            support_receipt_hash(support),
            standing_action_hash_from_call(call),
        )
        return self.presented.get(key)

    def _authority_for_call(self, call):
        support = self._support_for_call(call)
        if support is None:
            return None
        check = validate_manifest(support)
        if check["valid"] is not True:
            return None
        if support.get("decision_id") != call.arguments.get("decision_id"):
            return None
        return EvidenceAssertion(
            payload={
                "manifest_id": support["manifest_id"],
                "decision_id": support["decision_id"],
            },
            issuer_id="decision_authority",
            expires_in_seconds=60,
        )

    def _projection(
        self,
        *,
        decision_id: str,
        payload: str,
        standing: str,
        event_type: str,
        projection_id: str,
    ) -> dict[str, Any]:
        support = self.supports[decision_id]
        support_hash = support_receipt_hash(support)
        action_hash = self.action_hash(decision_id, payload)
        key = (support_hash, action_hash)
        current = self.presented.get(key)
        sequence = 1 if current is None else int(current["sequence"]) + 1
        predecessor = self.view.head_hash(support_hash, action_hash)

        now = datetime.now(timezone.utc)
        return sign_olp_body(
            {
                "schema": STANDING_PROJECTION_SCHEMA,
                "projection_id": projection_id,
                "issuer_id": self.standing_issuer,
                "support_hash": support_hash,
                "action_hash": action_hash,
                "standing": standing,
                "event_type": event_type,
                "sequence": sequence,
                "predecessor_hash": predecessor,
                "issued_at": _iso(now),
                "expires_at": _iso(now + timedelta(hours=1)),
            },
            self.standing_key,
        )

    def admit_active(
        self,
        *,
        decision_id: str,
        payload: str,
    ) -> dict[str, Any]:
        projection = self._projection(
            decision_id=decision_id,
            payload=payload,
            standing="ACTIVE",
            event_type="ADMIT",
            projection_id=f"{decision_id}:active:1",
        )
        admission = self.view.admit(
            projection,
            now=datetime.now(timezone.utc),
        )
        key = (
            support_receipt_hash(self.supports[decision_id]),
            self.action_hash(decision_id, payload),
        )
        self.presented[key] = projection
        return {"projection": projection, "admission": admission}

    def bridge_reopen(
        self,
        *,
        evaluation: Mapping[str, Any],
        target_disposition: str,
        target_witness: list[str],
        target_reason: str,
        decision_id: str,
        payload: str,
    ) -> dict[str, Any]:
        """The only experiment path allowed to change target Gate standing."""
        event = evaluation.get("event")
        if evaluation.get("disposition") != "EVENT":
            raise RuntimeError("bridge refused: Claim Graph evaluation is not EVENT")
        if not isinstance(event, Mapping):
            raise RuntimeError("bridge refused: Claim Graph event missing")
        if event.get("event_type") != "LOSS_OF_STANDING":
            raise RuntimeError("bridge refused: event is not LOSS_OF_STANDING")
        if target_disposition != "REOPEN":
            raise RuntimeError("bridge refused: Decision Recall did not REOPEN")
        if decision_id != TARGET_DECISION:
            raise RuntimeError("bridge refused: only frozen target may be reopened")

        self.bridge_calls += 1
        projection = self._projection(
            decision_id=decision_id,
            payload=payload,
            standing="INACTIVE",
            event_type="REVOKE",
            projection_id=f"{decision_id}:reopen:{self.bridge_calls}",
        )
        admission = self.view.admit(
            projection,
            now=datetime.now(timezone.utc),
        )
        key = (
            support_receipt_hash(self.supports[decision_id]),
            self.action_hash(decision_id, payload),
        )
        self.presented[key] = projection

        bridge_body = {
            "schema": "openline.standing-gate-bridge-receipt.v1",
            "claim_graph_evaluation_id": evaluation["evaluation_id"],
            "claim_graph_event": dict(event),
            "decision_recall_disposition": target_disposition,
            "decision_recall_witness": list(target_witness),
            "decision_recall_reason": target_reason,
            "decision_id": decision_id,
            "support_hash": key[0],
            "action_hash": key[1],
            "standing_projection_hash": projection["payload_hash"],
            "standing_projection_sequence": projection["sequence"],
            "standing": projection["standing"],
            "event_type": projection["event_type"],
        }
        receipt = {
            **bridge_body,
            "bridge_receipt_hash": canonical_hash(bridge_body),
        }
        self.bridge_receipts.append(receipt)
        return {
            "projection": projection,
            "admission": admission,
            "bridge_receipt": receipt,
        }

    def try_apply(self, decision_id: str, payload: str) -> dict[str, Any]:
        before = len(self.effects)
        try:
            value = self.apply_decision(decision_id, payload)
            if not isinstance(value, AuthorizedValue):
                raise RuntimeError("fixture invalid: expected AuthorizedValue")
            receipt_hash = canonical_hash(dict(value.decision_receipt))
            return {
                "executed": True,
                "blocked": False,
                "decision": "COMMIT",
                "reason_codes": [],
                "effect_delta": len(self.effects) - before,
                "decision_receipt_hash": receipt_hash,
                "execution_authorized": value.execution.get("authorized"),
                "execution_status": value.execution.get("execution_status"),
            }
        except AuthorizationBlocked as exc:
            return {
                "executed": False,
                "blocked": True,
                "decision": exc.decision,
                "reason_codes": list(exc.reason_codes),
                "effect_delta": len(self.effects) - before,
                "decision_receipt_hash": (
                    canonical_hash(dict(exc.decision_receipt))
                    if isinstance(exc.decision_receipt, Mapping)
                    else None
                ),
            }


def execute(
    *,
    repo: Path,
    receipt_gate_repo: Path,
    out: Path,
) -> dict[str, Any]:
    prereg_path = (
        repo / "experiments/openline-standing-gate-001/prereg.json"
    )
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("schema") != PREREG_SCHEMA:
        raise RuntimeError("prereg schema mismatch")
    if prereg.get("status") != "FROZEN_BEFORE_RUN":
        raise RuntimeError("prereg is not frozen")
    if prereg.get("claim_graph_base_sha") != CLAIM_GRAPH_BASE_SHA:
        raise RuntimeError("Claim Graph base SHA mismatch")
    if prereg.get("receipt_gate_sha") != RECEIPT_GATE_SHA:
        raise RuntimeError("Receipt Gate SHA mismatch")

    base_src_tree = _git(
        repo, "rev-parse", f"{CLAIM_GRAPH_BASE_SHA}:src/openline_claim_graph"
    )
    head_src_tree = _git(
        repo, "rev-parse", "HEAD:src/openline_claim_graph"
    )
    if (
        base_src_tree != CLAIM_GRAPH_SRC_TREE
        or head_src_tree != CLAIM_GRAPH_SRC_TREE
    ):
        raise RuntimeError(
            "Claim Graph production source changed after preregistration"
        )

    gate_head = _git(receipt_gate_repo, "rev-parse", "HEAD")
    gate_standing_blob = _git(
        receipt_gate_repo, "rev-parse", "HEAD:olp_gate/standing.py"
    )
    gate_adapter_blob = _git(
        receipt_gate_repo, "rev-parse", "HEAD:olp_gate/tool_adapter.py"
    )
    if gate_head != RECEIPT_GATE_SHA:
        raise RuntimeError("Receipt Gate checkout SHA mismatch")
    if gate_standing_blob != RECEIPT_GATE_STANDING_BLOB:
        raise RuntimeError("Receipt Gate standing.py blob mismatch")
    if gate_adapter_blob != RECEIPT_GATE_ADAPTER_BLOB:
        raise RuntimeError("Receipt Gate tool_adapter.py blob mismatch")

    # A local file is the external-state fixture. The Claim Graph result binds
    # the exact bytes observed before and after the state transition.
    state_path = out / "external-state-current.json"
    initial_state = {
        "schema": "openline.standing-gate.external-state.v1",
        "subject_id": "fixture://external-state/eligibility",
        "state": "VALID",
    }
    _write_json(state_path, initial_state)
    _write_json(out / "external-state-initial.json", initial_state)
    initial_evidence_hash = _sha256_file(state_path)

    now = datetime.now(timezone.utc)
    accepted_at = _iso(now - timedelta(seconds=30))
    pass_observed_at = _iso(now - timedelta(seconds=20))
    pass_admitted_at = _iso(now - timedelta(seconds=19))
    pass_evaluated_at = _iso(now - timedelta(seconds=18))
    fail_observed_at = _iso(now - timedelta(seconds=10))
    fail_admitted_at = _iso(now - timedelta(seconds=9))
    fail_evaluated_at = _iso(now - timedelta(seconds=8))

    contract = create_verification_contract(
        dependency_id="basis:external-state:eligibility",
        subject_id=initial_state["subject_id"],
        required_value="VALID",
        recognized_verifier_id="receiver:standing-gate-verifier:v1",
        freshness_seconds=3600,
        metadata={"experiment": "OPENLINE-STANDING-GATE-001"},
    )
    binding = decision_recall_binding(contract)

    target_manifest = _manifest(
        decision_id=TARGET_DECISION,
        accepted_at=accepted_at,
        basis=[binding["basis"]],
        required_dependencies=[binding["required_dependency"]],
        invalidation_conditions=[binding["invalidation_condition"]],
        locator="fixture://consequence/target",
    )

    control_basis = {
        "basis_id": "basis:unrelated:control",
        "kind": "FIXTURE_CONTROL",
        "statement": "Unrelated control basis remains standing",
        "locator": "fixture://external-state/control",
        "evidence_sha256": "",
        "role": "REQUIRED",
        "alternative_group": "",
    }
    control_condition = {
        "condition_id": "loss-control",
        "dependency_id": control_basis["basis_id"],
        "event_types": ["LOSS_OF_STANDING"],
        "note": "control reopens only if its own basis loses standing",
    }
    control_manifest = _manifest(
        decision_id=CONTROL_DECISION,
        accepted_at=accepted_at,
        basis=[control_basis],
        required_dependencies=[control_basis["basis_id"]],
        invalidation_conditions=[control_condition],
        locator="fixture://consequence/control",
    )

    passing_result = create_verification_result(
        contract=contract,
        verifier_id=contract["recognized_verifier_id"],
        observed_value=initial_state["state"],
        observed_at=pass_observed_at,
        evidence_sha256=initial_evidence_hash,
        locator=str(state_path),
    )
    passing_admission = create_receiver_admission(
        contract=contract,
        result=passing_result,
        receiver_id="receiver:openline:standing-gate-001",
        admitted_at=pass_admitted_at,
    )
    passing_evaluation = evaluate_verification_contract(
        contract=contract,
        accepted_at=accepted_at,
        evaluation_at=pass_evaluated_at,
        result=passing_result,
        admission=passing_admission,
    )
    if passing_evaluation.get("disposition") != "SURVIVE":
        raise RuntimeError(
            "fixture invalid: initial VALID verification did not SURVIVE: "
            f"{passing_evaluation!r}"
        )

    gate = GateHarness(
        target_manifest=target_manifest,
        control_manifest=control_manifest,
        runtime_dir=out / "receipt-gate-runtime",
    )
    target_payload = "perform-target-consequence"
    control_payload = "perform-control-consequence"

    target_active = gate.admit_active(
        decision_id=TARGET_DECISION,
        payload=target_payload,
    )
    control_active = gate.admit_active(
        decision_id=CONTROL_DECISION,
        payload=control_payload,
    )
    target_head_before = target_active["admission"]["head_hash"]
    control_head_before = control_active["admission"]["head_hash"]

    target_before = gate.try_apply(TARGET_DECISION, target_payload)
    control_before = gate.try_apply(CONTROL_DECISION, control_payload)
    if (
        not target_before["executed"]
        or target_before["effect_delta"] != 1
        or not control_before["executed"]
        or control_before["effect_delta"] != 1
    ):
        raise RuntimeError(
            "fixture invalid: target/control did not both execute before loss: "
            f"target={target_before!r} control={control_before!r}"
        )

    if gate.bridge_calls != 0:
        raise RuntimeError("fixture invalid: bridge changed standing before loss")
    gate.bridge_calls_before_loss = gate.bridge_calls

    changed_state = {
        "schema": "openline.standing-gate.external-state.v1",
        "subject_id": initial_state["subject_id"],
        "state": "WITHDRAWN",
    }
    _write_json(state_path, changed_state)
    _write_json(out / "external-state-after.json", changed_state)
    changed_evidence_hash = _sha256_file(state_path)
    if changed_evidence_hash == initial_evidence_hash:
        raise RuntimeError("fixture invalid: external state bytes did not change")

    failing_result = create_verification_result(
        contract=contract,
        verifier_id=contract["recognized_verifier_id"],
        observed_value=changed_state["state"],
        observed_at=fail_observed_at,
        evidence_sha256=changed_evidence_hash,
        locator=str(state_path),
    )
    failing_admission = create_receiver_admission(
        contract=contract,
        result=failing_result,
        receiver_id="receiver:openline:standing-gate-001",
        admitted_at=fail_admitted_at,
    )
    failing_evaluation = evaluate_verification_contract(
        contract=contract,
        accepted_at=accepted_at,
        evaluation_at=fail_evaluated_at,
        result=failing_result,
        admission=failing_admission,
    )
    expected_event = {
        "basis_id": contract["dependency_id"],
        "event_type": "LOSS_OF_STANDING",
    }
    if (
        failing_evaluation.get("disposition") != "EVENT"
        or failing_evaluation.get("event") != expected_event
    ):
        raise RuntimeError(
            "fixture invalid: fresh changed state did not produce the exact "
            f"LOSS_OF_STANDING event: {failing_evaluation!r}"
        )

    target_disposition, target_witness, target_reason = (
        _decision_recall_disposition(
            target_manifest,
            failing_evaluation["event"],
        )
    )
    control_disposition, control_witness, control_reason = (
        _decision_recall_disposition(
            control_manifest,
            failing_evaluation["event"],
        )
    )
    if target_disposition != "REOPEN":
        raise RuntimeError(
            "fixture invalid: existing Decision Recall did not REOPEN target: "
            f"{target_disposition} {target_reason}"
        )
    if control_disposition != "SURVIVE":
        raise RuntimeError(
            "fixture invalid: unrelated control did not SURVIVE: "
            f"{control_disposition} {control_reason}"
        )

    bridge = gate.bridge_reopen(
        evaluation=failing_evaluation,
        target_disposition=target_disposition,
        target_witness=target_witness,
        target_reason=target_reason,
        decision_id=TARGET_DECISION,
        payload=target_payload,
    )

    target_support_hash = support_receipt_hash(target_manifest)
    target_action_hash = gate.action_hash(TARGET_DECISION, target_payload)
    control_support_hash = support_receipt_hash(control_manifest)
    control_action_hash = gate.action_hash(CONTROL_DECISION, control_payload)

    target_head_after = gate.view.head_hash(
        target_support_hash,
        target_action_hash,
    )
    control_head_after = gate.view.head_hash(
        control_support_hash,
        control_action_hash,
    )

    if gate.bridge_calls_before_loss != 0 or gate.bridge_calls != 1:
        raise RuntimeError("fixture invalid: bridge call count/provenance mismatch")
    if bridge["projection"]["standing"] != "INACTIVE":
        raise RuntimeError("fixture invalid: bridge did not issue INACTIVE standing")
    if bridge["projection"]["event_type"] != "REVOKE":
        raise RuntimeError("fixture invalid: bridge did not issue REVOKE event")
    if bridge["projection"]["predecessor_hash"] != target_head_before:
        raise RuntimeError("fixture invalid: target successor predecessor mismatch")
    if control_head_after != control_head_before:
        raise RuntimeError("fixture invalid: bridge changed unrelated control head")

    target_after = gate.try_apply(TARGET_DECISION, target_payload)
    control_after = gate.try_apply(CONTROL_DECISION, control_payload)

    revoked_reason = any(
        str(reason).startswith("evidence_revoked:decision_standing")
        for reason in target_after.get("reason_codes", [])
    )
    pass_checks = {
        "claim_graph_src_unchanged": (
            base_src_tree == CLAIM_GRAPH_SRC_TREE
            and head_src_tree == CLAIM_GRAPH_SRC_TREE
        ),
        "receipt_gate_exact_pin": (
            gate_head == RECEIPT_GATE_SHA
            and gate_standing_blob == RECEIPT_GATE_STANDING_BLOB
            and gate_adapter_blob == RECEIPT_GATE_ADAPTER_BLOB
        ),
        "initial_valid_state_survived": (
            passing_evaluation["disposition"] == "SURVIVE"
        ),
        "target_and_control_executed_before_loss": (
            target_before["executed"]
            and control_before["executed"]
        ),
        "fresh_changed_state_emitted_loss_of_standing": (
            failing_evaluation["disposition"] == "EVENT"
            and failing_evaluation["event"] == expected_event
        ),
        "decision_recall_target_reopen_control_survive": (
            target_disposition == "REOPEN"
            and control_disposition == "SURVIVE"
        ),
        "bridge_only_after_reopen": (
            gate.bridge_calls_before_loss == 0
            and gate.bridge_calls == 1
            and bridge["bridge_receipt"]["decision_recall_disposition"]
            == "REOPEN"
            and bridge["bridge_receipt"]["claim_graph_evaluation_id"]
            == failing_evaluation["evaluation_id"]
        ),
        "target_successor_exact_and_monotonic": (
            target_head_after == bridge["projection"]["payload_hash"]
            and bridge["projection"]["sequence"] == 2
            and bridge["projection"]["predecessor_hash"] == target_head_before
            and bridge["projection"]["support_hash"] == target_support_hash
            and bridge["projection"]["action_hash"] == target_action_hash
        ),
        "target_retry_blocked_before_effect": (
            target_after["blocked"] is True
            and target_after["executed"] is False
            and target_after["effect_delta"] == 0
        ),
        "target_block_due_to_revoked_standing": revoked_reason,
        "unrelated_control_head_unchanged": (
            control_head_after == control_head_before
        ),
        "unrelated_control_retry_executes": (
            control_after["executed"] is True
            and control_after["blocked"] is False
            and control_after["effect_delta"] == 1
        ),
    }

    verdict = (
        "STANDING_LOSS_STOPS_CONSEQUENCE"
        if all(pass_checks.values())
        else "STANDING_LOSS_DOES_NOT_STOP_CONSEQUENCE"
    )

    result = {
        "schema": "openline.openline-standing-gate-001.result.v1",
        "experiment": "OPENLINE-STANDING-GATE-001",
        "verdict": verdict,
        "git_head": _git(repo, "rev-parse", "HEAD"),
        "source_guard": {
            "claim_graph_base_sha": CLAIM_GRAPH_BASE_SHA,
            "claim_graph_base_src_tree": base_src_tree,
            "claim_graph_head_src_tree": head_src_tree,
            "receipt_gate_sha": gate_head,
            "receipt_gate_standing_blob": gate_standing_blob,
            "receipt_gate_tool_adapter_blob": gate_adapter_blob,
            "product_semantic_files_changed_by_experiment": False,
        },
        "prereg_sha256": _sha256_file(prereg_path),
        "external_state": {
            "initial": initial_state,
            "initial_evidence_sha256": initial_evidence_hash,
            "after": changed_state,
            "after_evidence_sha256": changed_evidence_hash,
        },
        "claim_graph": {
            "contract": contract,
            "passing_result": passing_result,
            "passing_admission": passing_admission,
            "passing_evaluation": passing_evaluation,
            "failing_result": failing_result,
            "failing_admission": failing_admission,
            "failing_evaluation": failing_evaluation,
        },
        "decision_recall": {
            "target_manifest_id": target_manifest["manifest_id"],
            "target_disposition": target_disposition,
            "target_witness": target_witness,
            "target_reason": target_reason,
            "control_manifest_id": control_manifest["manifest_id"],
            "control_disposition": control_disposition,
            "control_witness": control_witness,
            "control_reason": control_reason,
        },
        "bridge": {
            "calls_before_loss": gate.bridge_calls_before_loss,
            "calls_total": gate.bridge_calls,
            "receipt": bridge["bridge_receipt"],
            "target_head_before": target_head_before,
            "target_head_after": target_head_after,
            "control_head_before": control_head_before,
            "control_head_after": control_head_after,
        },
        "receipt_gate": {
            "before_loss": {
                "target": target_before,
                "control": control_before,
            },
            "after_loss": {
                "target": target_after,
                "control": control_after,
            },
            "effects": list(gate.effects),
        },
        "pass_checks": pass_checks,
        "claim_boundary": [
            "One local cross-repo standing-to-consequence path only.",
            "Claim Graph emits standing evidence, not execution decisions.",
            "Decision Recall is reused unchanged.",
            "The bridge has no independent reopen policy.",
            "Receipt Gate remains final execution authority.",
            "The first historically valid target effect is not undone.",
            "No Wallet, Airlock, cross-receiver, or distributed propagation claim.",
        ],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--receipt-gate-repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo.resolve()
    gate_repo = args.receipt_gate_repo.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    _write_json(
        out / "run-start.json",
        {
            "schema": "openline.openline-standing-gate-001.run-start.v1",
            "status": "STARTED",
            "claim_graph_base_sha": CLAIM_GRAPH_BASE_SHA,
            "receipt_gate_sha": RECEIPT_GATE_SHA,
        },
    )

    try:
        result = execute(
            repo=repo,
            receipt_gate_repo=gate_repo,
            out=out,
        )
    except Exception as exc:
        _write_json(
            out / "OPENLINE_STANDING_GATE_001_INFRA_FAILURE.json",
            {
                "schema": "openline.openline-standing-gate-001.infra-failure.v1",
                "status": "INFRASTRUCTURE_FAILURE",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        raise

    result_path = out / "OPENLINE_STANDING_GATE_001_RESULT.json"
    _write_json(result_path, result)
    result_sha = _sha256_file(result_path)
    (
        out / "OPENLINE_STANDING_GATE_001_RESULT.sha256"
    ).write_text(result_sha + "\n", encoding="utf-8")

    print(result["verdict"])
    print(
        "Claim Graph: "
        f"{result['claim_graph']['failing_evaluation']['disposition']} / "
        f"{result['claim_graph']['failing_evaluation']['event']['event_type']}"
    )
    print(
        "Decision Recall: "
        f"target={result['decision_recall']['target_disposition']} "
        f"control={result['decision_recall']['control_disposition']}"
    )
    print(
        "Receipt Gate after loss: "
        f"target_blocked={result['receipt_gate']['after_loss']['target']['blocked']} "
        f"target_effect_delta={result['receipt_gate']['after_loss']['target']['effect_delta']} "
        f"control_executed={result['receipt_gate']['after_loss']['control']['executed']}"
    )
    print(f"result_sha256={result_sha}")

    # Both frozen scientific outcomes are valid completed experiments.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
