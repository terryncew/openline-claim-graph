from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from openline_claim_graph.canonical import content_id, hash_object
from openline_claim_graph.temporal_holdout import (
    create_authority,
    create_episode,
    create_future_record,
    create_future_seal,
    create_gold,
    create_pack,
    run_temporal,
    score_temporal,
)


BENCHMARK_ID = "temporal-mixed-selectivity-001-v1"
ROOT = Path(__file__).resolve().parents[1]
SHAH_DIR = ROOT / "artifacts/evidence-recall-temporal/real-001-shah-iron"

NARAYAN_T0 = "2014-02-25T23:59:59Z"
NARAYAN_T1 = "2014-02-26T00:00:00Z"
AUDIT_T2 = "2016-05-03T00:00:00Z"
RETRIEVAL_CUTOFF = "2025-01-27T23:59:59Z"

NARAYAN = "doi:10.1038/nature11700"
ZHOU = "zhou2012:death-by-deacetylation-summary"
VITNER = "vitner2014:gaucher-main-conclusion"

PROMOTION_POLICY_SCHEMA = "openline.evidence-recall-temporal-promotion-policy.v1"
MIN_RECALL_BPS = 9500
MIN_REVIEW_REDUCTION_BPS = 4000
MAX_ADDITIONAL_MISSED = 0

FROZEN_ENGINE_SHA256 = {
    "src/openline_claim_graph/temporal_holdout.py": "bc8f0011d65cb1c2c728ef374ebb82b86c3c08657e9919427ff5d80b2707886a",
    "src/openline_claim_graph/comparative_benchmark.py": "6c04e9e021cbc1c01aae78606acc6cd41393c99673185e1e8e3ee4ccaa06e4b1",
    "src/openline_claim_graph/impact.py": "1757340f69e919ff68d3cdfe4265fc1ac330bc99ff5bcd20b69058fa846905a2",
}


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_promotion_policy() -> dict:
    body = {
        "schema": PROMOTION_POLICY_SCHEMA,
        "candidate_system": "EVIDENCE_RECALL",
        "reference_system": "REVIEW_ALL_REACHABILITY",
        "minimum_reconsideration_recall_basis_points": MIN_RECALL_BPS,
        "minimum_review_load_reduction_vs_review_all_basis_points": MIN_REVIEW_REDUCTION_BPS,
        "maximum_additional_missed_reopenings_vs_review_all": MAX_ADDITIONAL_MISSED,
        "rule": (
            "Promotion requires Evidence Recall reconsideration recall >=95%, review-load reduction versus "
            "Review-All Reachability >=40%, and no additional missed warranted reopenings versus Review-All. "
            "No composite score is used."
        ),
        "declared_before_gold": True,
    }
    return {"promotion_policy_id": content_id("temporal-promotion-policy", body), **body}


