from __future__ import annotations

import argparse
from pathlib import Path

from external_common import (
    adaptation_manifest,
    build_adaptation,
    load_json,
    read_jsonl,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build frozen SRE-001 adaptation from pinned LongMemEval-V2 sample excerpts")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-pins", default=str(ROOT / "SOURCE_PINS.json"))
    parser.add_argument("--adapter-policy", default=str(ROOT / "ADAPTER_POLICY.json"))
    args = parser.parse_args()

    source_pins = load_json(args.source_pins)
    adapter_policy = load_json(args.adapter_policy)
    rows = read_jsonl(args.source)
    adaptation = build_adaptation(rows, source_pins, adapter_policy)
    manifest = adaptation_manifest(adaptation, args.source, source_pins)
    write_json(args.output, adaptation)
    write_json(args.manifest, manifest)
    print(f"built {adaptation['episode_count']} external lifecycle episodes from {len(adaptation['selected_trajectory_ids'])} trajectories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
