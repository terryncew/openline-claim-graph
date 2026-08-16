from __future__ import annotations

import argparse
import json
from pathlib import Path

from openline_claim_graph import (
    ClaimGraphWallet,
    build_source,
    compare_snapshots,
    create_claim,
    create_projection,
    create_relation,
    create_snapshot,
    create_source_disclosure,
    disagreement_report,
    private_key_from_hex,
    provenance_anchor,
    public_key_hex,
    sign_snapshot,
    verify_projection,
    verify_receipt,
    verify_bundle,
    verify_source_disclosure,
)


ACTOR = "fixture:independent-extractor-v1"
ISSUER = "fixture:openline-claim-graph"
ISSUED_AT = "2026-08-15T08:00:00Z"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def quote_claim(source, quote, *, slot, value):
    return create_claim(
        kind="SOURCE_ASSERTION",
        text=quote,
        asserted_by=ACTOR,
        provenance=[provenance_anchor(source, quote, mode="QUOTE", asserted_by=ACTOR)],
        slot=slot,
        value=value,
    )


def build_branch(*, base, routine, emergency, policy_source, status_source, status_quote, outage):
    approvals = 1 if outage else 2
    status = quote_claim(
        status_source,
        status_quote,
        slot="environment.outage_declared",
        value=outage,
    )
    policy_quote = (
        "During a declared outage, one approval is sufficient."
        if outage
        else "Routine production changes require two approvals."
    )
    conclusion = create_claim(
        kind="INFERENCE",
        text=f"The current change requires {approvals} approval{'s' if approvals != 1 else ''}.",
        asserted_by=ACTOR,
        provenance=[
            provenance_anchor(status_source, status_quote, mode="INFERENCE", asserted_by=ACTOR),
            provenance_anchor(policy_source, policy_quote, mode="INFERENCE", asserted_by=ACTOR),
        ],
        slot="decision.required_approvals",
        value=approvals,
    )
    snapshot = create_snapshot(
        claims=[routine, emergency, status, conclusion],
        relations=[],
        parent_snapshots=[base],
    )
    return snapshot, status, conclusion