def build_narayan_source_evidence() -> tuple[dict, dict, dict]:
    pre_cutoff = {
        "schema": "openline.temporal-source-evidence.v1",
        "hash_scope": "Canonical local evidence record; not publisher raw bytes.",
        "records": [
            {
                "role": "invalidated-study",
                "identifier": NARAYAN,
                "available_at": "2012-11-28T00:00:00Z",
                "title": "The NAD-dependent deacetylase SIRT2 is required for programmed necrosis",
                "facts": [
                    "Narayan et al. reported that SIRT2 was required for TNF-alpha-mediated necroptosis and proposed a SIRT2-dependent mechanism involving RIP1/RIP3.",
                    "The article was published online on 2012-11-28.",
                ],
            },
            {
                "role": "direct-summary",
                "identifier": "doi:10.1038/nature11761",
                "available_at": "2012-11-28T00:00:00Z",
                "title": "Death by deacetylation",
                "facts": [
                    "The Nature News & Views item states that a sirtuin protein regulates one form of necrosis through deacetylation and points readers to the Narayan article on page 199.",
                    "Its references identify Narayan et al. 2012 as the paper under discussion.",
                ],
            },
            {
                "role": "direct-method-citation",
                "identifier": "doi:10.1038/nm.3449",
                "available_at": "2014-01-19T00:00:00Z",
                "title": "RIPK3 as a potential therapeutic target for Gaucher's disease",
                "facts": [
                    "Vitner et al. report that RIPK3 deficiency improves neurological and systemic disease in a Gaucher-disease mouse model.",
                    "The paper directly cites Narayan et al. in its experimental-method context for RIPK3 detection rather than as the basis for the Gaucher-disease therapeutic conclusion.",
                    "Because the pre-cutoff citation establishes neighborhood membership but not conclusion-level dependence on the Narayan SIRT2-necroptosis result, that candidate relation is frozen as UNADMITTED.",
                ],
            },
        ],
    }
    trigger = {
        "schema": "openline.temporal-trigger-evidence.v1",
        "hash_scope": "Canonical local evidence record; not publisher raw bytes.",
        "identifier": "doi:10.1038/nature12897",
        "available_at": NARAYAN_T1,
        "title": "Retraction Note: The NAD-dependent deacetylase SIRT2 is required for programmed necrosis",
        "facts": [
            "Nature published the retraction note online on 2014-02-26.",
            "The authors said data supporting an in-vitro requirement for SIRT2 in TNF-alpha-mediated necroptosis appeared irreproducible and retracted the article in its entirety.",
        ],
    }
    later = {
        "schema": "openline.temporal-later-evidence.v1",
        "hash_scope": "Canonical local evidence record; not publisher raw bytes.",
        "identifier": "doi:10.1186/s41073-016-0008-5",
        "available_at": AUDIT_T2,
        "title": "Propagation of errors in citation networks: a study involving the entire citation network of a widely cited paper published in, and later retracted from, the journal Nature",
        "facts": [
            "The independent citation-network audit identifies Zhou and Yuan as a summary of the Narayan paper and says this summary enhanced the retracted paper's exposure.",
            "The audit identifies Vitner et al. as an exception in which part of Narayan's experimental method was cited, rather than a propagation of the retracted result into the paper's scientific conclusion.",
            "The audit concludes that directly citing papers were an important source of propagation overall while indirect citations did not propagate the retracted result in this case study.",
        ],
    }
    return pre_cutoff, trigger, later


