from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    status = json.loads((ROOT / "STATUS.json").read_text(encoding="utf-8"))
    if status.get("status") != "FROZEN_PROTOCOL_CONFORMANCE_PASS_EXTERNAL_ADAPTATION_UNRUN":
        raise SystemExit("unexpected SRE-001 status")
    if status.get("external_benchmark_run") is not False:
        raise SystemExit("external benchmark must remain unrun")
    if status.get("production_semantics_changed") is not False:
        raise SystemExit("SRE-001 must not claim a production semantics change")
    if status.get("policy_authority") != "NONE":
        raise SystemExit("policy authority must remain NONE")
    expected = status["conformance"]
    paths = {
        "fixture_sha256": ROOT / "artifacts/conformance/fixture.json",
        "score_sha256": ROOT / "artifacts/conformance/score.json",
        "independent_verification_sha256": ROOT / "artifacts/conformance/independent-verification.json",
    }
    mismatches = []
    for field, path in paths.items():
        observed = sha(path)
        if expected.get(field) != observed:
            mismatches.append({"field": field, "expected": expected.get(field), "observed": observed})
    if mismatches:
        print(json.dumps({"valid": False, "mismatches": mismatches}, indent=2, sort_keys=True))
        return 2
    print(json.dumps({"valid": True, "status": status["status"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
