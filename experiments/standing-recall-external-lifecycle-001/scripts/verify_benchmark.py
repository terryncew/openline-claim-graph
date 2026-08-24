from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

ACCEPTED = "ACCEPTED"


def cbytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(cbytes(value)).hexdigest()


def load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path: str, value: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def indexes(ep):
    evidence = {x["id"]: x for x in ep["evidence"]}
    decisions = {x["id"]: x for x in ep["decisions"]}
    return evidence, decisions


def standing(ep, when):
    evidence, decisions = indexes(ep)
    dcache = {}
    fcache = {}
    active = set()

    def binding_ok(binding, expected):
        sid, facet = binding["source"], binding["facet"]
        source_expected = binding.get("equals", expected)
        if sid in evidence:
            state = evidence[sid][when]
            return state["standing"] == ACCEPTED and state.get("facets", {}).get(facet) == source_expected
        if not decision_ok(sid):
            return False
        return facet_ok(sid, facet, source_expected)

    def decision_ok(did):
        if did in dcache:
            return dcache[did]
        key = ("d", did)
        if key in active:
            raise ValueError("cycle")
        active.add(key)
        try:
            value = True
            for requirement in decisions[did]["requires"]:
                expected = requirement["equals"]
                if not any(binding_ok(b, expected) for b in requirement["bindings"]):
                    value = False
                    break
            dcache[did] = value
            return value
        finally:
            active.remove(key)

    def facet_ok(did, facet, expected):
        key0 = (did, facet, json.dumps(expected, sort_keys=True))
        if key0 in fcache:
            return fcache[key0]
        output = decisions[did].get("outputs", {}).get(facet)
        if output is None or output.get("value") != expected:
            fcache[key0] = False
            return False
        key = ("f", did, facet)
        if key in active:
            raise ValueError("cycle")
        active.add(key)
        try:
            value = any(binding_ok(b, expected) for b in output["bindings"])
            fcache[key0] = value
            return value
        finally:
            active.remove(key)

    return {did: decision_ok(did) for did in decisions}


def edges(ep):
    result = set()
    for d in ep["decisions"]:
        for req in d["requires"]:
            for b in req["bindings"]:
                result.add((b["source"], d["id"]))
        for output in d.get("outputs", {}).values():
            for b in output["bindings"]:
                result.add((b["source"], d["id"]))
    return sorted(result)


def descendant_decisions(ep):
    roots = ep["event"]["roots"]
    children = defaultdict(set)
    for a, b in edges(ep):
        children[a].add(b)
    seen = set(roots)
    q = deque(roots)
    while q:
        n = q.popleft()
        for child in sorted(children[n]):
            if child not in seen:
                seen.add(child)
                q.append(child)
    decision_ids = {d["id"] for d in ep["decisions"]}
    return seen & decision_ids


def preds(ep):
    p = defaultdict(set)
    for a, b in edges(ep):
        p[b].add(a)
    return p


def topo(ep):
    _, decisions = indexes(ep)
    decision_ids = set(decisions)
    p = preds(ep)
    indegree = {d: 0 for d in decision_ids}
    children = defaultdict(set)
    for d in decision_ids:
        for s in p[d]:
            if s in decision_ids:
                indegree[d] += 1
                children[s].add(d)
    q = deque(sorted(d for d, k in indegree.items() if k == 0))
    result = []
    while q:
        n = q.popleft()
        result.append(n)
        for child in sorted(children[n]):
            indegree[child] -= 1
            if indegree[child] == 0:
                q.append(child)
    if len(result) != len(decision_ids):
        raise ValueError("cycle")
    return result


def evidence_alive(ep, eid):
    evidence, _ = indexes(ep)
    return evidence[eid]["after"]["standing"] == ACCEPTED


def predict_dgrr(ep):
    _, decisions = indexes(ep)
    affected = descendant_decisions(ep)
    p = preds(ep)
    invalid = set(ep["event"]["roots"])
    reopen = set()
    replay = set()
    for did in topo(ep):
        if did not in affected:
            continue
        surviving = False
        for source in p[did]:
            if source in invalid:
                continue
            if source in decisions:
                if source not in reopen:
                    surviving = True
                    break
            elif evidence_alive(ep, source):
                surviving = True
                break
        if not surviving:
            reopen.add(did)
            invalid.add(did)
            replay.add(did)
    return reopen, replay, affected


def predict_memorepair(ep):
    _, decisions = indexes(ep)
    affected = descendant_decisions(ep)
    p = preds(ep)
    servable = {d for d in decisions if d not in affected}
    reopen = set()
    for did in topo(ep):
        if did not in affected:
            continue
        can = False
        for source in p[did]:
            if source in ep["event"]["roots"]:
                continue
            if source in decisions:
                if source in servable:
                    can = True
                    break
            elif evidence_alive(ep, source):
                can = True
                break
        if can:
            servable.add(did)
        else:
            reopen.add(did)
    return reopen, set(affected), affected


