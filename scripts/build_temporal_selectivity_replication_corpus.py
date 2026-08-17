from __future__ import annotations

import argparse
import hashlib
import json
import statistics
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

ROOT = Path(__file__).resolve().parents[1]
SHAH_DIR = ROOT / "artifacts/evidence-recall-temporal/real-001-shah-iron"
BENCHMARK_ID = "temporal-selectivity-replication-001-v1"
RETRIEVAL_CUTOFF = "2026-08-17T00:00:00Z"
AUDIT_AVENELL = "2019-10-30T00:00:00Z"
AUDIT_NARAYAN = "2016-05-03T00:00:00Z"

MIN_RECALL_BPS = 9500
MIN_REVIEW_REDUCTION_BPS = 4000
MAX_ADDITIONAL_MISSED = 0
MIN_EPISODES_WITH_RECURRING_SAVINGS = 3

FROZEN_ENGINE_SHA256 = {
    "src/openline_claim_graph/temporal_holdout.py": "bc8f0011d65cb1c2c728ef374ebb82b86c3c08657e9919427ff5d80b2707886a",
    "src/openline_claim_graph/comparative_benchmark.py": "6c04e9e021cbc1c01aae78606acc6cd41393c99673185e1e8e3ee4ccaa06e4b1",
    "src/openline_claim_graph/impact.py": "1757340f69e919ff68d3cdfe4265fc1ac330bc99ff5bcd20b69058fa846905a2",
}

NARAYAN = "doi:10.1038/nature11700"
ZHOU = "zhou2012:death-by-deacetylation-summary"
CAI = "cai2013:mlkl-necroptosis-context"
WEBSTER = "webster2014:autophagy-necroptosis-context"
VITNER = "vitner2014:gaucher-main-conclusion"

SATO8 = "doi:10.1136/jnnp.66.1.64"
PETERSON = "peterson2014:vitamin-d-parkinson-conclusion"
LATHAM = "latham2003:vitamin-d-falls-conclusion"
AHRQ_FALLS = "ahrq-falls:falls-prevention-conclusion"

SATO11 = "doi:10.1212/01.WNL.0000152871.65027.76"
AHRQ2007 = "ahrq2007:bisphosphonate-high-risk-falls-conclusion"
VERHEYDEN11 = "verheyden2013:sato2005a-awaiting-assessment"
MCCARUS = "mccarus:report11-passing-reference"

SATO12 = "doi:10.1001/archinte.165.15.1743"
HANDBOOK2008 = "handbook2008:risedronate-fracture-prevention-conclusion"
VERHEYDEN12 = "verheyden2013:sato2005b-awaiting-assessment"


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bps(numerator: int, denominator: int) -> int:
    return (numerator * 10_000) // denominator if denominator else 0


def evidence_record(name: str, records: list[dict], note: str) -> dict:
    return {
        "schema": "openline.temporal-source-evidence.v1",
        "name": name,
        "hash_scope": "Canonical local evidence record; not publisher raw bytes.",
        "records": records,
        "note": note,
    }


def edge(prerequisite: str, dependent: str, relation: str, available_at: str, evidence: str) -> dict:
    return {
        "prerequisite_node_id": prerequisite,
        "dependent_node_id": dependent,
        "relation": relation,
        "available_at": available_at,
        "evidence": [evidence],
    }


def node(node_id: str, label: str, text: str, locator: str, available_at: str, independent_basis: bool = False) -> dict:
    return {
        "node_id": node_id,
        "label": label,
        "text": text,
        "locator": locator,
        "available_at": available_at,
        "independent_basis": independent_basis,
    }