def build(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    evidence_dir = output / "source-evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # Reuse the already-frozen Shah episode and its source evidence without re-authoring it.
    shah_pack = load(SHAH_DIR / "pack.json")
    shah_authority = load(SHAH_DIR / "authority.json")
    shah_seal = load(SHAH_DIR / "future-seal.private.json")
    shah_episode = dict(shah_pack["episodes"][0])
    shah_future_record = dict(shah_seal["records"][0])
    shah_pre = load(SHAH_DIR / "source-evidence/pre-cutoff.json")
    shah_trigger = load(SHAH_DIR / "source-evidence/trigger.json")
    shah_later = load(SHAH_DIR / "source-evidence/later.private.json")
    write(evidence_dir / "shah-pre-cutoff.json", shah_pre)
    write(evidence_dir / "shah-trigger.json", shah_trigger)
    write(evidence_dir / "shah-later.private.json", shah_later)

    pre_cutoff, trigger, later = build_narayan_source_evidence()
    write(evidence_dir / "narayan-pre-cutoff.json", pre_cutoff)
    write(evidence_dir / "narayan-trigger.json", trigger)
    write(evidence_dir / "narayan-later.private.json", later)
    narayan_pre_sha = hash_object(pre_cutoff)
    narayan_trigger_sha = hash_object(trigger)
    narayan_later_sha = hash_object(later)

    narayan_episode = create_episode(
        episode_name="Narayan SIRT2 retraction -> pre-retraction direct citation contexts",
        cutoff_at=NARAYAN_T0,
        event_at=NARAYAN_T1,
        invalidated_node_id=NARAYAN,
        target_node_ids=[ZHOU, VITNER],
        nodes=[
            {
                "node_id": NARAYAN,
                "label": "Narayan 2012 SIRT2-necroptosis article",
                "text": "Narayan et al. reported a required role for SIRT2 in programmed necrosis/necroptosis.",
                "locator": NARAYAN,
                "available_at": "2012-11-28T00:00:00Z",
            },
            {
                "node_id": ZHOU,
                "label": "Zhou and Yuan 2012 News & Views summary",
                "text": "Death by deacetylation summarizes the reported SIRT2-dependent necrosis finding from Narayan et al.",
                "locator": "doi:10.1038/nature11761",
                "available_at": "2012-11-28T00:00:00Z",
            },
            {
                "node_id": VITNER,
                "label": "Vitner 2014 Gaucher-disease conclusion",
                "text": "Vitner et al. conclude that modulating the RIPK3 pathway improves disease in a Gaucher-disease mouse model.",
                "locator": "doi:10.1038/nm.3449",
                "available_at": "2014-01-19T00:00:00Z",
                "independent_basis": True,
            },
        ],
        edges=[
            {
                "prerequisite_node_id": NARAYAN,
                "dependent_node_id": ZHOU,
                "relation": "DERIVED_FROM",
                "available_at": "2012-11-28T00:00:00Z",
                "evidence": [
                    "The pre-cutoff Nature News & Views item explicitly identifies itself as commentary on the Narayan article and summarizes its SIRT2-necroptosis result."
                ],
            },
            {
                "prerequisite_node_id": NARAYAN,
                "dependent_node_id": VITNER,
                "relation": "SUPPORTS",
                "available_at": "2014-01-19T00:00:00Z",
                "evidence": [
                    "The pre-cutoff Vitner article directly cites Narayan in experimental-method context, which establishes reachability but does not establish that the Gaucher-disease conclusion relies on the retracted SIRT2-necroptosis result."
                ],
            },
        ],
        event={
            "status": "RETRACTED",
            "identifier": NARAYAN,
            "locator": "doi:10.1038/nature12897",
            "reason": "Nature retracted the article after the reported TNF-alpha necroptosis result could not be reproduced.",
            "available_at": NARAYAN_T1,
            "evidence_sha256": narayan_trigger_sha,
        },
        metadata={
            "domain": "SCIENTIFIC_CLINICAL",
            "historical_resolution": "DAY",
            "construction_basis": "Primary pre-cutoff publication and citation context only; later 2016 audit is sealed from prediction.",
            "case_role": "MIXED_REAL_TEMPORAL_SELECTIVITY",
        },
    )

    audit_positive = create_future_record(
        episode_id=narayan_episode["episode_id"],
        available_at=AUDIT_T2,
        record_type="INDEPENDENT_DEPENDENCY_AUDIT_RELIANCE",
        target_node_ids=[ZHOU],
        locator="doi:10.1186/s41073-016-0008-5",
        evidence_sha256=narayan_later_sha,
        description=(
            "The independent 2016 audit identifies Zhou and Yuan as a summary of the Narayan paper and describes that summary as increasing its exposure."
        ),
    )
    audit_negative = create_future_record(
        episode_id=narayan_episode["episode_id"],
        available_at=AUDIT_T2,
        record_type="INDEPENDENT_CITATION_CONTEXT_NO_RELIANCE",
        target_node_ids=[VITNER],
        locator="doi:10.1186/s41073-016-0008-5",
        evidence_sha256=narayan_later_sha,
        description=(
            "The independent 2016 audit singles out Vitner et al. as a method-only citation of Narayan, not propagation of the retracted SIRT2-necroptosis result into the Gaucher-disease conclusion scored here."
        ),
    )

    # Future evidence is sealed before pack construction and before any predictions.
    seal = create_future_seal(
        benchmark_id=BENCHMARK_ID,
        scope_definition=(
            "Trigger-attributed later records for the already-frozen Shah/Darwish episode plus the independently published 2016 Narayan citation-context audit. "
            "Negative gold requires affirmative non-reliance for the exact scored target; silence is excluded."
        ),
        retrieval_cutoff_at=RETRIEVAL_CUTOFF,
        records=[shah_future_record, audit_positive, audit_negative],
    )
    write(output / "future-seal.private.json", seal)

    source_manifest = []
    for item in shah_pack["source_manifest"]:
        copied = dict(item)
        if copied.get("locator") == "source-evidence/pre-cutoff.json":
            copied["locator"] = "source-evidence/shah-pre-cutoff.json"
        elif copied.get("locator") == "source-evidence/trigger.json":
            copied["locator"] = "source-evidence/shah-trigger.json"
        source_manifest.append(copied)
    source_manifest.extend(
        [
            {
                "role": "narayan-pre-cutoff-primary-context",
                "identifier": "narayan-zhou-vitner-pre-2014-02-26",
                "available_at": "2014-01-19T00:00:00Z",
                "sha256": narayan_pre_sha,
                "locator": "source-evidence/narayan-pre-cutoff.json",
            },
            {
                "role": "narayan-trigger-retraction-evidence",
                "identifier": "doi:10.1038/nature12897",
                "available_at": NARAYAN_T1,
                "sha256": narayan_trigger_sha,
                "locator": "source-evidence/narayan-trigger.json",
            },
        ]
    )
    pack = create_pack(
        benchmark_id=BENCHMARK_ID,
        episodes=[shah_episode, narayan_episode],
        source_manifest=source_manifest,
        construction_rule=(
            "Each episode uses only information available by its own t0 cutoff. The trigger is prediction-visible. "
            "Later records are separately sealed. The Shah episode is reused unchanged from 0.5.0.dev1. For Narayan, "
            "the explicit News & Views summary relation is admitted HARD; the Vitner direct-citation candidate is UNADMITTED "
            "because its pre-cutoff citation context is method-only rather than conclusion-level reliance."
        ),
        future_seal=seal,
        status="MIXED_TEMPORAL_SELECTIVITY_INPUTS_FROZEN",
    )
    write(output / "pack.json", pack)

    shah_entries = [dict(item) for item in shah_authority["edge_authority"]]
    narayan_edges = {edge["dependent_node_id"]: edge["edge_id"] for edge in narayan_episode["edges"]}
    authority = create_authority(
        pack,
        edge_authority=(
            shah_entries
            + [
                {
                    "episode_id": narayan_episode["episode_id"],
                    "edge_id": narayan_edges[ZHOU],
                    "authority": "HARD",
                },
                {
                    "episode_id": narayan_episode["episode_id"],
                    "edge_id": narayan_edges[VITNER],
                    "authority": "UNADMITTED",
                },
            ]
        ),
        declared_by="temporal-mixed-selectivity-construction-rule",
        construction_rule=(
            "Reuse Shah authority exactly. For Narayan, HARD requires explicit pre-cutoff conclusion-level derivation; "
            "a direct citation that is only method-context reachability remains UNADMITTED. No later audit label is an input."
        ),
    )
    write(output / "authority.json", authority)

    # This threshold artifact is intentionally written before gold is created/opened.
    promotion_policy = create_promotion_policy()
    write(output / "promotion-policy.json", promotion_policy)

    predictions = run_temporal(pack, authority, include_naive_diagnostic=True)
    write(output / "predictions.json", predictions)

    shah_gold = load(SHAH_DIR / "gold.private.json")
    labels = [
        {
            "episode_id": shah_episode["episode_id"],
            "target_node_id": item["target_node_id"],
            "outcome": item["outcome"],
            "future_record_ids": [shah_future_record["record_id"]],
        }
        for item in shah_gold["labels"]
    ]
    labels.extend(
        [
            {
                "episode_id": narayan_episode["episode_id"],
                "target_node_id": ZHOU,
                "outcome": "REOPEN",
                "future_record_ids": [audit_positive["record_id"]],
            },
            {
                "episode_id": narayan_episode["episode_id"],
                "target_node_id": VITNER,
                "outcome": "NO_REOPEN",
                "future_record_ids": [audit_negative["record_id"]],
            },
        ]
    )
    gold = create_gold(
        pack,
        seal,
        labels,
        label_definition=(
            "REOPEN requires a later independent record of actual reconsideration or affirmative reliance on the invalidated result. "
            "NO_REOPEN requires affirmative later evidence that the exact scored target did not rely on the invalidated result. "
            "Silence and unchanged conclusions are not negative gold."
        ),
    )
    write(output / "gold.private.json", gold)

    score = score_temporal(pack, authority, seal, gold, predictions)
    write(output / "score.json", score)

    direct = score["metrics"]["DIRECT_LOOKUP"]
    review_all = score["metrics"]["REVIEW_ALL_REACHABILITY"]
    er = score["metrics"]["EVIDENCE_RECALL"]
    er_cmp = score["comparisons_vs_review_all"]["EVIDENCE_RECALL"]
    er_recall_bps = int(er["reconsideration_recall"]["basis_points"])
    review_reduction_bps = (
        (er_cmp["reviewer_savings_vs_review_all"] * 10_000) // review_all["total_review_load"]
        if review_all["total_review_load"]
        else 0
    )
    additional_missed = int(er_cmp["additional_missed_reopenings_vs_review_all"])
    promotion_pass = (
        er_recall_bps >= MIN_RECALL_BPS
        and review_reduction_bps >= MIN_REVIEW_REDUCTION_BPS
        and additional_missed <= MAX_ADDITIONAL_MISSED
    )
    promotion_result = {
        "schema": "openline.evidence-recall-temporal-promotion-result.v1",
        "promotion_policy_id": promotion_policy["promotion_policy_id"],
        "score_id": score["score_id"],
        "observed_reconsideration_recall_basis_points": er_recall_bps,
        "observed_review_load_reduction_vs_review_all_basis_points": review_reduction_bps,
        "observed_additional_missed_reopenings_vs_review_all": additional_missed,
        "verdict": "PROMOTION_CANDIDATE" if promotion_pass else "NO_PROMOTION",
        "failed_conditions": sorted(
            [
                name
                for name, passed in (
                    ("minimum_reconsideration_recall", er_recall_bps >= MIN_RECALL_BPS),
                    ("minimum_review_load_reduction", review_reduction_bps >= MIN_REVIEW_REDUCTION_BPS),
                    ("maximum_additional_missed_reopenings", additional_missed <= MAX_ADDITIONAL_MISSED),
                )
                if not passed
            ]
        ),
    }
    promotion_result["promotion_result_id"] = content_id(
        "temporal-promotion-result", promotion_result
    )
    write(output / "promotion-result.json", promotion_result)

    engine_hashes = {path: file_sha256(ROOT / path) for path in FROZEN_ENGINE_SHA256}
    custody = {
        "schema": "openline.temporal-mixed-corpus-custody.v1",
        "benchmark_id": BENCHMARK_ID,
        "episode_ids": sorted([shah_episode["episode_id"], narayan_episode["episode_id"]]),
        "build_sequence": [
            "reuse frozen Shah episode and authority from 0.5.0.dev1",
            "create Narayan pre-cutoff and trigger evidence snapshots",
            "create combined future seal from later records",
            "create public pack bound only to future-seal commitment",
            "freeze receiver authority from pre-cutoff evidence",
            "write predeclared promotion policy",
            "emit Direct / Review-All / frozen Evidence Recall predictions",
            "create gold from already sealed later records",
            "score frozen predictions",
            "apply predeclared promotion policy",
        ],
        "shah_evidence_hashes": {
            "pre_cutoff": hash_object(shah_pre),
            "trigger": hash_object(shah_trigger),
            "later_record": hash_object(shah_later),
        },
        "narayan_evidence_hashes": {
            "pre_cutoff": narayan_pre_sha,
            "trigger": narayan_trigger_sha,
            "later_record": narayan_later_sha,
        },
        "shah_episode_id_reused": shah_episode["episode_id"],
        "shah_episode_hash": hash_object(shah_episode),
        "engine_sha256": engine_hashes,
        "engine_sha256_expected_from_0_5_0_dev0": FROZEN_ENGINE_SHA256,
        "engine_unchanged": engine_hashes == FROZEN_ENGINE_SHA256,
        "construction_limit": (
            "This 2026 build reconstructs historical states after outcomes are known. Artifact custody and timestamps are mechanically enforced, "
            "but code cannot prove psychological blindness of the constructor. The Shah episode is reused unchanged; Narayan authority is based only "
            "on primary pre-cutoff citation context, while the 2016 audit is present only in the private future seal/gold path."
        ),
    }
    write(output / "custody.json", custody)

    status = "MIXED_TEMPORAL_SELECTIVITY_CORPUS_RUN_BELOW_PROMOTION_BAR"
    summary = {
        "valid": True,
        "status": status,
        "benchmark_id": BENCHMARK_ID,
        "pack_id": pack["pack_id"],
        "future_seal_id": seal["future_seal_id"],
        "predictions_id": predictions["predictions_id"],
        "gold_id": gold["gold_id"],
        "score_id": score["score_id"],
        "promotion_policy_id": promotion_policy["promotion_policy_id"],
        "promotion_result_id": promotion_result["promotion_result_id"],
        "promotion_verdict": promotion_result["verdict"],
        "engine_unchanged": custody["engine_unchanged"],
        "scored_targets": er["scored_cases"],
        "reopen_gold": er["reopen_gold"],
        "no_reopen_gold": er["no_reopen_gold"],
        "direct_reopenings_caught": direct["true_reopen_reviews"],
        "direct_missed_reopenings": direct["missed_reopenings"],
        "direct_review_load": direct["total_review_load"],
        "review_all_reopenings_caught": review_all["true_reopen_reviews"],
        "review_all_missed_reopenings": review_all["missed_reopenings"],
        "review_all_review_load": review_all["total_review_load"],
        "review_all_unnecessary_reviews": review_all["unnecessary_reviews"],
        "evidence_recall_reopenings_caught": er["true_reopen_reviews"],
        "evidence_recall_missed_reopenings": er["missed_reopenings"],
        "evidence_recall_review_load": er["total_review_load"],
        "evidence_recall_unnecessary_reviews": er["unnecessary_reviews"],
        "evidence_recall_reviewer_savings_vs_review_all": er_cmp["reviewer_savings_vs_review_all"],
        "evidence_recall_review_load_reduction_basis_points": review_reduction_bps,
        "evidence_recall_reconsideration_recall_basis_points": er_recall_bps,
        "minimum_required_review_reduction_basis_points": MIN_REVIEW_REDUCTION_BPS,
        "minimum_required_recall_basis_points": MIN_RECALL_BPS,
    }
    write(output / "summary.json", summary)

    report = f"""# Evidence Recall Temporal Holdout — Mixed Selectivity Corpus 001

Status: `{status}`

## Frozen question

Given only the accepted dependency state available before each trigger, can frozen Evidence Recall retain near-Review-All reconsideration recall while materially reducing how many targets humans must reopen?

The promotion bar was written before gold construction: at least **95% reconsideration recall**, at least **40% review-load reduction versus Review-All Reachability**, and **no additional missed reopenings** versus Review-All. There is no composite score.

## Real historical episodes

1. **Shah / Darwish intravenous iron** — reused byte-for-byte at the episode level from `0.5.0.dev1`. Two targets later received explicit reanalysis after the included Darwish trial was retracted. Both remain `REOPEN` even though the reanalysis reported no change.
2. **Narayan SIRT2 / necroptosis** — frozen on {NARAYAN_T0}, before Nature's {NARAYAN_T1} retraction. The pre-cutoff Nature News & Views summary is a HARD derivation. A pre-cutoff Vitner paper is reachable because it cites Narayan in experimental-method context, but the candidate conclusion-level relation is UNADMITTED. A 2016 independent citation audit later identifies the News & Views item as a summary of Narayan while singling out Vitner as method-only rather than propagation of the retracted scientific result into the Gaucher-disease conclusion.

This produces the first real mixed gold in the temporal line: **3 REOPEN + 1 affirmative NO_REOPEN**. The negative is not institutional silence; it is a later independent citation-context audit of the exact target relationship.

## Result

| System | Reopenings caught | Missed | Review load | Unnecessary reviews | Savings vs Review-All |
|---|---:|---:|---:|---:|---:|
| Direct Lookup | {direct['true_reopen_reviews']}/{direct['reopen_gold']} | {direct['missed_reopenings']} | {direct['total_review_load']} | {direct['unnecessary_reviews']} | {score['comparisons_vs_review_all']['DIRECT_LOOKUP']['reviewer_savings_vs_review_all']} |
| Review-All Reachability | {review_all['true_reopen_reviews']}/{review_all['reopen_gold']} | {review_all['missed_reopenings']} | {review_all['total_review_load']} | {review_all['unnecessary_reviews']} | 0 |
| Frozen Evidence Recall | {er['true_reopen_reviews']}/{er['reopen_gold']} | {er['missed_reopenings']} | {er['total_review_load']} | {er['unnecessary_reviews']} | {er_cmp['reviewer_savings_vs_review_all']} |

Frozen Evidence Recall retains **{er_recall_bps / 100:.2f}% recall** and reduces review load from {review_all['total_review_load']} to {er['total_review_load']}, a **{review_reduction_bps / 100:.2f}% reduction**. It eliminates the one affirmative unnecessary review in this small corpus. Direct Lookup uses the same review load as Evidence Recall but misses one warranted downstream reopening.

## Promotion verdict

`{promotion_result['verdict']}`

Evidence Recall clears the recall requirement and adds no misses versus Review-All, but its {review_reduction_bps / 100:.2f}% attention saving is below the predeclared 40% materiality threshold. This is the first case-level evidence that typed authority can buy back *some* attention rather than merely relabeling Review-All, but the effect is too small and the corpus is too small to promote the product thesis.

No engine semantics were changed. The failure is recorded as-is.

## Boundaries

- Four scored targets across two historical episodes are not a stable population estimate.
- The Narayan negative gold is narrow: the later audit establishes that Vitner's citation was method-only rather than reliance of the scored Gaucher-disease conclusion on the retracted SIRT2-necroptosis result. It does not certify every method from the retracted paper.
- The historical packs were reconstructed in 2026. Mechanical timestamps and sealed artifacts prevent explicit future records from entering prediction, but cannot prove constructor ignorance.
- No weighted support, generalized revocation, hidden-edge discovery, UI, Receipt Gate work, or Successor Gate work was added.
"""
    write(output / "REPORT.md", report)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the first mixed real Evidence Recall temporal selectivity corpus")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    summary = build(Path(args.output))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
