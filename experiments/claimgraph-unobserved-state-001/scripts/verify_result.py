from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
RESULT = HERE / "artifacts" / "RESULT.json"
VERIFICATION = HERE / "artifacts" / "VERIFICATION.json"
RESULT_SHA = HERE / "artifacts" / "RESULT.sha256"
RUNNER = HERE / "scripts" / "run_experiment.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("claimgraph_unobserved_runner", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load experiment runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    runner = load_runner()
    fixture = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
    observed = json.loads(RESULT.read_text(encoding="utf-8"))
    reproduced = runner.run(fixture)
    result_bytes = RESULT.read_bytes()
    result_sha256 = hashlib.sha256(result_bytes).hexdigest()

    checks = {
        "result_reproduces": observed == reproduced,
        "verdict_is_falsifier": observed.get("verdict") == "CLAIMGRAPH_UNOBSERVED_STATE_FALSIFIED",
        "fresh_verification_still_survives": observed["arms"][2]["target"]["disposition"] == "SURVIVE",
        "unrelated_control_never_reopened": all(arm["control"]["disposition"] == "SURVIVE" for arm in observed["arms"]),
        "manifests_unchanged": observed["metrics"]["frozen_manifests_unchanged"] is True,
        "no_post_outcome_dependency_added": observed["metrics"]["post_outcome_dependency_edges_added"] == 0,
        "production_semantics_unchanged": observed.get("production_semantics_changed") is False,
    }
    verification = {
        "schema": "openline.claimgraph-unobserved-state-verification.v1",
        "experiment": "CLAIMGRAPH-UNOBSERVED-STATE-001",
        "result_sha256": result_sha256,
        "checks": checks,
        "pass": all(checks.values()),
        "meaning": "PASS means the frozen falsifier result reproduced exactly; it does not mean the tested standing model passed the falsifier.",
    }
    VERIFICATION.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_SHA.write_text(result_sha256 + "  RESULT.json\n", encoding="utf-8")
    print(json.dumps({"verification_pass": verification["pass"], "result_sha256": result_sha256}, sort_keys=True))
    if not verification["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
