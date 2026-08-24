#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "artifacts" / "standing-recall"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def verify_receipt(relative: str) -> dict[str, Any]:
    directory = LEDGER / relative
    receipt = load(directory / "RUN_RECEIPT.json")
    require(receipt.get("schema") == "openline.standing-recall-ci-receipt.v1", f"{relative}: bad receipt schema")
    require(receipt.get("policy_authority") == "NONE", f"{relative}: policy authority drift")
    files = receipt.get("files")
    require(isinstance(files, dict) and files, f"{relative}: missing file table")
    for name, meta in sorted(files.items()):
        path = directory / name
        require(path.exists(), f"{relative}: missing {name}")
        require(path.stat().st_size == meta.get("bytes"), f"{relative}: byte length mismatch for {name}")
        require(sha256_file(path) == meta.get("sha256"), f"{relative}: SHA-256 mismatch for {name}")

    verdict = load(directory / "verdict.json")
    independent = load(directory / "independent-verification.json")
    score = load(directory / "score.json")

    require(verdict.get("verdict") == receipt.get("verdict"), f"{relative}: verdict/receipt mismatch")
    require(independent.get("verified") is True, f"{relative}: independent verifier did not pass")
    require(independent.get("mismatch_count") == 0, f"{relative}: independent mismatch count is non-zero")
    require(independent.get("verdict") == verdict.get("verdict"), f"{relative}: independent verdict mismatch")
    require(score.get("policy_authority") == "NONE", f"{relative}: score policy authority drift")
    return {"receipt": receipt, "verdict": verdict, "score": score, "independent": independent}


def main() -> None:
    index = load(LEDGER / "INDEX.json")
    require(index.get("schema") == "openline.standing-recall-evidence-ledger.v1", "bad ledger schema")
    require(index.get("status") == "FROZEN_EVIDENCE_CLOSURE", "ledger is not frozen")
    require(index.get("stable_release_unchanged") == "0.5.2", "stable release drift")
    require(index.get("production_api_promotion") is False, "closure cannot promote production API")
    require(index.get("policy_authority") == "NONE", "ledger policy authority drift")

    s1 = verify_receipt("sre-001-external-longmemeval-v2")
    s2 = verify_receipt("sre-002-natural-events")

    rows = {row["experiment"]: row for row in index["experiments"]}
    for result in [s1, s2]:
        exp = result["receipt"]["experiment"]
        row = rows.get(exp)
        require(row is not None, f"missing index row for {exp}")
        verdict = result["verdict"]
        require(row["verdict"] == verdict["verdict"], f"{exp}: index verdict drift")
        require(row["openline_recall"] == verdict["openline"]["affected_decision_recall"], f"{exp}: recall drift")
        require(row["openline_preservation"] == verdict["openline"]["unaffected_state_preservation"], f"{exp}: preservation drift")
        require(row["openline_replay_surface"] == verdict["openline"]["replay_surface"], f"{exp}: replay surface drift")
        require(row["best_accuracy_matching_baseline"] == verdict["best_accuracy_matching_baseline"], f"{exp}: baseline drift")
        require(row["baseline_replay_surface"] == verdict["best_accuracy_matching_baseline_replay_surface"], f"{exp}: baseline surface drift")
        require(abs(row["replay_surface_reduction"] - verdict["replay_surface_reduction_vs_best_accuracy_matching_baseline"]) < 1e-15, f"{exp}: reduction drift")

    # Weld the narrow public readout.
    require(s1["verdict"]["openline"]["affected_decision_recall"] == 1.0, "SRE-001 recall changed")
    require(s1["verdict"]["openline"]["unaffected_state_preservation"] == 1.0, "SRE-001 preservation changed")
    require(s1["verdict"]["openline"]["replay_surface"] == 40, "SRE-001 OpenLine surface changed")
    require(s1["verdict"]["best_accuracy_matching_baseline_replay_surface"] == 120, "SRE-001 baseline surface changed")

    require(s2["verdict"]["natural_event_count"] == 8, "SRE-002 event count changed")
    require(s2["verdict"]["scored_target_count"] == 24, "SRE-002 target count changed")
    require(s2["verdict"]["gold_distribution"] == {"REOPEN": 12, "SURVIVE": 12}, "SRE-002 gold distribution changed")
    require(s2["verdict"]["openline"]["affected_decision_recall"] == 1.0, "SRE-002 recall changed")
    require(s2["verdict"]["openline"]["unaffected_state_preservation"] == 1.0, "SRE-002 preservation changed")
    require(s2["verdict"]["openline"]["replay_surface"] == 12, "SRE-002 OpenLine surface changed")
    require(s2["verdict"]["best_accuracy_matching_baseline_replay_surface"] == 24, "SRE-002 baseline surface changed")

    print(json.dumps({
        "valid": True,
        "schema": "openline.standing-recall-evidence-ledger-verification.v1",
        "sre001_verdict": s1["verdict"]["verdict"],
        "sre002_verdict": s2["verdict"]["verdict"],
        "production_api_promotion": False,
        "policy_authority": "NONE",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
