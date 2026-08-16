"""Build a receiver policy that pins the execution keys named by a run config."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from openline_claim_graph import create_frame_policy, private_key_from_hex, public_key_hex


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--human-mode", choices=("OPTIONAL", "REQUIRED", "DISABLED"), default="OPTIONAL")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))

    def registry(actor):
        env_name = str(actor["private_key_env"])
        value = os.environ.get(env_name)
        if not value:
            raise SystemExit(f"missing private execution key environment variable: {env_name}")
        key = private_key_from_hex(value)
        return {
            "actor_id": str(actor["actor_id"]),
            "model_id": str(actor["model"]),
            "family": str(actor["family"]),
            "kind": str(actor.get("kind", "AI")),
            "public_key": public_key_hex(key),
        }

    policy = create_frame_policy(
        mechanical_auto_admit=True,
        advisory_min_confirmations=2,
        advisory_min_distinct_families=2,
        challenge_blocks=True,
        human_mode=args.human_mode,
        proposers=[registry(config["proposer"])],
        reviewers=[registry(item) for item in config["reviewers"]],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"valid": True, "output": str(args.output), "policy_id": policy["policy_id"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
