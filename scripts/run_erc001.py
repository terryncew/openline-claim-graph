from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
WHEEL = ROOT / "vendor" / "openline_claim_graph-0.6.1.dev0-py3-none-any.whl"
sys.path.insert(0, str(WHEEL))

from openline_claim_graph.decision_recall import (  # noqa: E402
    SYSTEM_DECISION_RECALL,
    SYSTEM_FLAT_SEARCH,
    SYSTEM_FULL_HISTORY,
    create_adjudication_packet,
    create_gold,
    create_manifest,
    create_pre_trigger_record,
    create_revocation_event,
    create_stream_seal,
    run_predictions,
    score_predictions,
)


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def material_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest(*, decision_id: str, decision: str, basis_id: str, basis_statement: str, locator: str) -> dict:
    return create_manifest(
        decision_id=decision_id,
        accepted_at="2026-03-13T12:00:00Z",
        decision=decision,
        basis=[{
            "basis_id": basis_id,
            "kind": "OPERATIONAL_BASIS",
            "statement": basis_statement,
            "locator": locator,
            "role": "REQUIRED",
        }],
        required_dependencies=[basis_id],
        alternative_support=[],
        assumptions=[],
        invalidation_conditions=[{
            "condition_id": f"{basis_id}-loss",
            "dependency_id": basis_id,
            "event_types": ["LOSS_OF_STANDING"],
            "note": "Reopen the accepted state if its required basis loses standing.",
        }],
        resulting_artifact={"kind": "HISTORICAL_ACCEPTED_STATE_PROJECTION", "locator": locator},
        capture={
            "started_at": "2026-08-19T20:00:00Z",
            "confirmed_at": "2026-08-19T20:00:00Z",
            "human_capture_milliseconds": 0,
            "drafted_by": "erc001-reconstruction",
            "confirmed_by": "erc001-reconstruction",
            "correction_count": 0,
            "timing_source": "RETROSPECTIVE_NOT_MEASURED",
        },
        metadata={
            "evidence_credit": "RETROSPECTIVE_EXTERNAL_STRUCTURAL_ONLY",
            "natural_decision": False,
            "cohort001_credit": False,
            "dependency_admission": "PRE_TRIGGER_EXPLICIT_SURFACE_ONLY",
        },
    )


