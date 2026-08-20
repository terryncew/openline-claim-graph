from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SOURCE_ZIP_SHA256 = "24820cfd4633fced028022ab8cff4e21c7665985322263c0a5f7f4a026070236"
EXPECTED_WHEEL_SHA256 = "cec858bd7a0b812368d70066118e0feccfbadac6aa5a3562baee315074f731c3"
SOURCE_ZIP = ROOT / "vendor" / "openline-claim-graph-v0.6.1.dev0-source.zip"
WHEEL = ROOT / "vendor" / "openline_claim_graph-0.6.1.dev0-py3-none-any.whl"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    checks = []
    def check(name: str, ok: bool, detail=None):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    check("source_zip_sha256", SOURCE_ZIP.exists() and sha(SOURCE_ZIP) == EXPECTED_SOURCE_ZIP_SHA256, sha(SOURCE_ZIP) if SOURCE_ZIP.exists() else "MISSING")
    check("wheel_sha256", WHEEL.exists() and sha(WHEEL) == EXPECTED_WHEEL_SHA256, sha(WHEEL) if WHEEL.exists() else "MISSING")

    if SOURCE_ZIP.exists():
        with zipfile.ZipFile(SOURCE_ZIP) as zf:
            names = set(zf.namelist())
            check("source_zip_root_ready", "pyproject.toml" in names and "src/openline_claim_graph/decision_recall.py" in names)
            pyproject = zf.read("pyproject.toml").decode("utf-8")
            check("source_version_0_6_1_dev0", 'version = "0.6.1.dev0"' in pyproject)
            designation = json.loads(zf.read("experiments/decision-recall-prospective-001/cohort-001/DESIGNATION.json"))
            check("source_cohort_generation_2", designation.get("generation") == 2, designation.get("generation"))
            check("source_cohort_zero_prior_eligible", designation.get("prior_generation_eligible_observations") == 0, designation.get("prior_generation_eligible_observations"))

    source_manifest = load(ROOT / "SOURCE_MANIFEST.json")
    source_ids = {x["source_id"] for x in source_manifest["sources"]}
    check("source_manifest_four_sources", len(source_ids) == 4, sorted(source_ids))
    pretrigger = {x["source_id"]: x for x in source_manifest["sources"] if x["kind"] == "PRE_TRIGGER_REPOSITORY_FILE"}
    check("security_scan_blob_pinned", pretrigger.get("litellm-security-scans-v1.82.6.dev1", {}).get("git_blob_sha1") == "801b700f64f11485307ae64b2b779fc37dce5bc3")
    check("publish_workflow_blob_pinned", pretrigger.get("litellm-pypi-publish-v1.82.6.dev1", {}).get("git_blob_sha1") == "e1830556819b0181680f70b79e7e87d13acc6b90")

    with tempfile.TemporaryDirectory(prefix="erc001-rebuild-") as td:
        proc = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "run_erc001.py"), "--output", td], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        check("rebuild_exit_zero", proc.returncode == 0, proc.stderr[-1000:])
        if proc.returncode == 0:
            for name in ["stream-seal.json", "event.json", "predictions.json", "adjudication-packet.json", "gold.json", "score.json", "RESULT.json"]:
                a = ROOT / "artifacts" / name
                b = Path(td) / name
                check(f"rebuild:{name}", a.read_bytes() == b.read_bytes())

    result = load(ROOT / "artifacts" / "RESULT.json")
    score = load(ROOT / "artifacts" / "score.json")
    predictions = load(ROOT / "artifacts" / "predictions.json")
    rows = {x["decision_id"]: x for x in predictions["rows"]}
    check("verdict_representation_gap_flat_parity", result.get("verdict") == "REPRESENTATION_GAP_FLAT_SEARCH_PARITY", result.get("verdict"))
    check("no_promotion", result.get("promotion_eligible") is False)
    check("zero_cohort_credit", result.get("cohort001_credit") is False)
    check("direct_ci_reopens", rows["ci-security-scan-trust"]["DECISION_RECALL"]["disposition"] == "REOPEN")
    check("credential_gap_survives_incorrectly", rows["pypi-publish-credential-standing"]["DECISION_RECALL"]["disposition"] == "SURVIVE")
    check("github_lineage_survives", rows["github-release-source-lineage"]["DECISION_RECALL"]["disposition"] == "SURVIVE")
    check("flat_and_recall_same_review_load", score["metrics"]["FLAT_LOG_SEARCH"]["review_load"] == score["metrics"]["DECISION_RECALL"]["review_load"] == 1)
    check("flat_and_recall_same_miss", score["metrics"]["FLAT_LOG_SEARCH"]["missed_reopenings"] == score["metrics"]["DECISION_RECALL"]["missed_reopenings"] == 1)
    check("full_history_no_triage_miss", score["metrics"]["FULL_HISTORY_REVIEW"]["missed_reopenings"] == 0)

    rejected = load(ROOT / "HINDSIGHT_EDGE_REJECTED.json")
    seal = load(ROOT / "artifacts" / "stream-seal.json")
    credential_manifest = next(x for x in seal["manifests"] if x["decision_id"] == "pypi-publish-credential-standing")
    dependency_ids = {x["basis_id"] for x in credential_manifest["basis"]}
    check("hindsight_trivy_edge_not_laundered", rejected["proposed_dependency"] not in dependency_ids, sorted(dependency_ids))

    failed = [x for x in checks if not x["pass"]]
    report = {
        "schema": "openline.erc001-verification.v1",
        "valid": not failed,
        "check_count": len(checks),
        "failed_count": len(failed),
        "checks": checks,
        "claim_boundary": "Verifier proves internal fixture reproducibility and vendored OpenLine custody. It does not live-fetch or independently authenticate the external web sources."
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
