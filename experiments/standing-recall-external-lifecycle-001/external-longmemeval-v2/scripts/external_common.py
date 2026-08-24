from __future__ import annotations

import hashlib
import importlib.util
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
EXTERNAL_ROOT = HERE.parent
SRE_ROOT = EXTERNAL_ROOT.parent
FROZEN_STANDING = SRE_ROOT / "scripts" / "standing_recall.py"

EVENT_TYPES = ("EXPIRE", "REVOKE", "SUPERSEDE", "CORRECT")
ACCEPTED = "ACCEPTED"
TARGET_EPISODES = 40
TARGET_TRAJECTORIES = 5


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line {line_no} is not an object")
        rows.append(value)
    return rows


def _load_frozen_standing_module():
    if not FROZEN_STANDING.exists():
        raise RuntimeError(f"frozen standing implementation missing: {FROZEN_STANDING}")
    spec = importlib.util.spec_from_file_location("sre001_frozen_standing", FROZEN_STANDING)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load frozen SRE-001 standing module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def eligible_trajectory(row: dict[str, Any]) -> bool:
    trajectory_id = row.get("id")
    domain = row.get("domain")
    environment = row.get("environment")
    states = row.get("states")
    if not isinstance(trajectory_id, str) or not trajectory_id:
        return False
    if not isinstance(domain, str) or not domain:
        return False
    if not isinstance(environment, str) or not environment:
        return False
    if not isinstance(states, list) or len(states) < 2:
        return False
    usable = [state for state in states if isinstance(state, dict) and isinstance(state.get("url"), str) and state.get("url")]
    return len(usable) >= 2


def select_trajectories(rows: list[dict[str, Any]], count: int = TARGET_TRAJECTORIES) -> list[dict[str, Any]]:
    eligible = sorted((row for row in rows if eligible_trajectory(row)), key=lambda row: str(row["id"]))
    if len(eligible) < count:
        raise ValueError(f"need at least {count} structurally eligible external trajectories; found {len(eligible)}")
    return eligible[:count]


