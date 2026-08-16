"""Build one natural-material review whose fault line was later externally confirmed.

The source packet contains only passages from the original PLOS ONE article.
The correction notice is kept outside the receiver bundle and is used only as a
post-hoc external anchor. Extraction is manual and disclosed as such; this is a
real-material mechanism check, not evidence that the surface improves decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from openline_claim_graph import (
    build_source,
    create_claim,
    create_projection,
    create_relation,
    create_snapshot,
    create_source_disclosure,
    private_key_from_hex,
    provenance_anchor,
    public_key_hex,
    render_review,
    sign_snapshot,
    verify_bundle,
)


ACTOR = "example:manual-key-blind-extraction-v1"
ISSUER = "example:openline-natural-material-case"
ISSUED_AT = "2026-08-15T18:00:00Z"
ORIGINAL_DOI = "10.1371/journal.pone.0223255"
CORRECTION_DOI = "10.1371/journal.pone.0249731"


ABSTRACT_RESULTS = (
    "Of 29,543 patients with MDD, 3,225 (10.9%) met the study definition of TRD; "
    "157,611 were included in the non-MDD cohort. Matched patients with TRD and "
    "non-TRD MDD were, on average, 58.9 and 59.0 years old, respectively. The TRD "
    "cohort had higher per-patient-per-year (PPPY) HRU than the non-TRD MDD (e.g., "
    "inpatient visits: incidence rate ratio [IRR] = 1.36) and non-MDD cohorts (e.g., "
    "inpatient visits: IRR = 1.84, all P<0.001). The TRD cohort had significantly "
    "higher total PPPY healthcare costs than the non-TRD MDD cohort ($25,517 vs. "
    "$20,425, adjusted cost difference = $3,385) and non-MDD cohort ($25,517 vs. "
    "$14,542, adjusted cost difference = $4,015, all P<0.001)."
)

MAIN_SAMPLE_RESULTS = (
    "In total, 503,017 patients had ≥1 MDD diagnosis, among which 29,540 were "
    "pharmacologically-treated patients with MDD who qualified for inclusion. Of these, "
    "3,224 (10.9%) met the study definition of TRD. Patients with non-TRD MDD "
    "(N = 26,316) or non-MDD (N = 157,590) were all matched 1:1 to patients with TRD."
)

MAIN_COST_RESULTS = (
    "During the observation period, the total all-cause PPPY healthcare costs were "
    "$25,059 in the TRD cohort, $19,945 in the non-TRD MDD cohort, and $14,410 in the "
    "non-MDD cohort (all P <0.001; Fig 3 and Table 2 ). The TRD cohort had significantly "
    "higher adjusted PPPY all-cause healthcare costs versus the non-TRD MDD (adjusted "
    "cost difference = $3,377, P <0.001) or non-MDD cohorts (adjusted cost difference = "
    "$3,675, P <0.001; Fig 3 and Table 2 )."
)

CORRECTION_ANCHOR = (
    "In the Results subsection of the Abstract. there are numbers reported which are "
    "inconsistent with those of the main text."
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _quote_claim(source, quote: str, *, slot: str, value: int) -> dict:
    return create_claim(
        kind="MEASUREMENT",
        text=quote,
        asserted_by=ACTOR,
        provenance=[provenance_anchor(source, quote, mode="QUOTE", asserted_by=ACTOR)],
        slot=slot,
        value=value,
    )


def build(output: Path) -> dict:
    abstract = build_source(
        ABSTRACT_RESULTS,
        locator=f"https://doi.org/{ORIGINAL_DOI}#abstract-results",
    )
    main_sample = build_source(
        MAIN_SAMPLE_RESULTS,
        locator=f"https://doi.org/{ORIGINAL_DOI}#results-sample",
    )
    main_cost = build_source(
        MAIN_COST_RESULTS,
        locator=f"https://doi.org/{ORIGINAL_DOI}#results-costs",
    )
    sources = {item["source_id"]: item for item in (abstract, main_sample, main_cost)}

    pairs = [
        (
            _quote_claim(abstract, "Of 29,543 patients with MDD", slot="sample.mdd", value=29543),
            _quote_claim(
                main_sample,
                "29,540 were pharmacologically-treated patients with MDD who qualified for inclusion.",
                slot="sample.mdd",
                value=29540,
            ),
        ),
        (
            _quote_claim(
                abstract,
                "3,225 (10.9%) met the study definition of TRD",
                slot="sample.trd",
                value=3225,
            ),
            _quote_claim(
                main_sample,
                "3,224 (10.9%) met the study definition of TRD.",
                slot="sample.trd",
                value=3224,
            ),
        ),
        (
            _quote_claim(
                abstract,
                "157,611 were included in the non-MDD cohort.",
                slot="sample.non_mdd",
                value=157611,
            ),
            _quote_claim(
                main_sample,
                "Patients with non-TRD MDD (N = 26,316) or non-MDD (N = 157,590) were all matched 1:1 to patients with TRD.",
                slot="sample.non_mdd",
                value=157590,
            ),
        ),
        (
            _quote_claim(
                abstract,
                "$25,517 vs. $20,425, adjusted cost difference = $3,385",
                slot="cost.trd_vs_non_trd_adjusted_difference",
                value=3385,
            ),
            _quote_claim(
                main_cost,
                "adjusted cost difference = $3,377, P <0.001",
                slot="cost.trd_vs_non_trd_adjusted_difference",
                value=3377,
            ),
        ),
        (
            _quote_claim(
                abstract,
                "$25,517 vs. $14,542, adjusted cost difference = $4,015",
                slot="cost.trd_vs_non_mdd_adjusted_difference",
                value=4015,
            ),
            _quote_claim(
                main_cost,
                "adjusted cost difference = $3,675, P <0.001",
                slot="cost.trd_vs_non_mdd_adjusted_difference",
                value=3675,
            ),
        ),
    ]
    claims = [claim for pair in pairs for claim in pair]
    relations = []
    for left, right in pairs:
        anchors = []
        for claim in (left, right):
            anchor = dict(claim["provenance"][0])
            source = sources[anchor["source_id"]]
            quote = source["content"].encode("utf-8")[
                anchor["span"]["start"] : anchor["span"]["end"]
            ].decode("utf-8")
            anchors.append(provenance_anchor(source, quote, mode="INFERENCE", asserted_by=ACTOR))
        relations.append(
            create_relation(
                source_claim_id=left["claim_id"],
                target_claim_id=right["claim_id"],
                relation="CONTRADICTS",
                asserted_by=ACTOR,
                provenance=anchors,
            )
        )

    snapshot = create_snapshot(claims=claims, relations=relations)
    key = private_key_from_hex("33" * 32)
    pin = public_key_hex(key)
    receipt = sign_snapshot(
        snapshot,
        sources,
        private_key=key,
        issuer=ISSUER,
        issued_at=ISSUED_AT,
        parent_snapshots=[],
    )
    projection = create_projection(
        snapshot,
        claim_ids=[item["claim_id"] for item in claims],
        relation_ids=[item["relation_id"] for item in relations],
        purpose="Locate numerical conflicts between the published abstract and main results before relying on the summary.",
        selected_by="example:bounded-receiver-policy-v1",
    )
    policy = {
        "required_slots": sorted({item["slot"] for item in claims}),
        "required_relations": ["CONTRADICTS"],
        "deny_unanchored_claims": True,
        "allow_unanchored_relations": False,
        "allowed_provenance_modes": ["QUOTE", "INFERENCE"],
        "accept_bounded_projection": True,
    }
    disclosure = create_source_disclosure(projection, snapshot, receipt, sources)
    verification = verify_bundle(
        snapshot=snapshot,
        receipt=receipt,
        sources=sources,
        projection=projection,
        source_disclosure=disclosure,
        receiver_policy=policy,
        pinned_public_key=pin,
        parent_snapshots=[],
    )
    review = render_review(
        snapshot=snapshot,
        receipt=receipt,
        sources=sources,
        projection=projection,
        source_disclosure=disclosure,
        receiver_policy=policy,
        pinned_public_key=pin,
        parent_snapshots=[],
        title="Published abstract vs. main results",
    )
    anchor = {
        "schema": "openline.claim-graph.external-anchor.v1",
        "anchor_class": "E1_EXPLICIT_EXTERNAL_ANCHOR",
        "original_doi": ORIGINAL_DOI,
        "correction_doi": CORRECTION_DOI,
        "correction_locator": f"https://doi.org/{CORRECTION_DOI}",
        "anchor_text": CORRECTION_ANCHOR,
        "anchor_sha256": hashlib.sha256(CORRECTION_ANCHOR.encode("utf-8")).hexdigest(),
        "use": "Post-hoc confirmation that the represented fault line existed; excluded from the receiver bundle.",
        "claim_boundary": "The correction confirms the inconsistency, not that this review surface improves human decisions.",
    }
    _write_json(output / "sources.json", {"sources": list(sources.values())})
    _write_json(output / "snapshot.json", snapshot)
    _write_json(output / "receipt.json", receipt)
    _write_json(output / "projection.json", projection)
    _write_json(output / "source-disclosure.json", disclosure)
    _write_json(output / "receiver-policy.json", policy)
    _write_json(output / "public-key.json", {"issuer": ISSUER, "public_key": pin})
    _write_json(output / "verification.json", verification)
    _write_json(output / "external-anchor.json", anchor)
    (output / "review.html").write_text(review, encoding="utf-8")
    report = {
        "schema": "openline.claim-graph.natural-material-report.v1",
        "status": "MECHANISM_WORKS_ON_ONE_EXTERNALLY_ANCHORED_NATURAL_CASE_VALUE_UNTESTED",
        "bundle_valid": verification["valid"],
        "disposition": verification["disposition"],
        "claim_count": len(claims),
        "conflict_count": len(relations),
        "external_anchor": anchor,
        "review_sha256": hashlib.sha256(review.encode("utf-8")).hexdigest(),
        "manual_extraction": True,
        "claim_boundary": (
            "This demonstrates a review generated from real published material and an externally confirmed fault line. "
            "It does not establish extraction accuracy, completeness, or decision-value superiority."
        ),
    }
    _write_json(output / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/plos-correction-case"))
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
