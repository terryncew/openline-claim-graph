"""Independent deterministic verifier for PARSER-PROVENANCE-COLD-001."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
RUN_PATH = HERE / "run.py"
EXPECTED_BASE = "559d179dcb30417f7e453edf3ed5778ba99733a0"
ALLOWED_VERDICTS = {
    "PROVENANCE_OR_LINEAGE_BARRIER_FAILED",
    "SEMANTIC_IDENTITY_GUARD_ALREADY_PRESENT",
    "PROVENANCE_BARRIER_HELD_IDENTITY_SEMANTICS_UNEARNED",
    "INCONCLUSIVE_EXISTING_BOUNDARY",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_runner():
    spec = importlib.util.spec_from_file_location("parser_provenance_cold_runner", RUN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_dir")
    args = parser.parse_args(argv)
    artifact = Path(args.artifact_dir).resolve()

    result_path = artifact / "result.json"
    sums_path = artifact / "SHA256SUMS.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    sums = json.loads(sums_path.read_text(encoding="utf-8"))

    if result.get("experiment_id") != "PARSER-PROVENANCE-COLD-001":
        raise AssertionError("experiment id mismatch")
    if result.get("base_commit") != EXPECTED_BASE:
        raise AssertionError("base commit mismatch")
    if result.get("verdict") not in ALLOWED_VERDICTS:
        raise AssertionError("unknown verdict")
    if sums.get("result.json") != sha(result_path):
        raise AssertionError("result checksum mismatch")
    if sums.get("fixture.json") != sha(HERE / "fixture.json"):
        raise AssertionError("fixture checksum mismatch")

    runner = load_runner()
    runner.self_test()
    with tempfile.TemporaryDirectory() as td:
        reproduced = runner.reproduce(Path(td))
        if reproduced != result:
            raise AssertionError("deterministic reproduction mismatch")

    cases = result["cases"]
    if result["verdict"] == "PROVENANCE_BARRIER_HELD_IDENTITY_SEMANTICS_UNEARNED":
        if not cases["source_anchor_tamper"]["tamper_rejected"]:
            raise AssertionError("source tamper survived")
        if not cases["parallel_conflict"]["silent_merge_rejected"]:
            raise AssertionError("parallel conflict collapsed silently")
        if not cases["parallel_conflict"]["preserve_all_valid"]:
            raise AssertionError("explicit preserve-all conflict state invalid")
        if not cases["receipt_binding"]["tamper_rejected"]:
            raise AssertionError("receipt did not bind merge selection")
        if not cases["semantic_identity_boundary"]["wrong_selection_receipt_valid"]:
            raise AssertionError("boundary classification inconsistent")
        if cases["semantic_identity_boundary"]["wrong_selection_projection_disposition"] != "ADMIT":
            raise AssertionError("boundary classification inconsistent")

    print(f"PARSER-PROVENANCE-COLD-001 verified: {result['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