def select_anchor_states(row: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    states = row["states"]
    valid = [(idx, state) for idx, state in enumerate(states) if isinstance(state, dict) and isinstance(state.get("url"), str) and state.get("url")]
    if len(valid) < 2:
        raise ValueError(f"trajectory {row.get('id')} has fewer than two usable state URLs")
    return [valid[0], valid[-1]]


def select_replacement_state(row: dict[str, Any], chosen_index: int) -> tuple[int, dict[str, Any]]:
    states = row["states"]
    candidates = [
        (idx, state)
        for idx, state in enumerate(states)
        if idx != chosen_index and isinstance(state, dict) and isinstance(state.get("url"), str) and state.get("url")
    ]
    if candidates:
        return candidates[-1]
    chosen = states[chosen_index]
    replacement = dict(chosen)
    replacement["url"] = f"{chosen['url']}#replacement"
    return chosen_index, replacement


def _evidence(eid: str, facets: dict[str, Any], *, before: str = ACCEPTED, after: str = ACCEPTED) -> dict[str, Any]:
    return {
        "id": eid,
        "kind": "evidence",
        "before": {"standing": before, "facets": facets},
        "after": {"standing": after, "facets": facets},
    }


def _decision(
    did: str,
    requires: list[dict[str, Any]],
    outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {"id": did, "kind": "decision", "requires": requires, "outputs": outputs}


def _req(facet: str, equals: Any, bindings: list[dict[str, Any]]) -> dict[str, Any]:
    return {"facet": facet, "equals": equals, "bindings": bindings}


def _binding(source: str, facet: str, equals: Any | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"source": source, "facet": facet}
    if equals is not None:
        out["equals"] = equals
    return out


def build_episode(row: dict[str, Any], event_type: str, source_pins: dict[str, Any], *, anchor_ordinal: int, state_index: int, state: dict[str, Any]) -> dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unsupported event type: {event_type}")
    idx = state_index
    replacement_idx, replacement_state = select_replacement_state(row, idx)
    trajectory_id = str(row["id"])
    environment = row["environment"]
    domain = row["domain"]
    state_url = state["url"]
    outcome = row.get("outcome")

    root_after = {
        "EXPIRE": "EXPIRED",
        "REVOKE": "REVOKED",
        "SUPERSEDE": "SUPERSEDED",
        "CORRECT": "CORRECTED",
    }[event_type]

    evidence = [
        _evidence(
            "E1",
            {
                "environment": environment,
                "domain": domain,
                "state_url": state_url,
                "state_step": state.get("step", state.get("state_index", idx)),
            },
            after=root_after,
        ),
        _evidence(
            "E2",
            {
                "environment": environment,
                "domain": domain,
                "outcome": outcome,
                "start_url": row.get("start_url"),
            },
        ),
    ]

    if event_type in {"SUPERSEDE", "CORRECT"}:
        evidence.append(
            _evidence(
                "E1R",
                {
                    "environment": environment,
                    "domain": domain,
                    "state_url": replacement_state["url"],
                    "state_step": replacement_state.get("step", replacement_state.get("state_index", replacement_idx)),
                },
                before="UNAVAILABLE",
                after=ACCEPTED,
            )
        )

    decisions = [
        _decision(
            "D1",
            [
                _req(
                    "environment",
                    environment,
                    [_binding("E1", "environment"), _binding("E2", "environment")],
                )
            ],
            {
                "core_environment": {
                    "value": environment,
                    "bindings": [_binding("E1", "environment"), _binding("E2", "environment")],
                },
                "state_url": {
                    "value": state_url,
                    "bindings": [_binding("E1", "state_url")],
                },
            },
        ),
        _decision(
            "D2",
            [
                _req(
                    "state_url",
                    state_url,
                    [_binding("D1", "state_url")],
                )
            ],
            {
                "authorization": {
                    "value": "RELY_ON_STATE_URL",
                    "bindings": [_binding("D1", "state_url", state_url)],
                }
            },
        ),
        _decision(
            "D3",
            [
                _req(
                    "core_environment",
                    environment,
                    [_binding("D1", "core_environment")],
                )
            ],
            {
                "authorization": {
                    "value": environment,
                    "bindings": [_binding("D1", "core_environment")],
                }
            },
        ),
        _decision(
            "D4",
            [_req("domain", domain, [_binding("E2", "domain")])],
            {
                "domain": {
                    "value": domain,
                    "bindings": [_binding("E2", "domain")],
                }
            },
        ),
    ]

    record_sha = sha256_bytes(canonical_bytes(row))
    state_sha = sha256_bytes(canonical_bytes(state))
    episode = {
        "episode_id": f"lmev2-{trajectory_id}-a{anchor_ordinal}-{event_type.lower()}",
        "experiment": "standing-recall-external-lifecycle-001",
        "external_source": {
            "source_family": "LongMemEval-V2",
            "trajectory_id": trajectory_id,
            "domain": domain,
            "environment": environment,
            "source_record_sha256": record_sha,
            "anchor_ordinal": anchor_ordinal,
            "selected_state_index": idx,
            "selected_state_sha256": state_sha,
            "selection_rule": "LEXICOGRAPHIC_FIRST_5_ELIGIBLE_THEN_FIRST_AND_LAST_USABLE_STATE",
            "github_repository": source_pins["longmemeval_v2_github"]["repository"],
            "github_commit": source_pins["longmemeval_v2_github"]["commit"],
            "hf_repository": source_pins["longmemeval_v2_hf"]["repository"],
            "hf_revision": source_pins["longmemeval_v2_hf"]["revision"],
            "hf_path": source_pins["longmemeval_v2_hf"]["trajectory_sample_path"],
            "excerpt_only": True,
        },
        "lifecycle_injection": {
            "synthetic": True,
            "post_finalization": True,
            "event_type": event_type,
            "root_evidence": "E1",
            "content_bytes_changed": False,
            "replacement_state_index": replacement_idx if event_type in {"SUPERSEDE", "CORRECT"} else None,
            "replacement_state_sha256": (
                sha256_bytes(canonical_bytes(replacement_state)) if event_type in {"SUPERSEDE", "CORRECT"} else None
            ),
            "boundary": "The source trajectory is external. The later standing event is a controlled synthetic lifecycle injection; it is not a natural LongMemEval-V2 label.",
        },
        "event": {"type": event_type, "roots": ["E1"]},
        "evidence": evidence,
        "decisions": decisions,
    }
    return episode


def build_adaptation(rows: list[dict[str, Any]], source_pins: dict[str, Any], adapter_policy: dict[str, Any]) -> dict[str, Any]:
    required = int(adapter_policy["source_selection"]["trajectory_count"])
    selected = select_trajectories(rows, required)
    episodes = []
    for row in selected:
        for anchor_ordinal, (state_index, state) in enumerate(select_anchor_states(row)):
            for event in EVENT_TYPES:
                episodes.append(build_episode(row, event, source_pins, anchor_ordinal=anchor_ordinal, state_index=state_index, state=state))
    distribution = Counter(ep["event"]["type"] for ep in episodes)
    return {
        "schema": "openline.standing-recall-external-adaptation.v1",
        "experiment": "standing-recall-external-lifecycle-001",
        "adapter_id": adapter_policy["adapter_id"],
        "source_family": "LongMemEval-V2",
        "source_kind": "PINNED_PUBLIC_SAMPLE_EXCERPTS",
        "selected_trajectory_ids": [str(row["id"]) for row in selected],
        "selected_anchor_count": sum(len(select_anchor_states(row)) for row in selected),
        "episode_count": len(episodes),
        "event_distribution": dict(sorted(distribution.items())),
        "episodes": episodes,
        "policy_authority": "NONE",
        "claim_boundary": [
            "This is an external-source adaptation over pinned LongMemEval-V2 sample trajectory excerpts, not the full LongMemEval-V2 benchmark.",
            "The EXPIRE/REVOKE/SUPERSEDE/CORRECT events are controlled post-finalization injections, not LongMemEval-V2 labels.",
            "No DGRR or MemoRepair author implementation is executed by this adapter.",
        ],
    }


def adaptation_manifest(adaptation: dict[str, Any], source_file: str | Path, source_pins: dict[str, Any]) -> dict[str, Any]:
    mappings = []
    for ep in adaptation["episodes"]:
        src = ep["external_source"]
        mappings.append(
            {
                "episode_id": ep["episode_id"],
                "trajectory_id": src["trajectory_id"],
                "source_record_sha256": src["source_record_sha256"],
                "anchor_ordinal": src["anchor_ordinal"],
                "selected_state_index": src["selected_state_index"],
                "selected_state_sha256": src["selected_state_sha256"],
                "event_type": ep["event"]["type"],
            }
        )
    return {
        "schema": "openline.standing-recall-external-source-manifest.v1",
        "experiment": adaptation["experiment"],
        "source_file_sha256": sha256_file(source_file),
        "source_pins": source_pins,
        "adaptation_sha256": sha256_bytes(canonical_bytes(adaptation)),
        "mapping_count": len(mappings),
        "mappings": mappings,
        "policy_authority": "NONE",
    }


def _influence_edges(episode: dict[str, Any]) -> list[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for decision in episode["decisions"]:
        did = decision["id"]
        for req in decision["requires"]:
            for binding in req["bindings"]:
                edges.add((binding["source"], did))
        for output in decision.get("outputs", {}).values():
            for binding in output["bindings"]:
                edges.add((binding["source"], did))
    return sorted(edges)


def _decision_ids(episode: dict[str, Any]) -> set[str]:
    return {item["id"] for item in episode["decisions"]}


def _descendants(episode: dict[str, Any], roots: list[str]) -> set[str]:
    children: dict[str, set[str]] = defaultdict(set)
    for left, right in _influence_edges(episode):
        children[left].add(right)
    seen = set(roots)
    queue = deque(roots)
    while queue:
        current = queue.popleft()
        for child in sorted(children.get(current, ())):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return seen & _decision_ids(episode)


def _predecessors(episode: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for left, right in _influence_edges(episode):
        result[right].add(left)
    return result


def _topological(episode: dict[str, Any]) -> list[str]:
    ids = _decision_ids(episode)
    pred = _predecessors(episode)
    indegree = {did: sum(1 for src in pred.get(did, ()) if src in ids) for did in ids}
    children: dict[str, set[str]] = defaultdict(set)
    for did in ids:
        for src in pred.get(did, ()):
            if src in ids:
                children[src].add(did)
    queue = deque(sorted(did for did, n in indegree.items() if n == 0))
    out: list[str] = []
    while queue:
        did = queue.popleft()
        out.append(did)
        for child in sorted(children.get(did, ())):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(out) != len(ids):
        raise ValueError("cyclic decision graph")
    return out


def _evidence_alive(episode: dict[str, Any], eid: str) -> bool:
    for evidence in episode["evidence"]:
        if evidence["id"] == eid:
            return evidence["after"]["standing"] == ACCEPTED
    return False


def dgrr_contract_prediction(episode: dict[str, Any]) -> dict[str, Any]:
    """DGRR contract adaptation with conservative outside-affected support.

    This is not author code. It mirrors the paper's diagnosed-root trace plus
    conservative independent-support rule: affected nodes do not recursively
    validate one another as independent support.
    """

    roots = list(episode["event"]["roots"])
    affected = _descendants(episode, roots)
    pred = _predecessors(episode)
    ids = _decision_ids(episode)
    reopened: set[str] = set()
    for did in _topological(episode):
        if did not in affected:
            continue
        independent = False
        for src in pred.get(did, ()):
            if src in roots or src in affected:
                continue
            if src in ids:
                independent = True
                break
            if _evidence_alive(episode, src):
                independent = True
                break
        if not independent:
            reopened.add(did)
    return {
        "system": "DGRR_CONTRACT_NODE_SUPPORT_EXTERNAL_V1",
        "reopen": sorted(reopened),
        "replay": sorted(reopened),
        "analysis_surface": sorted(affected),
        "boundary": "Paper-contract adaptation, not DGRR author code or the paper's private adapted benchmark.",
    }


def memorepair_property_validation_prediction(episode: dict[str, Any]) -> dict[str, Any]:
    """Strong MemoRepair contract adaptation with property-aware validation.

    Barrier-first invalidates the complete affected descendant set. Repair then
    validates reconstructed successors with the exact requirement/output
    properties. This intentionally gives the MemoRepair-style baseline a strong
    validator so OpenLine cannot win merely because the baseline is node-blind.
    Replay surface remains the complete withdrawn repair set.
    """

    frozen = _load_frozen_standing_module()
    roots = list(episode["event"]["roots"])
    affected = _descendants(episode, roots)
    oracle = frozen.StandingOracle(episode, "after")
    reopened = sorted(did for did in affected if not oracle.decision_stands(did))
    return {
        "system": "MEMOREPAIR_CONTRACT_PROPERTY_VALIDATION_EXTERNAL_V1",
        "reopen": reopened,
        "replay": sorted(affected),
        "analysis_surface": sorted(affected),
        "boundary": "Strong paper-contract adaptation with an exact property-aware validator; not MemoRepair author code, min-cut implementation, or reported benchmark.",
    }


def openline_external_prediction(episode: dict[str, Any]) -> dict[str, Any]:
    frozen = _load_frozen_standing_module()
    pred = frozen.openline_prediction(episode)
    pred = dict(pred)
    pred["system"] = "OPENLINE_STANDING_PROPAGATION_EXTERNAL_V1"
    return pred


def score_system(episodes: list[dict[str, Any]], predictor: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    frozen = _load_frozen_standing_module()
    return frozen.score_system(episodes, predictor)


def run_external_benchmark(adaptation: dict[str, Any]) -> dict[str, Any]:
    episodes = adaptation["episodes"]
    systems = [
        score_system(episodes, dgrr_contract_prediction),
        score_system(episodes, memorepair_property_validation_prediction),
        score_system(episodes, openline_external_prediction),
    ]
    return {
        "schema": "openline.standing-recall-external-score.v1",
        "experiment": adaptation["experiment"],
        "adaptation_sha256": sha256_bytes(canonical_bytes(adaptation)),
        "systems": systems,
        "policy_authority": "NONE",
        "claim_boundary": [
            "The source records are external LongMemEval-V2 sample excerpts; lifecycle events are controlled synthetic injections.",
            "DGRR and MemoRepair comparisons are paper-contract adaptations, not author implementations or reported benchmark numbers.",
            "The MemoRepair contract baseline receives an exact property-aware validator and is intentionally strong.",
        ],
    }


def _system(score: dict[str, Any], system_id: str) -> dict[str, Any]:
    for item in score["systems"]:
        if item["system"] == system_id:
            return item
    raise KeyError(system_id)


def grade_external(adaptation: dict[str, Any], score: dict[str, Any], promotion: dict[str, Any]) -> dict[str, Any]:
    openline = _system(score, "OPENLINE_STANDING_PROPAGATION_EXTERNAL_V1")
    baselines = [item for item in score["systems"] if item["system"] != openline["system"]]
    event_counts = Counter(ep["event"]["type"] for ep in adaptation["episodes"])
    independent_support_cases = sum(
        1
        for ep in adaptation["episodes"]
        if any(
            decision["id"] == "D1" and len(decision["requires"][0]["bindings"]) >= 2
            for decision in ep["decisions"]
        )
    )
    property_specific_cases = sum(
        1 for ep in adaptation["episodes"] if {"D2", "D3"}.issubset({d["id"] for d in ep["decisions"]})
    )

    requirements = promotion["promotion_requirements"]
    recall_min = float(requirements["openline_recall_minimum"])
    preservation_min = float(requirements["openline_preservation_minimum"])
    max_extra_fn = int(requirements["additional_missed_reopenings_vs_strongest_baseline_maximum"])
    max_extra_fp = int(requirements["additional_false_reopenings_vs_strongest_baseline_maximum"])
    replay_min = float(requirements["replay_surface_reduction_vs_best_accuracy_matching_baseline_minimum"])

    strongest_accuracy = sorted(baselines, key=lambda item: (item["fn"] + item["fp"], item["replay_surface"], item["system"]))[0]
    extra_fn = openline["fn"] - strongest_accuracy["fn"]
    extra_fp = openline["fp"] - strongest_accuracy["fp"]

    accuracy_matching = [
        item
        for item in baselines
        if item["tp"] == openline["tp"]
        and item["fp"] == openline["fp"]
        and item["fn"] == openline["fn"]
        and item["tn"] == openline["tn"]
    ]
    best_matching = min(accuracy_matching, key=lambda item: item["replay_surface"]) if accuracy_matching else None
    replay_reduction = None
    if best_matching and best_matching["replay_surface"] > 0:
        replay_reduction = (best_matching["replay_surface"] - openline["replay_surface"]) / best_matching["replay_surface"]

    structural_checks = {
        "minimum_external_episodes": len(adaptation["episodes"]) >= int(promotion["minimum_external_episodes"]),
        "minimum_independent_support_cases": independent_support_cases >= int(promotion["minimum_independent_support_cases"]),
        "minimum_property_specific_downstream_cases": property_specific_cases >= int(promotion["minimum_property_specific_downstream_cases"]),
        "minimum_per_event_type": all(
            event_counts.get(event, 0) >= int(promotion["minimum_per_event_type"])
            for event in promotion["required_event_types"]
        ),
    }
    accuracy_checks = {
        "openline_recall": openline["affected_decision_recall"] >= recall_min,
        "openline_preservation": openline["unaffected_state_preservation"] >= preservation_min,
        "no_additional_missed_reopenings": extra_fn <= max_extra_fn,
        "no_additional_false_reopenings": extra_fp <= max_extra_fp,
    }
    replay_check = replay_reduction is None or replay_reduction >= replay_min

    if not all(structural_checks.values()):
        verdict = "INCOMPLETE_EXTERNAL_ADAPTATION"
    elif not all(accuracy_checks.values()):
        verdict = "EXTERNAL_STANDING_SEPARATION_NOT_EARNED"
    elif not replay_check:
        verdict = "NO_REPAIR_SURFACE_SEPARATION"
    else:
        verdict = "EXTERNAL_STANDING_SEPARATION_ADAPTED_LONGMEMEVAL_V2"

    return {
        "schema": "openline.standing-recall-external-verdict.v1",
        "experiment": adaptation["experiment"],
        "verdict": verdict,
        "status": verdict,
        "external_source_family": "LongMemEval-V2",
        "external_episode_count": len(adaptation["episodes"]),
        "unique_external_trajectories": len(set(adaptation["selected_trajectory_ids"])),
        "unique_external_state_anchors": adaptation.get("selected_anchor_count", 0),
        "event_distribution": dict(sorted(event_counts.items())),
        "independent_support_cases": independent_support_cases,
        "property_specific_downstream_cases": property_specific_cases,
        "openline": {
            "affected_decision_recall": openline["affected_decision_recall"],
            "unaffected_state_preservation": openline["unaffected_state_preservation"],
            "replay_surface": openline["replay_surface"],
            "fn": openline["fn"],
            "fp": openline["fp"],
        },
        "strongest_accuracy_baseline": strongest_accuracy["system"],
        "best_accuracy_matching_baseline": best_matching["system"] if best_matching else None,
        "best_accuracy_matching_baseline_replay_surface": best_matching["replay_surface"] if best_matching else None,
        "replay_surface_reduction_vs_best_accuracy_matching_baseline": replay_reduction,
        "structural_checks": structural_checks,
        "accuracy_checks": accuracy_checks,
        "replay_check": replay_check,
        "falsifier_readout": (
            "The strong MemoRepair contract adaptation matches OpenLine accuracy but requires a larger barrier-first repair surface. "
            "Therefore this run can support only a repair-surface/standing-lifecycle separation, not a claim that MemoRepair cannot express property-aware validation."
            if best_matching and best_matching["system"].startswith("MEMOREPAIR")
            else "No MemoRepair contract baseline matched OpenLine accuracy in this adaptation; property-semantic novelty remains unresolved without author code."
        ),
        "claim_boundary": [
            "This is not the DGRR paper's private 50-case LongMemEval-V2 adaptation.",
            "This is not the full LongMemEval-V2 benchmark; it uses 5 pinned public sample trajectory excerpts, two state anchors per trajectory, expanded into 40 controlled lifecycle episodes.",
            "The 40 lifecycle episodes are not 40 independent trajectories; they are repeated controlled interventions over 10 state anchors from 5 external trajectories.",
            "The lifecycle events are synthetic and do not estimate natural revocation frequency.",
            "DGRR and MemoRepair baselines are paper-contract adaptations, not author implementations.",
            "A successful verdict does not establish broad agent reliability, truth discovery, or rollback of irreversible external effects.",
        ],
        "policy_authority": "NONE",
    }