def predict_openline(ep):
    before = standing(ep, "before")
    after = standing(ep, "after")
    if not all(before.values()):
        raise ValueError("non-standing pre-event decision")
    reopen = {d for d in before if not after[d]}
    return reopen, set(reopen), descendant_decisions(ep)


PREDICTORS = {
    "DGRR_STYLE_NODE_SUPPORT_V1": predict_dgrr,
    "MEMOREPAIR_STYLE_CASCADE_V1": predict_memorepair,
    "OPENLINE_STANDING_PROPAGATION_V1": predict_openline,
}


def recompute(fixture):
    totals = {}
    for system, predictor in PREDICTORS.items():
        tp = fp = fn = tn = replay = analysis = 0
        per = []
        for ep in fixture["episodes"]:
            before = standing(ep, "before")
            after = standing(ep, "after")
            gold = {d for d in before if before[d] and not after[d]}
            universe = set(before)
            pred, rep, ana = predictor(ep)
            tpe = len(gold & pred)
            fpe = len(pred - gold)
            fne = len(gold - pred)
            tne = len((universe - gold) - pred)
            tp += tpe; fp += fpe; fn += fne; tn += tne
            replay += len(rep); analysis += len(ana)
            per.append({
                "episode_id": ep["episode_id"],
                "event_type": ep["event"]["type"],
                "gold_reopen": sorted(gold),
                "predicted_reopen": sorted(pred),
                "replay": sorted(rep),
                "tp": tpe, "fp": fpe, "fn": fne, "tn": tne,
            })
        totals[system] = {
            "system": system,
            "episodes": len(fixture["episodes"]),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "affected_decision_recall": tp / (tp + fn) if tp + fn else 1.0,
            "unaffected_state_preservation": tn / (tn + fp) if tn + fp else 1.0,
            "replay_surface": replay,
            "analysis_surface": analysis,
            "per_episode": per,
        }
    return totals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--score", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    fixture = load(args.fixture)
    score = load(args.score)
    errors = []

    body = dict(fixture)
    claimed_self = body.pop("fixture_sha256", "")
    if claimed_self != digest(body):
        errors.append("fixture self-hash mismatch")
    if score.get("fixture_sha256") != digest(fixture):
        errors.append("score fixture binding mismatch")
    if score.get("status") != "MECHANICS_ONLY_EXTERNAL_BENCHMARK_UNRUN":
        errors.append("conformance score must not claim external benchmark promotion")
    if score.get("policy_authority") != "NONE":
        errors.append("policy authority must remain NONE")

    counts = Counter(ep["event"]["type"] for ep in fixture["episodes"])
    required = {"EXPIRE": 16, "REVOKE": 16, "SUPERSEDE": 16, "CORRECT": 16}
    if dict(counts) != required:
        errors.append(f"unexpected event distribution: {dict(counts)}")

    for ep in fixture["episodes"]:
        if not ep["event"].get("occurred_after_finalization"):
            errors.append(f"{ep['episode_id']}: lifecycle event is not post-finalization")
        if ep["event"].get("content_bytes_changed"):
            errors.append(f"{ep['episode_id']}: conformance root content unexpectedly changed")
        if not all(standing(ep, "before").values()):
            errors.append(f"{ep['episode_id']}: a finalized decision lacked pre-event standing")

    expected = recompute(fixture)
    observed = {item["system"]: item for item in score.get("systems", [])}
    if set(expected) != set(observed):
        errors.append("system set mismatch")
    else:
        for system in expected:
            if expected[system] != observed[system]:
                errors.append(f"{system}: independently recomputed score differs")

    openline = expected["OPENLINE_STANDING_PROPAGATION_V1"]
    mechanics_pass = (
        openline["affected_decision_recall"] == 1.0
        and openline["unaffected_state_preservation"] == 1.0
        and any(item["fn"] > 0 for name, item in expected.items() if name != "OPENLINE_STANDING_PROPAGATION_V1")
    )
    if not mechanics_pass:
        errors.append("fixture does not pressure the candidate mechanism as frozen")

    result = {
        "schema": "openline.standing-recall-external-lifecycle-independent-verification.v1",
        "verified": not errors,
        "status": "MECHANICS_ONLY_EXTERNAL_BENCHMARK_UNRUN" if not errors else "INVALID",
        "mechanics_pressure_test_pass": mechanics_pass and not errors,
        "errors": errors,
        "event_counts": dict(sorted(counts.items())),
        "systems": {
            name: {
                "affected_decision_recall": item["affected_decision_recall"],
                "unaffected_state_preservation": item["unaffected_state_preservation"],
                "replay_surface": item["replay_surface"],
            }
            for name, item in expected.items()
        },
        "claim_boundary": "Independent replay verifies only the checked conformance mechanics. It does not establish performance on DGRR, MemoRepair, LongMemEval-V2, ToolBench, MemoryArena, or any author-released benchmark.",
        "policy_authority": "NONE",
    }
    write(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
