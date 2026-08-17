from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from openline_claim_graph.canonical import hash_object
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


BENCHMARK_ID = "temporal-real-001-shah-iron-v1"
T0 = "2023-01-18T23:59:59Z"
T1 = "2023-01-19T00:00:00Z"
T2 = "2025-01-27T00:00:00Z"
RETRIEVAL_CUTOFF = "2025-01-27T23:59:59Z"

DARWISH = "doi:10.1080/14767058.2017.1379988"
HEMOGLOBIN = "shah2021:pooled-hemoglobin"
HEMOGLOBIN_FINDING = "shah2021:finding-improved-hemoglobin"

ROOT = Path(__file__).resolve().parents[1]
FROZEN_ENGINE_SHA256 = {
    "src/openline_claim_graph/temporal_holdout.py": "bc8f0011d65cb1c2c728ef374ebb82b86c3c08657e9919427ff5d80b2707886a",
    "src/openline_claim_graph/comparative_benchmark.py": "6c04e9e021cbc1c01aae78606acc6cd41393c99673185e1e8e3ee4ccaa06e4b1",
    "src/openline_claim_graph/impact.py": "1757340f69e919ff68d3cdfe4265fc1ac330bc99ff5bcd20b69058fa846905a2",
}


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_source_evidence() -> tuple[dict, dict, dict]:
    pre_cutoff = {
        "schema": "openline.temporal-source-evidence.v1",
        "hash_scope": "Canonical local evidence record; not publisher raw bytes.",
        "records": [
            {
                "role": "invalidated-study",
                "identifier": "doi:10.1080/14767058.2017.1379988",
                "pmid": "28901214",
                "available_at": "2017-10-03T00:00:00Z",
                "title": "Total dose iron dextran infusion versus oral iron for treating iron deficiency anemia in pregnant women: a randomized controlled trial",
                "facts": [
                    "The study compared intravenous low-molecular-weight iron dextran with oral ferrous fumarate in 66 pregnant women with iron-deficiency anemia.",
                    "The study reported hemoglobin and other anemia-response outcomes after treatment.",
                ],
            },
            {
                "role": "accepted-systematic-review",
                "identifier": "doi:10.1001/jamanetworkopen.2021.33935",
                "available_at": "2021-11-12T00:00:00Z",
                "title": "Risk of Infection Associated With Administration of Intravenous Iron: A Systematic Review and Meta-analysis",
                "facts": [
                    "The review included 154 randomized clinical trials overall.",
                    "The hemoglobin analysis used 111 randomized clinical trials and its enumerated reference range includes reference 76, the Darwish trial.",
                    "The pooled hemoglobin result reported a mean difference of 0.57 g/dL with intravenous iron versus oral or no iron.",
                    "The discussion identifies improved hemoglobin as one of the review's main findings.",
                    "The primary infection analysis enumerates 64 trials and does not include reference 76; that branch is intentionally outside this first scored pack.",
                    "The RBC-transfusion-requirement analysis enumerates 54 trials and does not include reference 76; that branch is intentionally outside this first scored pack.",
                ],
            },
        ],
    }
    trigger = {
        "schema": "openline.temporal-trigger-evidence.v1",
        "hash_scope": "Canonical local evidence record; not publisher raw bytes.",
        "identifier": "doi:10.1080/14767058.2023.2169999",
        "pmid": "36658746",
        "available_at": T1,
        "title": "Statement of Retraction: Total dose iron dextran infusion versus oral iron for treating iron deficiency anemia in pregnant women: a randomized controlled trial",
        "facts": [
            "The publisher retracted the Darwish trial online on January 19, 2023.",
            "The notice cites significant concerns about the integrity of the data and reported results, including unexplained overlap with another study.",
            "The notice reports 27 identical baseline values and 38 identical outcome values between the two studies and states that sufficient original data were not supplied for review.",
        ],
    }
    later = {
        "schema": "openline.temporal-later-evidence.v1",
        "hash_scope": "Canonical local evidence record; not publisher raw bytes.",
        "identifier": "doi:10.1001/jamanetworkopen.2025.0887",
        "available_at": T2,
        "title": "Correction to Meta-Analysis to Acknowledge Retracted Study",
        "facts": [
            "The 2025 JAMA Network Open correction explicitly identifies study 76 as having been retracted after the 2021 meta-analysis was published.",
            "The correction reports that the meta-analysis was reanalyzed without the retracted study and that the reported results were unaffected.",
            "Because an explicit reanalysis occurred, this benchmark treats the affected accepted results as warranted REOPEN even though they survived the reanalysis.",
        ],
    }
    return pre_cutoff, trigger, later


