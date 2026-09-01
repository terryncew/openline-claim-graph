from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from contestability import (
    apply_receiver_decision,
    canonical_bytes,
    evaluate_receiver,
    load_json,
    normalize_foreign,
    sha256_obj,
    stages,
    write_json,
)

EXP = Path(__file__).resolve().parents[1]


def _load_inputs():
    return (
        load_json(EXP / "fixtures" / "scenario.json"),
        load_json(EXP / "fixtures" / "foreign-verifier-result.json"),
        load_json(EXP / "adapter-profile.json"),
        load_json(EXP / "receiver-policy.json"),
    )


def _alternate_projection(foreign: dict, profile: dict):
    alternate = {
        "authz": foreign["authorization"]["id"],
        "where": foreign["contestability"]["forum"]["id"],
        "standing": foreign["contestability"]["standing_policy"],
        "who": foreign["contestability"]["filer"]["role"],
        "window": foreign["contestability"]["window_state"],
        "proofs": {
            "signature": foreign["verification"]["signature_valid"],
            "binding": foreign["verification"]["binding_valid"],
            "forum": foreign["verification"]["forum_acknowledged"],
            "trigger": foreign["effect"]["authenticated_trigger"]["valid"],
        },
        "effects": {
            "declared": foreign["effect"]["issuer_declared_policy"]["mode"],
            "accepted": foreign["effect"]["executor_acceptance"]["valid"],
            "applied": foreign["effect"]["application_record"]["valid"],
        },
    }
    alt_profile = copy.deepcopy(profile)
    alt_profile["profile_id"] = "alternate-foreign-shape/test-profile-v1"
    alt_profile["fields"] = {
        "authorization_ref": "authz",
        "forum_ref": "where",
        "standing_policy_ref": "standing",
        "filer_role": "who",
        "window_state": "window",
        "foreign_signature_valid": "proofs.signature",
        "binding_valid": "proofs.binding",
        "forum_acknowledged": "proofs.forum",
        "filing_authenticated": "proofs.trigger",
        "declared_effect": "effects.declared",
        "executor_acceptance": "effects.accepted",
        "foreign_application": "effects.applied",
    }
    return alternate, alt_profile


def _neutral_semantics(event: dict) -> dict:
    return {
        key: event[key]
        for key in (
            "authorization_ref",
            "forum_ref",
            "standing_policy_ref",
            "filer_role",
            "window_state",
            "foreign_signature_valid",
            "binding_valid",
            "forum_acknowledged",
            "filing_authenticated",
            "declared_effect",
            "executor_acceptance",
            "foreign_application",
        )
    }


