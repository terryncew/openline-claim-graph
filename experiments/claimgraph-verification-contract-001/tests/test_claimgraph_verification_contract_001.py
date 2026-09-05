from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "scripts" / "run_experiment.py"


def _runner():
    spec = importlib.util.spec_from_file_location("claimgraph_verification_contract_runner_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prospective_verification_contract_survives_falsifiers():
    fixture = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
    result = _runner().run(fixture)
    by_arm = {row["arm"]: row for row in result["arms"]}

    assert result["verdict"] == "CLAIMGRAPH_VERIFICATION_CONTRACT_PASS"
    assert by_arm["WITHIN_BUDGET_NO_RESULT"]["target"]["disposition"] == "SURVIVE"
    assert by_arm["MISSED_DEADLINE_NO_RESULT"]["target"]["disposition"] == "ESCALATE"
    assert by_arm["UNADMITTED_FRESH_FAILURE"]["target"]["disposition"] == "ESCALATE"
    assert by_arm["UNRECOGNIZED_VERIFIER_FAILURE"]["target"]["disposition"] == "ESCALATE"
    assert by_arm["STALE_ADMITTED_FAILURE"]["target"]["disposition"] == "ESCALATE"
    assert by_arm["FRESH_ADMITTED_PASS"]["target"]["disposition"] == "SURVIVE"
    assert by_arm["FRESH_ADMITTED_FAILURE"]["target"]["disposition"] == "REOPEN"
    assert all(row["control"]["disposition"] == "SURVIVE" for row in result["arms"])


def test_contract_is_prospective_and_manifests_never_mutate():
    fixture = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
    result = _runner().run(fixture)
    contract = fixture["verification_contract"]
    target = next(row["manifest"] for row in fixture["decisions"] if row["role"] == "TARGET")

    assert contract["declared_at_acceptance"] is True
    assert contract["current_external_state_embedded"] is False
    assert contract["dependency_id"] in {item["basis_id"] for item in target["basis"]}
    assert result["metrics"]["frozen_manifests_unchanged"] is True
    assert result["metrics"]["post_outcome_dependency_edges_added"] == 0
    assert result["production_semantics_changed"] is False
