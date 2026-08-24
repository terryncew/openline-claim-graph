from __future__ import annotations

import argparse
import json
from pathlib import Path

from standing_recall import load_json, run_benchmark, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    fixture = load_json(args.fixture)
    score = run_benchmark(fixture)
    write_json(args.output, score)
    summary = {
        item["system"]: {
            "recall": item["affected_decision_recall"],
            "preservation": item["unaffected_state_preservation"],
            "replay_surface": item["replay_surface"],
        }
        for item in score["systems"]
    }
    print(json.dumps({"status": score["status"], "systems": summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