def build(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    evidence_dir = output / "source-evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    pre_cutoff, trigger, later = build_source_evidence()
    write(evidence_dir / "pre-cutoff.json", pre_cutoff)
    write(evidence_dir / "trigger.json", trigger)
    write(evidence_dir / "later.private.json", later)

    pre_sha = hash_object(pre_cutoff)
    trigger_sha = hash_object(trigger)
    later_sha = hash_object(later)

    nodes = [
        {
            "node_id": DARWISH,
            "label": "Darwish 2019 randomized trial",
            "text": "Darwish et al. randomized trial of intravenous iron dextran versus oral iron in pregnancy.",
            "locator": "doi:10.1080/14767058.2017.1379988",
            "available_at": "2017-10-03T00:00:00Z",
        },
        {
            "node_id": HEMOGLOBIN,
            "label": "Shah 2021 pooled hemoglobin result",
            "text": "Intravenous iron was associated with a pooled hemoglobin increase of 0.57 g/dL versus oral iron or no iron.",
            "locator": "doi:10.1001/jamanetworkopen.2021.33935#hemoglobin",
            "available_at": "2021-11-12T00:00:00Z",
        },
        {
            "node_id": HEMOGLOBIN_FINDING,
            "label": "Shah 2021 improved-hemoglobin finding",
            "text": "The systematic review identifies improved hemoglobin as one of its main findings for intravenous iron.",
            "locator": "doi:10.1001/jamanetworkopen.2021.33935#discussion",
            "available_at": "2021-11-12T00:00:00Z",
        },
    ]
    edges = [
        {
            "prerequisite_node_id": DARWISH,
            "dependent_node_id": HEMOGLOBIN,
            "relation": "DERIVED_FROM",
            "available_at": "2021-11-12T00:00:00Z",
            "evidence": [
                "Pre-cutoff review explicitly lists 111 RCTs for hemoglobin and includes reference 76, the Darwish trial."
            ],
        },
        {
            "prerequisite_node_id": HEMOGLOBIN,
            "dependent_node_id": HEMOGLOBIN_FINDING,
            "relation": "DERIVED_FROM",
            "available_at": "2021-11-12T00:00:00Z",
            "evidence": [
                "Pre-cutoff discussion restates improved hemoglobin as a main finding from the pooled hemoglobin analysis."
            ],
        },
    ]

    episode = create_episode(
        episode_name="Darwish retraction -> Shah intravenous-iron meta-analysis",
        cutoff_at=T0,
        event_at=T1,
        invalidated_node_id=DARWISH,
        target_node_ids=[HEMOGLOBIN, HEMOGLOBIN_FINDING],
        nodes=nodes,
        edges=edges,
        event={
            "status": "RETRACTED",
            "identifier": "doi:10.1080/14767058.2017.1379988",
            "locator": "doi:10.1080/14767058.2023.2169999",
            "reason": "Publisher retraction after integrity concerns about data and reported results.",
            "available_at": T1,
            "evidence_sha256": trigger_sha,
        },
        metadata={
            "domain": "SCIENTIFIC_CLINICAL",
            "historical_resolution": "DAY",
            "construction_basis": "Explicit pre-cutoff study membership and derivation statements only.",
            "case_role": "FIRST_REAL_TEMPORAL_HOLDOUT",
        },
    )

    # Build the private later-record seal first. Only its commitment enters pack.json.
    later_record = create_future_record(
        episode_id=episode["episode_id"],
        available_at=T2,
        record_type="EXPLICIT_NO_CHANGE_AFTER_REANALYSIS",
        target_node_ids=[HEMOGLOBIN, HEMOGLOBIN_FINDING],
        locator="doi:10.1001/jamanetworkopen.2025.0887",
        evidence_sha256=later_sha,
        description=(
            "JAMA Network Open later acknowledged the retracted included study and reported an explicit reanalysis "
            "without it; the reported results did not change."
        ),
    )
    seal = create_future_seal(
        benchmark_id=BENCHMARK_ID,
        scope_definition=(
            "Published records through 2025-01-27 that explicitly attribute reconsideration of the Shah 2021 "
            "meta-analysis to the Darwish retraction. Unrelated corrections are outside this trigger-specific scope."
        ),
        retrieval_cutoff_at=RETRIEVAL_CUTOFF,
        records=[later_record],
    )
    write(output / "future-seal.private.json", seal)

    pack = create_pack(
        benchmark_id=BENCHMARK_ID,
        episodes=[episode],
        source_manifest=[
            {
                "role": "pre-cutoff-study-and-review-evidence",
                "identifier": "darwish-2017-shah-2021",
                "available_at": "2021-11-12T00:00:00Z",
                "sha256": pre_sha,
                "locator": "source-evidence/pre-cutoff.json",
            },
            {
                "role": "trigger-retraction-evidence",
                "identifier": "doi:10.1080/14767058.2023.2169999",
                "available_at": T1,
                "sha256": trigger_sha,
                "locator": "source-evidence/trigger.json",
            },
        ],
        construction_rule=(
            "Graph nodes and edges use only evidence published by the t0 cutoff. HARD authority is granted only to "
            "explicit pre-cutoff inclusion/derivation relations. The t1 retraction is prediction-visible. Later "
            "records are committed by seal but are not inputs to prediction."
        ),
        future_seal=seal,
        status="REAL_TEMPORAL_CASE_001_INPUTS_FROZEN",
    )
    write(output / "pack.json", pack)

    authority = create_authority(
        pack,
        edge_authority={edge["edge_id"]: "HARD" for edge in episode["edges"]},
        declared_by="temporal-real-case-construction-rule",
        construction_rule=(
            "HARD only because the 2021 review explicitly identifies study 76 as an input to the hemoglobin analysis "
            "and explicitly derives the improved-hemoglobin finding from that pooled analysis. No later record is used."
        ),
    )
    write(output / "authority.json", authority)

    # Prediction phase: the API accepts pack + authority only. Neither seal nor gold is passed.
    predictions = run_temporal(pack, authority, include_naive_diagnostic=True)
    write(output / "predictions.json", predictions)

    # Only after predictions exist do we bind labels to the already-created future seal.
    gold = create_gold(
        pack,
        seal,
        [
            {
                "episode_id": episode["episode_id"],
                "target_node_id": target,
                "outcome": "REOPEN",
                "future_record_ids": [later_record["record_id"]],
            }
            for target in [HEMOGLOBIN, HEMOGLOBIN_FINDING]
        ],
        label_definition=(
            "REOPEN means a later independent publication explicitly shows trigger-attributed reanalysis or "
            "reconsideration. The 2025 correction reports reanalysis after the included Darwish study was retracted; "
            "unchanged results still count as warranted reconsideration."
        ),
    )
    write(output / "gold.private.json", gold)

    score = score_temporal(pack, authority, seal, gold, predictions)
    write(output / "score.json", score)

    engine_hashes = {path: file_sha256(ROOT / path) for path in FROZEN_ENGINE_SHA256}
    custody = {
        "schema": "openline.temporal-real-case-custody.v1",
        "benchmark_id": BENCHMARK_ID,
        "case_id": episode["episode_id"],
        "cutoff_at": T0,
        "trigger_at": T1,
        "later_record_at": T2,
        "build_sequence": [
            "local source evidence snapshots created",
            "later-record seal created",
            "public pack bound to seal commitment",
            "receiver authority frozen from pre-cutoff evidence",
            "predictions emitted from pack and authority only",
            "gold bound to already sealed later record",
            "score computed from frozen predictions",
        ],
        "evidence_hashes": {
            "pre_cutoff": pre_sha,
            "trigger": trigger_sha,
            "later_record": later_sha,
        },
        "engine_sha256": engine_hashes,
        "engine_sha256_expected_from_0_5_0_dev0": FROZEN_ENGINE_SHA256,
        "engine_unchanged": engine_hashes == FROZEN_ENGINE_SHA256,
        "construction_limit": (
            "This is a retrospective historical reconstruction built in 2026. Timestamp and artifact custody are "
            "mechanically checked, but code cannot prove the human constructor was psychologically blind to later history. "
            "The graph therefore uses only explicit pre-cutoff study membership and derivation statements to minimize discretion."
        ),
    }
    write(output / "custody.json", custody)

    direct = score["metrics"]["DIRECT_LOOKUP"]
    review_all = score["metrics"]["REVIEW_ALL_REACHABILITY"]
    evidence_recall = score["metrics"]["EVIDENCE_RECALL"]
    report = f"""# Evidence Recall Temporal Holdout — Real Case 001\n\nStatus: `REAL_TEMPORAL_CASE_001_RUN_NO_SELECTIVITY_ADVANTAGE`\n\n## Case\n\n- Accepted review: Shah et al., JAMA Network Open, 2021, DOI `10.1001/jamanetworkopen.2021.33935`.\n- Invalidated study: Darwish et al., DOI `10.1080/14767058.2017.1379988`.\n- `t0`: {T0} (day before the publisher retraction).\n- `t1`: {T1} (publisher retraction date, DOI `10.1080/14767058.2023.2169999`).\n- Later record: {T2}, JAMA Network Open correction DOI `10.1001/jamanetworkopen.2025.0887`.\n\nThe pre-cutoff review explicitly places reference 76 (Darwish) inside the 111-RCT hemoglobin analysis. The pack therefore models a HARD `DERIVED_FROM` relation from the Darwish trial to the pooled hemoglobin result, and a second HARD derivation from that pooled result to the review's improved-hemoglobin finding. No later correction is needed to construct either edge.\n\nThe later JAMA correction explicitly reports that the review was reanalyzed without the retracted study and that the reported results did not change. Under the frozen temporal-gold rule, both targets are `REOPEN`: reconsideration really occurred even though the findings survived.\n\n## Frozen predictions and score\n\n| System | Reopenings caught | Missed | Review load | Reviewer savings vs Review-All |\n|---|---:|---:|---:|---:|\n| Direct Lookup | {direct['true_reopen_reviews']}/{direct['reopen_gold']} | {direct['missed_reopenings']} | {direct['total_review_load']} | {score['comparisons_vs_review_all']['DIRECT_LOOKUP']['reviewer_savings_vs_review_all']} |\n| Review-All Reachability | {review_all['true_reopen_reviews']}/{review_all['reopen_gold']} | {review_all['missed_reopenings']} | {review_all['total_review_load']} | 0 |\n| Frozen Evidence Recall | {evidence_recall['true_reopen_reviews']}/{evidence_recall['reopen_gold']} | {evidence_recall['missed_reopenings']} | {evidence_recall['total_review_load']} | {score['comparisons_vs_review_all']['EVIDENCE_RECALL']['reviewer_savings_vs_review_all']} |\n\nDirect Lookup catches the immediate pooled result but misses the downstream improved-hemoglobin finding. Review-All and frozen Evidence Recall catch both. Evidence Recall saves **zero** reviews versus Review-All in this first real historical episode.\n\n## Verdict\n\n`NO_PROMOTION`.\n\nThis episode establishes real temporal mechanism contact: a graph frozen before a 2023 retraction is graded by a 2025 trigger-attributed reanalysis. It does **not** establish an attention-selectivity advantage. On this two-target HARD dependency chain, Evidence Recall and Review-All are equivalent.\n\nThe result is intentionally not rescued. No relation semantics, weighting, basis type, or evaluator rule changed after the later record was examined. More real historical episodes are required before any product-level temporal claim can be considered.\n\n## Boundaries\n\n- This is one small real case, not a corpus-level estimate.\n- Both scored gold labels are positive; this case does not estimate false-review precision.\n- The local evidence JSON files are source-backed factual snapshots, not byte-for-byte publisher archives.\n- The historical reconstruction was authored after the events occurred; mechanical timestamp controls prevent explicit data leakage into the pack but cannot prove human ignorance.\n- Infection and RBC-transfusion branches are excluded from scoring because the pre-cutoff review's enumerated study lists do not include reference 76 and the later trigger-specific correction does not provide an independent target-level negative-gold record for them.\n"""
    (output / "REPORT.md").write_text(report, encoding="utf-8")

    summary = {
        "valid": True,
        "status": "REAL_TEMPORAL_CASE_001_RUN_NO_SELECTIVITY_ADVANTAGE",
        "benchmark_id": BENCHMARK_ID,
        "episode_id": episode["episode_id"],
        "pack_id": pack["pack_id"],
        "future_seal_id": seal["future_seal_id"],
        "predictions_id": predictions["predictions_id"],
        "gold_id": gold["gold_id"],
        "score_id": score["score_id"],
        "engine_unchanged": custody["engine_unchanged"],
        "direct_review_load": direct["total_review_load"],
        "review_all_review_load": review_all["total_review_load"],
        "evidence_recall_review_load": evidence_recall["total_review_load"],
        "direct_missed_reopenings": direct["missed_reopenings"],
        "evidence_recall_missed_reopenings": evidence_recall["missed_reopenings"],
        "evidence_recall_reviewer_savings_vs_review_all": score["comparisons_vs_review_all"]["EVIDENCE_RECALL"]["reviewer_savings_vs_review_all"],
    }
    write(output / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the first real Evidence Recall temporal holdout case")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    summary = build(Path(args.output))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
