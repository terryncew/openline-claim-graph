from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "scripts" / "run_experiment.py"
RESULT = HERE / "artifacts" / "RESULT.json"
VERIFICATION = HERE / "artifacts" / "VERIFICATION.json"
RESULT_SHA = HERE / "artifacts" / "RESULT.sha256"


def load_runner():
    spec = importlib.util.spec_from_file_location("claimgraph_verification_contract_runner", RUNNER)
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
    result_sha256 = hashlib.sha256(RESULT.read_bytes()).hexdigest()
    by_arm = {row["arm"]: row for row in observed["arms"]}

    checks = {
        "result_reproduces": observed == reproduced,
        "verdict_passed": observed.get("verdict") == "CLAIMGRAPH_VERIFICATION_CONTRACT_PASS",
        "fresh_admitted_failure_reopens": by_arm["FRESH_ADMITTED_FAILURE"]["target"]["disposition"] == "REOPEN",
        "fresh_admitted_pass_survives": by_arm["FRESH_ADMITTED_PASS"]["target"]["disposition"] == "SURVIVE",
        "overdue_missing_verification_escalates": by_arm["MISSED_DEADLINE_NO_RESULT"]["target"]["disposition"] == "ESCALATE",
        "unadmitted_result_does_not_reopen": by_arm["UNADMITTED_FRESH_FAILURE"]["target"]["disposition"] == "ESCALATE",
        "unrecognized_verifier_does_not_reopen": by_arm["UNRECOGNIZED_VERIFIER_FAILURE"]["target"]["disposition"] == "ESCALATE",
        "stale_result_does_not_reopen": by_arm["STALE_ADMITTED_FAILURE"]["target"]["disposition"] == "ESCALATE",
        "unrelated_control_never_reopens": all(row["control"]["disposition"] == "SURVIVE" for row in observed["arms"]),
        "prospective_contract_present": observed["metrics"]["prospective_contract_present_at_acceptance"] is True,
        "manifests_unchanged": observed["metrics"]["frozen_manifests_unchanged"] is True,
        "no_post_outcome_dependency_added": observed["metrics"]["post_outcome_dependency_edges_added"] == 0,
        "production_semantics_unchanged": observed.get("production_semantics_changed") is False,
    }
    verification = {
        "schema": "openline.claimgraph-verification-contract-verification.v1",
        "experiment": "CLAIMGRAPH-VERIFICATION-CONTRACT-001",
        "result_sha256": result_sha256,
        "checks": checks,
        "pass": all(checks.values()),
        "meaning": "PASS means the frozen candidate primitive reproduced and survived every preregistered falsifier in this injected case.",
    }
    VERIFICATION.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_SHA.write_text(result_sha256 + "  RESULT.json\n", encoding="utf-8")
    print(json.dumps({"verification_pass": verification["pass"], "result_sha256": result_sha256}, sort_keys=True))
    if not verification["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
