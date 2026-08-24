from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path
from typing import Any

ACCEPTED = "ACCEPTED"


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


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_map(episode: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for item in episode["evidence"]:
        result[item["id"]] = item
    for item in episode["decisions"]:
        result[item["id"]] = item
    return result


def _evidence_facet_valid(
    evidence: dict[str, Any], when: str, facet: str, expected: Any
) -> bool:
    state = evidence[when]
    return state["standing"] == ACCEPTED and state.get("facets", {}).get(facet) == expected


def _decision_index(episode: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in episode["decisions"]}


class StandingOracle:
    """Receiver-owned facet standing over finalized decisions.

    This is the candidate OpenLine mechanism for SRE-001. A decision can remain
    standing while one exported facet loses support. Downstream decisions are
    evaluated against the exact facet/value they relied on, not merely against
    the upstream decision node's coarse alive/dead state.
    """

    def __init__(self, episode: dict[str, Any], when: str):
        self.episode = episode
        self.when = when
        self.sources = _source_map(episode)
        self.decisions = _decision_index(episode)
        self._decision_cache: dict[str, bool] = {}
        self._facet_cache: dict[tuple[str, str, str], bool] = {}
        self._active: set[tuple[str, str, str]] = set()

    def binding_valid(self, binding: dict[str, Any], expected: Any) -> bool:
        source_id = binding["source"]
        facet = binding["facet"]
        source_expected = binding.get("equals", expected)
        source = self.sources[source_id]
        if source["kind"] == "evidence":
            return _evidence_facet_valid(source, self.when, facet, source_expected)
        if not self.decision_stands(source_id):
            return False
        return self.decision_facet_stands(source_id, facet, source_expected)

    def requirement_valid(self, requirement: dict[str, Any]) -> bool:
        expected = requirement["equals"]
        return any(self.binding_valid(binding, expected) for binding in requirement["bindings"])

    def decision_stands(self, decision_id: str) -> bool:
        if decision_id in self._decision_cache:
            return self._decision_cache[decision_id]
        decision = self.decisions[decision_id]
        key = ("decision", decision_id, "")
        if key in self._active:
            raise ValueError(f"cyclic decision requirement involving {decision_id}")
        self._active.add(key)
        try:
            value = all(self.requirement_valid(req) for req in decision["requires"])
            self._decision_cache[decision_id] = value
            return value
        finally:
            self._active.remove(key)

    def decision_facet_stands(self, decision_id: str, facet: str, expected: Any) -> bool:
        cache_key = (decision_id, facet, json.dumps(expected, sort_keys=True))
        if cache_key in self._facet_cache:
            return self._facet_cache[cache_key]
        decision = self.decisions[decision_id]
        output = decision.get("outputs", {}).get(facet)
        if output is None or output.get("value") != expected:
            self._facet_cache[cache_key] = False
            return False
        key = ("facet", decision_id, facet)
        if key in self._active:
            raise ValueError(f"cyclic output facet involving {decision_id}.{facet}")
        self._active.add(key)
        try:
            value = any(self.binding_valid(binding, expected) for binding in output["bindings"])
            self._facet_cache[cache_key] = value
            return value
        finally:
            self._active.remove(key)

    def standings(self) -> dict[str, bool]:
        return {decision_id: self.decision_stands(decision_id) for decision_id in self.decisions}


def derive_influence_edges(episode: dict[str, Any]) -> list[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for decision in episode["decisions"]:
        did = decision["id"]
        for requirement in decision["requires"]:
            for binding in requirement["bindings"]:
                edges.add((binding["source"], did))
        for output in decision.get("outputs", {}).values():
            for binding in output["bindings"]:
                edges.add((binding["source"], did))
    return sorted(edges)


def descendants(episode: dict[str, Any], roots: list[str]) -> set[str]:
    children: dict[str, set[str]] = defaultdict(set)
    for left, right in derive_influence_edges(episode):
        children[left].add(right)
    seen = set(roots)
    queue = deque(roots)
    while queue:
        current = queue.popleft()
        for child in sorted(children.get(current, ())):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    decision_ids = set(_decision_index(episode))
    return seen & decision_ids


def _node_predecessors(episode: dict[str, Any]) -> dict[str, set[str]]:
    pred: dict[str, set[str]] = defaultdict(set)
    for left, right in derive_influence_edges(episode):
        pred[right].add(left)
    return pred


def _evidence_node_alive(episode: dict[str, Any], evidence_id: str) -> bool:
    evidence = next(item for item in episode["evidence"] if item["id"] == evidence_id)
    return evidence["after"]["standing"] == ACCEPTED


def _topological_decisions(episode: dict[str, Any]) -> list[str]:
    decision_ids = set(_decision_index(episode))
    pred = _node_predecessors(episode)
    indegree = {did: 0 for did in decision_ids}
    children: dict[str, set[str]] = defaultdict(set)
    for did in decision_ids:
        for source in pred.get(did, ()):
            if source in decision_ids:
                indegree[did] += 1
                children[source].add(did)
    queue = deque(sorted([did for did, degree in indegree.items() if degree == 0]))
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for child in sorted(children.get(node, ())):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(decision_ids):
        raise ValueError("decision dependency graph contains a cycle")
    return order


def dgrr_style_prediction(episode: dict[str, Any]) -> dict[str, Any]:
    """Paper-inspired node-level rollback abstraction, not author code.

    Starting from the diagnosed/invalidation root, it traces descendants and
    preserves a candidate if an unaffected or already-preserved predecessor is
    still trusted. This mirrors the paper's reachability + independent-support
    shape while intentionally staying at node granularity. It therefore tests
    whether facet-specific standing adds anything beyond that abstraction.
    """

    roots = list(episode["event"]["roots"])
    affected = descendants(episode, roots)
    pred = _node_predecessors(episode)
    invalid_nodes = set(roots)
    reopened: set[str] = set()
    replayed: set[str] = set()

    for did in _topological_decisions(episode):
        if did not in affected:
            continue
        predecessors = pred.get(did, set())
        surviving = False
        for source in predecessors:
            if source in invalid_nodes:
                continue
            if source in _decision_index(episode):
                if source not in reopened:
                    surviving = True
                    break
            elif _evidence_node_alive(episode, source):
                surviving = True
                break
        if surviving:
            continue
        reopened.add(did)
        invalid_nodes.add(did)
        replayed.add(did)

    return {
        "system": "DGRR_STYLE_NODE_SUPPORT_V1",
        "reopen": sorted(reopened),
        "replay": sorted(replayed),
        "analysis_surface": sorted(affected),
        "boundary": "Paper-inspired node-level abstraction; not the authors' implementation or reported benchmark.",
    }


def memorepair_style_prediction(episode: dict[str, Any]) -> dict[str, Any]:
    """Paper-inspired barrier-first cascade abstraction, not author code.

    The entire invalidated descendant cascade is withdrawn first. A decision is
    republished if at least one predecessor node is still servable after repair.
    The abstraction preserves MemoRepair's barrier/predecessor-closure shape but
    does not add facet-level receiver standing to its validation oracle.
    """

    roots = list(episode["event"]["roots"])
    affected = descendants(episode, roots)
    pred = _node_predecessors(episode)
    servable_decisions: set[str] = set()
    reopened: set[str] = set()
    replayed: set[str] = set(affected)

    # unaffected decisions remain servable
    for did in _decision_index(episode):
        if did not in affected:
            servable_decisions.add(did)

    for did in _topological_decisions(episode):
        if did not in affected:
            continue
        predecessors = pred.get(did, set())
        can_republish = False
        for source in predecessors:
            if source in roots:
                continue
            if source in _decision_index(episode):
                if source in servable_decisions:
                    can_republish = True
                    break
            elif _evidence_node_alive(episode, source):
                can_republish = True
                break
        if can_republish:
            servable_decisions.add(did)
        else:
            reopened.add(did)

    return {
        "system": "MEMOREPAIR_STYLE_CASCADE_V1",
        "reopen": sorted(reopened),
        "replay": sorted(replayed),
        "analysis_surface": sorted(affected),
        "boundary": "Paper-inspired barrier/predecessor abstraction; not the authors' implementation, min-cut selector, or validation suite.",
    }


def openline_prediction(episode: dict[str, Any]) -> dict[str, Any]:
    before = StandingOracle(episode, "before").standings()
    after = StandingOracle(episode, "after").standings()
    finalized = sorted(before)
    if not all(before.values()):
        bad = [did for did, value in before.items() if not value]
        raise ValueError(f"fixture contains decision(s) not standing at finalization: {bad}")
    reopen = sorted(did for did in finalized if before[did] and not after[did])
    # Only decisions whose standing flips require replay/reopening. Standing
    # recomputation may inspect surviving nodes but does not replay them.
    return {
        "system": "OPENLINE_STANDING_PROPAGATION_V1",
        "reopen": reopen,
        "replay": reopen,
        "analysis_surface": sorted(descendants(episode, list(episode["event"]["roots"]))),
        "boundary": "Receiver-owned facet/value standing over finalized decisions; no truth oracle and no execution authority.",
    }


def gold_from_episode(episode: dict[str, Any]) -> dict[str, Any]:
    before = StandingOracle(episode, "before").standings()
    after = StandingOracle(episode, "after").standings()
    if not all(before.values()):
        raise ValueError("every scored decision must have stood before the lifecycle event")
    reopen = sorted(did for did in before if not after[did])
    survive = sorted(did for did in before if after[did])
    return {"reopen": reopen, "survive": survive}


def score_system(episodes: list[dict[str, Any]], predictor) -> dict[str, Any]:
    tp = fp = fn = tn = 0
    replay_total = 0
    analysis_total = 0
    per_episode = []
    for episode in episodes:
        gold = gold_from_episode(episode)
        pred = predictor(episode)
        universe = {item["id"] for item in episode["decisions"]}
        gold_reopen = set(gold["reopen"])
        pred_reopen = set(pred["reopen"])
        tp_e = len(gold_reopen & pred_reopen)
        fp_e = len(pred_reopen - gold_reopen)
        fn_e = len(gold_reopen - pred_reopen)
        tn_e = len((universe - gold_reopen) - pred_reopen)
        tp += tp_e
        fp += fp_e
        fn += fn_e
        tn += tn_e
        replay_total += len(pred["replay"])
        analysis_total += len(pred["analysis_surface"])
        per_episode.append(
            {
                "episode_id": episode["episode_id"],
                "event_type": episode["event"]["type"],
                "gold_reopen": sorted(gold_reopen),
                "predicted_reopen": sorted(pred_reopen),
                "replay": pred["replay"],
                "tp": tp_e,
                "fp": fp_e,
                "fn": fn_e,
                "tn": tn_e,
            }
        )
    recall = tp / (tp + fn) if tp + fn else 1.0
    preservation = tn / (tn + fp) if tn + fp else 1.0
    return {
        "system": predictor(episodes[0])["system"] if episodes else "UNKNOWN",
        "episodes": len(episodes),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "affected_decision_recall": recall,
        "unaffected_state_preservation": preservation,
        "replay_surface": replay_total,
        "analysis_surface": analysis_total,
        "per_episode": per_episode,
    }


def run_benchmark(fixture: dict[str, Any]) -> dict[str, Any]:
    episodes = fixture["episodes"]
    systems = [
        score_system(episodes, dgrr_style_prediction),
        score_system(episodes, memorepair_style_prediction),
        score_system(episodes, openline_prediction),
    ]
    return {
        "schema": "openline.standing-recall-external-lifecycle-score.v1",
        "experiment": fixture["experiment"],
        "fixture_sha256": sha256_bytes(canonical_bytes(fixture)),
        "status": "MECHANICS_ONLY_EXTERNAL_BENCHMARK_UNRUN",
        "systems": systems,
        "claim_boundary": [
            "The checked fixture is a deterministic conformance pressure test, not the DGRR or MemoRepair authors' benchmark.",
            "The DGRR-style and MemoRepair-style systems are paper-inspired abstractions, not author implementations.",
            "No external benchmark promotion is earned by this score.",
        ],
        "policy_authority": "NONE",
    }