def build() -> dict[str, dict]:
    records = []
    manifests = []

    scan_text = (
        "At LiteLLM tag v1.82.6.dev1, ci_cd/security_scans.sh configures Aqua's apt repository "
        "and executes `sudo apt-get install trivy` without pinning a version."
    )
    scan_record = create_pre_trigger_record(
        decision_id="ci-security-scan-trust",
        decision="Continue treating the unpinned Trivy installation used by LiteLLM security scans as a trusted control.",
        available_at="2026-03-13T12:00:00Z",
        materials=[{
            "material_id": "litellm-security-scans-v1.82.6.dev1",
            "kind": "REPOSITORY_FILE",
            "locator": "BerriAI/litellm@v1.82.6.dev1:ci_cd/security_scans.sh#blob-801b700f64f11485307ae64b2b779fc37dce5bc3",
            "sha256": material_sha(scan_text),
            "text": scan_text,
        }],
    )
    records.append(scan_record)
    manifests.append(manifest(
        decision_id=scan_record["decision_id"],
        decision=scan_record["decision"],
        basis_id="trivy-distribution-latest",
        basis_statement="The unpinned Trivy package resolved from Aqua's distribution remains trustworthy.",
        locator=scan_record["materials"][0]["locator"],
    ))

    publish_text = (
        "At LiteLLM tag v1.82.6.dev1, .github/workflows/simple_pypi_publish.yml passes the repository "
        "secret PYPI_PUBLISH_PASSWORD to Twine as TWINE_PASSWORD and uploads dist/* to PyPI. The workflow itself does not mention Trivy."
    )
    publish_record = create_pre_trigger_record(
        decision_id="pypi-publish-credential-standing",
        decision="Continue treating the LiteLLM PyPI publishing credential as confidential and valid publication authority.",
        available_at="2026-03-13T12:00:00Z",
        materials=[{
            "material_id": "litellm-pypi-publish-v1.82.6.dev1",
            "kind": "REPOSITORY_FILE",
            "locator": "BerriAI/litellm@v1.82.6.dev1:.github/workflows/simple_pypi_publish.yml#blob-e1830556819b0181680f70b79e7e87d13acc6b90",
            "sha256": material_sha(publish_text),
            "text": publish_text,
        }],
    )
    records.append(publish_record)
    manifests.append(manifest(
        decision_id=publish_record["decision_id"],
        decision=publish_record["decision"],
        basis_id="pypi-publish-secret-confidentiality",
        basis_statement="The PyPI publishing secret remains confidential and under legitimate maintainer control.",
        locator=publish_record["materials"][0]["locator"],
    ))

    source_text = (
        "LiteLLM repository tag v1.82.6.dev1 is the source-controlled pre-trigger release snapshot used by ERC-001."
    )
    source_record = create_pre_trigger_record(
        decision_id="github-release-source-lineage",
        decision="Continue treating LiteLLM's source-controlled GitHub release lineage through v1.82.6.dev1 as legitimate.",
        available_at="2026-03-13T12:00:00Z",
        materials=[{
            "material_id": "litellm-source-tag-v1.82.6.dev1",
            "kind": "GIT_TAG",
            "locator": "BerriAI/litellm@v1.82.6.dev1",
            "sha256": material_sha(source_text),
            "text": source_text,
        }],
    )
    records.append(source_record)
    manifests.append(manifest(
        decision_id=source_record["decision_id"],
        decision=source_record["decision"],
        basis_id="github-release-source-lineage",
        basis_statement="The source-controlled GitHub release lineage remains legitimate.",
        locator=source_record["materials"][0]["locator"],
    ))

    ids = {r["decision_id"]: r["pre_trigger_record_id"] for r in records}
    eligible = [
        {
            "basis_id": "trivy-distribution-latest",
            "kind": "SUPPLY_CHAIN_DEPENDENCY",
            "locator": "BerriAI/litellm@v1.82.6.dev1:ci_cd/security_scans.sh",
            "mentioned_record_ids": [ids["ci-security-scan-trust"]],
        },
        {
            "basis_id": "pypi-publish-secret-confidentiality",
            "kind": "AUTHORITY_CREDENTIAL",
            "locator": "BerriAI/litellm@v1.82.6.dev1:.github/workflows/simple_pypi_publish.yml",
            "mentioned_record_ids": [ids["pypi-publish-credential-standing"]],
        },
        {
            "basis_id": "github-release-source-lineage",
            "kind": "SOURCE_LINEAGE",
            "locator": "BerriAI/litellm@v1.82.6.dev1",
            "mentioned_record_ids": [ids["github-release-source-lineage"]],
        },
    ]
    seal = create_stream_seal(
        benchmark_id="erc001-trivy-litellm-retrospective",
        sealed_at="2026-03-19T18:20:00Z",
        manifests=manifests,
        pre_trigger_records=records,
        eligible_bases=eligible,
        eligible_basis_catalog_custody={
            "built_at": "2026-03-19T18:19:00Z",
            "builder_id": "erc001-retrospective-record-only-builder",
            "method": "HISTORICAL_PRE_TRIGGER_SURFACE_RECONSTRUCTION",
            "source_scope": "PUBLIC_PRE_TRIGGER_RECORDS_ONLY",
            "manifest_visible": False,
        },
        protocol_id="erc001-v1",
    )
    event = create_revocation_event(
        stream_seal=seal,
        basis_id="trivy-distribution-latest",
        event_at="2026-03-20T12:00:00Z",
        reason="Trivy distribution/action integrity lost standing after the documented March 19 compromise.",
        locator="GHSA-69fq-xp46-6x23",
        stratum="NATURAL",
    )
    predictions = run_predictions(seal=seal, event=event)
    packet = create_adjudication_packet(seal=seal, event=event)
    gold = create_gold(
        adjudication_packet=packet,
        adjudicated_at="2026-03-25T00:00:00Z",
        adjudicator_id="erc001-post-trigger-primary-source-reconstruction",
        method="RETROSPECTIVE_PRIMARY_SOURCE_ADJUDICATION_NOT_BLIND",
        labels=[
            {
                "decision_id": "ci-security-scan-trust",
                "label": "REOPEN",
                "rationale": "Trivy's unpinned distribution path entered the compromised exposure window and LiteLLM later attributed its compromise to the Trivy security-scan dependency.",
            },
            {
                "decision_id": "pypi-publish-credential-standing",
                "label": "REOPEN",
                "rationale": "LiteLLM later reported a hijacked maintainer PyPI account and attributed the compromise to the Trivy security-scan dependency; the credential therefore warranted reopening even though the pre-trigger publishing workflow did not name Trivy.",
            },
            {
                "decision_id": "github-release-source-lineage",
                "label": "SURVIVE",
                "rationale": "LiteLLM reported that malicious versions 1.82.7 and 1.82.8 were uploaded directly to PyPI and were not released through the official GitHub CI/CD lineage.",
            },
        ],
    )
    score = score_predictions(seal=seal, event=event, predictions=predictions, gold=gold)

    metrics = score["metrics"]
    recall = metrics[SYSTEM_DECISION_RECALL]
    flat = metrics[SYSTEM_FLAT_SEARCH]
    full = metrics[SYSTEM_FULL_HISTORY]
    representation_gap = recall["missed_reopenings"] > 0
    flat_parity = (
        recall["missed_reopenings"] == flat["missed_reopenings"]
        and recall["review_load"] == flat["review_load"]
    )
    if representation_gap and flat_parity:
        verdict = "REPRESENTATION_GAP_FLAT_SEARCH_PARITY"
    elif representation_gap:
        verdict = "REPRESENTATION_GAP"
    elif flat_parity:
        verdict = "FLAT_SEARCH_ENOUGH"
    else:
        verdict = "SUPPORTED_SELECTIVITY"

    result = {
        "schema": "openline.erc001-result.v1",
        "case_id": "ERC-001",
        "title": "Trivy -> LiteLLM revocation propagation",
        "status": "RETROSPECTIVE_EXTERNAL_STRUCTURAL_ONLY",
        "verdict": verdict,
        "promotion_eligible": False,
        "cohort001_credit": False,
        "engine_version": "openline-claim-graph 0.6.1.dev0",
        "event_basis": event["basis_id"],
        "gold_reopenings": sum(1 for x in gold["labels"] if x["label"] == "REOPEN"),
        "systems": {
            SYSTEM_FULL_HISTORY: {
                "review_load": full["review_load"],
                "missed_reopenings": full["missed_reopenings"],
            },
            SYSTEM_FLAT_SEARCH: {
                "review_load": flat["review_load"],
                "missed_reopenings": flat["missed_reopenings"],
            },
            SYSTEM_DECISION_RECALL: {
                "review_load": recall["review_load"],
                "missed_reopenings": recall["missed_reopenings"],
                "exact_or_correct_triage": recall["exact_or_correct_triage"],
            },
        },
        "finding": (
            "Frozen Decision Recall reopens the directly represented Trivy-dependent CI state, but it does not reopen the PyPI publishing credential standing because the pre-trigger manifest contains no Trivy edge. Flat Search surfaces the same direct case and misses the same multi-hop credential consequence."
        ),
        "mechanism_candidate_not_admitted": (
            "A future mechanism would need to represent derived dependency/authority ancestry so loss of an upstream basis can invalidate an intermediate credential or authority without hindsight-invented direct edges. ERC-001 does not earn that mechanism."
        ),
        "falsifier": (
            "If a pre-trigger public record is found that explicitly binds the LiteLLM PyPI publishing credential's standing to the Trivy security-scan dependency, the current reconstruction is incomplete and ERC-001 must be rebuilt rather than patched in place."
        ),
        "claim_boundary": (
            "This case is retrospective and outcome-known. It tests representational fit only. No capture cost, natural failure frequency, annual ROI, product demand, or prospective safety claim is earned."
        ),
    }
    return {"seal": seal, "event": event, "predictions": predictions, "packet": packet, "gold": gold, "score": score, "result": result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "artifacts"))
    args = parser.parse_args()
    out = Path(args.output)
    built = build()
    write(out / "stream-seal.json", built["seal"])
    write(out / "event.json", built["event"])
    write(out / "predictions.json", built["predictions"])
    write(out / "adjudication-packet.json", built["packet"])
    write(out / "gold.json", built["gold"])
    write(out / "score.json", built["score"])
    write(out / "RESULT.json", built["result"])
    print(json.dumps(built["result"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
