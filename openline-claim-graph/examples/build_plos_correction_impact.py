"""Build a real-event evidence-recall specimen from the PLOS correction case.

The correction notice and article excerpts are natural material verified in the
existing PLOS artifact.  The downstream review/decision dependencies added here
are an explicitly authored accepted-state specimen.  The result proves the
mechanical operation on a real source-status event; it does not prove that the
authored dependency graph is historically complete or scientifically true.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from openline_claim_graph import (
    analyze_source_impact,
    build_source,
    create_claim,
    create_impact_policy,
    create_relation,
    create_snapshot,
    create_source_status_event,
    private_key_from_hex,
    provenance_anchor,
    public_key_hex,
    render_impact_review,
    sign_snapshot,
    verify_impact_report,
    verify_impact_bundle,
    verify_receipt,
)

from build_plos_correction_case import CORRECTION_ANCHOR, CORRECTION_DOI, ORIGINAL_DOI


ACTOR = "example:accepted-review-author-v1"
EVENT_ACTOR = "example:plos-correction-admission-v1"
ISSUER = "example:openline-evidence-recall"
ISSUED_AT = "2026-08-16T08:00:00Z"
EFFECTIVE_AT = "2021-04-01T00:00:00Z"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _claim_by_slot(snapshot: dict, source_id: str, slot: str) -> dict:
    matches = [
        claim
        for claim in snapshot["claims"]
        if claim.get("slot") == slot
        and any(anchor.get("source_id") == source_id for anchor in claim.get("provenance", []))
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one claim for {slot} in {source_id}, found {len(matches)}")
    return matches[0]


def _edge(source: dict, target: dict, relation: str) -> dict:
    return create_relation(
        source_claim_id=source["claim_id"],
        target_claim_id=target["claim_id"],
        relation=relation,
        asserted_by=ACTOR,
    )


def _markdown(report: dict, labels: dict[str, str], event: dict, baseline: dict) -> str:
    reverse = {claim_id: label for label, claim_id in labels.items()}

    def named(claim_id: str) -> str:
        return reverse.get(claim_id, claim_id)

    lines = [
        "# Evidence Recall: PLOS correction specimen",
        "",
        f"Status: `{report['status']}`",
        "",
        "A real PLOS correction notice was admitted against an authored, signed accepted-state graph. "
        "The deterministic engine computed what must be reopened under the receiver's declared edge policy.",
        "",
        "## Result",
        "",
        f"- Direct source claims exposed: **{report['summary']['source_exposed']}**",
        f"- Claims proposed for quarantine: **{report['summary']['quarantine']}**",
        f"- Claims retaining an admitted alternative basis: **{report['summary']['survives']}**",
        f"- Claims requiring review because an advisory edge is involved: **{report['summary']['affected_unresolved']}**",
        f"- Accepted decisions touched: **{report['summary']['decisions_touched']}**",
        f"- Direct-only baseline misses: **{baseline['transitive_quarantine_missed']}** downstream claims",
        "",
        "## Proposed quarantine",
        "",
    ]
    for item in report["classifications"]["quarantine"]:
        path = item.get("witness_path") or {"steps": []}
        path_text = "direct source anchor"
        if path["steps"]:
            path_text = " → ".join(
                [named(path["origin_claim_id"])]
                + [f"{step['relation']} → {named(step['to_claim_id'])}" for step in path["steps"]]
            )
        lines.append(f"- **{named(item['claim_id'])}** — {item['reason']}; `{path_text}`")
    lines.extend(["", "## Preserved and unresolved", ""])
    for item in report["classifications"]["survives"]:
        retained = ", ".join(named(value) for value in item["retained_support_claim_ids"])
        lines.append(f"- **{named(item['claim_id'])}** survives; retained support: `{retained}`")
    for item in report["classifications"]["affected_unresolved"]:
        lines.append(f"- **{named(item['claim_id'])}** requires review; an advisory dependency is involved.")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            report["claim_boundary"],
            "",
            f"Event: `{event['event_id']}`",
            f"Report: `{report['report_id']}`",
            "",
            "The article passages and correction notice are real natural material. The downstream "
            "review and decision dependencies are an authored specimen, not a claim about what any "
            "historical institution actually relied on.",
            "",
        ]
    )
    return "\n".join(lines)


def build(base: Path, output: Path) -> dict:
    base_snapshot = _read(base / "snapshot.json")
    upstream_verification = _read(base / "upstream-verification.json")
    accepted_sources_list = _read(base / "sources.json")["sources"]
    accepted_sources = {item["source_id"]: item for item in accepted_sources_list}

    abstract_source = next(
        item for item in accepted_sources_list if str(item.get("locator", "")).endswith("#abstract-results")
    )
    main_sample_source = next(
        item for item in accepted_sources_list if str(item.get("locator", "")).endswith("#results-sample")
    )
    main_cost_source = next(
        item for item in accepted_sources_list if str(item.get("locator", "")).endswith("#results-costs")
    )
    abstract_sample = _claim_by_slot(base_snapshot, abstract_source["source_id"], "sample.mdd")
    main_sample = _claim_by_slot(base_snapshot, main_sample_source["source_id"], "sample.mdd")
    main_cost = _claim_by_slot(
        base_snapshot,
        main_cost_source["source_id"],
        "cost.trd_vs_non_mdd_adjusted_difference",
    )

    abstract_interpretation = create_claim(
        kind="INFERENCE",
        text="The eligible MDD cohort size is 29,543.",
        asserted_by=ACTOR,
        slot="accepted_review.eligible_mdd_cohort",
        value=29543,
    )
    denominator_decision = create_claim(
        kind="ASSUMPTION",
        text="Downstream rate calculations use 29,543 as the eligible MDD denominator.",
        asserted_by=ACTOR,
        slot="accepted_decision.mdd_denominator",
        value=29543,
    )
    approximate_sample = create_claim(
        kind="INFERENCE",
        text="The eligible MDD cohort was approximately 29.5 thousand patients.",
        asserted_by=ACTOR,
    )
    summary_review = create_claim(
        kind="UNRESOLVED_QUESTION",
        text="Does the executive summary require revision after the numerical correction?",
        asserted_by=ACTOR,
    )
    unaffected_decision = create_claim(
        kind="ASSUMPTION",
        text="Use $3,675 as the adjusted TRD versus non-MDD cost difference in downstream planning.",
        asserted_by=ACTOR,
        slot="accepted_decision.trd_vs_non_mdd_cost_difference",
        value=3675,
    )

    derived = _edge(abstract_interpretation, abstract_sample, "DERIVED_FROM")
    denominator_depends = _edge(denominator_decision, abstract_interpretation, "DEPENDS_ON")
    abstract_supports_approx = _edge(abstract_sample, approximate_sample, "SUPPORTS")
    main_supports_approx = _edge(main_sample, approximate_sample, "SUPPORTS")
    summary_advisory = _edge(summary_review, abstract_interpretation, "DERIVED_FROM")
    cost_depends = _edge(unaffected_decision, main_cost, "DEPENDS_ON")

    claims = list(base_snapshot["claims"]) + [
        abstract_interpretation,
        denominator_decision,
        approximate_sample,
        summary_review,
        unaffected_decision,
    ]
    relations = list(base_snapshot["relations"]) + [
        derived,
        denominator_depends,
        abstract_supports_approx,
        main_supports_approx,
        summary_advisory,
        cost_depends,
    ]
    snapshot = create_snapshot(claims=claims, relations=relations)

    correction_source = build_source(
        CORRECTION_ANCHOR,
        locator=f"https://doi.org/{CORRECTION_DOI}",
    )
    all_sources = {**accepted_sources, correction_source["source_id"]: correction_source}
    affected_spans = sorted(
        [
            dict(claim["provenance"][0]["span"])
            for claim in base_snapshot["claims"]
            if claim.get("provenance")
            and claim["provenance"][0].get("source_id") == abstract_source["source_id"]
        ],
        key=lambda item: (item["start"], item["end"]),
    )
    event = create_source_status_event(
        status="CORRECTED",
        affected=[{"source_id": abstract_source["source_id"], "spans": affected_spans}],
        evidence=[
            provenance_anchor(
                correction_source,
                CORRECTION_ANCHOR,
                mode="QUOTE",
                asserted_by=EVENT_ACTOR,
            )
        ],
        asserted_by=EVENT_ACTOR,
        effective_at=EFFECTIVE_AT,
        reason=(
            "The PLOS correction explicitly reports numerical inconsistency between the abstract "
            "and main text. This admitted scope maps that notice to the five represented abstract values."
        ),
    )
    hard_relations = [
        derived,
        denominator_depends,
        abstract_supports_approx,
        main_supports_approx,
        cost_depends,
    ]
    policy = create_impact_policy(
        snapshot,
        hard_relation_ids=[item["relation_id"] for item in hard_relations],
        advisory_relation_ids=[summary_advisory["relation_id"]],
        decision_claim_ids=[denominator_decision["claim_id"], unaffected_decision["claim_id"]],
    )
    report = analyze_source_impact(snapshot, all_sources, event, policy)
    verification = verify_impact_report(report, snapshot, all_sources, event, policy)
    key = private_key_from_hex("44" * 32)
    public_key = public_key_hex(key)
    receipt = sign_snapshot(
        snapshot,
        accepted_sources,
        private_key=key,
        issuer=ISSUER,
        issued_at=ISSUED_AT,
        parent_snapshots=[],
    )
    receipt_verification = verify_receipt(
        receipt,
        snapshot,
        accepted_sources,
        pinned_public_key=public_key,
        parent_snapshots=[],
    )
    bundle_verification = verify_impact_bundle(
        report,
        snapshot,
        all_sources,
        event,
        policy,
        receipt,
        pinned_public_key=public_key,
        parent_snapshots=[],
    )
    review = render_impact_review(
        report=report,
        snapshot=snapshot,
        sources=all_sources,
        event=event,
        policy=policy,
        accepted_receipt=receipt,
        pinned_public_key=public_key,
        parent_snapshots=[],
        title="Evidence Recall — PLOS correction",
    )

    labels = {
        "abstract.sample.mdd": abstract_sample["claim_id"],
        "main.sample.mdd": main_sample["claim_id"],
        "main.cost.non_mdd": main_cost["claim_id"],
        "accepted.abstract_interpretation": abstract_interpretation["claim_id"],
        "accepted.denominator_decision": denominator_decision["claim_id"],
        "accepted.approximate_sample": approximate_sample["claim_id"],
        "accepted.summary_review": summary_review["claim_id"],
        "accepted.unaffected_cost_decision": unaffected_decision["claim_id"],
    }
    direct = set(report["source_exposed_claim_ids"])
    quarantined = {item["claim_id"] for item in report["classifications"]["quarantine"]}
    baseline = {
        "schema": "openline.claim-impact.direct-only-baseline.v1",
        "method": "Flag only claims with admitted provenance spans overlapping the corrected source scope.",
        "direct_claim_ids": sorted(direct),
        "direct_count": len(direct),
        "graph_quarantine_count": len(quarantined),
        "transitive_quarantine_claim_ids_missed": sorted(quarantined - direct),
        "transitive_quarantine_missed": len(quarantined - direct),
        "claim_boundary": (
            "This is a deterministic capability comparison on an authored dependency graph, not a user study "
            "or evidence that ordinary prose can never convey the same facts."
        ),
    }
    expected = {
        "schema": "openline.claim-impact.specimen-expectation.v1",
        "labels": labels,
        "expected": {
            "quarantine": sorted(
                [
                    claim["claim_id"]
                    for claim in base_snapshot["claims"]
                    if claim.get("provenance")
                    and claim["provenance"][0].get("source_id") == abstract_source["source_id"]
                ]
                + [abstract_interpretation["claim_id"], denominator_decision["claim_id"]]
            ),
            "survives": [approximate_sample["claim_id"]],
            "affected_unresolved": [summary_review["claim_id"]],
            "decision_claim_ids_touched": [denominator_decision["claim_id"]],
        },
        "custody": (
            "Expected classifications were authored with the specimen topology. They test deterministic "
            "implementation fidelity, not independent discovery of the dependency edges."
        ),
    }

    result = {
        "schema": "openline.claim-impact.natural-event-specimen.v1",
        "status": "MECHANISM_WORKS_ON_REAL_CORRECTION_AUTHORED_DEPENDENCIES_VALUE_UNTESTED",
        "original_doi": ORIGINAL_DOI,
        "correction_doi": CORRECTION_DOI,
        "accepted_receipt_valid": receipt_verification["valid"],
        "impact_report_valid": verification["valid"],
        "impact_bundle_valid": bundle_verification["valid"],
        "upstream_exact_match": upstream_verification["exact_match"],
        "report_id": report["report_id"],
        "review_sha256": hashlib.sha256(review.encode("utf-8")).hexdigest(),
        "summary": report["summary"],
        "direct_only_baseline": baseline,
        "claim_boundary": (
            "Real article and correction; authored dependency state. Demonstrates exact, reproducible "
            "blast-radius computation and over-quarantine avoidance. Does not establish extraction accuracy, "
            "historical completeness, user demand, or commercial value."
        ),
    }

    _write(output / "accepted-sources.json", {"sources": accepted_sources_list})
    _write(output / "sources.json", {"sources": list(all_sources.values())})
    _write(output / "accepted.snapshot.json", snapshot)
    _write(output / "accepted.receipt.json", receipt)
    _write(output / "public-key.json", {"issuer": ISSUER, "public_key": public_key})
    _write(output / "source-status-event.json", event)
    _write(output / "impact-policy.json", policy)
    _write(output / "impact-report.json", report)
    _write(output / "verification.json", verification)
    _write(output / "accepted-receipt-verification.json", receipt_verification)
    _write(output / "impact-bundle-verification.json", bundle_verification)
    _write(output / "upstream-verification.json", upstream_verification)
    _write(output / "direct-only-baseline.json", baseline)
    _write(output / "expected.json", expected)
    _write(output / "report.json", result)
    (output / "REPORT.md").write_text(_markdown(report, labels, event, baseline), encoding="utf-8")
    (output / "review.html").write_text(review, encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("artifacts/plos-correction-case"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/plos-correction-impact"))
    args = parser.parse_args()
    print(json.dumps(build(args.base, args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
