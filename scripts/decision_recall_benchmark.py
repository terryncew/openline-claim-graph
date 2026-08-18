from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from openline_claim_graph.decision_recall import (
    aggregate_scores,
    create_adjudication_packet,
    create_gold,
    create_manifest,
    create_pre_trigger_record,
    create_review_packet,
    create_review_outcome,
    create_review_times,
    create_revocation_event,
    create_stream_seal,
    run_predictions,
    score_predictions,
    validate_manifest,
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _summary(draft: dict) -> str:
    lines = [
        f"DECISION: {draft.get('decision', '')}",
        f"REQUIRED: {', '.join(draft.get('required_dependencies', [])) or '(none)'}",
    ]
    alternatives = draft.get("alternative_support", [])
    lines.append(
        "ALTERNATIVES: " + (
            "; ".join(f"{item.get('group_id')}: {', '.join(item.get('dependency_ids', []))}" for item in alternatives)
            if alternatives else "(none)"
        )
    )
    assumptions = draft.get("assumptions", [])
    lines.append("ASSUMPTIONS: " + ("; ".join(item.get("statement", "") for item in assumptions) if assumptions else "(none)"))
    conditions = draft.get("invalidation_conditions", [])
    lines.append(
        "INVALIDATES ON: " + (
            "; ".join(f"{item.get('dependency_id')} -> {', '.join(item.get('event_types', []))}" for item in conditions)
            if conditions else "(none)"
        )
    )
    artifact = draft.get("resulting_artifact", {})
    lines.append(f"ARTIFACT: {artifact.get('locator', '')}")
    return "\n".join(lines)


def capture(args) -> int:
    draft_path = Path(args.draft)
    draft = load(draft_path)
    started_wall = now()
    started = time.monotonic_ns()
    corrections = 0
    working = dict(draft)

    while True:
        print("\n" + _summary(working) + "\n", flush=True)
        answer = input("Accept dependency record? [a]ccept / [e]dit / [q]uit: ").strip().lower()
        if answer in {"a", "accept", "y", "yes"}:
            break
        if answer in {"q", "quit", "n", "no"}:
            return 2
        if answer not in {"e", "edit"}:
            print("Choose a, e, or q.")
            continue
        editor = os.environ.get("EDITOR")
        if not editor:
            print("$EDITOR is not set; edit the draft file externally and press Enter when done.")
            input()
            working = load(draft_path)
        else:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
                temp_path = Path(handle.name)
                handle.write(json.dumps(working, indent=2, sort_keys=True) + "\n")
            try:
                subprocess.run([editor, str(temp_path)], check=True)
                working = load(temp_path)
            finally:
                temp_path.unlink(missing_ok=True)
        corrections += 1

    elapsed_ms = max(0, (time.monotonic_ns() - started) // 1_000_000)
    confirmed_wall = now()
    capture_meta = {
        "started_at": started_wall,
        "confirmed_at": confirmed_wall,
        "human_capture_milliseconds": int(elapsed_ms),
        "drafted_by": working.get("drafted_by", args.drafted_by),
        "confirmed_by": args.confirmed_by,
        "correction_count": corrections,
        "timing_source": "MONOTONIC_CLI",
    }
    manifest = create_manifest(
        decision_id=working["decision_id"],
        accepted_at=working.get("accepted_at", confirmed_wall),
        decision=working["decision"],
        basis=working.get("basis", []),
        required_dependencies=working.get("required_dependencies", []),
        alternative_support=working.get("alternative_support", []),
        assumptions=working.get("assumptions", []),
        invalidation_conditions=working.get("invalidation_conditions", []),
        resulting_artifact=working.get("resulting_artifact", {}),
        capture=capture_meta,
        metadata=working.get("metadata", {}),
    )
    write(Path(args.output), manifest)
    print(json.dumps({
        "valid": True,
        "decision_id": manifest["decision_id"],
        "manifest_id": manifest["manifest_id"],
        "human_capture_milliseconds": manifest["capture"]["human_capture_milliseconds"],
        "correction_count": corrections,
        "output": args.output,
    }, indent=2))
    return 0


def record(args) -> int:
    payload = load(Path(args.input))
    result = create_pre_trigger_record(
        decision_id=payload["decision_id"],
        decision=payload["decision"],
        available_at=payload.get("available_at", now()),
        materials=payload.get("materials", []),
    )
    write(Path(args.output), result)
    print(json.dumps({"valid": True, "pre_trigger_record_id": result["pre_trigger_record_id"], "output": args.output}, indent=2))
    return 0


def seal(args) -> int:
    manifest_paths = sorted(Path(args.manifest_dir).glob(args.glob))
    if not manifest_paths:
        raise SystemExit("no manifest files found")
    manifests = [load(path) for path in manifest_paths]
    bad = [(str(path), validate_manifest(manifest)) for path, manifest in zip(manifest_paths, manifests)]
    bad = [(path, result) for path, result in bad if not result["valid"]]
    if bad:
        raise SystemExit(f"invalid manifests: {bad}")
    record_paths = sorted(Path(args.record_dir).glob(args.record_glob))
    if not record_paths:
        raise SystemExit("no pre-trigger record files found")
    pre_trigger_records = [load(path) for path in record_paths]
    eligible_payload = load(Path(args.eligible_bases))
    if not isinstance(eligible_payload, dict) or "eligible_bases" not in eligible_payload or "custody" not in eligible_payload:
        raise SystemExit("eligible-bases file must contain both eligible_bases and custody")
    eligible_bases = eligible_payload["eligible_bases"]
    catalog_custody = eligible_payload["custody"]
    stream = create_stream_seal(
        benchmark_id=args.benchmark_id,
        sealed_at=args.sealed_at or now(),
        manifests=manifests,
        pre_trigger_records=pre_trigger_records,
        eligible_bases=eligible_bases,
        eligible_basis_catalog_custody=catalog_custody,
        protocol_id=args.protocol_id,
    )
    write(Path(args.output), stream)
    print(json.dumps({"valid": True, "manifest_count": stream["manifest_count"], "stream_seal_id": stream["stream_seal_id"], "output": args.output}, indent=2))
    return 0


def natural_event(args) -> int:
    seal_value = load(Path(args.stream_seal))
    result = create_revocation_event(
        stream_seal=seal_value,
        basis_id=args.basis_id,
        event_at=args.event_at or now(),
        reason=args.reason,
        locator=args.locator or "",
        evidence_sha256=args.evidence_sha256 or "",
        stratum="NATURAL",
    )
    write(Path(args.output), result)
    print(json.dumps({"valid": True, "event_id": result["event_id"], "output": args.output}, indent=2))
    return 0


def predict(args) -> int:
    seal_value = load(Path(args.stream_seal))
    event = load(Path(args.event))
    out = Path(args.output_dir)
    predictions = run_predictions(seal=seal_value, event=event)
    packet = create_adjudication_packet(seal=seal_value, event=event)
    review_packets = {
        system: create_review_packet(seal=seal_value, event=event, predictions=predictions, system=system)
        for system in ("FULL_HISTORY_REVIEW", "FLAT_LOG_SEARCH", "DECISION_RECALL")
    }
    write(out / "event.json", event)
    write(out / "predictions.json", predictions)
    write(out / "adjudication-packet.json", packet)
    write(out / "review-packet.full-history.json", review_packets["FULL_HISTORY_REVIEW"])
    write(out / "review-packet.flat-search.json", review_packets["FLAT_LOG_SEARCH"])
    write(out / "review-packet.decision-recall.json", review_packets["DECISION_RECALL"])
    print(json.dumps({
        "valid": True,
        "predictions_id": predictions["predictions_id"],
        "adjudication_packet_id": packet["adjudication_packet_id"],
        "review_packet_ids": {system: value["review_packet_id"] for system, value in review_packets.items()},
        "output_dir": str(out),
    }, indent=2))
    return 0


def gold(args) -> int:
    packet = load(Path(args.adjudication_packet))
    labels_payload = load(Path(args.labels))
    labels = labels_payload["labels"] if isinstance(labels_payload, dict) and "labels" in labels_payload else labels_payload
    result = create_gold(
        adjudication_packet=packet,
        adjudicated_at=args.adjudicated_at or now(),
        adjudicator_id=args.adjudicator_id,
        labels=labels,
        method=args.method,
    )
    write(Path(args.output), result)
    print(json.dumps({"valid": True, "gold_id": result["gold_id"], "output": args.output}, indent=2))
    return 0


def review_outcome(args) -> int:
    packet = load(Path(args.review_packet))
    labels_payload = load(Path(args.labels))
    labels = labels_payload["labels"] if isinstance(labels_payload, dict) and "labels" in labels_payload else labels_payload
    result = create_review_outcome(
        review_packet=packet,
        reviewed_at=args.reviewed_at or now(),
        reviewer_id=args.reviewer_id,
        labels=labels,
        method="BLINDED_BASELINE_REVIEW",
    )
    write(Path(args.output), result)
    print(json.dumps({"valid": True, "review_outcome_id": result["review_outcome_id"], "system": result["system"], "output": args.output}, indent=2))
    return 0


def time_review(args) -> int:
    """Measure one reviewer condition with a monotonic CLI timer.

    The packet is revealed only after the reviewer explicitly starts the trial.
    The output is a single-record JSON payload accepted by `review-times`.
    """

    packet = load(Path(args.review_packet))
    if packet.get("schema") != "openline.decision-recall-review-packet.v1":
        raise SystemExit("review packet schema mismatch")
    system = str(packet.get("system", "")).upper()
    if system not in {"FULL_HISTORY_REVIEW", "FLAT_LOG_SEARCH", "DECISION_RECALL"}:
        raise SystemExit(f"unsupported review packet system: {system}")
    print(f"Condition: {system}")
    input("Press Enter to reveal the blinded review packet and start the timer...")
    started = time.monotonic_ns()
    print(json.dumps({
        "event": packet.get("event"),
        "instructions": packet.get("instructions"),
        "rows": packet.get("rows", []),
    }, indent=2, sort_keys=True), flush=True)
    input("\nPress Enter only when this review condition is complete...")
    elapsed_ms = max(0, (time.monotonic_ns() - started) // 1_000_000)
    payload = {
        "records": [{
            "system": system,
            "reviewer_id": args.reviewer_id,
            "review_packet_id": packet["review_packet_id"],
            "review_milliseconds": int(elapsed_ms),
            "timing_source": "MONOTONIC_CLI",
            "notes": args.notes or "",
        }]
    }
    write(Path(args.output), payload)
    print(json.dumps({
        "valid": True,
        "system": system,
        "review_packet_id": packet["review_packet_id"],
        "review_milliseconds": int(elapsed_ms),
        "output": args.output,
    }, indent=2))
    return 0


def review_times(args) -> int:
    seal_value = load(Path(args.stream_seal))
    event = load(Path(args.event))
    records = []
    for path in args.records:
        payload = load(Path(path))
        values = payload["records"] if isinstance(payload, dict) and "records" in payload else payload
        records.extend(values)
    result = create_review_times(seal=seal_value, event=event, records=records)
    write(Path(args.output), result)
    print(json.dumps({"valid": True, "review_times_id": result["review_times_id"], "output": args.output}, indent=2))
    return 0


def score(args) -> int:
    outcomes = [load(Path(path)) for path in (args.review_outcome or [])]
    result = score_predictions(
        seal=load(Path(args.stream_seal)),
        event=load(Path(args.event)),
        predictions=load(Path(args.predictions)),
        gold=load(Path(args.gold)),
        review_times=load(Path(args.review_times)) if args.review_times else None,
        review_outcomes=outcomes or None,
    )
    write(Path(args.output), result)
    print(json.dumps({"valid": True, "score_id": result["score_id"], "economics": result["economics"], "output": args.output}, indent=2))
    return 0


def aggregate(args) -> int:
    seal_value = load(Path(args.stream_seal))
    policy = load(Path(args.policy))
    bundles = []
    scores = []
    for raw_dir in args.run_dir:
        run_dir = Path(raw_dir)
        bundle = {
            "event": load(run_dir / "event.json"),
            "predictions": load(run_dir / "predictions.json"),
            "gold": load(run_dir / "gold.private.json"),
            "score": load(run_dir / "score.json"),
        }
        review_path = run_dir / "review-times.json"
        if review_path.exists():
            bundle["review_times"] = load(review_path)
        outcome_paths = [run_dir / "review-outcome.full-history.json", run_dir / "review-outcome.flat-search.json"]
        if all(path.exists() for path in outcome_paths):
            bundle["review_outcomes"] = [load(path) for path in outcome_paths]
        bundles.append(bundle)
        scores.append(bundle["score"])
    result = aggregate_scores(seal=seal_value, scores=scores, policy=policy, score_artifacts=bundles)
    write(Path(args.output), result)
    print(json.dumps({"valid": True, "verdict": result["verdict"], "failed_conditions": result["failed_conditions"], "output": args.output}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prospective Decision Recall benchmark workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("capture", help="time receiver confirmation/correction of one agent-drafted decision manifest")
    p.add_argument("--draft", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--drafted-by", default="agent")
    p.add_argument("--confirmed-by", default="receiver")
    p.set_defaults(func=capture)

    p = sub.add_parser("record", help="content-address one conventional complete pre-trigger record")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=record)

    p = sub.add_parser("seal", help="seal a directory of prospectively captured manifests")
    p.add_argument("--manifest-dir", required=True)
    p.add_argument("--glob", default="*.json")
    p.add_argument("--record-dir", required=True, help="complete conventional pre-trigger records, separate from dependency manifests")
    p.add_argument("--record-glob", default="*.json")
    p.add_argument("--eligible-bases", required=True, help="manifest-blind basis catalog plus custody declaration; may include bases omitted from manifests")
    p.add_argument("--benchmark-id", required=True)
    p.add_argument("--protocol-id", default="decision-recall-prospective-001-v1")
    p.add_argument("--sealed-at")
    p.add_argument("--output", required=True)
    p.set_defaults(func=seal)

    p = sub.add_parser("natural-event", help="record a real post-seal loss of standing, including bases absent from the controlled catalog")
    p.add_argument("--stream-seal", required=True)
    p.add_argument("--basis-id", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--locator")
    p.add_argument("--evidence-sha256")
    p.add_argument("--event-at")
    p.add_argument("--output", required=True)
    p.set_defaults(func=natural_event)

    p = sub.add_parser("predict", help="run baselines and Decision Recall, then emit a prediction-blind adjudication packet")
    p.add_argument("--stream-seal", required=True)
    p.add_argument("--event", required=True)
    p.add_argument("--output-dir", required=True)
    p.set_defaults(func=predict)

    p = sub.add_parser("gold", help="bind blinded adjudication labels after predictions exist")
    p.add_argument("--adjudication-packet", required=True)
    p.add_argument("--labels", required=True)
    p.add_argument("--adjudicator-id", required=True)
    p.add_argument("--adjudicated-at")
    p.add_argument("--method", default="INDEPENDENT_BLINDED_REVIEW")
    p.add_argument("--output", required=True)
    p.set_defaults(func=gold)

    p = sub.add_parser("review-outcome", help="bind a blinded human baseline disposition to a Full History or Flat Search review packet")
    p.add_argument("--review-packet", required=True)
    p.add_argument("--labels", required=True)
    p.add_argument("--reviewer-id", required=True)
    p.add_argument("--reviewed-at")
    p.add_argument("--output", required=True)
    p.set_defaults(func=review_outcome)

    p = sub.add_parser("time-review", help="run one system-specific reviewer condition with a monotonic CLI timer")
    p.add_argument("--review-packet", required=True)
    p.add_argument("--reviewer-id", required=True)
    p.add_argument("--notes")
    p.add_argument("--output", required=True, help="single-record JSON payload; combine three conditions before review-times")
    p.set_defaults(func=time_review)

    p = sub.add_parser("review-times", help="bind instrumented reviewer-time measurements for one revocation")
    p.add_argument("--stream-seal", required=True)
    p.add_argument("--event", required=True)
    p.add_argument("--records", action="append", required=True, help="repeatable JSON array or {records:[...]} with instrumented per-system review records")
    p.add_argument("--output", required=True)
    p.set_defaults(func=review_times)

    p = sub.add_parser("score", help="score one revocation against independent gold")
    p.add_argument("--stream-seal", required=True)
    p.add_argument("--event", required=True)
    p.add_argument("--predictions", required=True)
    p.add_argument("--gold", required=True)
    p.add_argument("--review-times")
    p.add_argument("--review-outcome", action="append", help="repeat for Full History and Flat Search blinded baseline outcomes")
    p.add_argument("--output", required=True)
    p.set_defaults(func=score)

    p = sub.add_parser("aggregate", help="apply the frozen promotion rule across scored revocations")
    p.add_argument("--stream-seal", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--run-dir", action="append", required=True, help="repeatable event-run directory containing event/predictions/gold/score and optional review-times")
    p.add_argument("--output", required=True)
    p.set_defaults(func=aggregate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
