from __future__ import annotations
import hashlib, json
from copy import deepcopy
from pathlib import Path

OUT = Path(__file__).parent

# Minimal experimental representation only. This does not modify incumbent code.
DECISIONS = {
    "X": {"support_sets": [{"A"}], "unresolved": set()},
    "Y": {"support_sets": [{"A", "B"}], "unresolved": set()},
    "Z": {"support_sets": [{"A"}], "unresolved": {"O"}},
    "ALT": {"support_sets": [{"A", "B"}, {"C"}], "unresolved": set()},
}


def root(state):
    body = json.dumps({
        "standing": sorted(state["standing"]),
        "unresolved": {k: sorted(v) for k, v in sorted(state["unresolved"].items())},
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def _status(decision, state, name):
    complete = [sorted(s) for s in decision["support_sets"] if s <= state["standing"]]
    unresolved = set(state["unresolved"].get(name, set())) | set(decision.get("unresolved", set()))
    if not complete:
        cls = "BLOCKED"
    elif unresolved:
        cls = "AFFECTED_UNRESOLVED"
    else:
        cls = "RECONSIDERABLE"
    return cls, complete, sorted(unresolved)


def project(decisions, state, basis, expected_root):
    if root(state) != expected_root:
        raise ValueError("state_root_mismatch")
    universe = {x for d in decisions.values() for s in d["support_sets"] for x in s}
    if basis not in universe:
        return {"event": "NO_CHANGE", "state": state, "rows": {}}
    if basis in state["standing"]:
        return {"event": "NO_CHANGE", "state": state, "rows": {}}
    post = deepcopy(state)
    post["standing"].add(basis)
    rows = {}
    for name, d in decisions.items():
        if not any(basis in s for s in d["support_sets"]):
            continue
        before, _before_sets, _before_unresolved = _status(d, state, name)
        after, complete, unresolved = _status(d, post, name)
        if before == after:
            continue
        rows[name] = {
            "before": before,
            "classification": after,
            "complete_support_sets": complete,
            "unresolved": unresolved,
        }
    return {"event": "GAIN_OF_STANDING", "state": post, "rows": rows}


def run():
    base = {
        "standing": {"C"},
        "unresolved": {"Z": {"O"}},
    }
    r = root(base)
    tests = {}

    out = project(DECISIONS, base, "A", r)
    tests["sole_blocker_reopens_option"] = out["rows"]["X"]["classification"] == "RECONSIDERABLE"
    tests["second_hard_blocker_not_laundered"] = "Y" not in out["rows"]
    tests["unresolved_objection_not_laundered"] = out["rows"]["Z"]["classification"] == "AFFECTED_UNRESOLVED"
    # ALT already has complete alternative C before A; restoration should not be credited with an existing option.
    tests["existing_alternative_not_misread_as_gain"] = "ALT" not in out["rows"]

    replay = project(DECISIONS, out["state"], "A", root(out["state"]))
    tests["idempotent_replay"] = replay["event"] == "NO_CHANGE" and replay["rows"] == {}

    try:
        project(DECISIONS, base, "A", "0" * 64)
        tests["stale_state_rejected"] = False
    except ValueError as e:
        tests["stale_state_rejected"] = str(e) == "state_root_mismatch"

    unknown = project(DECISIONS, base, "NOT_A_DEPENDENCY", r)
    tests["unknown_basis_no_effect"] = unknown["event"] == "NO_CHANGE" and unknown["rows"] == {}

    # Exact binding: B restoration cannot satisfy A.
    b_out = project(DECISIONS, base, "B", r)
    tests["exact_basis_binding"] = "Y" not in b_out["rows"]

    result = {
        "tests": tests,
        "passed": sum(tests.values()),
        "total": len(tests),
        "all_passed": all(tests.values()),
        "sample_A_rows": out["rows"],
    }
    (OUT / "ADVERSARIAL_RESULT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    assert all(tests.values())

if __name__ == "__main__":
    run()