def build_narayan(evidence_dir: Path):
    pre = evidence_record(
        "Narayan pre-retraction accepted-state evidence",
        [
            {"role": "invalidated-study", "identifier": NARAYAN, "available_at": "2012-11-28T00:00:00Z", "fact": "Narayan et al. reported SIRT2 as required for TNF-alpha-mediated necroptosis."},
            {"role": "direct-summary", "identifier": "doi:10.1038/nature11761", "available_at": "2012-11-28T00:00:00Z", "fact": "The contemporaneous Nature News & Views item summarized the Narayan SIRT2-necroptosis result."},
            {"role": "direct-citing-original", "identifier": "doi:10.1038/ncb2883", "available_at": "2013-12-08T00:00:00Z", "fact": "Cai et al. directly cited Narayan in a necroptosis paper before the retraction."},
            {"role": "direct-citing-review", "identifier": "doi:10.1016/j.bbalip.2014.02.001", "available_at": "2014-02-11T00:00:00Z", "fact": "Webster et al. directly cited Narayan in a pre-retraction review."},
            {"role": "method-only-direct-citation", "identifier": "doi:10.1038/nm.3449", "available_at": "2014-01-19T00:00:00Z", "fact": "Vitner et al. directly cited Narayan in experimental-method context; the Gaucher-disease conclusion had its own experimental basis."},
        ],
        "Authority is assigned from pre-retraction citation use only. The later audit is sealed from prediction.",
    )
    trigger = {
        "schema": "openline.temporal-trigger-evidence.v1",
        "identifier": "doi:10.1038/nature12897",
        "available_at": "2014-02-26T00:00:00Z",
        "fact": "Nature retracted the Narayan article because key TNF-alpha necroptosis data appeared irreproducible.",
    }
    later = evidence_record(
        "van der Vet/Nijveen later citation-use audit",
        [{"role": "later-audit", "identifier": "doi:10.1186/s41073-016-0008-5", "available_at": AUDIT_NARAYAN, "fact": "The audit read direct citation contexts, found direct propagation of the retracted result with narrow exceptions, and found no propagation through the inspected indirect citations."}],
        "The audit is used only after predictions exist.",
    )
    for name, value in (("narayan-pre-cutoff.json", pre), ("narayan-trigger.json", trigger), ("narayan-later.private.json", later)):
        write(evidence_dir / name, value)
    pre_hash, trigger_hash, later_hash = hash_object(pre), hash_object(trigger), hash_object(later)
    episode = create_episode(
        episode_name="Narayan SIRT2 retraction — expanded manually inspected direct contexts",
        cutoff_at="2014-02-25T23:59:59Z",
        event_at="2014-02-26T00:00:00Z",
        invalidated_node_id=NARAYAN,
        target_node_ids=[ZHOU, CAI, WEBSTER, VITNER],
        nodes=[
            node(NARAYAN, "Narayan 2012 SIRT2-necroptosis article", "SIRT2 was reported as required for programmed necrosis.", NARAYAN, "2012-11-28T00:00:00Z"),
            node(ZHOU, "Zhou & Yuan 2012 News & Views", "Summary of the Narayan SIRT2-necroptosis result.", "doi:10.1038/nature11761", "2012-11-28T00:00:00Z"),
            node(CAI, "Cai et al. necroptosis paper", "Pre-retraction direct citation in a paper about TNF-induced necroptosis.", "doi:10.1038/ncb2883", "2013-12-08T00:00:00Z"),
            node(WEBSTER, "Webster et al. review", "Pre-retraction direct citation in a review discussing acetylation and cell-death biology.", "doi:10.1016/j.bbalip.2014.02.001", "2014-02-11T00:00:00Z"),
            node(VITNER, "Vitner 2014 Gaucher conclusion", "RIPK3 modulation improves disease in a Gaucher-disease mouse model.", "doi:10.1038/nm.3449", "2014-01-19T00:00:00Z", True),
        ],
        edges=[
            edge(NARAYAN, ZHOU, "DERIVED_FROM", "2012-11-28T00:00:00Z", "The News & Views item explicitly summarizes Narayan's main reported result."),
            edge(NARAYAN, CAI, "SUPPORTS", "2013-12-08T00:00:00Z", "Cai directly cites the pre-retraction Narayan result in the necroptosis context."),
            edge(NARAYAN, WEBSTER, "SUPPORTS", "2014-02-11T00:00:00Z", "Webster directly cites the pre-retraction Narayan result in the relevant review context."),
            edge(NARAYAN, VITNER, "SUPPORTS", "2014-01-19T00:00:00Z", "Vitner cites Narayan for experimental method, establishing reachability but not conclusion-level reliance."),
        ],
        event={"status": "RETRACTED", "identifier": NARAYAN, "locator": "doi:10.1038/nature12897", "reason": "Key TNF-alpha necroptosis data appeared irreproducible.", "available_at": "2014-02-26T00:00:00Z", "evidence_sha256": trigger_hash},
        metadata={"domain": "SCIENTIFIC_CLINICAL", "historical_resolution": "DAY", "case_role": "TEMPORAL_SELECTIVITY_REPLICATION", "source_family": "NARAYAN_VAN_DER_VET"},
    )
    ids = {item["dependent_node_id"]: item["edge_id"] for item in episode["edges"]}
    authority = {target: ("UNADMITTED" if target == VITNER else "HARD") for target in [ZHOU, CAI, WEBSTER, VITNER]}
    future = [
        create_future_record(episode_id=episode["episode_id"], available_at=AUDIT_NARAYAN, record_type="INDEPENDENT_DEPENDENCY_AUDIT_RELIANCE", target_node_ids=[ZHOU, CAI, WEBSTER], locator="doi:10.1186/s41073-016-0008-5", evidence_sha256=later_hash, description="Later manual citation-use audit establishes direct propagation of the retracted result for the scored admitted contexts."),
        create_future_record(episode_id=episode["episode_id"], available_at=AUDIT_NARAYAN, record_type="INDEPENDENT_CITATION_CONTEXT_NO_RELIANCE", target_node_ids=[VITNER], locator="doi:10.1186/s41073-016-0008-5", evidence_sha256=later_hash, description="Later manual audit identifies the scored Vitner use as method-only rather than propagation of the retracted conclusion."),
    ]
    labels = {ZHOU: "REOPEN", CAI: "REOPEN", WEBSTER: "REOPEN", VITNER: "NO_REOPEN"}
    manifest = [
        {"role": "narayan-pre-cutoff", "identifier": "narayan-pre-retraction-contexts", "available_at": "2014-02-11T00:00:00Z", "sha256": pre_hash, "locator": "source-evidence/narayan-pre-cutoff.json"},
        {"role": "narayan-trigger", "identifier": "doi:10.1038/nature12897", "available_at": "2014-02-26T00:00:00Z", "sha256": trigger_hash, "locator": "source-evidence/narayan-trigger.json"},
    ]
    return episode, ids, authority, future, labels, manifest, {"pre": pre_hash, "trigger": trigger_hash, "later": later_hash}


