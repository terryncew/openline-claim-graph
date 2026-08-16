from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .bundle import verify_bundle
from .graph import verify_projection
from .receipts import verify_receipt, verify_source_disclosure


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(value: Any) -> int:
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0 if value.get("valid") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify OpenLine claim-graph prototype artifacts")
    sub = parser.add_subparsers(dest="command", required=True)

    receipt = sub.add_parser("verify-receipt", help="verify a signed graph-state receipt")
    receipt.add_argument("--snapshot", required=True)
    receipt.add_argument("--receipt", required=True)
    receipt.add_argument("--sources", required=True)
    receipt.add_argument("--public-key", required=True)
    receipt.add_argument("--parent", action="append", default=[])

    projection = sub.add_parser("verify-projection", help="verify a bounded graph projection")
    projection.add_argument("--projection", required=True)
    projection.add_argument("--policy")

    disclosure = sub.add_parser("verify-source-disclosure", help="verify projected source commitments")
    disclosure.add_argument("--disclosure", required=True)
    disclosure.add_argument("--projection", required=True)
    disclosure.add_argument("--receipt", required=True)

    bundle = sub.add_parser("verify-bundle", help="verify the complete receiver-scoped bundle")
    bundle.add_argument("--snapshot", required=True)
    bundle.add_argument("--receipt", required=True)
    bundle.add_argument("--sources", required=True)
    bundle.add_argument("--projection", required=True)
    bundle.add_argument("--disclosure", required=True)
    bundle.add_argument("--policy", required=True)
    bundle.add_argument("--public-key", required=True)
    bundle.add_argument("--parent", action="append", default=[])

    args = parser.parse_args(argv)
    if args.command == "verify-receipt":
        sources_doc = _load(args.sources)
        sources = {item["source_id"]: item for item in sources_doc["sources"]}
        return _emit(
            verify_receipt(
                _load(args.receipt),
                _load(args.snapshot),
                sources,
                pinned_public_key=args.public_key,
                parent_snapshots=[_load(path) for path in args.parent],
            )
        )
    if args.command == "verify-projection":
        policy = _load(args.policy) if args.policy else None
        return _emit(verify_projection(_load(args.projection), policy))
    if args.command == "verify-bundle":
        sources_doc = _load(args.sources)
        sources = {item["source_id"]: item for item in sources_doc["sources"]}
        return _emit(
            verify_bundle(
                snapshot=_load(args.snapshot),
                receipt=_load(args.receipt),
                sources=sources,
                projection=_load(args.projection),
                source_disclosure=_load(args.disclosure),
                receiver_policy=_load(args.policy),
                pinned_public_key=args.public_key,
                parent_snapshots=[_load(path) for path in args.parent],
            )
        )
    return _emit(
        verify_source_disclosure(
            _load(args.disclosure),
            _load(args.projection),
            _load(args.receipt),
        )
    )
