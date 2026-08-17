from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any


EXPECTED_SCHEMA = "openline.evidence-recall-temporal-published-diagnostic.v1"
EXPECTED_STATUS = "TEMPORAL_CORPUS_CANDIDATES_VERIFIED_CASE_LEVEL_HOLDOUT_NOT_YET_RUN"


def normalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        raise ValueError("floating point forbidden")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", str(key)): normalize(item) for key, item in value.items()}
    raise TypeError(type(value).__name__)


def canonical_json(value: Any) -> bytes:
    return json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_id(namespace: str, value: Any) -> str:
    return f"{namespace}:sha256:{hashlib.sha256(canonical_json(value)).hexdigest()}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently verify temporal published diagnostic")
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    body = dict(report)
    body.pop("diagnostic_id", None)
    checks = {
        "schema": report.get("schema") == EXPECTED_SCHEMA,
        "status": report.get("status") == EXPECTED_STATUS,
        "content_id": report.get("diagnostic_id") == content_id("evidence-recall-temporal-published-diagnostic", body),
        "kataoka_doi": report.get("candidate_corpora", {}).get("kataoka_2022", {}).get("doi") == "10.1016/j.jclinepi.2022.06.015",
        "kataoka_pre_retraction": report.get("candidate_corpora", {}).get("kataoka_2022", {}).get("published_facts", {}).get("published_before_retraction") == 335,
        "kataoka_evidence_synthesis": report.get("candidate_corpora", {}).get("kataoka_2022", {}).get("published_facts", {}).get("pre_retraction_articles_using_rct_in_evidence_synthesis") == 239,
        "jama_doi": report.get("candidate_corpora", {}).get("jama_2025", {}).get("doi") == "10.1001/jamainternmed.2025.0256",
        "jama_recomputed": report.get("candidate_corpora", {}).get("jama_2025", {}).get("published_facts", {}).get("meta_analyses_recomputed") == 166,
        "jama_significance_changed": report.get("candidate_corpora", {}).get("jama_2025", {}).get("published_facts", {}).get("statistical_significance_changed") == 18,
        "vitality_doi": report.get("candidate_corpora", {}).get("vitality_2025", {}).get("doi") == "10.1136/bmj-2024-082068",
        "vitality_reviews": report.get("candidate_corpora", {}).get("vitality_2025", {}).get("published_facts", {}).get("systematic_reviews_quantitatively_synthesizing_retracted_trials") == 847,
        "vitality_meta_analyses": report.get("candidate_corpora", {}).get("vitality_2025", {}).get("published_facts", {}).get("meta_analyses_replicated") == 3902,
        "no_temporal_win_claim": "empirical Evidence Recall temporal advantage" in report.get("not_present", []),
    }
    result = {
        "valid": all(checks.values()),
        "independent_of_candidate_module": True,
        "check_count": len(checks),
        "checks": checks,
    }
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
