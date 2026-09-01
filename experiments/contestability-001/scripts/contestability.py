from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


ADAPTER_SCHEMA = "openline.foreign-contestation-adapter-profile.v1"
EVENT_SCHEMA = "openline.foreign-contestation-event.v1"
POLICY_SCHEMA = "openline.contestation-receiver-policy.v1"
DECISION_SCHEMA = "openline.contestation-standing-decision.v1"
APPLICATION_SCHEMA = "openline.contestation-application.v1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def content_id(prefix: str, body: dict[str, Any]) -> str:
    return f"{prefix}:sha256:{sha256_obj(body)}"


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _path(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if not part:
            raise ValueError("adapter path contains an empty component")
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"adapter field missing: {dotted}")
        current = current[part]
    return current


_REQUIRED_NEUTRAL_FIELDS = {
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
}


def normalize_foreign(artifact: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Project a foreign verifier result into an OpenLine-neutral evidence event.

    The code knows only the neutral field contract. Foreign field locations live
    entirely in the adapter profile, making the draft a replaceable substrate.
    Normalization never changes receiver state.
    """
    if profile.get("schema") != ADAPTER_SCHEMA:
        raise ValueError("unsupported adapter profile")
    fields = profile.get("fields")
    if not isinstance(fields, dict):
        raise ValueError("adapter profile has no fields map")
    missing = sorted(_REQUIRED_NEUTRAL_FIELDS - set(fields))
    extra = sorted(set(fields) - _REQUIRED_NEUTRAL_FIELDS)
    if missing or extra:
        raise ValueError(f"adapter neutral field mismatch: missing={missing} extra={extra}")

    neutral = {name: _path(artifact, str(fields[name])) for name in sorted(fields)}
    body = {
        "schema": EVENT_SCHEMA,
        "adapter_profile_id": str(profile.get("profile_id", "")),
        "foreign_artifact_sha256": sha256_obj(artifact),
        "authorization_ref": str(neutral["authorization_ref"]),
        "forum_ref": str(neutral["forum_ref"]),
        "standing_policy_ref": str(neutral["standing_policy_ref"]),
        "filer_role": str(neutral["filer_role"]),
        "window_state": str(neutral["window_state"]),
        "foreign_signature_valid": bool(neutral["foreign_signature_valid"]),
        "binding_valid": bool(neutral["binding_valid"]),
        "forum_acknowledged": bool(neutral["forum_acknowledged"]),
        "filing_authenticated": bool(neutral["filing_authenticated"]),
        "stages": {
            "issuer_declared_effect": {
                "observed": neutral["declared_effect"] is not None,
                "value": neutral["declared_effect"],
            },
            "executor_acceptance": {
                "observed": bool(neutral["executor_acceptance"]),
            },
            "authenticated_filing_trigger": {
                "observed": bool(neutral["filing_authenticated"]),
            },
            "foreign_application_claim": {
                "observed": bool(neutral["foreign_application"]),
            },
            "receiver_acceptance": "NOT_EVALUATED",
            "local_application": "NOT_APPLIED",
        },
        # These are evidence fields, not transition instructions.
        "declared_effect": neutral["declared_effect"],
        "executor_acceptance": bool(neutral["executor_acceptance"]),
        "foreign_application": bool(neutral["foreign_application"]),
    }
    return {"event_id": content_id("foreign-contestation-event", body), **body}


def _nodes(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("graph nodes missing")
    result = {}
    for node in nodes:
        if not isinstance(node, dict) or not node.get("id"):
            raise ValueError("invalid graph node")
        node_id = str(node["id"])
        if node_id in result:
            raise ValueError(f"duplicate graph node: {node_id}")
        result[node_id] = node
    return result


def _rule_check(event: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    field = str(rule.get("field", ""))
    if field not in event:
        return {"field": field, "ok": False, "reason": "FIELD_MISSING"}
    observed = event[field]
    op = rule.get("op")
    expected = rule.get("value")
    if op == "equals":
        ok = observed == expected
    elif op == "in":
        ok = isinstance(expected, list) and observed in expected
    else:
        raise ValueError(f"unsupported receiver rule op: {op}")
    return {
        "field": field,
        "op": op,
        "expected": expected,
        "observed": observed,
        "ok": ok,
    }


def evaluate_receiver(
    event: dict[str, Any],
    policy: dict[str, Any],
    graph: dict[str, Any],
) -> dict[str, Any]:
    """Make the receiver-owned standing decision without applying consequences."""
    if event.get("schema") != EVENT_SCHEMA:
        raise ValueError("unsupported foreign event")
    if policy.get("schema") != POLICY_SCHEMA:
        raise ValueError("unsupported receiver policy")

    nodes = _nodes(graph)
    auth_id = str(event["authorization_ref"])
    auth = nodes.get(auth_id)
    transition = dict(policy.get("transition", {}))
    checks = [_rule_check(event, dict(rule)) for rule in policy.get("requirements", [])]
    checks.append({
        "field": "authorization_ref",
        "op": "exists_locally",
        "observed": auth_id,
        "ok": auth is not None and auth.get("kind") == "AUTHORIZATION",
    })
    checks.append({
        "field": "authorization_status",
        "op": "equals",
        "expected": transition.get("from"),
        "observed": auth.get("status") if auth else None,
        "ok": auth is not None and auth.get("status") == transition.get("from"),
    })

    accepted = all(bool(row["ok"]) for row in checks)
    body = {
        "schema": DECISION_SCHEMA,
        "event_id": str(event["event_id"]),
        "foreign_artifact_sha256": str(event["foreign_artifact_sha256"]),
        "authorization_ref": auth_id,
        "receiver_policy_id": str(policy.get("policy_id", "")),
        "accepted": accepted,
        "disposition": "ACCEPT_STANDING_CHANGE" if accepted else "NO_STANDING_CHANGE",
        "transition": (
            {"from": transition.get("from"), "to": transition.get("to")}
            if accepted
            else None
        ),
        "checks": checks,
        "foreign_effect_evidence_not_authority": {
            "declared_effect": event.get("declared_effect"),
            "executor_acceptance": bool(event.get("executor_acceptance")),
            "foreign_application": bool(event.get("foreign_application")),
        },
        "application_state": "NOT_APPLIED",
    }
    return {"decision_id": content_id("contestation-standing-decision", body), **body}


def _descendants(graph: dict[str, Any], root: str) -> set[str]:
    nodes = _nodes(graph)
    if root not in nodes:
        raise ValueError(f"unknown root: {root}")
    children: dict[str, list[str]] = defaultdict(list)
    for edge in graph.get("edges", []):
        left = str(edge["from"])
        right = str(edge["to"])
        if left not in nodes or right not in nodes:
            raise ValueError(f"edge references unknown node: {left}->{right}")
        children[left].append(right)
    seen = {root}
    queue = deque([root])
    while queue:
        current = queue.popleft()
        for child in sorted(children.get(current, [])):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    seen.remove(root)
    return seen


def apply_receiver_decision(
    graph: dict[str, Any],
    decision: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Apply a receiver decision. A rejected/not-yet-made decision is a no-op."""
    if decision.get("schema") != DECISION_SCHEMA:
        raise ValueError("unsupported receiver decision")
    if policy.get("schema") != POLICY_SCHEMA:
        raise ValueError("unsupported receiver policy")

    before = copy.deepcopy(graph)
    after = copy.deepcopy(graph)
    nodes = _nodes(after)
    auth_id = str(decision["authorization_ref"])
    reopenable = set(map(str, policy.get("reopenable_kinds", [])))
    reopen_from = set(map(str, policy.get("reopen_from_statuses", [])))
    reopened: list[str] = []
    affected_nonreopenable: list[str] = []

    if decision.get("accepted"):
        transition = dict(decision.get("transition") or {})
        auth = nodes[auth_id]
        if auth.get("status") != transition.get("from"):
            raise ValueError("authorization standing changed after receiver decision")
        auth["status"] = transition.get("to")

        for node_id in sorted(_descendants(after, auth_id)):
            node = nodes[node_id]
            if node.get("kind") in reopenable and node.get("status") in reopen_from:
                node["status"] = "REOPEN"
                reopened.append(node_id)
            else:
                affected_nonreopenable.append(node_id)

    before_nodes = _nodes(before)
    after_nodes = _nodes(after)
    unrelated_unchanged = sorted(
        node_id
        for node_id in before_nodes
        if node_id != auth_id
        and node_id not in set(_descendants(before, auth_id))
        and before_nodes[node_id] == after_nodes[node_id]
    )
    body = {
        "schema": APPLICATION_SCHEMA,
        "decision_id": str(decision["decision_id"]),
        "receiver_policy_id": str(policy.get("policy_id", "")),
        "applied": bool(decision.get("accepted")),
        "authorization_ref": auth_id,
        "reopened": reopened,
        "affected_nonreopenable": affected_nonreopenable,
        "unrelated_unchanged": unrelated_unchanged,
        "state_before_sha256": sha256_obj(before),
        "state_after_sha256": sha256_obj(after),
    }
    return {
        "application_id": content_id("contestation-application", body),
        **body,
        "state": after,
    }


def stages(event: dict[str, Any], decision: dict[str, Any] | None, application: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "issuer_declared_effect": event["stages"]["issuer_declared_effect"],
        "executor_acceptance": event["stages"]["executor_acceptance"],
        "authenticated_filing_trigger": event["stages"]["authenticated_filing_trigger"],
        "foreign_application_claim": event["stages"]["foreign_application_claim"],
        "receiver_acceptance": (
            "ACCEPTED" if decision and decision.get("accepted")
            else "REJECTED" if decision
            else "NOT_EVALUATED"
        ),
        "local_application": (
            "APPLIED" if application and application.get("applied")
            else "NOT_APPLIED"
        ),
    }
