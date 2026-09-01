from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location(
    "contestability_runner", HERE / "run_contestability.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load CONTESTABILITY-001 runner")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    observed = json.loads(Path(args.result).read_text(encoding="utf-8"))
    expected = runner.run_experiment()
    valid = observed == expected and observed.get("verdict") == "PASS"
    report = {
        "schema": "openline.contestability-001-independent-verification.v1",
        "valid": valid,
        "observed_result_sha256": observed.get("result_sha256"),
        "expected_result_sha256": expected.get("result_sha256"),
        "disposition": "ADMIT_MECHANICS_RESULT" if valid else "DENY_MECHANICS_RESULT",
        "claim_boundary": (
            "Recomputes the experiment from frozen local fixtures/profile/policy. "
            "It does not independently verify the IETF draft's COSE objects."
        ),
    }
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