def build_sato_episode(*, evidence_dir: Path, key: str, origin: str, original_title: str, original_at: str, cutoff_at: str, event_at: str, trigger_locator: str, trigger_note: str, targets: list[dict]):
    pre = evidence_record(
        f"{key} pre-retraction dependency evidence",
        [{"role": "invalidated-trial", "identifier": origin, "available_at": original_at, "fact": original_title}]
        + [{"role": "downstream-target", "identifier": item["locator"], "available_at": item["available_at"], "fact": item["pre_fact"]} for item in targets],
        "Only facts that were encoded in the downstream publication before the trigger are used for authority. Later Avenell audit classifications are sealed.",
    )
    trigger = {"schema": "openline.temporal-trigger-evidence.v1", "identifier": trigger_locator, "available_at": event_at, "fact": trigger_note}
    later = evidence_record(
        f"Avenell later audit for {key}",
        [{"role": "later-audit", "identifier": "doi:10.1136/bmjopen-2019-031909", "available_at": AUDIT_AVENELL, "fact": "Avenell et al. manually assessed citation use and impact of retracted Sato trial reports in systematic reviews and guidelines."}],
        "Later audit facts are used only for gold after prediction.",
    )
    safe = key.replace("/", "-").replace(" ", "-").lower()
    write(evidence_dir / f"{safe}-pre-cutoff.json", pre)
    write(evidence_dir / f"{safe}-trigger.json", trigger)
    write(evidence_dir / f"{safe}-later.private.json", later)
    pre_hash, trigger_hash, later_hash = hash_object(pre), hash_object(trigger), hash_object(later)
    episode = create_episode(
        episode_name=f"{key} retraction — explicit inclusion versus affirmative non-reliance",
        cutoff_at=cutoff_at,
        event_at=event_at,
        invalidated_node_id=origin,
        target_node_ids=[item["node_id"] for item in targets],
        nodes=[node(origin, original_title, original_title, origin, original_at)] + [node(item["node_id"], item["label"], item["text"], item["locator"], item["available_at"], item.get("independent_basis", False)) for item in targets],
        edges=[edge(origin, item["node_id"], item.get("relation", "SUPPORTS"), item["available_at"], item["edge_evidence"]) for item in targets],
        event={"status": "RETRACTED", "identifier": origin, "locator": trigger_locator, "reason": trigger_note, "available_at": event_at, "evidence_sha256": trigger_hash},
        metadata={"domain": "SCIENTIFIC_CLINICAL", "historical_resolution": "MONTH" if key == "Sato trial 8" else "DAY", "case_role": "TEMPORAL_SELECTIVITY_REPLICATION", "source_family": "SATO_AVENELL", "timestamp_note": "Month-resolution benchmark marker; not asserted as exact publisher day." if key == "Sato trial 8" else "Exact publication day used where available."},
    )
    edge_ids = {item["dependent_node_id"]: item["edge_id"] for item in episode["edges"]}
    authority = {item["node_id"]: item["authority"] for item in targets}
    future = []
    labels = {}
    for item in targets:
        record = create_future_record(
            episode_id=episode["episode_id"],
            available_at=AUDIT_AVENELL,
            record_type=item["future_type"],
            target_node_ids=[item["node_id"]],
            locator="doi:10.1136/bmjopen-2019-031909",
            evidence_sha256=later_hash,
            description=item["later_fact"],
        )
        future.append(record)
        labels[item["node_id"]] = item["gold"]
    manifest = [
        {"role": f"{safe}-pre-cutoff", "identifier": f"{safe}-pre-cutoff-evidence", "available_at": max(item["available_at"] for item in targets), "sha256": pre_hash, "locator": f"source-evidence/{safe}-pre-cutoff.json"},
        {"role": f"{safe}-trigger", "identifier": trigger_locator, "available_at": event_at, "sha256": trigger_hash, "locator": f"source-evidence/{safe}-trigger.json"},
    ]
    return episode, edge_ids, authority, future, labels, manifest, {"pre": pre_hash, "trigger": trigger_hash, "later": later_hash}


def create_promotion_policy() -> dict:
    body = {
        "schema": "openline.evidence-recall-temporal-replication-promotion-policy.v1",
        "candidate_system": "EVIDENCE_RECALL",
        "reference_system": "REVIEW_ALL_REACHABILITY",
        "minimum_reconsideration_recall_basis_points": MIN_RECALL_BPS,
        "minimum_review_load_reduction_vs_review_all_basis_points": MIN_REVIEW_REDUCTION_BPS,
        "maximum_additional_missed_reopenings_vs_review_all": MAX_ADDITIONAL_MISSED,
        "minimum_independent_trigger_episodes_with_positive_savings_and_zero_additional_misses": MIN_EPISODES_WITH_RECURRING_SAVINGS,
        "declared_before_gold": True,
        "rule": "Promotion requires >=95% pooled reconsideration recall, >=40% pooled review-load reduction versus Review-All, zero additional misses, and positive savings with zero additional misses in at least three independent trigger episodes. No composite score.",
    }
    return {"promotion_policy_id": content_id("temporal-replication-promotion-policy", body), **body}


