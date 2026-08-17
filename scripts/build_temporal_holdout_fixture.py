from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from openline_claim_graph.temporal_holdout import (
    create_authority,
    create_episode,
    create_future_record,
    create_future_seal,
    create_gold,
    create_pack,
    run_temporal,
    score_temporal,
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the temporal-holdout conformance fixture")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    t0 = "2018-12-31T23:59:59Z"
    t1 = "2019-06-01T00:00:00Z"
    pre = "2018-01-01T00:00:00Z"
    root, a, b, c, d, backup, e = (
        "fixture:root", "fixture:a", "fixture:b", "fixture:c", "fixture:d", "fixture:backup", "fixture:e"
    )
    nodes = [
        {"node_id": root, "label": "invalidated root", "available_at": pre},
        {"node_id": a, "label": "direct dependent", "available_at": pre},
        {"node_id": b, "label": "hard transitive dependent", "available_at": pre},
        {"node_id": c, "label": "advisory transitive dependent", "available_at": pre},
        {"node_id": d, "label": "alternative-support survivor", "available_at": pre},
        {"node_id": backup, "label": "independent backup", "available_at": pre, "independent_basis": True},
        {"node_id": e, "label": "unadmitted reachable target", "available_at": pre},
    ]
    edges = [
        {"prerequisite_node_id": root, "dependent_node_id": a, "relation": "DERIVED_FROM", "available_at": pre, "evidence": ["pre-cutoff direct basis"]},
        {"prerequisite_node_id": a, "dependent_node_id": b, "relation": "DEPENDS_ON", "available_at": pre, "evidence": ["pre-cutoff hard dependency"]},
        {"prerequisite_node_id": a, "dependent_node_id": c, "relation": "DEPENDS_ON", "available_at": pre, "evidence": ["pre-cutoff inferred dependency"]},
        {"prerequisite_node_id": root, "dependent_node_id": d, "relation": "SUPPORTS", "available_at": pre, "evidence": ["pre-cutoff support"]},
        {"prerequisite_node_id": backup, "dependent_node_id": d, "relation": "SUPPORTS", "available_at": pre, "evidence": ["pre-cutoff independent support"]},
        {"prerequisite_node_id": a, "dependent_node_id": e, "relation": "DEPENDS_ON", "available_at": pre, "evidence": ["pre-cutoff unadmitted relation"]},
    ]
    episode = create_episode(
        episode_name="temporal conformance",
        cutoff_at=t0,
        event_at=t1,
        invalidated_node_id=root,
        target_node_ids=[a, b, c, d, e],
        nodes=nodes,
        edges=edges,
        event={
            "status": "RETRACTED",
            "identifier": "fixture-trigger",
            "locator": "fixture:event",
            "reason": "Conformance-only invalidation.",
            "available_at": t1,
            "evidence_sha256": digest("fixture event notice"),
        },
        metadata={"domain": "CONFORMANCE"},
    )
    future_specs = [
        (a, "DOWNSTREAM_CORRECTION", "A later corrected"),
        (b, "ACCEPTED_DECISION_FORMALLY_REOPENED", "B later reopened"),
        (c, "INDEPENDENT_DEPENDENCY_AUDIT_NO_RELIANCE", "C later found not reliant"),
        (d, "FORMAL_SCOPE_EXCLUSION", "D later explicitly outside affected scope"),
        (e, "INDEPENDENT_CITATION_CONTEXT_NO_RELIANCE", "E later found not reliant"),
    ]
    records = [
        create_future_record(
            episode_id=episode["episode_id"],
            available_at=f"2020-0{index}-01T00:00:00Z",
            record_type=record_type,
            target_node_ids=[target],
            locator=f"fixture:future:{target}",
            evidence_sha256=digest(description),
            description=description,
        )
        for index, (target, record_type, description) in enumerate(future_specs, start=1)
    ]
    seal = create_future_seal(
        benchmark_id="temporal-conformance-v1",
        scope_definition="All predetermined later records for the five conformance targets.",
        retrieval_cutoff_at="2021-01-01T00:00:00Z",
        records=records,
    )
    pack = create_pack(
        benchmark_id="temporal-conformance-v1",
        episodes=[episode],
        source_manifest=[{"role": "conformance_only", "identifier": "self-authored-fixture"}],
        construction_rule="Only pre-cutoff fixture state plus the trigger event are prediction-visible; later records are committed but sealed.",
        future_seal=seal,
        status="CONFORMANCE_ONLY",
    )
    authority_map = {}
    for edge in episode["edges"]:
        evidence = set(edge["evidence"])
        authority_map[edge["edge_id"]] = (
            "ADVISORY" if "pre-cutoff inferred dependency" in evidence
            else "UNADMITTED" if "pre-cutoff unadmitted relation" in evidence
            else "HARD"
        )
    authority = create_authority(
        pack,
        edge_authority=authority_map,
        declared_by="conformance-fixture",
        construction_rule="Inferred fixture edge advisory; explicit unadmitted fixture edge unadmitted; all remaining edges hard.",
    )
    records_by_target = {record["target_node_ids"][0]: record["record_id"] for record in records}
    labels = [
        {
            "episode_id": episode["episode_id"],
            "target_node_id": target,
            "outcome": "REOPEN" if target in {a, b} else "NO_REOPEN",
            "future_record_ids": [records_by_target[target]],
        }
        for target in [a, b, c, d, e]
    ]
    gold = create_gold(
        pack,
        seal,
        labels,
        label_definition="Conformance-only later reconsideration labels; not empirical evidence.",
    )
    predictions = run_temporal(pack, authority, include_naive_diagnostic=True)
    score = score_temporal(pack, authority, seal, gold, predictions)

    write(output / "pack.json", pack)
    write(output / "authority.json", authority)
    write(output / "future-seal.private.json", seal)
    write(output / "gold.private.json", gold)
    write(output / "predictions.json", predictions)
    write(output / "score.json", score)
    print(json.dumps({
        "valid": True,
        "pack_id": pack["pack_id"],
        "future_seal_id": seal["future_seal_id"],
        "score_id": score["score_id"],
        "review_all_load": score["metrics"]["REVIEW_ALL_REACHABILITY"]["total_review_load"],
        "evidence_recall_load": score["metrics"]["EVIDENCE_RECALL"]["total_review_load"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
