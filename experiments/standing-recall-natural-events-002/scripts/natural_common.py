from __future__ import annotations

import hashlib
import importlib.util
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
NATURAL_ROOT = HERE.parent
CLAIM_GRAPH_ROOT = NATURAL_ROOT.parents[1]
FROZEN_SRE001 = CLAIM_GRAPH_ROOT / "experiments" / "standing-recall-external-lifecycle-001" / "scripts" / "standing_recall.py"
CASES_PATH = NATURAL_ROOT / "NATURAL_CASES.json"
PROMOTION_PATH = NATURAL_ROOT / "promotion-policy.json"

EXPECTED_FROZEN_SRE001_SHA256 = "17ae11cadf44f9fb2dda01582e894c7eb14bc59592bf6db9f08b071702ff692f"
EVENT_TYPES = ("CORRECT", "REVOKE", "SUPERSEDE", "EXPIRE")
OPENLINE_SYSTEM = "OPENLINE_STANDING_PROPAGATION_NATURAL_V1"
DGRR_SYSTEM = "DGRR_CONTRACT_NODE_SUPPORT_NATURAL_V1"
MEMOREPAIR_SYSTEM = "MEMOREPAIR_CONTRACT_PROPERTY_VALIDATION_NATURAL_V1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


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


def load_frozen_sre001():
    if not FROZEN_SRE001.exists():
        raise RuntimeError(f"frozen SRE-001 mechanism missing: {FROZEN_SRE001}")
    observed = sha256_file(FROZEN_SRE001)
    if observed != EXPECTED_FROZEN_SRE001_SHA256:
        raise RuntimeError(f"frozen SRE-001 mechanism drift: expected {EXPECTED_FROZEN_SRE001_SHA256}, got {observed}")
    spec = importlib.util.spec_from_file_location("sre001_frozen_natural", FROZEN_SRE001)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load frozen SRE-001 mechanism")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gold_for_event(event: dict[str, Any]) -> dict[str, list[str]]:
    gold = event.get("gold", {})
    reopen = sorted(str(v) for v in gold.get("reopen", []))
    survive = sorted(str(v) for v in gold.get("survive", []))
    return {"reopen": reopen, "survive": survive}