def build(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    evidence_dir = output / "source-evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # Freeze Kataoka as a corpus candidate without inventing case-level rows we cannot reproduce here.
    kataoka = {
        "schema": "openline.temporal-case-level-admission.v1",
        "corpus": "Kataoka 2022",
        "doi": "10.1016/j.jclinepi.2022.06.015",
        "aggregate_facts": {"pre_retraction_reviews_or_guidelines": 335, "included_later_retracted_rct": 239},
        "scored_rows_admitted": 0,
        "reason": "Aggregate counts are source-backed, but reproducible case-level inclusion/affirmative-exclusion rows were not available to this build. No rows are synthesized from aggregate numbers or silence.",
    }
    write(evidence_dir / "kataoka-case-level-admission.json", kataoka)

    shah_pack = load(SHAH_DIR / "pack.json")
    shah_authority = load(SHAH_DIR / "authority.json")
    shah_seal = load(SHAH_DIR / "future-seal.private.json")
    shah_gold = load(SHAH_DIR / "gold.private.json")
    shah_episode = dict(shah_pack["episodes"][0])
    shah_future = [dict(item) for item in shah_seal["records"]]
    for source, dest in (("pre-cutoff.json", "shah-pre-cutoff.json"), ("trigger.json", "shah-trigger.json"), ("later.private.json", "shah-later.private.json")):
        write(evidence_dir / dest, load(SHAH_DIR / "source-evidence" / source))

    narayan = build_narayan(evidence_dir)

    sato8 = build_sato_episode(
        evidence_dir=evidence_dir,
        key="Sato trial 8",
        origin=SATO8,
        original_title="Sato et al. 1999 vitamin D/Parkinson osteopenia trial",
        original_at="1999-01-01T00:00:00Z",
        cutoff_at="2017-07-31T23:59:59Z",
        event_at="2017-08-31T23:59:59Z",
        trigger_locator="doi:10.1136/jnnp.66.1.64ret",
        trigger_note="The trial was retracted in 2017; this benchmark uses an August 2017 month-resolution trigger marker because an exact online day is not asserted by the frozen source record.",
        targets=[
            {"node_id": PETERSON, "label": "Peterson 2014 vitamin D/Parkinson review", "text": "Review conclusion about vitamin D and Parkinson's disease.", "locator": "doi:10.1016/j.maturitas.2014.02.012", "available_at": "2014-03-05T00:00:00Z", "pre_fact": "The pre-retraction review incorporated the Sato Parkinson trial among the affected reports underlying its conclusions.", "edge_evidence": "The review used the Sato report as conclusion-level evidence.", "authority": "HARD", "gold": "REOPEN", "future_type": "INDEPENDENT_DEPENDENCY_AUDIT_RELIANCE", "later_fact": "Avenell et al. judged Peterson's conclusions to be based almost entirely on four affected trial reports including report 8."},
            {"node_id": LATHAM, "label": "Latham 2003 vitamin D/falls review", "text": "Systematic review of vitamin D supplementation, physical performance, and falls.", "locator": "doi:10.1046/j.1532-5415.2003.51405.x", "available_at": "2003-08-15T00:00:00Z", "pre_fact": "The review cited but excluded the Sato trial because of poor quality.", "edge_evidence": "Citation establishes reachability, but explicit exclusion means the scored synthesis did not depend on the trial.", "authority": "UNADMITTED", "gold": "NO_REOPEN", "future_type": "FORMAL_SCOPE_EXCLUSION", "later_fact": "Avenell et al. report that Latham et al. appeared to exclude affected trial report 8 because of poor quality."},
            {"node_id": AHRQ_FALLS, "label": "AHRQ falls-prevention guideline", "text": "AHRQ review of interventions to prevent falls in older people.", "locator": "Avenell-2019-ref57", "available_at": "2007-12-31T00:00:00Z", "pre_fact": "The guideline cited but excluded trial report 8 because it did not focus on the outcome of interest.", "edge_evidence": "Citation establishes reachability, but explicit scope exclusion means no admitted dependency for the scored conclusion.", "authority": "UNADMITTED", "gold": "NO_REOPEN", "future_type": "FORMAL_SCOPE_EXCLUSION", "later_fact": "Avenell et al. report that AHRQ excluded trial report 8 because it did not focus on falls rate or number of fallers."},
        ],
    )

    sato11 = build_sato_episode(
        evidence_dir=evidence_dir,
        key="Sato trial 11",
        origin=SATO11,
        original_title="Sato et al. 2005 risedronate after stroke in elderly women",
        original_at="2005-01-01T00:00:00Z",
        cutoff_at="2016-07-11T23:59:59Z",
        event_at="2016-07-12T00:00:00Z",
        trigger_locator="doi:10.1212/WNL.0000000000002788",
        trigger_note="Neurology published the retraction record on 2016-07-12.",
        targets=[
            {"node_id": AHRQ2007, "label": "AHRQ 2007 fracture review", "text": "Bisphosphonate evidence for high-risk falls populations and low-dose risedronate.", "locator": "PMID:20704035", "available_at": "2007-12-01T00:00:00Z", "pre_fact": "The AHRQ review included trial report 11 in its fracture evidence synthesis.", "edge_evidence": "The trial is an included evidentiary input to the scored synthesis.", "authority": "HARD", "gold": "REOPEN", "future_type": "INDEPENDENT_DEPENDENCY_AUDIT_RELIANCE", "later_fact": "Avenell et al. report that AHRQ included reports 11-13 and that those reports were the only evidence for 2.5 mg risedronate preventing hip fracture."},
            {"node_id": VERHEYDEN11, "label": "Verheyden 2013 falls-after-stroke review — report 11", "text": "Sato 2005 report remained awaiting assessment rather than included.", "locator": "doi:10.1002/14651858.CD008728.pub2", "available_at": "2013-05-31T00:00:00Z", "pre_fact": "The Cochrane review categorised affected report 11 as awaiting assessment.", "edge_evidence": "Reachable citation exists, but awaiting-assessment status means no admitted dependency in the scored review conclusion.", "authority": "UNADMITTED", "gold": "NO_REOPEN", "future_type": "FORMAL_SCOPE_EXCLUSION", "later_fact": "Avenell et al. identify reports 11 and 12 as awaiting assessment in Verheyden et al.; they were not included in the scored synthesis."},
            {"node_id": MCCARUS, "label": "McCarus review — report 11", "text": "Narrative review containing a passing citation to the trial.", "locator": "Avenell-2019-ref29", "available_at": "2006-12-31T00:00:00Z", "pre_fact": "The cited trial was a passing reference; its data were not used in the review.", "edge_evidence": "Citation establishes reachability but no data-use dependency for the scored conclusion.", "authority": "UNADMITTED", "gold": "NO_REOPEN", "future_type": "INDEPENDENT_CITATION_CONTEXT_NO_RELIANCE", "later_fact": "Avenell et al. explicitly state that report 11 in McCarus et al. was little more than a passing reference and its data were not used."},
        ],
    )

    sato12 = build_sato_episode(
        evidence_dir=evidence_dir,
        key="Sato trial 12",
        origin=SATO12,
        original_title="Sato et al. 2005 risedronate in men after stroke",
        original_at="2005-08-08T00:00:00Z",
        cutoff_at="2016-06-02T23:59:59Z",
        event_at="2016-06-03T00:00:00Z",
        trigger_locator="doi:10.1001/jamainternmed.2016.3771",
        trigger_note="JAMA Internal Medicine published the retraction notice online on 2016-06-03 because of scientific misconduct and data-integrity concerns.",
        targets=[
            {"node_id": HANDBOOK2008, "label": "2008 evidence-based nursing handbook", "text": "Risedronate fracture-prevention statement for older stroke/Alzheimer populations.", "locator": "Avenell-2019-ref56", "available_at": "2008-04-01T00:00:00Z", "pre_fact": "The handbook's risedronate statement was based entirely on affected reports 12 and 13.", "edge_evidence": "The scored conclusion explicitly uses the affected report as an evidentiary basis.", "authority": "HARD", "gold": "REOPEN", "future_type": "INDEPENDENT_DEPENDENCY_AUDIT_RELIANCE", "later_fact": "Avenell et al. report that the handbook statement was based entirely on affected trial reports 12 and 13."},
            {"node_id": VERHEYDEN12, "label": "Verheyden 2013 falls-after-stroke review — report 12", "text": "Sato 2005 report remained awaiting assessment rather than included.", "locator": "doi:10.1002/14651858.CD008728.pub2", "available_at": "2013-05-31T00:00:00Z", "pre_fact": "The Cochrane review categorised affected report 12 as awaiting assessment.", "edge_evidence": "Reachable citation exists, but awaiting-assessment status means no admitted dependency in the scored review conclusion.", "authority": "UNADMITTED", "gold": "NO_REOPEN", "future_type": "FORMAL_SCOPE_EXCLUSION", "later_fact": "Avenell et al. identify reports 11 and 12 as awaiting assessment in Verheyden et al.; they were not included in the scored synthesis."},
        ],
    )

    episodes = [shah_episode, narayan[0], sato8[0], sato11[0], sato12[0]]
    future_records = shah_future + narayan[3] + sato8[3] + sato11[3] + sato12[3]
    seal = create_future_seal(
        benchmark_id=BENCHMARK_ID,
        scope_definition="Later records are admitted only where an independent case-level record establishes actual reliance/reconsideration or affirmative non-reliance/scope exclusion for the exact scored target. Silence is UNASSESSED. Kataoka aggregate counts are not converted to rows.",
        retrieval_cutoff_at=RETRIEVAL_CUTOFF,
        records=future_records,
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
    for built in (narayan, sato8, sato11, sato12):
        source_manifest.extend(built[5])
    source_manifest.append({"role": "kataoka-case-level-admission", "identifier": "doi:10.1016/j.jclinepi.2022.06.015", "available_at": "2022-07-01T00:00:00Z", "sha256": hash_object(kataoka), "locator": "source-evidence/kataoka-case-level-admission.json"})

    pack = create_pack(
        benchmark_id=BENCHMARK_ID,
        episodes=episodes,
        source_manifest=source_manifest,
        construction_rule="Reuse Shah unchanged. For every added episode, build only from facts available by its t0 cutoff. HARD means explicit pre-trigger inclusion or conclusion-level reliance; UNADMITTED means explicit exclusion, awaiting-assessment status, method-only use, or passing citation with no data use. Later audits are sealed from prediction. No silence is scored as NO_REOPEN.",
        future_seal=seal,
        status="TEMPORAL_SELECTIVITY_REPLICATION_INPUTS_FROZEN",
    )
    write(output / "pack.json", pack)

    authority_entries = [dict(item) for item in shah_authority["edge_authority"]]
    for built in (narayan, sato8, sato11, sato12):
        episode, edge_ids, authorities = built[0], built[1], built[2]
        for target, level in authorities.items():
            authority_entries.append({"episode_id": episode["episode_id"], "edge_id": edge_ids[target], "authority": level})
    authority = create_authority(pack, edge_authority=authority_entries, declared_by="temporal-selectivity-replication-construction-rule", construction_rule="HARD only for explicit pre-trigger inclusion or conclusion-level dependence. Explicit exclusion, awaiting-assessment, method-only citation, or passing reference without data use remains UNADMITTED. No future audit label is an authority input.")
    write(output / "authority.json", authority)

    promotion_policy = create_promotion_policy()
    write(output / "promotion-policy.json", promotion_policy)

    predictions = run_temporal(pack, authority, include_naive_diagnostic=True)
    write(output / "predictions.json", predictions)

    future_by_episode_target = {}
    for record in future_records:
        for target in record["target_node_ids"]:
            future_by_episode_target.setdefault((record["episode_id"], target), []).append(record["record_id"])

    labels = []
    for item in shah_gold["labels"]:
        labels.append({"episode_id": shah_episode["episode_id"], "target_node_id": item["target_node_id"], "outcome": item["outcome"], "future_record_ids": future_by_episode_target[(shah_episode["episode_id"], item["target_node_id"])]})
    for built in (narayan, sato8, sato11, sato12):
        episode, label_map = built[0], built[4]
        for target, outcome in label_map.items():
            labels.append({"episode_id": episode["episode_id"], "target_node_id": target, "outcome": outcome, "future_record_ids": future_by_episode_target[(episode["episode_id"], target)]})

    gold = create_gold(pack, seal, labels, label_definition="REOPEN requires a later independent case-level record of actual reconsideration or explicit reliance on the invalidated input. NO_REOPEN requires affirmative non-reliance or scope exclusion for the exact target. Silence is never negative gold; unchanged recomputation is still REOPEN if reconsideration occurred.")
    write(output / "gold.private.json", gold)

    score = score_temporal(pack, authority, seal, gold, predictions)
    write(output / "score.json", score)

    label_by_key = {(item["episode_id"], item["target_node_id"]): item["outcome"] for item in gold["labels"]}
    episode_name = {episode["episode_id"]: episode["episode_name"] for episode in episodes}
    episode_metrics = []
    for episode in sorted(episodes, key=lambda x: x["episode_name"]):
        eid = episode["episode_id"]
        counts = score["episode_counts"][eid]
        reopen_gold = sum(1 for (ep, _), outcome in label_by_key.items() if ep == eid and outcome == "REOPEN")
        no_reopen_gold = sum(1 for (ep, _), outcome in label_by_key.items() if ep == eid and outcome == "NO_REOPEN")
        ra = counts["REVIEW_ALL_REACHABILITY"]
        er = counts["EVIDENCE_RECALL"]
        savings = ra["total_review_load"] - er["total_review_load"]
        additional = er["missed_reopenings"] - ra["missed_reopenings"]
        episode_metrics.append({
            "episode_id": eid,
            "episode_name": episode_name[eid],
            "reopen_gold": reopen_gold,
            "no_reopen_gold": no_reopen_gold,
            "review_all_reopenings_caught": ra["true_reopen_reviews"],
            "review_all_review_load": ra["total_review_load"],
            "evidence_recall_reopenings_caught": er["true_reopen_reviews"],
            "evidence_recall_missed_reopenings": er["missed_reopenings"],
            "evidence_recall_review_load": er["total_review_load"],
            "reviewer_savings": savings,
            "reviewer_savings_basis_points": bps(savings, ra["total_review_load"]),
            "additional_missed_reopenings_vs_review_all": additional,
            "recurring_savings_pass": savings > 0 and additional <= 0,
        })
    savings_bps_values = [item["reviewer_savings_basis_points"] for item in episode_metrics]
    aggregate_episode_metrics = {
        "schema": "openline.temporal-selectivity-episode-metrics.v1",
        "episode_count": len(episode_metrics),
        "episodes": episode_metrics,
        "mean_episode_review_savings_basis_points": sum(savings_bps_values) // len(savings_bps_values),
        "median_episode_review_savings_basis_points": int(statistics.median(savings_bps_values)),
        "episodes_with_positive_savings_and_zero_additional_misses": sum(1 for item in episode_metrics if item["recurring_savings_pass"]),
    }
    aggregate_episode_metrics["episode_metrics_id"] = content_id("temporal-selectivity-episode-metrics", aggregate_episode_metrics)
    write(output / "episode-metrics.json", aggregate_episode_metrics)

    direct = score["metrics"]["DIRECT_LOOKUP"]
    review_all = score["metrics"]["REVIEW_ALL_REACHABILITY"]
    er = score["metrics"]["EVIDENCE_RECALL"]
    cmp_er = score["comparisons_vs_review_all"]["EVIDENCE_RECALL"]
    recall_bps = er["reconsideration_recall"]["basis_points"]
    reduction_bps = bps(cmp_er["reviewer_savings_vs_review_all"], review_all["total_review_load"])
    extra_misses = cmp_er["additional_missed_reopenings_vs_review_all"]
    recurring_count = aggregate_episode_metrics["episodes_with_positive_savings_and_zero_additional_misses"]
    conditions = {
        "minimum_reconsideration_recall": recall_bps >= MIN_RECALL_BPS,
        "minimum_review_load_reduction": reduction_bps >= MIN_REVIEW_REDUCTION_BPS,
        "maximum_additional_missed_reopenings": extra_misses <= MAX_ADDITIONAL_MISSED,
        "multi_episode_recurrence": recurring_count >= MIN_EPISODES_WITH_RECURRING_SAVINGS,
    }
    verdict = "PROMOTION" if all(conditions.values()) else "NO_PROMOTION"
    promotion_result = {
        "schema": "openline.evidence-recall-temporal-replication-promotion-result.v1",
        "promotion_policy_id": promotion_policy["promotion_policy_id"],
        "score_id": score["score_id"],
        "episode_metrics_id": aggregate_episode_metrics["episode_metrics_id"],
        "observed_reconsideration_recall_basis_points": recall_bps,
        "observed_review_load_reduction_vs_review_all_basis_points": reduction_bps,
        "observed_additional_missed_reopenings_vs_review_all": extra_misses,
        "observed_episodes_with_positive_savings_and_zero_additional_misses": recurring_count,
        "conditions": conditions,
        "failed_conditions": sorted(name for name, passed in conditions.items() if not passed),
        "verdict": verdict,
    }
    promotion_result["promotion_result_id"] = content_id("temporal-replication-promotion-result", promotion_result)
    write(output / "promotion-result.json", promotion_result)

    target_ledger = {
        "schema": "openline.temporal-selectivity-target-ledger.v1",
        "rows": sorted([
            {"episode_id": item["episode_id"], "target_node_id": item["target_node_id"], "gold": item["outcome"], "future_record_ids": item["future_record_ids"]}
            for item in gold["labels"]
        ], key=lambda x: (x["episode_id"], x["target_node_id"])),
        "unassessed_policy": "Silence, ambiguous audit language, and aggregate-only corpus counts remain outside scored gold.",
    }
    target_ledger["target_ledger_id"] = content_id("temporal-selectivity-target-ledger", target_ledger)
    write(output / "target-ledger.json", target_ledger)

    engine_hashes = {path: sha256_file(ROOT / path) for path in FROZEN_ENGINE_SHA256}
    custody = {
        "schema": "openline.temporal-selectivity-replication-custody.v1",
        "benchmark_id": BENCHMARK_ID,
        "build_sequence": ["freeze source-backed case list", "seal later records", "construct public pack", "freeze pre-trigger authority", "write promotion policy", "emit predictions", "open future records into gold", "score pooled and per episode", "apply unchanged promotion thresholds plus recurrence sufficiency"],
        "engine_sha256": engine_hashes,
        "engine_sha256_expected": FROZEN_ENGINE_SHA256,
        "engine_unchanged": engine_hashes == FROZEN_ENGINE_SHA256,
        "historical_reconstruction_limit": "The pack is reconstructed after outcomes are known. Mechanical timestamps and seals prevent explicit future records from entering the prediction artifact, but cannot prove psychological blindness of the constructor. Case-level inclusion/exclusion facts must themselves have existed by t0.",
        "corpus_selection_limit": "Three Sato trigger episodes are distinct retractions but share one later Avenell audit and one research-misconduct family; episode replication is not equivalent to independent-domain replication.",
    }
    write(output / "custody.json", custody)

    point = "Evidence Recall did save meaningful review work." if verdict == "PROMOTION" else "Evidence Recall did not save enough review work for promotion."
    because = f"It caught {er['true_reopen_reviews']}/{er['reopen_gold']} warranted reopenings while reviewing {er['total_review_load']} instead of {review_all['total_review_load']} items under Review-All Reachability."
    but = f"Savings recurred in {recurring_count}/{len(episode_metrics)} trigger episodes, and Evidence Recall missed {er['missed_reopenings']} warranted cases; three trigger episodes come from the same Sato/Avenell audit family."
    so = verdict
    card = f"POINT\n{point}\n\nBECAUSE\n{because}\n\nBUT\n{but}\n\nSO\n{so}\n"
    write(output / "POINT_BECAUSE_BUT_SO.md", card)

    status = "TEMPORAL_SELECTIVITY_REPLICATION_PROMOTED" if verdict == "PROMOTION" else "TEMPORAL_SELECTIVITY_REPLICATION_BELOW_PROMOTION_BAR"
    summary = {
        "valid": True,
        "status": status,
        "benchmark_id": BENCHMARK_ID,
        "episode_count": len(episodes),
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
        "evidence_recall_reviewer_savings_vs_review_all": cmp_er["reviewer_savings_vs_review_all"],
        "evidence_recall_review_load_reduction_basis_points": reduction_bps,
        "evidence_recall_reconsideration_recall_basis_points": recall_bps,
        "episodes_with_recurring_savings": recurring_count,
        "mean_episode_review_savings_basis_points": aggregate_episode_metrics["mean_episode_review_savings_basis_points"],
        "median_episode_review_savings_basis_points": aggregate_episode_metrics["median_episode_review_savings_basis_points"],
        "promotion_verdict": verdict,
        "engine_unchanged": custody["engine_unchanged"],
        "pack_id": pack["pack_id"],
        "authority_id": authority["authority_id"],
        "future_seal_id": seal["future_seal_id"],
        "predictions_id": predictions["predictions_id"],
        "gold_id": gold["gold_id"],
        "score_id": score["score_id"],
        "promotion_policy_id": promotion_policy["promotion_policy_id"],
        "promotion_result_id": promotion_result["promotion_result_id"],
    }
    write(output / "summary.json", summary)

    rows = "\n".join(
        f"| {item['episode_name']} | {item['evidence_recall_reopenings_caught']}/{item['reopen_gold']} | {item['review_all_review_load']} | {item['evidence_recall_review_load']} | {item['reviewer_savings']} | {item['reviewer_savings_basis_points']/100:.2f}% | {item['additional_missed_reopenings_vs_review_all']} |"
        for item in episode_metrics
    )
    report = f"""# Evidence Recall 0.5.2 — Temporal Selectivity Replication

Status: `{status}`

## Frozen question

Can the unchanged Evidence Recall engine repeatedly avoid waking reachable targets that later case-level records establish did not require reconsideration, while retaining near-Review-All recall?

## Corpus rule

Only explicit case-level reliance/reconsideration or affirmative non-reliance/scope exclusion is scored. Silence is UNASSESSED. Kataoka's aggregate 335/239 pathway is recorded but contributes zero scored rows because this build cannot reproduce its case-level inclusion/exclusion rows without inventing them. JAMA and VITALITY remain quantitative stress assets rather than negative-gold factories.

The scored corpus contains {len(episodes)} trigger episodes and {er['scored_cases']} targets: Shah/Darwish, expanded Narayan, and three separately triggered Sato retractions evaluated against the later Avenell manual audit.

## Pooled result

| System | Reopenings caught | Missed | Review load | Unnecessary reviews |
|---|---:|---:|---:|---:|
| Direct Lookup | {direct['true_reopen_reviews']}/{direct['reopen_gold']} | {direct['missed_reopenings']} | {direct['total_review_load']} | {direct['unnecessary_reviews']} |
| Review-All Reachability | {review_all['true_reopen_reviews']}/{review_all['reopen_gold']} | {review_all['missed_reopenings']} | {review_all['total_review_load']} | {review_all['unnecessary_reviews']} |
| Frozen Evidence Recall | {er['true_reopen_reviews']}/{er['reopen_gold']} | {er['missed_reopenings']} | {er['total_review_load']} | {er['unnecessary_reviews']} |

Evidence Recall reduces review load by {cmp_er['reviewer_savings_vs_review_all']} of {review_all['total_review_load']} items ({reduction_bps/100:.2f}%) while retaining {recall_bps/100:.2f}% reconsideration recall and adding {extra_misses} misses versus Review-All.

## Episode-level replication

| Episode | ER recall | Review-All load | ER load | Saved | Savings | Extra misses |
|---|---:|---:|---:|---:|---:|---:|
{rows}

Mean episode savings: {aggregate_episode_metrics['mean_episode_review_savings_basis_points']/100:.2f}%  
Median episode savings: {aggregate_episode_metrics['median_episode_review_savings_basis_points']/100:.2f}%  
Episodes with positive savings and zero additional misses: {recurring_count}/{len(episode_metrics)}

## Promotion rule and verdict

Predeclared pooled bar: >=95% recall, >=40% review-load reduction, zero additional misses. Replication sufficiency: positive savings with zero additional misses in at least {MIN_EPISODES_WITH_RECURRING_SAVINGS} trigger episodes.

**{verdict}**

This verdict promotes only the observed temporal-selectivity behavior under this frozen benchmark contract. It is not proof of commercial moat, broad-domain generality, or automated dependency discovery.

## Boundaries

- The engine files are byte-identical to 0.5.0.dev0 / 0.5.1.
- Historical construction occurred after outcomes were known; artifact separation cannot prove constructor psychology.
- Three of five trigger episodes belong to the same Sato research-misconduct family and are graded by the same later Avenell audit. That clustering limits claims of independence.
- Kataoka contributes no scored rows because aggregate counts are not case-level gold.
- No engine repair, weighted support, generalized revocation, hidden-edge discovery, UI, Frame Ledger expansion, Receipt Gate work, or Successor Gate work is included.
"""
    write(output / "REPORT.md", report)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Evidence Recall 0.5.2 temporal selectivity replication corpus")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(build(Path(args.output)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
