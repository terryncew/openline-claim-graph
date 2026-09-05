from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "scripts" / "run_experiment.py"


def _runner():
    spec = importlib.util.spec_from_file_location("claimgraph_unobserved_runner_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_unobserved_state_falsifier_triggers_without_retroactive_edge():
    fixture = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
    result = _runner().run(fixture)

    assert result["verdict"] == "CLAIMGRAPH_UNOBSERVED_STATE_FALSIFIED"
    assert result["arms"][1]["target"]["disposition"] == "SURVIVE"
    assert result["arms"][2]["target"]["disposition"] == "SURVIVE"
    assert result["metrics"]["declared_replay_unresolved_recall"] == 0.0
    assert result["metrics"]["fresh_verification_reopen_recall"] == 0.0
    assert result["metrics"]["unrelated_state_preservation"] == 1.0
    assert result["metrics"]["frozen_manifests_unchanged"] is True
    assert result["metrics"]["post_outcome_dependency_edges_added"] == 0
    assert result["earned_next_primitive"] == "PROSPECTIVE_VERIFICATION_DEPENDENCY_OR_REPLAY_CONTRACT"


def test_external_basis_is_absent_from_both_frozen_manifests():
    fixture = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
    external = fixture["external_state"]["basis_id"]
    for row in fixture["decisions"]:
        manifest = row["manifest"]
        ids = {item.get("basis_id") for item in manifest.get("basis", [])}
        ids |= {item.get("assumption_id") for item in manifest.get("assumptions", [])}
        assert external not in ids
