"""Randomized differential check for claim-impact propagation semantics.

The production engine is compared with a separately written set-based oracle
across graphs containing cycles, alternative support, required dependencies,
advisory edges, exact source spans, and receiver-declared decision nodes.
This validates implementation fidelity, not real-world edge accuracy.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import deque
from pathlib import Path

from openline_claim_graph import (
    analyze_source_impact,
    build_source,
    create_claim,
    create_impact_policy,
    create_relation,
    create_snapshot,
    create_source_status_event,
    provenance_anchor,
)


SEED = 0x0E1D_E11C
ACTOR = "probe:fixture-author"


def _direction(relation: dict) -> tuple[str, str]:
    if relation["relation"] == "SUPPORTS":
        return relation["source_claim_id"], relation["target_claim_id"]
    return relation["target_claim_id"], relation["source_claim_id"]


def _reach(origins: set[str], adjacency: dict[str, list[str]]) -> set[str]:
    seen = set(origins)
    queue = deque(origins)
    while queue:
        for dependent in adjacency.get(queue.popleft(), []):
            if dependent not in seen:
                seen.add(dependent)
                queue.append(dependent)
    return seen


def _oracle(snapshot: dict, event: dict, policy: dict) -> dict[str, set[str]]:
    claims = {item["claim_id"]: item for item in snapshot["claims"]}
    relations = {item["relation_id"]: item for item in snapshot["relations"]}
    affected = {
        item["source_id"]: (
            [(span["start"], span["end"]) for span in item["spans"]]
            if "spans" in item
            else None
        )
        for item in event["affected"]
    }

    exposed: set[str] = set()
    live_anchor: set[str] = set()
    for claim_id, claim in claims.items():
        for anchor in claim.get("provenance", []):
            if anchor["mode"] not in policy["hard_provenance_modes"]:
                continue
            scopes = affected.get(anchor["source_id"], "absent")
            if scopes == "absent":
                live_anchor.add(claim_id)
                continue
            start, end = anchor["span"]["start"], anchor["span"]["end"]
            hit = scopes is None or any(start < right and left < end for left, right in scopes)
            (exposed if hit else live_anchor).add(claim_id)

    hard: dict[str, list[str]] = {}
    advisory: dict[str, list[str]] = {}
    required: dict[str, list[str]] = {}
    supporters: dict[str, list[str]] = {}
    for relation_id in policy["hard_relation_ids"] + policy["advisory_relation_ids"]:
        relation = relations[relation_id]
        prerequisite, dependent = _direction(relation)
        destination = hard if relation_id in policy["hard_relation_ids"] else advisory
        destination.setdefault(prerequisite, []).append(dependent)
        if relation_id in policy["hard_relation_ids"]:
            if relation["relation"] == "SUPPORTS":
                supporters.setdefault(dependent, []).append(prerequisite)
            else:
                required.setdefault(dependent, []).append(prerequisite)

    grounded: set[str] = set()
    while True:
        before = len(grounded)
        for claim_id in claims:
            if claim_id in grounded:
                continue
            declared_support = supporters.get(claim_id, [])
            own = claim_id in live_anchor or (claim_id not in exposed and not declared_support)
            alternate = any(item in grounded for item in declared_support)
            if own or alternate:
                grounded.add(claim_id)
        if len(grounded) == before:
            break

    invalid = set(claims) - grounded
    while True:
        before = len(invalid)
        for claim_id in claims:
            if any(item in invalid for item in required.get(claim_id, [])):
                invalid.add(claim_id)
        if len(invalid) == before:
            break
    alive = set(claims) - invalid

    hard_touched = _reach(exposed, hard)
    quarantine = hard_touched - alive
    states = {(item, False) for item in exposed}
    queue = deque(states)
    advisory_touched: set[str] = set()
    while queue:
        current, used_advisory = queue.popleft()
        for is_advisory, adjacency in ((False, hard), (True, advisory)):
            for dependent in adjacency.get(current, []):
                next_used = used_advisory or is_advisory
                state = (dependent, next_used)
                if state not in states:
                    states.add(state)
                    queue.append(state)
                if next_used:
                    advisory_touched.add(dependent)
    review = advisory_touched - quarantine
    survives = (hard_touched & alive) - review
    return {
        "source_exposed": exposed,
        "quarantine": quarantine,
        "survives": survives,
        "affected_unresolved": review,
        "unaffected": set(claims) - quarantine - survives - review,
        "decisions_touched": set(policy["decision_claim_ids"]) & (quarantine | survives | review),
    }


def _case(rng: random.Random, index: int) -> tuple[dict, dict]:
    count = rng.randint(4, 14)
    lines = [f"Case {index} claim {item} has an admitted source basis." for item in range(count)]
    primary = build_source("\n".join(lines), locator=f"probe://{index}/primary")
    backup = build_source(
        "Independent archive copy.\n" + "\n".join(lines),
        locator=f"probe://{index}/backup",
    )
    notice = build_source(
        f"Case {index} correction notice withdraws selected source spans.",
        locator=f"probe://{index}/notice",
    )
    sources = {item["source_id"]: item for item in (primary, backup, notice)}
    anchored_indexes = {item for item in range(count) if rng.random() < 0.72}
    if not anchored_indexes:
        anchored_indexes.add(rng.randrange(count))
    claims = []
    for item, text in enumerate(lines):
        provenance = []
        if item in anchored_indexes:
            provenance.append(provenance_anchor(primary, text, mode="QUOTE", asserted_by=ACTOR))
            if rng.random() < 0.22:
                provenance.append(provenance_anchor(backup, text, mode="QUOTE", asserted_by=ACTOR))
        claims.append(
            create_claim(
                kind="SOURCE_ASSERTION" if provenance else "INFERENCE",
                text=text,
                asserted_by=ACTOR,
                provenance=provenance,
            )
        )

    selected = rng.sample(sorted(anchored_indexes), rng.randint(1, len(anchored_indexes)))
    affected_spans = [
        dict(
            next(
                anchor
                for anchor in claims[item]["provenance"]
                if anchor["source_id"] == primary["source_id"]
            )["span"]
        )
        for item in selected
    ]
    event = create_source_status_event(
        status=rng.choice(["CORRECTED", "RETRACTED", "WITHDRAWN"]),
        affected=[{"source_id": primary["source_id"], "spans": affected_spans}],
        evidence=[
            provenance_anchor(
                notice,
                notice["content"],
                mode="QUOTE",
                asserted_by=ACTOR,
            )
        ],
        asserted_by=ACTOR,
        effective_at="2026-08-16T00:00:00Z",
        reason="Randomized differential fixture.",
    )

    relation_specs: set[tuple[int, int, str]] = set()
    for _ in range(rng.randint(count, count * 3)):
        source_index = rng.randrange(count)
        target_index = rng.randrange(count)
        if source_index == target_index:
            continue
        relation_specs.add(
            (source_index, target_index, rng.choice(["SUPPORTS", "DEPENDS_ON", "DERIVED_FROM"]))
        )
    relations = [
        create_relation(
            source_claim_id=claims[source]["claim_id"],
            target_claim_id=claims[target]["claim_id"],
            relation=relation,
            asserted_by=ACTOR,
        )
        for source, target, relation in sorted(relation_specs)
    ]
    snapshot = create_snapshot(claims=claims, relations=relations)
    hard = []
    advisory = []
    for relation in relations:
        (advisory if rng.random() < 0.25 else hard).append(relation["relation_id"])
    decisions = [claim["claim_id"] for claim in claims if rng.random() < 0.18]
    policy = create_impact_policy(
        snapshot,
        hard_relation_ids=hard,
        advisory_relation_ids=advisory,
        decision_claim_ids=decisions,
    )
    report = analyze_source_impact(snapshot, sources, event, policy)
    candidate = {
        name: {item["claim_id"] for item in report["classifications"][name]}
        for name in ("quarantine", "survives", "affected_unresolved", "unaffected")
    }
    candidate["source_exposed"] = set(report["source_exposed_claim_ids"])
    candidate["decisions_touched"] = set(report["decision_claim_ids_touched"])
    oracle = _oracle(snapshot, event, policy)
    return candidate, {
        "oracle": oracle,
        "has_cycle": len(relation_specs) > 1,
        "has_advisory": bool(advisory),
        "has_backup": any(len(claim["provenance"]) > 1 for claim in claims),
    }


def run(iterations: int) -> dict:
    rng = random.Random(SEED)
    mismatches = []
    coverage = {"cases_with_advisory": 0, "cases_with_backup_anchor": 0, "cases_with_transitive_quarantine": 0}
    for index in range(iterations):
        candidate, metadata = _case(rng, index)
        oracle = metadata["oracle"]
        if candidate != oracle:
            mismatches.append(
                {
                    "case": index,
                    "candidate": {key: sorted(value) for key, value in candidate.items()},
                    "oracle": {key: sorted(value) for key, value in oracle.items()},
                }
            )
            if len(mismatches) >= 3:
                break
        coverage["cases_with_advisory"] += int(metadata["has_advisory"])
        coverage["cases_with_backup_anchor"] += int(metadata["has_backup"])
        coverage["cases_with_transitive_quarantine"] += int(
            bool(oracle["quarantine"] - oracle["source_exposed"])
        )
    return {
        "schema": "openline.claim-impact.differential-probe.v1",
        "status": "PASS" if not mismatches else "FAIL",
        "seed": SEED,
        "iterations": iterations,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "coverage": coverage,
        "claim_boundary": (
            "Randomized differential testing validates implementation agreement with a separate oracle. "
            "It does not validate real-world dependency-edge accuracy or product value."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=2_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.iterations)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
