"""Run a fully unattended Frame Ledger proposal/review/admission cycle.

The receiver supplies a policy, public-key-pinned actor configuration, and
private execution keys via environment variables.  Human confirmation is used
only when the receiver policy says REQUIRED.  Model endpoints never mutate an
accepted state directly; they return bounded proposals and reviews that are
signed and evaluated under the receiver's policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from openline_claim_graph import (
    call_openai_compatible,
    call_openai_responses,
    private_key_from_hex,
    render_frame_ledger,
    run_autonomous_frame_pipeline,
)


CONFIG_SCHEMA = "openline.frame-agent-run-config.v1"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title", default="Autonomous Frame Ledger")
    args = parser.parse_args()

    source = read(args.source)
    policy = read(args.policy)
    config = read(args.config)
    if config.get("schema") != CONFIG_SCHEMA:
        raise SystemExit("invalid run config schema")
    proposer = dict(config["proposer"])
    reviewer_configs = [dict(item) for item in config["reviewers"]]
    actor_configs = {str(proposer["actor_id"]): proposer}
    for item in reviewer_configs:
        actor_id = str(item["actor_id"])
        if actor_id in actor_configs:
            raise SystemExit(f"duplicate actor config: {actor_id}")
        actor_configs[actor_id] = item

    private_keys = {}
    for actor_id, actor in actor_configs.items():
        env_name = str(actor["private_key_env"])
        value = os.environ.get(env_name)
        if not value:
            raise SystemExit(f"missing private execution key environment variable: {env_name}")
        private_keys[actor_id] = private_key_from_hex(value)

    api_executions: list[dict[str, Any]] = []

    def agent_call(actor_id: str, task: Mapping[str, Any], schema: Mapping[str, Any]) -> Mapping[str, Any]:
        actor = actor_configs[actor_id]
        api_key_env = str(actor.get("api_key_env", "OPENAI_API_KEY"))
        api_key = os.environ.get(api_key_env)
        common = {
            "base_url": str(actor["base_url"]),
            "model": str(actor["model"]),
            "task": task,
            "output_schema": schema,
            "timeout_seconds": int(actor.get("timeout_seconds", 180)),
        }
        if actor["api_style"] == "responses":
            if not api_key:
                raise SystemExit(f"missing API key environment variable: {api_key_env}")
            response = call_openai_responses(**common, api_key=api_key)
        elif actor["api_style"] == "chat":
            response = call_openai_compatible(**common, api_key=api_key)
        else:
            raise SystemExit(f"unsupported api_style for {actor_id}")
        api_executions.append({"actor_id": actor_id, **response["execution"]})
        return response["result"]

    run = run_autonomous_frame_pipeline(
        source=source,
        policy=policy,
        proposer_id=str(proposer["actor_id"]),
        reviewer_ids=[str(item["actor_id"]) for item in reviewer_configs],
        private_keys=private_keys,
        agent_call=agent_call,
        issued_at=str(config["issued_at"]),
        absence_sets=config.get("absence_sets", []),
    )
    report = run["report"]
    html = render_frame_ledger(
        report=report,
        source=source,
        findings=run["findings"],
        policy=policy,
        finding_attestations=run["finding_attestations"],
        reviews=run["reviews"],
        review_attestations=run["review_attestations"],
        title=args.title,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write(args.output / "run.json", run)
    write(args.output / "report.json", report)
    write(args.output / "findings.json", {"findings": run["findings"]})
    write(args.output / "finding-attestations.json", {"attestations": run["finding_attestations"]})
    write(args.output / "reviews.json", {"reviews": run["reviews"]})
    write(args.output / "review-attestations.json", {"attestations": run["review_attestations"]})
    write(args.output / "execution.json", {"executions": api_executions})
    write(args.output / "review.html", html)
    summary = {
        "valid": True,
        "status": "AUTONOMOUS_RECEIVER_POLICY_RUN_COMPLETED",
        "run_id": run["run_id"],
        "report_id": report["report_id"],
        "summary": report["summary"],
        "review_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "claim_boundary": run["claim_boundary"],
    }
    write(args.output / "SUMMARY.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
