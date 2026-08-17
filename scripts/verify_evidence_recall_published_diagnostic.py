"""Independent stdlib-only verifier for the published aggregate diagnostic."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def content_id(namespace: str, value) -> str:
    return f"{namespace}:sha256:{hashlib.sha256(canonical_json(value)).hexdigest()}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    errors = []
    body = dict(report)
    diagnostic_id = body.pop("diagnostic_id", None)
    if report.get("schema") != "openline.evidence-recall-published-diagnostic.v1":
        errors.append("schema_invalid")
    if diagnostic_id != content_id("evidence-recall-published-diagnostic", body):
        errors.append("diagnostic_id_mismatch")
    if report.get("status") != "AGGREGATE_DIAGNOSTIC_ONLY_CASE_LEVEL_EMPIRICAL_PROMOTION_BLOCKED":
        errors.append("status_not_blocked")

    s = report.get("schneider", {})
    if s.get("accessible_second_generation") != 152 or s.get("externally_annotated_possible_diffusion") != 23:
        errors.append("schneider_published_counts_mismatch")
    if s.get("not_marked_possible_diffusion_or_unassessed") != 129:
        errors.append("schneider_remainder_mismatch")
    if s.get("second_generation_items_also_direct_in_full_161_network") != 4:
        errors.append("schneider_direct_overlap_mismatch")
    ss = s.get("systems", {})
    if ss.get("DIRECT_LOOKUP", {}).get("missed_exposure") != 23:
        errors.append("schneider_direct_fn_mismatch")
    if ss.get("NAIVE_TRANSITIVE_TAINT", {}).get("hard_false_quarantine_lower_bound") != 125:
        errors.append("schneider_naive_lower_bound_mismatch")
    if ss.get("EVIDENCE_RECALL", {}).get("unnecessary_unresolved_review_lower_bound") != 125:
        errors.append("schneider_er_review_lower_bound_mismatch")
    if ss.get("NAIVE_TRANSITIVE_TAINT", {}).get("total_review_load") != 152 or ss.get("EVIDENCE_RECALL", {}).get("total_review_load") != 152:
        errors.append("schneider_review_load_mismatch")

    v = report.get("van_der_vet", {})
    if v.get("indirect_candidates_manually_inspected") != 10 or v.get("indirect_propagation_found") != 0:
        errors.append("van_der_vet_counts_mismatch")
    if v.get("systems", {}).get("NAIVE_TRANSITIVE_TAINT", {}).get("hard_false_quarantine") != 10:
        errors.append("van_der_vet_naive_fp_mismatch")
    if v.get("systems", {}).get("EVIDENCE_RECALL", {}).get("unnecessary_unresolved_review") != 10:
        errors.append("van_der_vet_er_review_mismatch")

    j = report.get("jama", {})
    expected_jama = {
        "meta_analyses_rerun": 166,
        "significance_changed": 18,
        "no_change_pooled_effect": 21,
        "effect_evolution_cases": 163,
        "effect_change_ge_10_percent": 57,
        "effect_change_ge_30_percent": 31,
        "effect_change_ge_50_percent": 23,
        "reviews": 50,
        "reviews_with_potentially_meaningful_abstract_interpretation_change": 7,
    }
    for key, value in expected_jama.items():
        if j.get(key) != value:
            errors.append(f"jama_count_mismatch:{key}")

    result = {
        "valid": not errors,
        "errors": sorted(errors),
        "disposition": "ADMIT_AGGREGATE_DIAGNOSTIC" if not errors else "DENY_AGGREGATE_DIAGNOSTIC",
        "independent_of_candidate_module": True,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
