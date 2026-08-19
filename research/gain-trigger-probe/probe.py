from __future__ import annotations
import json
from collections import deque
from pathlib import Path

OUT = Path(__file__).parent

# Frozen fixture declared in PROTOCOL.md before this file existed.
# hard adjacency expresses prerequisite -> dependent.
hard_adjacency = {
    "A": ["X", "Y", "Z"],
    "B": ["Y"],
}

pre_blockers = {
    "X": {"hard": {"A"}, "unresolved": set()},
    "Y": {"hard": {"A", "B"}, "unresolved": set()},
    "Z": {"hard": {"A"}, "unresolved": {"O"}},
}


def reachable(origin: str) -> set[str]:
    seen = {origin}
    q = deque([origin])
    while q:
        cur = q.popleft()
        for dep in hard_adjacency.get(cur, []):
            if dep not in seen:
                seen.add(dep)
                q.append(dep)
    return seen - {origin}


def recompute_after_restore(restored: str):
    results = {}
    for node, blockers in pre_blockers.items():
        hard = set(blockers["hard"])
        unresolved = set(blockers["unresolved"])
        hard.discard(restored)
        results[node] = {
            "remaining_hard": sorted(hard),
            "remaining_unresolved": sorted(unresolved),
            "auto_clean": not hard and not unresolved,
        }
    return results


naive = sorted(reachable("A"))
recomputed = recompute_after_restore("A")
expected = {"X": True, "Y": False, "Z": False}
actual = {node: row["auto_clean"] for node, row in recomputed.items()}

fail_naive_nodes = sorted(
    node for node in naive
    if recomputed[node]["remaining_hard"] or recomputed[node]["remaining_unresolved"]
)

report = {
    "protocol_sha256": "30d56f74e45b867162af72722c9359671a8c238c43e3aecb81367dcee9498e5b",
    "restored_basis": "A",
    "naive_reachability": naive,
    "condition_recomputation": recomputed,
    "expected_auto_clean": expected,
    "actual_auto_clean": actual,
    "fail_naive_nodes": fail_naive_nodes,
    "fixture_result": "PASS" if actual == expected else "FAIL",
    "naive_result": "FAIL-NAIVE" if fail_naive_nodes else "NAIVE-NOT-FALSIFIED",
}

(OUT / "RESULT.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print(json.dumps(report, indent=2, sort_keys=True))

assert actual == expected
assert fail_naive_nodes == ["Y", "Z"]