def validate_registry(registry: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if registry.get("schema") != "openline.standing-recall-natural-cases.v1":
        errors.append("unexpected corpus schema")
    if registry.get("experiment") != "standing-recall-natural-events-002":
        errors.append("unexpected experiment id")
    events = registry.get("events")
    if not isinstance(events, list):
        errors.append("events must be a list")
        events = []
    seen_events: set[str] = set()
    target_count = reopen_count = survive_count = 0
    type_counts: Counter[str] = Counter()
    frozen = load_frozen_sre001()

    for idx, event in enumerate(events):
        prefix = f"event[{idx}]"
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            errors.append(f"{prefix}: invalid event_id")
            continue
        if event_id in seen_events:
            errors.append(f"{prefix}: duplicate event_id {event_id}")
        seen_events.add(event_id)
        event_type = event.get("event_type")
        if event_type not in EVENT_TYPES:
            errors.append(f"{event_id}: unsupported event_type {event_type!r}")
        else:
            type_counts[event_type] += 1
        if event.get("event", {}).get("type") != event_type:
            errors.append(f"{event_id}: event.type disagrees with event_type")
        roots = event.get("event", {}).get("roots")
        evidence_ids = {item.get("id") for item in event.get("evidence", []) if isinstance(item, dict)}
        if not isinstance(roots, list) or not roots or not set(roots).issubset(evidence_ids):
            errors.append(f"{event_id}: invalid event roots")
        decisions = event.get("decisions", [])
        decision_ids = [item.get("id") for item in decisions if isinstance(item, dict)]
        if len(decision_ids) != len(set(decision_ids)) or any(not isinstance(v, str) or not v for v in decision_ids):
            errors.append(f"{event_id}: invalid or duplicate decision ids")
        gold = gold_for_event(event)
        if set(gold["reopen"]) & set(gold["survive"]):
            errors.append(f"{event_id}: gold reopen/survive overlap")
        if set(gold["reopen"]) | set(gold["survive"]) != set(decision_ids):
            errors.append(f"{event_id}: gold does not partition decision universe")
        target_count += len(decision_ids)
        reopen_count += len(gold["reopen"])
        survive_count += len(gold["survive"])
        if not event.get("sources"):
            errors.append(f"{event_id}: no public source anchors")
        if len(event.get("gold_basis", [])) != len(decision_ids):
            errors.append(f"{event_id}: one gold_basis record required per target")
        try:
            before = frozen.StandingOracle(event, "before").standings()
            if not before or not all(before.values()):
                errors.append(f"{event_id}: every scored decision must stand before the natural event")
        except Exception as exc:
            errors.append(f"{event_id}: frozen SRE-001 pre-event evaluation failed: {exc}")

    return {
        "valid": not errors,
        "errors": errors,
        "events": len(events),
        "targets": target_count,
        "gold_reopen": reopen_count,
        "gold_survive": survive_count,
        "event_distribution": dict(sorted(type_counts.items())),
        "corpus_sha256": sha256_bytes(canonical_bytes(registry)),
        "frozen_sre001_sha256": sha256_file(FROZEN_SRE001) if FROZEN_SRE001.exists() else "MISSING",
    }


def build_fixture(registry: dict[str, Any]) -> dict[str, Any]:
    check = validate_registry(registry)
    if not check["valid"]:
        raise ValueError(f"invalid natural registry: {check['errors']}")
    episodes = []
    for event in registry["events"]:
        episodes.append({
            "episode_id": event["event_id"],
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "domain": event["domain"],
            "effective_at": event["effective_at"],
            "title": event["title"],
            "sources": event["sources"],
            "source_facts": event["source_facts"],
            "gold_basis": event["gold_basis"],
            "gold": gold_for_event(event),
            "event": event["event"],
            "evidence": event["evidence"],
            "decisions": event["decisions"],
        })
    return {
        "schema": "openline.standing-recall-natural-fixture.v1",
        "experiment": "standing-recall-natural-events-002",
        "corpus_sha256": check["corpus_sha256"],
        "frozen_sre001_sha256": check["frozen_sre001_sha256"],
        "event_count": check["events"],
        "target_count": check["targets"],
        "event_distribution": check["event_distribution"],
        "gold_distribution": {"REOPEN": check["gold_reopen"], "SURVIVE": check["gold_survive"]},
        "episodes": episodes,
        "policy_authority": "NONE",
        "claim_boundary": [
            "The lifecycle events and target dispositions are anchored to public historical records; dependency/facet mappings are retrospective human-authored representations.",
            "Gold comes from the disclosed public-record disposition mapping, not from the OpenLine standing evaluator.",
            "This corpus does not test automatic dependency discovery, semantic truth, natural event frequency, or irreversible-effect rollback.",
        ],
    }


def _decision_ids(episode: dict[str, Any]) -> set[str]:
    return {str(item["id"]) for item in episode["decisions"]}


def _edges(episode: dict[str, Any]) -> list[tuple[str, str]]:
    frozen = load_frozen_sre001()
    return frozen.derive_influence_edges(episode)


def _descendants(episode: dict[str, Any], roots: list[str]) -> set[str]:
    frozen = load_frozen_sre001()
    return frozen.descendants(episode, roots)


def _predecessors(episode: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for left, right in _edges(episode):
        out[right].add(left)
    return out


def _evidence_alive_after(episode: dict[str, Any], evidence_id: str) -> bool:
    for item in episode["evidence"]:
        if item["id"] == evidence_id:
            return item["after"]["standing"] == "ACCEPTED"
    raise KeyError(evidence_id)


def _topological(episode: dict[str, Any]) -> list[str]:
    ids = _decision_ids(episode)
    pred = _predecessors(episode)
    indegree = {did: 0 for did in ids}
    children: dict[str, set[str]] = defaultdict(set)
    for did in ids:
        for source in pred.get(did, set()):
            if source in ids:
                indegree[did] += 1
                children[source].add(did)
    queue = deque(sorted(did for did, degree in indegree.items() if degree == 0))
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for child in sorted(children.get(node, set())):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(ids):
        raise ValueError("cyclic natural decision graph")
    return order


def dgrr_contract_prediction(episode: dict[str, Any]) -> dict[str, Any]:
    roots = list(episode["event"]["roots"])
    affected = _descendants(episode, roots)
    pred = _predecessors(episode)
    ids = _decision_ids(episode)
    reopened: set[str] = set()
    for did in _topological(episode):
        if did not in affected:
            continue
        independent = False
        for source in pred.get(did, set()):
            if source in roots or source in affected:
                continue
            if source in ids:
                independent = True
                break
            if _evidence_alive_after(episode, source):
                independent = True
                break
        if not independent:
            reopened.add(did)
    return {
        "system": DGRR_SYSTEM,
        "reopen": sorted(reopened),
        "replay": sorted(reopened),
        "analysis_surface": sorted(affected),
        "boundary": "DGRR-style diagnosed-root/node-support contract abstraction; not author code or reported paper results.",
    }


def memorepair_contract_prediction(episode: dict[str, Any]) -> dict[str, Any]:
    frozen = load_frozen_sre001()
    roots = list(episode["event"]["roots"])
    affected = _descendants(episode, roots)
    oracle = frozen.StandingOracle(episode, "after")
    reopened = sorted(did for did in affected if not oracle.decision_stands(did))
    return {
        "system": MEMOREPAIR_SYSTEM,
        "reopen": reopened,
        "replay": sorted(affected),
        "analysis_surface": sorted(affected),
        "boundary": "Strong MemoRepair-style barrier-first contract abstraction with exact property-aware validation; not author code, min-cut implementation, or reported paper results.",
    }


def openline_natural_prediction(episode: dict[str, Any]) -> dict[str, Any]:
    frozen = load_frozen_sre001()
    result = dict(frozen.openline_prediction(episode))
    result["system"] = OPENLINE_SYSTEM
    result["boundary"] = "Frozen SRE-001 receiver-owned facet/value standing; no new SRE-002 inference semantics."
    return result


def score_system(episodes: list[dict[str, Any]], predictor: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    tp = fp = fn = tn = 0
    replay_total = analysis_total = 0
    per_episode = []
    for episode in episodes:
        gold = episode["gold"]
        pred = predictor(episode)
        universe = _decision_ids(episode)
        gold_reopen = set(gold["reopen"])
        pred_reopen = set(pred["reopen"])
        if not pred_reopen.issubset(universe):
            raise ValueError(f"{pred['system']} predicted unknown decision ids")
        tp_e = len(gold_reopen & pred_reopen)
        fp_e = len(pred_reopen - gold_reopen)
        fn_e = len(gold_reopen - pred_reopen)
        tn_e = len((universe - gold_reopen) - pred_reopen)
        tp += tp_e; fp += fp_e; fn += fn_e; tn += tn_e
        replay_total += len(pred["replay"])
        analysis_total += len(pred["analysis_surface"])
        per_episode.append({
            "event_id": episode["event_id"],
            "event_type": episode["event_type"],
            "gold_reopen": sorted(gold_reopen),
            "gold_survive": sorted(set(gold["survive"])),
            "predicted_reopen": sorted(pred_reopen),
            "replay": sorted(pred["replay"]),
            "tp": tp_e, "fp": fp_e, "fn": fn_e, "tn": tn_e,
        })
    recall = tp / (tp + fn) if tp + fn else 1.0
    preservation = tn / (tn + fp) if tn + fp else 1.0
    return {
        "system": predictor(episodes[0])["system"] if episodes else "UNKNOWN",
        "events": len(episodes),
        "targets": sum(len(ep["decisions"]) for ep in episodes),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "affected_decision_recall": recall,
        "unaffected_state_preservation": preservation,
        "replay_surface": replay_total,
        "analysis_surface": analysis_total,
        "per_episode": per_episode,
    }


def run_benchmark(fixture: dict[str, Any]) -> dict[str, Any]:
    episodes = fixture["episodes"]
    systems = [
        score_system(episodes, dgrr_contract_prediction),
        score_system(episodes, memorepair_contract_prediction),
        score_system(episodes, openline_natural_prediction),
    ]
    return {
        "schema": "openline.standing-recall-natural-score.v1",
        "experiment": fixture["experiment"],
        "fixture_sha256": sha256_bytes(canonical_bytes(fixture)),
        "corpus_sha256": fixture["corpus_sha256"],
        "systems": systems,
        "policy_authority": "NONE",
        "claim_boundary": [
            "Gold is the frozen public-record disposition mapping, not the OpenLine evaluator's output.",
            "DGRR and MemoRepair comparisons are contract abstractions, not author implementations.",
            "The dependency/facet representation was authored retrospectively and can be incomplete or mistaken.",
        ],
    }


def _system(score: dict[str, Any], system_id: str) -> dict[str, Any]:
    for item in score["systems"]:
        if item["system"] == system_id:
            return item
    raise KeyError(system_id)


def _direct_alternative_survival_targets(episodes: list[dict[str, Any]]) -> int:
    count = 0
    for ep in episodes:
        roots = set(ep["event"]["roots"])
        survive = set(ep["gold"]["survive"])
        for decision in ep["decisions"]:
            if decision["id"] not in survive:
                continue
            has_mixed = False
            for req in decision.get("requires", []):
                sources = {b["source"] for b in req.get("bindings", [])}
                if sources & roots and sources - roots:
                    has_mixed = True
            for output in decision.get("outputs", {}).values():
                sources = {b["source"] for b in output.get("bindings", [])}
                if sources & roots and sources - roots:
                    has_mixed = True
            if has_mixed:
                count += 1
    return count


def grade_natural(fixture: dict[str, Any], score: dict[str, Any], promotion: dict[str, Any]) -> dict[str, Any]:
    episodes = fixture["episodes"]
    openline = _system(score, OPENLINE_SYSTEM)
    baselines = [item for item in score["systems"] if item["system"] != OPENLINE_SYSTEM]
    event_counts = Counter(ep["event_type"] for ep in episodes)
    gold_reopen = sum(len(ep["gold"]["reopen"]) for ep in episodes)
    gold_survive = sum(len(ep["gold"]["survive"]) for ep in episodes)
    alt_survive = _direct_alternative_survival_targets(episodes)

    req = promotion["promotion_requirements"]
    strongest_accuracy = sorted(baselines, key=lambda item: (item["fn"] + item["fp"], item["replay_surface"], item["system"]))[0]
    extra_fn = openline["fn"] - strongest_accuracy["fn"]
    extra_fp = openline["fp"] - strongest_accuracy["fp"]
    accuracy_matching = [
        item for item in baselines
        if (item["tp"], item["fp"], item["fn"], item["tn"]) == (openline["tp"], openline["fp"], openline["fn"], openline["tn"])
    ]
    best_matching = min(accuracy_matching, key=lambda item: item["replay_surface"]) if accuracy_matching else None
    replay_reduction = None
    if best_matching and best_matching["replay_surface"] > 0:
        replay_reduction = (best_matching["replay_surface"] - openline["replay_surface"]) / best_matching["replay_surface"]

    structural_checks = {
        "minimum_natural_events": len(episodes) >= int(promotion["minimum_natural_events"]),
        "minimum_scored_targets": fixture["target_count"] >= int(promotion["minimum_scored_targets"]),
        "minimum_gold_reopen": gold_reopen >= int(promotion["minimum_gold_reopen"]),
        "minimum_gold_survive": gold_survive >= int(promotion["minimum_gold_survive"]),
        "minimum_direct_alternative_support_survivals": alt_survive >= int(promotion["minimum_direct_alternative_support_survivals"]),
        "minimum_per_event_type": all(event_counts.get(kind, 0) >= int(promotion["minimum_per_event_type"]) for kind in promotion["required_event_types"]),
    }
    accuracy_checks = {
        "openline_recall": openline["affected_decision_recall"] >= float(req["openline_recall_minimum"]),
        "openline_preservation": openline["unaffected_state_preservation"] >= float(req["openline_preservation_minimum"]),
        "no_additional_missed_reopenings": extra_fn <= int(req["additional_missed_reopenings_vs_strongest_baseline_maximum"]),
        "no_additional_false_reopenings": extra_fp <= int(req["additional_false_reopenings_vs_strongest_baseline_maximum"]),
    }
    replay_check = replay_reduction is not None and replay_reduction >= float(req["replay_surface_reduction_vs_best_accuracy_matching_baseline_minimum"])

    if not all(structural_checks.values()):
        verdict = "INCOMPLETE_NATURAL_CORPUS"
    elif not all(accuracy_checks.values()):
        verdict = "NATURAL_STANDING_SELECTIVITY_NOT_EARNED"
    elif best_matching is None or not replay_check:
        verdict = "NO_NATURAL_REPAIR_SURFACE_SEPARATION"
    else:
        verdict = "NATURAL_STANDING_SELECTIVITY"

    return {
        "schema": "openline.standing-recall-natural-verdict.v1",
        "experiment": fixture["experiment"],
        "verdict": verdict,
        "status": verdict,
        "natural_event_count": len(episodes),
        "scored_target_count": fixture["target_count"],
        "event_distribution": dict(sorted(event_counts.items())),
        "gold_distribution": {"REOPEN": gold_reopen, "SURVIVE": gold_survive},
        "direct_alternative_support_survival_targets": alt_survive,
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
            "A strong MemoRepair-style property-aware baseline matched the public-record target dispositions; any surviving OpenLine distinction is limited to repair-surface selectivity."
            if best_matching and best_matching["system"] == MEMOREPAIR_SYSTEM
            else "No strong MemoRepair-style baseline matched OpenLine's target-level accuracy; the mechanism boundary remains unresolved without author code."
        ),
        "claim_boundary": [
            "Eight natural public lifecycle events yield 24 scored target dispositions; the 24 targets are not 24 independent events.",
            "The public records anchor event occurrence and target disposition, while dependency/facet mappings remain retrospective human-authored representations.",
            "The corpus is not blinded, prospective, randomly sampled, or representative of natural event frequency.",
            "DGRR and MemoRepair systems are contract abstractions, not author implementations.",
            "A successful verdict supports selectivity only on this frozen corpus and does not establish truth discovery or rollback of irreversible external effects.",
        ],
        "policy_authority": "NONE",
    }
