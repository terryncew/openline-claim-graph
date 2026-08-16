"""Run one Frame Ledger task against OpenAI Responses or an OpenAI-compatible server.

The process reads one task JSON object on stdin and writes one strict result
object on stdout.  It intentionally keeps provider credentials and SDKs out of
the package core.  vLLM, SGLang, llama.cpp, and many hosted open-model services
can expose the compatible chat-completions route.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from openline_claim_graph.frontier import (
    FRAME_AGENT_TASK_SCHEMA,
    call_openai_compatible,
    call_openai_responses,
    proposal_output_schema,
    review_output_schema,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a strict Frame Ledger agent task")
    parser.add_argument("--api-style", choices=("chat", "responses"), required=True)
    parser.add_argument("--base-url", required=True, help="API root including /v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    task = json.load(sys.stdin)
    if task.get("schema") != FRAME_AGENT_TASK_SCHEMA:
        raise SystemExit("invalid task schema")
    role = task.get("role")
    if role == "PROPOSER":
        schema = proposal_output_schema()
    elif role == "REVIEWER":
        schema = review_output_schema()
    else:
        raise SystemExit("invalid task role")
    api_key = os.environ.get(args.api_key_env)
    if args.api_style == "responses":
        if not api_key:
            raise SystemExit(f"missing API key environment variable: {args.api_key_env}")
        response = call_openai_responses(
            base_url=args.base_url,
            model=args.model,
            task=task,
            output_schema=schema,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
        )
    else:
        response = call_openai_compatible(
            base_url=args.base_url,
            model=args.model,
            task=task,
            output_schema=schema,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
        )
    print(json.dumps(response["result"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
