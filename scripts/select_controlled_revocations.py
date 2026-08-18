from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from openline_claim_graph.canonical import content_id
from openline_claim_graph.decision_recall import create_revocation_event, validate_stream_seal


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Select future-blind controlled revocations after a Decision Recall stream is sealed")
    parser.add_argument("--stream-seal", required=True)
    parser.add_argument("--seed-file", required=True, help="independent random seed bytes created after stream sealing")
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--selection-at", required=True, help="timestamp after stream seal when the independent selector commits to the seed")
    parser.add_argument("--event-at", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    seal = load(Path(args.stream_seal))
    check = validate_stream_seal(seal)
    if not check["valid"]:
        raise SystemExit(f"invalid stream seal: {check['errors']}")
    def parse_time(value: str):
        text = value[:-1] + "+00:00" if value.endswith("Z") else value
        return datetime.fromisoformat(text)
    if parse_time(args.selection_at) <= parse_time(seal["sealed_at"]):
        raise SystemExit("selection-at must be after the sealed decision stream")
    if parse_time(args.event_at) < parse_time(args.selection_at):
        raise SystemExit("event-at cannot precede selection-at")

    seed = Path(args.seed_file).read_bytes()
    if not seed:
        raise SystemExit("seed file is empty")
    # Selection uses the independently sealed eligible-basis universe, not
    # only dependencies the capture manifest happened to declare.  This is what
    # allows the benchmark to discover omitted material dependencies.
    basis_ids = sorted(item["basis_id"] for item in seal.get("eligible_bases", []))
    if args.count < 1 or args.count > len(basis_ids):
        raise SystemExit(f"count must be between 1 and {len(basis_ids)}")
    ranked = sorted(
        basis_ids,
        key=lambda basis_id: hashlib.sha256(seed + b"\0" + seal["stream_seal_id"].encode() + b"\0" + basis_id.encode()).digest(),
    )
    selected = ranked[: args.count]
    events = [
        create_revocation_event(
            stream_seal=seal,
            basis_id=basis_id,
            event_at=args.event_at,
            reason="Controlled loss-of-standing event selected after the decision stream was sealed.",
            stratum="CONTROLLED",
            selection_proof={
                "selection_at": args.selection_at,
                "selection_method": "sha256_rank(seed || stream_seal_id || basis_id)",
                "seed_hex": seed.hex(),
                "selected_count": len(selected),
                "rank": ranked.index(basis_id),
            },
        )
        for basis_id in selected
    ]
    body = {
        "schema": "openline.decision-recall-controlled-revocation-plan.v1",
        "stream_seal_id": seal["stream_seal_id"],
        "selection_at": args.selection_at,
        "selection_method": "sha256_rank(seed || stream_seal_id || basis_id)",
        "seed_sha256": hashlib.sha256(seed).hexdigest(),
        "candidate_basis_count": len(basis_ids),
        "selected_count": len(events),
        "events": events,
    }
    body = {"plan_id": content_id("decision-recall-controlled-revocation-plan", body), **body}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"valid": True, "output": str(output), "selected_count": len(events), "seed_sha256": body["seed_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
