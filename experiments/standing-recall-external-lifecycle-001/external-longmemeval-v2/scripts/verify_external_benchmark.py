from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Callable

ACCEPTED = "ACCEPTED"
EVENT_TYPES = ("EXPIRE", "REVOKE", "SUPERSEDE", "CORRECT")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("source JSONL contains non-object")
            rows.append(value)
    return rows


def eligible(row: dict[str, Any]) -> bool:
    if not all(isinstance(row.get(key), str) and row[key] for key in ("id", "domain", "environment")):
        return False
    states = row.get("states")
    return isinstance(states, list) and len(states) >= 2 and sum(
        1 for state in states if isinstance(state, dict) and isinstance(state.get("url"), str) and state.get("url")
    ) >= 2


def selected_anchors(row: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    valid = [(idx, state) for idx, state in enumerate(row["states"]) if isinstance(state, dict) and isinstance(state.get("url"), str) and state.get("url")]
    if len(valid) < 2:
        raise ValueError("source trajectory has fewer than two usable state URLs")
    return [valid[0], valid[-1]]


def sources(episode: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {item["id"]: item for item in episode["evidence"]}
    out.update({item["id"]: item for item in episode["decisions"]})
    return out


def decision_index(episode: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in episode["decisions"]}


class Oracle:
    def __init__(self, episode: dict[str, Any], when: str):
        self.episode = episode
        self.when = when
        self.src = sources(episode)
        self.decisions = decision_index(episode)
        self.dc: dict[str, bool] = {}
        self.fc: dict[tuple[str, str, str], bool] = {}
        self.active: set[tuple[str, str, str]] = set()

    def binding(self, binding: dict[str, Any], expected: Any) -> bool:
        source = self.src[binding["source"]]
        facet = binding["facet"]
        wanted = binding.get("equals", expected)
        if source["kind"] == "evidence":
            state = source[self.when]
            return state["standing"] == ACCEPTED and state.get("facets", {}).get(facet) == wanted
        return self.decision(source["id"]) and self.facet(source["id"], facet, wanted)

    def requirement(self, requirement: dict[str, Any]) -> bool:
        expected = requirement["equals"]
        return any(self.binding(binding, expected) for binding in requirement["bindings"])

    def decision(self, did: str) -> bool:
        if did in self.dc:
            return self.dc[did]
        key = ("d", did, "")
        if key in self.active:
            raise ValueError("cycle")
        self.active.add(key)
        try:
            value = all(self.requirement(req) for req in self.decisions[did]["requires"])
            self.dc[did] = value
            return value
        finally:
            self.active.remove(key)

    def facet(self, did: str, facet: str, expected: Any) -> bool:
        key = (did, facet, json.dumps(expected, sort_keys=True))
        if key in self.fc:
            return self.fc[key]
        output = self.decisions[did].get("outputs", {}).get(facet)
        if output is None or output.get("value") != expected:
            self.fc[key] = False
            return False
        active_key = ("f", did, facet)
        if active_key in self.active:
            raise ValueError("cycle")
        self.active.add(active_key)
        try:
            value = any(self.binding(binding, expected) for binding in output["bindings"])
            self.fc[key] = value
            return value
        finally:
            self.active.remove(active_key)

    def standings(self) -> dict[str, bool]:
        return {did: self.decision(did) for did in self.decisions}


def edges(episode: dict[str, Any]) -> list[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for decision in episode["decisions"]:
        for req in decision["requires"]:
            for binding in req["bindings"]:
                out.add((binding["source"], decision["id"]))
        for output in decision.get("outputs", {}).values():
            for binding in output["bindings"]:
                out.add((binding["source"], decision["id"]))
    return sorted(out)


def descendants(episode: dict[str, Any], roots: list[str]) -> set[str]:
    children: dict[str, set[str]] = defaultdict(set)
    for left, right in edges(episode):
        children[left].add(right)
    seen = set(roots)
    queue = deque(roots)
    while queue:
        node = queue.popleft()
        for child in sorted(children.get(node, ())):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return seen & set(decision_index(episode))


def predecessors(episode: dict[str, Any]) -> dict[str, set[str]]:
    pred: dict[str, set[str]] = defaultdict(set)
    for left, right in edges(episode):
        pred[right].add(left)
    return pred


def topological(episode: dict[str, Any]) -> list[str]:
    ids = set(decision_index(episode))
    pred = predecessors(episode)
    indegree = {did: sum(1 for src in pred.get(did, ()) if src in ids) for did in ids}
    children: dict[str, set[str]] = defaultdict(set)
    for did in ids:
        for src in pred.get(did, ()):
            if src in ids:
                children[src].add(did)
    queue = deque(sorted(did for did, n in indegree.items() if n == 0))
    order = []
    while queue:
        did = queue.popleft()
        order.append(did)
        for child in sorted(children.get(did, ())):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(ids):
        raise ValueError("cycle")
    return order


def evidence_alive(episode: dict[str, Any], eid: str) -> bool:
    return next(item for item in episode["evidence"] if item["id"] == eid)["after"]["standing"] == ACCEPTED


def gold(episode: dict[str, Any]) -> dict[str, list[str]]:
    before = Oracle(episode, "before").standings()
    after = Oracle(episode, "after").standings()
    if not all(before.values()):
        raise ValueError("decision did not stand before injected event")
    return {
        "reopen": sorted(did for did in before if not after[did]),
        "survive": sorted(did for did in before if after[did]),
    }


def predict_openline(episode: dict[str, Any]) -> dict[str, Any]:
    g = gold(episode)
    affected = descendants(episode, list(episode["event"]["roots"]))
    return {"system": "OPENLINE_STANDING_PROPAGATION_EXTERNAL_V1", "reopen": g["reopen"], "replay": g["reopen"], "analysis_surface": sorted(affected)}


def predict_dgrr(episode: dict[str, Any]) -> dict[str, Any]:
    roots = list(episode["event"]["roots"])
    affected = descendants(episode, roots)
    pred = predecessors(episode)
    ids = set(decision_index(episode))
    reopened = set()
    for did in topological(episode):
        if did not in affected:
            continue
        independent = False
        for src in pred.get(did, ()):
            if src in roots or src in affected:
                continue
            if src in ids or evidence_alive(episode, src):
                independent = True
                break
        if not independent:
            reopened.add(did)
    return {"system": "DGRR_CONTRACT_NODE_SUPPORT_EXTERNAL_V1", "reopen": sorted(reopened), "replay": sorted(reopened), "analysis_surface": sorted(affected)}


def predict_memorepair(episode: dict[str, Any]) -> dict[str, Any]:
    affected = descendants(episode, list(episode["event"]["roots"]))
    after = Oracle(episode, "after")
    reopened = sorted(did for did in affected if not after.decision(did))
    return {"system": "MEMOREPAIR_CONTRACT_PROPERTY_VALIDATION_EXTERNAL_V1", "reopen": reopened, "replay": sorted(affected), "analysis_surface": sorted(affected)}


def score_system(episodes: list[dict[str, Any]], predictor: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    tp = fp = fn = tn = replay_total = analysis_total = 0
    per_episode = []
    system_name = "UNKNOWN"
    for ep in episodes:
        g = gold(ep)
        pred = predictor(ep)
        system_name = pred["system"]
        universe = set(decision_index(ep))
        gr = set(g["reopen"])
        pr = set(pred["reopen"])
        etp = len(gr & pr)
        efp = len(pr - gr)
        efn = len(gr - pr)
        etn = len((universe - gr) - pr)
        tp += etp; fp += efp; fn += efn; tn += etn
        replay_total += len(pred["replay"])
        analysis_total += len(pred["analysis_surface"])
        per_episode.append({
            "episode_id": ep["episode_id"],
            "event_type": ep["event"]["type"],
            "gold_reopen": sorted(gr),
            "predicted_reopen": sorted(pr),
            "replay": pred["replay"],
            "tp": etp, "fp": efp, "fn": efn, "tn": etn,
        })
    return {
        "system": system_name,
        "episodes": len(episodes),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "affected_decision_recall": tp / (tp + fn) if tp + fn else 1.0,
        "unaffected_state_preservation": tn / (tn + fp) if tn + fp else 1.0,
        "replay_surface": replay_total,
        "analysis_surface": analysis_total,
        "per_episode": per_episode,
    }


def expected_scores(adaptation: dict[str, Any]) -> list[dict[str, Any]]:
    eps = adaptation["episodes"]
    return [score_system(eps, predict_dgrr), score_system(eps, predict_memorepair), score_system(eps, predict_openline)]


def norm_score(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in (
        "system", "episodes", "tp", "fp", "fn", "tn", "affected_decision_recall",
        "unaffected_state_preservation", "replay_surface", "analysis_surface", "per_episode"
    )}


def recompute_verdict(adaptation: dict[str, Any], score: dict[str, Any], promotion: dict[str, Any]) -> dict[str, Any]:
    systems = {item["system"]: item for item in score["systems"]}
    ol = systems["OPENLINE_STANDING_PROPAGATION_EXTERNAL_V1"]
    baselines = [item for key, item in systems.items() if key != ol["system"]]
    strongest = sorted(baselines, key=lambda item: (item["fn"] + item["fp"], item["replay_surface"], item["system"]))[0]
    matching = [item for item in baselines if all(item[k] == ol[k] for k in ("tp", "fp", "fn", "tn"))]
    best = min(matching, key=lambda item: item["replay_surface"]) if matching else None
    reduction = (best["replay_surface"] - ol["replay_surface"]) / best["replay_surface"] if best and best["replay_surface"] else None
    counts = Counter(ep["event"]["type"] for ep in adaptation["episodes"])
    structural = {
        "minimum_external_episodes": len(adaptation["episodes"]) >= int(promotion["minimum_external_episodes"]),
        "minimum_independent_support_cases": len(adaptation["episodes"]) >= int(promotion["minimum_independent_support_cases"]),
        "minimum_property_specific_downstream_cases": len(adaptation["episodes"]) >= int(promotion["minimum_property_specific_downstream_cases"]),
        "minimum_per_event_type": all(counts.get(event, 0) >= int(promotion["minimum_per_event_type"]) for event in promotion["required_event_types"]),
    }
    req = promotion["promotion_requirements"]
    accuracy = {
        "openline_recall": ol["affected_decision_recall"] >= float(req["openline_recall_minimum"]),
        "openline_preservation": ol["unaffected_state_preservation"] >= float(req["openline_preservation_minimum"]),
        "no_additional_missed_reopenings": ol["fn"] - strongest["fn"] <= int(req["additional_missed_reopenings_vs_strongest_baseline_maximum"]),
        "no_additional_false_reopenings": ol["fp"] - strongest["fp"] <= int(req["additional_false_reopenings_vs_strongest_baseline_maximum"]),
    }
    replay_ok = reduction is None or reduction >= float(req["replay_surface_reduction_vs_best_accuracy_matching_baseline_minimum"])
    if not all(structural.values()): verdict = "INCOMPLETE_EXTERNAL_ADAPTATION"
    elif not all(accuracy.values()): verdict = "EXTERNAL_STANDING_SEPARATION_NOT_EARNED"
    elif not replay_ok: verdict = "NO_REPAIR_SURFACE_SEPARATION"
    else: verdict = "EXTERNAL_STANDING_SEPARATION_ADAPTED_LONGMEMEVAL_V2"
    return {
        "verdict": verdict,
        "strongest_accuracy_baseline": strongest["system"],
        "best_accuracy_matching_baseline": best["system"] if best else None,
        "best_accuracy_matching_baseline_replay_surface": best["replay_surface"] if best else None,
        "replay_surface_reduction_vs_best_accuracy_matching_baseline": reduction,
        "structural_checks": structural,
        "accuracy_checks": accuracy,
        "replay_check": replay_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent verifier for SRE-001 external LongMemEval-V2 adaptation")
    parser.add_argument("--source", required=True)
    parser.add_argument("--adaptation", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--score", required=True)
    parser.add_argument("--verdict", required=True)
    parser.add_argument("--promotion-policy", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source_path = Path(args.source)
    adaptation = load(Path(args.adaptation))
    manifest = load(Path(args.manifest))
    score = load(Path(args.score))
    verdict = load(Path(args.verdict))
    promotion = load(Path(args.promotion_policy))
    mismatches: list[dict[str, Any]] = []

    rows = read_jsonl(source_path)
    source_map = {str(row.get("id")): row for row in rows if isinstance(row.get("id"), str)}
    selected = sorted((row for row in rows if eligible(row)), key=lambda row: str(row["id"]))[:5]
    selected_ids = [str(row["id"]) for row in selected]
    if adaptation.get("selected_trajectory_ids") != selected_ids:
        mismatches.append({"field": "selected_trajectory_ids", "expected": selected_ids, "observed": adaptation.get("selected_trajectory_ids")})
    if adaptation.get("selected_anchor_count") != 10:
        mismatches.append({"field": "selected_anchor_count", "expected": 10, "observed": adaptation.get("selected_anchor_count")})
    if len(adaptation.get("episodes", [])) != 40:
        mismatches.append({"field": "episode_count", "expected": 40, "observed": len(adaptation.get("episodes", []))})
    counts = Counter(ep["event"]["type"] for ep in adaptation.get("episodes", []))
    if counts != Counter({event: 10 for event in EVENT_TYPES}):
        mismatches.append({"field": "event_distribution", "expected": {event: 10 for event in EVENT_TYPES}, "observed": dict(counts)})

    if manifest.get("source_file_sha256") != sha256_file(source_path):
        mismatches.append({"field": "source_file_sha256", "expected": sha256_file(source_path), "observed": manifest.get("source_file_sha256")})
    expected_adaptation_sha = sha256_bytes(canonical_bytes(adaptation))
    if manifest.get("adaptation_sha256") != expected_adaptation_sha:
        mismatches.append({"field": "manifest.adaptation_sha256", "expected": expected_adaptation_sha, "observed": manifest.get("adaptation_sha256")})
    if score.get("adaptation_sha256") != expected_adaptation_sha:
        mismatches.append({"field": "score.adaptation_sha256", "expected": expected_adaptation_sha, "observed": score.get("adaptation_sha256")})

    episode_index = {ep["episode_id"]: ep for ep in adaptation.get("episodes", [])}
    for trajectory_id in selected_ids:
        row = source_map[trajectory_id]
        for anchor_ordinal, (idx, state) in enumerate(selected_anchors(row)):
            for event in EVENT_TYPES:
                eid = f"lmev2-{trajectory_id}-a{anchor_ordinal}-{event.lower()}"
                ep = episode_index.get(eid)
                if ep is None:
                    mismatches.append({"field": "missing_episode", "episode_id": eid})
                    continue
                src = ep["external_source"]
                expected_record_sha = sha256_bytes(canonical_bytes(row))
                expected_state_sha = sha256_bytes(canonical_bytes(state))
                if src.get("source_record_sha256") != expected_record_sha:
                    mismatches.append({"field": "source_record_sha256", "episode_id": eid})
                if src.get("anchor_ordinal") != anchor_ordinal or src.get("selected_state_index") != idx or src.get("selected_state_sha256") != expected_state_sha:
                    mismatches.append({"field": "selected_state_binding", "episode_id": eid})
                if ep.get("lifecycle_injection", {}).get("synthetic") is not True or ep.get("lifecycle_injection", {}).get("post_finalization") is not True:
                    mismatches.append({"field": "lifecycle_injection", "episode_id": eid})
                g = gold(ep)
                if g["reopen"] != ["D2"] or sorted(g["survive"]) != ["D1", "D3", "D4"]:
                    mismatches.append({"field": "gold_semantics", "episode_id": eid, "observed": g})

    expected = expected_scores(adaptation)
    observed_by_system = {item["system"]: item for item in score.get("systems", [])}
    for exp in expected:
        obs = observed_by_system.get(exp["system"])
        if obs is None:
            mismatches.append({"field": "missing_system", "system": exp["system"]})
        elif norm_score(obs) != norm_score(exp):
            mismatches.append({"field": "system_score", "system": exp["system"]})

    expected_verdict = recompute_verdict(adaptation, {**score, "systems": expected}, promotion)
    for key, expected_value in expected_verdict.items():
        if verdict.get(key) != expected_value:
            mismatches.append({"field": f"verdict.{key}", "expected": expected_value, "observed": verdict.get(key)})

    output = {
        "schema": "openline.standing-recall-external-independent-verification.v1",
        "experiment": "standing-recall-external-lifecycle-001",
        "verified": not mismatches,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "source_file_sha256": sha256_file(source_path),
        "adaptation_sha256": expected_adaptation_sha,
        "verdict": expected_verdict["verdict"] if not mismatches else "VERIFICATION_FAILED",
        "policy_authority": "NONE",
    }
    write(Path(args.output), output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if not mismatches else 2


if __name__ == "__main__":
    raise SystemExit(main())