def build(output: Path) -> dict:
    policy_source = build_source(
        "Routine production changes require two approvals.\n"
        "During a declared outage, one approval is sufficient.\n",
        locator="fixture://policy.txt",
    )
    no_outage_source = build_source(
        "No outage has been declared.", locator="fixture://status-no-outage.txt"
    )
    outage_source = build_source(
        "An outage has been declared.", locator="fixture://status-outage.txt"
    )
    sources = {
        item["source_id"]: item for item in (policy_source, no_outage_source, outage_source)
    }
    routine = quote_claim(
        policy_source,
        "Routine production changes require two approvals.",
        slot="policy.routine_approvals",
        value=2,
    )
    emergency = quote_claim(
        policy_source,
        "During a declared outage, one approval is sufficient.",
        slot="policy.outage_approvals",
        value=1,
    )
    base = create_snapshot(claims=[routine, emergency], relations=[])
    branch_a, status_a, conclusion_a = build_branch(
        base=base,
        routine=routine,
        emergency=emergency,
        policy_source=policy_source,
        status_source=no_outage_source,
        status_quote="No outage has been declared.",
        outage=False,
    )
    branch_b, status_b, conclusion_b = build_branch(
        base=base,
        routine=routine,
        emergency=emergency,
        policy_source=policy_source,
        status_source=outage_source,
        status_quote="An outage has been declared.",
        outage=True,
    )
    status_conflict = create_relation(
        source_claim_id=status_a["claim_id"],
        target_claim_id=status_b["claim_id"],
        relation="CONTRADICTS",
        asserted_by=ACTOR,
        provenance=[
            provenance_anchor(
                no_outage_source,
                "No outage has been declared.",
                mode="INFERENCE",
                asserted_by=ACTOR,
            ),
            provenance_anchor(
                outage_source,
                "An outage has been declared.",
                mode="INFERENCE",
                asserted_by=ACTOR,
            ),
        ],
    )
    decision_conflict = create_relation(
        source_claim_id=conclusion_a["claim_id"],
        target_claim_id=conclusion_b["claim_id"],
        relation="CONTRADICTS",
        asserted_by=ACTOR,
        provenance=[
            provenance_anchor(
                no_outage_source,
                "No outage has been declared.",
                mode="INFERENCE",
                asserted_by=ACTOR,
            ),
            provenance_anchor(
                outage_source,
                "An outage has been declared.",
                mode="INFERENCE",
                asserted_by=ACTOR,
            ),
        ],
    )
    claims = {item["claim_id"]: item for item in branch_a["claims"] + branch_b["claims"]}
    merged = create_snapshot(
        claims=claims.values(),
        relations=[status_conflict, decision_conflict],
        parent_snapshots=[branch_a, branch_b],
        merge_resolutions=[
            {
                "slot": "environment.outage_declared",
                "action": "PRESERVE_ALL",
                "parent_claim_ids": sorted([status_a["claim_id"], status_b["claim_id"]]),
                "reason": "The two signed status sources conflict; merging must not manufacture agreement.",
            },
            {
                "slot": "decision.required_approvals",
                "action": "PRESERVE_ALL",
                "parent_claim_ids": sorted([conclusion_a["claim_id"], conclusion_b["claim_id"]]),
                "reason": "The conclusions inherit the unresolved status conflict.",
            },
        ],
    )

    key = private_key_from_hex("11" * 32)
    pin = public_key_hex(key)
    base_receipt = sign_snapshot(base, sources, private_key=key, issuer=ISSUER, issued_at=ISSUED_AT, parent_snapshots=[])
    branch_a_receipt = sign_snapshot(
        branch_a, sources, private_key=key, issuer=ISSUER, issued_at=ISSUED_AT, parent_snapshots=[base]
    )
    branch_b_receipt = sign_snapshot(
        branch_b, sources, private_key=key, issuer=ISSUER, issued_at=ISSUED_AT, parent_snapshots=[base]
    )
    merge_receipt = sign_snapshot(
        merged,
        sources,
        private_key=key,
        issuer=ISSUER,
        issued_at=ISSUED_AT,
        parent_snapshots=[branch_a, branch_b],
    )

    projection = create_projection(
        merged,
        claim_ids=[status_a["claim_id"], status_b["claim_id"], conclusion_a["claim_id"], conclusion_b["claim_id"]],
        relation_ids=[status_conflict["relation_id"], decision_conflict["relation_id"]],
        purpose="Expose the unresolved premise before applying an approval rule.",
        selected_by="fixture:receiver-policy-v1",
    )
    policy = {
        "required_slots": ["environment.outage_declared", "decision.required_approvals"],
        "required_relations": ["CONTRADICTS"],
        "deny_unanchored_claims": True,
        "allowed_provenance_modes": ["QUOTE", "INFERENCE"],
        "accept_bounded_projection": True,
    }
    disclosure = create_source_disclosure(projection, merged, merge_receipt, sources)
    wallet = ClaimGraphWallet(issuer_pins={ISSUER: pin})
    admissions = [
        wallet.admit(base, base_receipt, sources),
        wallet.admit(branch_a, branch_a_receipt, sources),
        wallet.admit(branch_b, branch_b_receipt, sources),
        wallet.admit(merged, merge_receipt, sources),
    ]
    verification = {
        "schema": "openline.claim-graph.demo-verification.v1",
        "fixture_only": True,
        "receipt": verify_receipt(
            merge_receipt,
            merged,
            sources,
            pinned_public_key=pin,
            parent_snapshots=[branch_a, branch_b],
        ),
        "projection": verify_projection(projection, policy),
        "source_disclosure": verify_source_disclosure(disclosure, projection, merge_receipt),
        "bundle": verify_bundle(
            snapshot=merged,
            receipt=merge_receipt,
            sources=sources,
            projection=projection,
            source_disclosure=disclosure,
            receiver_policy=policy,
            pinned_public_key=pin,
            parent_snapshots=[branch_a, branch_b],
        ),
        "wallet_admissions": admissions,
        "claim_boundary": (
            "This controlled fixture demonstrates mechanics only. It supplies no evidence of automated extraction "
            "accuracy or decision improvement on natural material."
        ),
    }
    structural_analysis = {
        "schema": "openline.claim-graph.demo-analysis.v1",
        "branch_comparison": compare_snapshots(branch_a, branch_b),
        "merged_disagreements": disagreement_report(merged),
        "claim_boundary": "Deterministic fixture structure only; no branch ranking or truth claim.",
    }

    write_json(output / "sources.fixture.json", {"schema": "openline.source-bundle.v1", "sources": list(sources.values())})
    for name, snapshot, receipt in (
        ("base", base, base_receipt),
        ("branch-a", branch_a, branch_a_receipt),
        ("branch-b", branch_b, branch_b_receipt),
        ("merged", merged, merge_receipt),
    ):
        write_json(output / f"{name}.snapshot.json", snapshot)
        write_json(output / f"{name}.receipt.json", receipt)
    write_json(output / "projection.json", projection)
    write_json(output / "receiver-policy.json", policy)
    write_json(output / "source-disclosure.json", disclosure)
    write_json(output / "wallet.json", wallet.export())
    write_json(output / "verification.json", verification)
    write_json(output / "structural-analysis.json", structural_analysis)
    write_json(output / "fixture-public-key.json", {"issuer": ISSUER, "public_key": pin, "trust": "fixture_only"})
    return verification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/demo")
    args = parser.parse_args()
    verification = build(Path(args.output))
    print(json.dumps(verification, indent=2, sort_keys=True))
    return 0 if all(
        [
            verification["receipt"]["valid"],
            verification["projection"]["valid"],
            verification["source_disclosure"]["valid"],
            verification["bundle"]["disposition"] == "ADMIT",
            all(item["disposition"].startswith("ADMIT") for item in verification["wallet_admissions"]),
        ]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