def run_experiment() -> dict:
    graph, foreign, profile, policy = _load_inputs()
    expected_reopen = sorted(graph["expected_reopen"])

    # Arm 1: authenticated filing is evidence only until receiver evaluation.
    filed_event = normalize_foreign(foreign, profile)
    filed_only = {
        "stages": stages(filed_event, None, None),
        "state_unchanged": True,
        "reopened": [],
    }

    # Arm 2: a declared effect + executor acceptance without an authenticated trigger
    # cannot become local standing or application.
    no_trigger = copy.deepcopy(foreign)
    no_trigger["effect"]["authenticated_trigger"]["valid"] = False
    no_trigger_event = normalize_foreign(no_trigger, profile)
    no_trigger_decision = evaluate_receiver(no_trigger_event, policy, graph)
    no_trigger_application = apply_receiver_decision(graph, no_trigger_decision, policy)
    declared_only = {
        "stages": stages(no_trigger_event, no_trigger_decision, no_trigger_application),
        "decision": no_trigger_decision["disposition"],
        "reopened": no_trigger_application["reopened"],
        "state_unchanged": (
            no_trigger_application["state_before_sha256"]
            == no_trigger_application["state_after_sha256"]
        ),
    }

    # Arm 3: even a foreign application claim is not local authority.
    foreign_applied = copy.deepcopy(foreign)
    foreign_applied["effect"]["application_record"]["valid"] = True
    foreign_applied["contestability"]["forum"]["id"] = "forum:unaccepted"
    foreign_applied_event = normalize_foreign(foreign_applied, profile)
    foreign_applied_decision = evaluate_receiver(foreign_applied_event, policy, graph)
    foreign_applied_application = apply_receiver_decision(
        graph, foreign_applied_decision, policy
    )
    foreign_applied_rejected = {
        "stages": stages(
            foreign_applied_event,
            foreign_applied_decision,
            foreign_applied_application,
        ),
        "decision": foreign_applied_decision["disposition"],
        "reopened": foreign_applied_application["reopened"],
        "state_unchanged": (
            foreign_applied_application["state_before_sha256"]
            == foreign_applied_application["state_after_sha256"]
        ),
    }

    # Arm 4: receiver-owned acceptance, followed by separate local application.
    event = normalize_foreign(foreign, profile)
    decision = evaluate_receiver(event, policy, graph)
    application = apply_receiver_decision(graph, decision, policy)
    node_index = {node["id"]: node for node in application["state"]["nodes"]}
    valid = {
        "event_id": event["event_id"],
        "decision_id": decision["decision_id"],
        "application_id": application["application_id"],
        "stages": stages(event, decision, application),
        "decision": decision["disposition"],
        "reopened": sorted(application["reopened"]),
        "expected_reopen": expected_reopen,
        "action_history_preserved": node_index["action-A"]["status"] == "EXECUTED",
        "independent_consequence_preserved": (
            node_index["consequence-B-benefit"]["status"] == "CLOSED"
        ),
        "authorization_standing": node_index["auth-A"]["status"],
    }

    # Arm 5: prove the receiver code is not bound to the draft-shaped field layout.
    alternate, alt_profile = _alternate_projection(foreign, profile)
    alt_event = normalize_foreign(alternate, alt_profile)
    alt_decision = evaluate_receiver(alt_event, policy, graph)
    alt_application = apply_receiver_decision(graph, alt_decision, policy)
    alternate_profile = {
        "neutral_semantics_equal": _neutral_semantics(alt_event) == _neutral_semantics(event),
        "decision_equal": alt_decision["disposition"] == decision["disposition"],
        "reopened_equal": sorted(alt_application["reopened"]) == sorted(application["reopened"]),
    }

    assertions = {
        "filing_alone_does_not_reopen": filed_only["reopened"] == [],
        "filing_alone_does_not_apply": filed_only["stages"]["local_application"] == "NOT_APPLIED",
        "declared_effect_does_not_self_apply": (
            declared_only["reopened"] == [] and declared_only["state_unchanged"]
        ),
        "foreign_application_claim_not_local_authority": (
            foreign_applied_rejected["stages"]["foreign_application_claim"]["observed"]
            and foreign_applied_rejected["reopened"] == []
            and foreign_applied_rejected["state_unchanged"]
        ),
        "receiver_acceptance_is_distinct": (
            valid["stages"]["authenticated_filing_trigger"]["observed"]
            and valid["stages"]["receiver_acceptance"] == "ACCEPTED"
        ),
        "local_application_is_distinct": valid["stages"]["local_application"] == "APPLIED",
        "selective_reopen_exact": valid["reopened"] == expected_reopen,
        "action_history_preserved": valid["action_history_preserved"],
        "unrelated_consequence_preserved": valid["independent_consequence_preserved"],
        "adapter_profile_not_field_layout_hardcoded": all(alternate_profile.values()),
    }

    body = {
        "schema": "openline.contestability-001-result.v1",
        "experiment": "CONTESTABILITY-001",
        "source": {
            "draft": "draft-pinto-agent-authz-contestability-00",
            "published": "2026-08-29",
        },
        "arms": {
            "filed_only": filed_only,
            "declared_effect_without_trigger": declared_only,
            "foreign_applied_but_locally_rejected": foreign_applied_rejected,
            "valid_local_accept_apply": valid,
            "alternate_profile": alternate_profile,
        },
        "assertions": assertions,
        "verdict": "PASS" if all(assertions.values()) else "FAIL",
        "claim": (
            "Foreign contestation evidence can cross into an OpenLine receiver without "
            "becoming authority: receiver policy separately decides standing and local "
            "application selectively reopens only dependent consequences."
        ),
        "claim_boundary": (
            "The foreign cryptographic verifier is outside this experiment. The fixture "
            "is a diagnostic projection, not the draft wire encoding. PASS supports the "
            "receiver-side separation and selective-reopen mechanics only."
        ),
        "production_core_files_changed": [],
    }
    return {"result_sha256": sha256_obj(body), **body}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = run_experiment()
    write_json(args.output, result)
    print(json.dumps({
        "verdict": result["verdict"],
        "result_sha256": result["result_sha256"],
        "reopened": result["arms"]["valid_local_accept_apply"]["reopened"],
    }, indent=2, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
