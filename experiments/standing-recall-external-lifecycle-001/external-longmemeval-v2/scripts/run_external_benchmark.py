from __future__ import annotations

import argparse
from pathlib import Path

from external_common import grade_external, load_json, run_external_benchmark, write_json

ROOT = Path(__file__).resolve().parents[1]
SRE_ROOT = ROOT.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frozen SRE-001 external LongMemEval-V2 adaptation")
    parser.add_argument("--adaptation", required=True)
    parser.add_argument("--score", required=True)
    parser.add_argument("--verdict", required=True)
    parser.add_argument("--promotion-policy", default=str(SRE_ROOT / "promotion-policy.json"))
    args = parser.parse_args()

    adaptation = load_json(args.adaptation)
    promotion = load_json(args.promotion_policy)
    score = run_external_benchmark(adaptation)
    verdict = grade_external(adaptation, score, promotion)
    write_json(args.score, score)
    write_json(args.verdict, verdict)
    print(verdict["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
