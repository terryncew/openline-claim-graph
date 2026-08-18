from __future__ import annotations

import argparse
import json
from pathlib import Path

from openline_claim_graph.canonical import sha256_hex
from openline_claim_graph.decision_recall import (
    SYSTEM_DECISION_RECALL,
    create_adjudication_packet,
    create_gold,
    create_manifest,
    create_pre_trigger_record,
    create_promotion_policy,
    create_review_packet,
    create_review_outcome,
    create_review_times,
    create_revocation_event,
    create_stream_seal,
    run_predictions,
    score_predictions,
)


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def evidence(text: str) -> str:
    return sha256_hex(text.encode("utf-8"))


def manifest(i: int, *, role: str, alt: bool = False, ambiguous: bool = False, context_extra: bool = False):
    shared = {
        "basis_id": f"dep-{i}",
        "kind": "SOFTWARE_REQUIREMENT",
        "statement": f"Requirement {i} justifies accepted change {i}.",
        "locator": f"issue:{100+i}",
        "evidence_sha256": evidence(f"requirement-{i}"),
        "role": "AMBIGUOUS" if ambiguous else role,
    }
    basis = [shared]
    required = [f"dep-{i}"] if role == "REQUIRED" and not ambiguous else []
    alternatives = []
    if alt:
        basis.append({
            "basis_id": f"alt-{i}",
            "kind": "TEST_EVIDENCE",
            "statement": f"Independent compatibility test for change {i}.",
            "locator": f"test:test_{i}",
            "evidence_sha256": evidence(f"alt-{i}"),
            "role": "ALTERNATIVE",
            "alternative_group": f"g-{i}",
        })
        alternatives = [{"group_id": f"g-{i}", "dependency_ids": [f"alt-{i}"]}]
    if context_extra:
        basis.append({
            "basis_id": "shared-context",
            "kind": "DISCUSSION",
            "statement": "Background discussion mentioned by several decisions but not relied upon.",
            "locator": "doc:background",
            "evidence_sha256": evidence("shared-context"),
            "role": "CONTEXT",
        })
    conditions = []
    if role in {"REQUIRED", "ALTERNATIVE"} and not ambiguous:
        conditions.append({
            "condition_id": f"loss-{i}",
            "dependency_id": f"dep-{i}",
            "event_types": ["LOSS_OF_STANDING"],
            "note": "Loss of this admitted material basis requires contract evaluation.",
        })
    return create_manifest(
        decision_id=f"decision-{i}",
        accepted_at=f"2026-08-18T00:{i:02d}:00Z",
        decision=f"Accept software change {i}",
        basis=basis,
        required_dependencies=required,
        alternative_support=alternatives,
        assumptions=[],
        invalidation_conditions=conditions,
        resulting_artifact={"kind": "COMMIT", "locator": f"commit:fixture-{i}", "sha256": evidence(f"artifact-{i}")},
        capture={
            "started_at": f"2026-08-18T00:{i:02d}:00Z",
            "confirmed_at": f"2026-08-18T00:{i:02d}:{20 + (i % 5)}Z",
            "human_capture_milliseconds": (20 + (i % 5)) * 1000,
            "drafted_by": "fixture-agent",
            "confirmed_by": "fixture-receiver",
            "correction_count": 0 if i % 3 else 1,
        },
        metadata={"fixture_only": True},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a mechanics-only prospective Decision Recall conformance fixture")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    manifests = [
        manifest(1, role="REQUIRED", context_extra=True),
        manifest(2, role="REQUIRED", alt=True, context_extra=True),
        manifest(3, role="CONTEXT", context_extra=False),
        manifest(4, role="REQUIRED", ambiguous=True, context_extra=True),
        manifest(5, role="REQUIRED", context_extra=True),
        manifest(6, role="REQUIRED", alt=True, context_extra=True),
        manifest(7, role="CONTEXT", context_extra=False),
        manifest(8, role="REQUIRED", context_extra=True),
    ]
    pre_trigger_records = []
    eligible_mentions: dict[str, list[str]] = {}
    for i, item in enumerate(manifests, start=1):
        mentioned = [f"dep-{i}"]
        if i in {1, 2, 4, 5, 6, 8}:
            mentioned.append("shared-context")
        if i in {2, 6}:
            mentioned.append(f"alt-{i}")
        if i == 5:
            # Central failure injection: the conventional pre-trigger record
            # contains a real basis that the tiny dependency manifest omitted.
            mentioned.append("hidden-5")
        text = "Accepted change materials. Mentioned bases: " + ", ".join(mentioned)
        record = create_pre_trigger_record(
            decision_id=item["decision_id"],
            decision=item["decision"],
            available_at=item["accepted_at"],
            materials=[{
                "material_id": f"record-{i}",
                "kind": "ISSUE_PR_TEST_BUNDLE",
                "locator": f"fixture:decision-{i}",
                "text": text,
            }],
        )
        pre_trigger_records.append(record)
        for basis_id in mentioned:
            eligible_mentions.setdefault(basis_id, []).append(record["pre_trigger_record_id"])

    eligible_bases = [
        {
            "basis_id": basis_id,
            "kind": "FIXTURE_RECORDED_BASIS",
            "locator": f"fixture-basis:{basis_id}",
            "evidence_sha256": evidence(basis_id),
            "mentioned_record_ids": record_ids,
        }
        for basis_id, record_ids in sorted(eligible_mentions.items())
    ]
    seal = create_stream_seal(
        benchmark_id="decision-recall-prospective-conformance-001",
        sealed_at="2026-08-18T01:00:00Z",
        manifests=manifests,
        pre_trigger_records=pre_trigger_records,
        eligible_bases=eligible_bases,
        eligible_basis_catalog_custody={
            "built_at": "2026-08-18T00:59:00Z",
            "builder_id": "fixture-catalog-builder",
            "method": "MANIFEST_BLIND_RECORD_ENUMERATION",
            "source_scope": "CONVENTIONAL_PRE_TRIGGER_RECORDS_ONLY",
            "manifest_visible": False,
        },
        protocol_id="decision-recall-prospective-001-v1",
    )
    policy = create_promotion_policy(
        declared_at="2026-08-18T00:00:00Z",
        minimum_decisions=30,
        minimum_controlled_revocations=10,
    )
    write(out / "stream-seal.json", seal)
    write(out / "promotion-policy.json", policy)

    events = [
        create_revocation_event(stream_seal=seal, basis_id="dep-1", event_at="2026-08-18T02:00:00Z", reason="fixture controlled revocation"),
        create_revocation_event(stream_seal=seal, basis_id="dep-2", event_at="2026-08-18T02:01:00Z", reason="fixture controlled revocation"),
        create_revocation_event(stream_seal=seal, basis_id="shared-context", event_at="2026-08-18T02:02:00Z", reason="fixture negative control"),
        create_revocation_event(stream_seal=seal, basis_id="dep-4", event_at="2026-08-18T02:03:00Z", reason="fixture ambiguity control"),
        create_revocation_event(stream_seal=seal, basis_id="hidden-5", event_at="2026-08-18T02:04:00Z", reason="fixture omitted-dependency control"),
    ]
    summaries = []
    for index, event in enumerate(events, start=1):
        event_dir = out / f"event-{index:02d}"
        predictions = run_predictions(seal=seal, event=event)
        packet = create_adjudication_packet(seal=seal, event=event)

        # This fixture gold is pre-authored conformance data, not human evidence.
        labels = []
        for row in packet["rows"]:
            did = row["decision_id"]
            decision = row["decision"]
            if event["basis_id"] == "dep-1" and decision == "Accept software change 1":
                label = "REOPEN"
            elif event["basis_id"] == "dep-2" and decision == "Accept software change 2":
                label = "SURVIVE"  # independent alternative remains
            elif event["basis_id"] == "dep-4" and decision == "Accept software change 4":
                label = "ESCALATE"
            elif event["basis_id"] == "hidden-5" and decision == "Accept software change 5":
                label = "REOPEN"  # dependency omitted from the prospective manifest
            else:
                label = "SURVIVE"
            labels.append({"decision_id": did, "label": label, "rationale": "fixture-only expected disposition"})
        gold = create_gold(
            adjudication_packet=packet,
            adjudicated_at="2026-08-18T03:00:00Z",
            adjudicator_id="fixture-not-human",
            labels=labels,
            method="CONFORMANCE_FIXTURE_NOT_EMPIRICAL_GOLD",
        )
        review_packets = {
            system: create_review_packet(seal=seal, event=event, predictions=predictions, system=system)
            for system in ("FULL_HISTORY_REVIEW", "FLAT_LOG_SEARCH", "DECISION_RECALL")
        }
        gold_map = {item["decision_id"]: item["label"] for item in labels}
        full_labels = []
        for row in review_packets["FULL_HISTORY_REVIEW"]["rows"]:
            label = gold_map[row["decision_id"]]
            # Authored control: prove the scoring layer can discover that a
            # full-history human baseline missed a warranted reopening.
            if index == 1 and row["decision_id"] == "decision-1":
                label = "SURVIVE"
            full_labels.append({"decision_id": row["decision_id"], "label": label, "rationale": "fixture baseline outcome"})
        flat_labels = [
            {"decision_id": row["decision_id"], "label": gold_map[row["decision_id"]], "rationale": "fixture baseline outcome"}
            for row in review_packets["FLAT_LOG_SEARCH"]["rows"]
        ]
        full_outcome = create_review_outcome(
            review_packet=review_packets["FULL_HISTORY_REVIEW"],
            reviewed_at="2026-08-18T02:30:00Z",
            reviewer_id="fixture-full-reviewer",
            labels=full_labels,
        )
        flat_outcome = create_review_outcome(
            review_packet=review_packets["FLAT_LOG_SEARCH"],
            reviewed_at="2026-08-18T02:31:00Z",
            reviewer_id="fixture-flat-reviewer",
            labels=flat_labels,
        )
        review_times = create_review_times(
            seal=seal,
            event=event,
            records=[
                {"system": "FULL_HISTORY_REVIEW", "reviewer_id": "fixture-full-reviewer", "review_packet_id": review_packets["FULL_HISTORY_REVIEW"]["review_packet_id"], "review_milliseconds": 480000, "timing_source": "SYNTHETIC_FIXTURE"},
                {"system": "FLAT_LOG_SEARCH", "reviewer_id": "fixture-flat-reviewer", "review_packet_id": review_packets["FLAT_LOG_SEARCH"]["review_packet_id"], "review_milliseconds": 180000, "timing_source": "SYNTHETIC_FIXTURE"},
                {"system": "DECISION_RECALL", "reviewer_id": "fixture-dr-reviewer", "review_packet_id": review_packets["DECISION_RECALL"]["review_packet_id"], "review_milliseconds": 60000, "timing_source": "SYNTHETIC_FIXTURE"},
            ],
        )
        score = score_predictions(
            seal=seal,
            event=event,
            predictions=predictions,
            gold=gold,
            review_times=review_times,
            review_outcomes=[full_outcome, flat_outcome],
        )
        write(event_dir / "event.json", event)
        write(event_dir / "predictions.json", predictions)
        write(event_dir / "adjudication-packet.json", packet)
        write(event_dir / "gold.private.json", gold)
        write(event_dir / "review-packet.full-history.json", review_packets["FULL_HISTORY_REVIEW"])
        write(event_dir / "review-packet.flat-search.json", review_packets["FLAT_LOG_SEARCH"])
        write(event_dir / "review-packet.decision-recall.json", review_packets["DECISION_RECALL"])
        write(event_dir / "review-outcome.full-history.fixture.json", full_outcome)
        write(event_dir / "review-outcome.flat-search.fixture.json", flat_outcome)
        write(event_dir / "review-times.fixture.json", review_times)
        write(event_dir / "score.json", score)
        summaries.append({
            "event_id": event["event_id"],
            "basis_id": event["basis_id"],
            "decision_recall_review_load": score["metrics"][SYSTEM_DECISION_RECALL]["review_load"],
            "decision_recall_missed_reopenings": score["metrics"][SYSTEM_DECISION_RECALL]["missed_reopenings"],
            "full_history_reviewer_missed_reopenings": score["metrics"]["FULL_HISTORY_REVIEW"]["missed_reopenings"],
        })

    report = {
        "schema": "openline.decision-recall-prospective-conformance-report.v1",
        "status": "MECHANICS_ONLY_NOT_PRODUCT_EVIDENCE",
        "benchmark_id": seal["benchmark_id"],
        "manifest_count": seal["manifest_count"],
        "event_count": len(events),
        "events": summaries,
        "promotion_policy_id": policy["promotion_policy_id"],
        "promotion_eligible": False,
        "why_not": [
            "fixture decisions are authored calibration data rather than a real accepted decision stream",
            "fixture gold is pre-authored rather than independent blinded human adjudication",
            "fixture baseline-review outcomes are pre-authored and fixture review times are synthetic, so neither accuracy nor attention economics is empirical",
            "fixture has fewer than the predeclared minimum decisions and revocations",
        ],
    }
    write(out / "REPORT.json", report)
    print(json.dumps({"valid": True, "output": str(out), "status": report["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
