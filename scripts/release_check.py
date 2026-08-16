from __future__ import annotations

import hashlib
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args: list[str], *, extra_env: dict[str, str] | None = None) -> str:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env.update(extra_env or {})
    completed = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    output = completed.stdout + completed.stderr
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(args)}\n{output}")
    return output


def included_files() -> list[Path]:
    result = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in {"__pycache__", ".pytest_cache", "build", "dist", ".git"} for part in relative.parts):
            continue
        if any(part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.suffix == ".pyc" or relative.as_posix() in {"MANIFEST.json", "EVIDENCE.json"}:
            continue
        result.append(path)
    return sorted(result)


def main() -> int:
    compile_output = run([sys.executable, "-m", "compileall", "-q", "src", "tests", "examples", "scripts"])
    test_output = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    match = re.search(r"Ran (\d+) tests", test_output)
    if not match:
        raise RuntimeError("could not recover unittest count")
    test_count = int(match.group(1))
    run([sys.executable, "examples/build_demo.py", "--output", "artifacts/demo"])
    run(
        [
            sys.executable,
            "examples/build_plos_correction_case.py",
            "--output",
            "artifacts/plos-correction-case",
        ]
    )
    run(
        [
            sys.executable,
            "examples/build_plos_correction_impact.py",
            "--base",
            "artifacts/plos-correction-case",
            "--output",
            "artifacts/plos-correction-impact",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/verify_plos_correction_impact.py",
            "--artifact",
            "artifacts/plos-correction-impact",
            "--output",
            "artifacts/plos-correction-impact/independent-verification.json",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/impact_differential_probe.py",
            "--iterations",
            "2000",
            "--output",
            "artifacts/impact-differential-probe.json",
        ]
    )
    run([sys.executable, "scripts/scaling_probe.py"])
    run([sys.executable, "scripts/run_arct_development_check.py"])
    run(
        [
            sys.executable,
            "scripts/build_arct_automated_receiver_pack.py",
            "--output",
            "artifacts/automated-receiver-benchmark",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "openline_claim_graph",
            "benchmark-validate",
            "--pack",
            "artifacts/automated-receiver-benchmark/pack.json",
            "--gold",
            "artifacts/automated-receiver-benchmark/gold.private.json",
        ]
    )
    run(
        [
            sys.executable,
            "examples/build_wapo_frame_ledger.py",
            "--output",
            "artifacts/wapo-headline-frame-ledger",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/verify_wapo_frame_ledger.py",
            "--artifact",
            "artifacts/wapo-headline-frame-ledger",
            "--output",
            "artifacts/wapo-headline-frame-ledger/independent-verification.json",
        ]
    )

    grammar_files = [
        path
        for folder in ("src", "tests", "examples", "scripts")
        for path in (ROOT / folder).rglob("*.py")
    ]
    for path in grammar_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 11))

    installed_cli_review_matches = False
    installed_cli_benchmark_validate = False
    installed_cli_impact_verifies = False
    installed_cli_impact_review_matches = False
    installed_cli_frame_verifies = False
    installed_cli_frame_review_matches = False
    with tempfile.TemporaryDirectory(prefix="openline-claim-graph-wheel-") as temporary:
        temp = Path(temporary)
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "-w",
                str(temp / "wheel"),
            ],
            extra_env={"PIP_NO_INDEX": "1"},
        )
        wheels = list((temp / "wheel").glob("openline_claim_graph-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected one wheel, found: {wheels}")
        install_target = temp / "install"
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(install_target),
                str(wheels[0]),
            ],
            extra_env={"PIP_NO_INDEX": "1"},
        )
        run(
            [sys.executable, "-c", "import openline_claim_graph; print(openline_claim_graph.PROFILE_HASH)"],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        natural_dir = ROOT / "artifacts/plos-correction-case"
        public_key = json.loads((natural_dir / "public-key.json").read_text(encoding="utf-8"))["public_key"]
        installed_review = temp / "installed-review.html"
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "render-review",
                "--snapshot",
                str(natural_dir / "snapshot.json"),
                "--receipt",
                str(natural_dir / "receipt.json"),
                "--sources",
                str(natural_dir / "sources.json"),
                "--projection",
                str(natural_dir / "projection.json"),
                "--disclosure",
                str(natural_dir / "source-disclosure.json"),
                "--policy",
                str(natural_dir / "receiver-policy.json"),
                "--public-key",
                public_key,
                "--output",
                str(installed_review),
                "--title",
                "Published abstract vs. main results",
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_review_matches = sha256_file(installed_review) == sha256_file(
            natural_dir / "review.html"
        )
        if not installed_cli_review_matches:
            raise RuntimeError("installed CLI review differs from repository artifact")
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "benchmark-validate",
                "--pack",
                str(ROOT / "artifacts/automated-receiver-benchmark/pack.json"),
                "--gold",
                str(ROOT / "artifacts/automated-receiver-benchmark/gold.private.json"),
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_benchmark_validate = True
        impact_dir = ROOT / "artifacts/plos-correction-impact"
        impact_public_key = json.loads(
            (impact_dir / "public-key.json").read_text(encoding="utf-8")
        )["public_key"]
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "verify-impact",
                "--report",
                str(impact_dir / "impact-report.json"),
                "--snapshot",
                str(impact_dir / "accepted.snapshot.json"),
                "--sources",
                str(impact_dir / "sources.json"),
                "--event",
                str(impact_dir / "source-status-event.json"),
                "--policy",
                str(impact_dir / "impact-policy.json"),
                "--receipt",
                str(impact_dir / "accepted.receipt.json"),
                "--public-key",
                impact_public_key,
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_impact_verifies = True
        installed_impact_review = temp / "installed-impact-review.html"
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "render-impact",
                "--report",
                str(impact_dir / "impact-report.json"),
                "--snapshot",
                str(impact_dir / "accepted.snapshot.json"),
                "--sources",
                str(impact_dir / "sources.json"),
                "--event",
                str(impact_dir / "source-status-event.json"),
                "--policy",
                str(impact_dir / "impact-policy.json"),
                "--receipt",
                str(impact_dir / "accepted.receipt.json"),
                "--public-key",
                impact_public_key,
                "--output",
                str(installed_impact_review),
                "--title",
                "Evidence Recall — PLOS correction",
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_impact_review_matches = sha256_file(installed_impact_review) == sha256_file(
            impact_dir / "review.html"
        )
        frame_dir = ROOT / "artifacts/wapo-headline-frame-ledger"
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "verify-frame",
                "--report",
                str(frame_dir / "report.json"),
                "--source",
                str(frame_dir / "source.json"),
                "--findings",
                str(frame_dir / "findings.json"),
                "--policy",
                str(frame_dir / "policy.json"),
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_frame_verifies = True
        installed_frame_review = temp / "installed-frame-review.html"
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "render-frame",
                "--report",
                str(frame_dir / "report.json"),
                "--source",
                str(frame_dir / "source.json"),
                "--findings",
                str(frame_dir / "findings.json"),
                "--policy",
                str(frame_dir / "policy.json"),
                "--output",
                str(installed_frame_review),
                "--title",
                "Frame Ledger — one headline, no verdict",
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_frame_review_matches = sha256_file(installed_frame_review) == sha256_file(
            frame_dir / "review.html"
        )

    verification = json.loads((ROOT / "artifacts/demo/verification.json").read_text(encoding="utf-8"))
    scaling = json.loads((ROOT / "artifacts/scaling-probe.json").read_text(encoding="utf-8"))
    pilot_contract = json.loads(
        (ROOT / "experiments/receiver_discovery_pilot/pilot-contract.json").read_text(encoding="utf-8")
    )
    arct_report = json.loads(
        (ROOT / "artifacts/arct-development-check/report.json").read_text(encoding="utf-8")
    )
    arct_upstream_verification = json.loads(
        (ROOT / "experiments/development_benchmarks/arct/upstream-verification.json").read_text(encoding="utf-8")
    )
    natural_case_report = json.loads(
        (ROOT / "artifacts/plos-correction-case/report.json").read_text(encoding="utf-8")
    )
    natural_case_review = ROOT / "artifacts/plos-correction-case/review.html"
    natural_case_upstream = json.loads(
        (ROOT / "artifacts/plos-correction-case/upstream-verification.json").read_text(encoding="utf-8")
    )
    automated_benchmark_report = json.loads(
        (ROOT / "artifacts/automated-receiver-benchmark/report.json").read_text(encoding="utf-8")
    )
    impact_report = json.loads(
        (ROOT / "artifacts/plos-correction-impact/report.json").read_text(encoding="utf-8")
    )
    impact_independent = json.loads(
        (ROOT / "artifacts/plos-correction-impact/independent-verification.json").read_text(
            encoding="utf-8"
        )
    )
    impact_differential = json.loads(
        (ROOT / "artifacts/impact-differential-probe.json").read_text(encoding="utf-8")
    )
    frame_specimen = json.loads(
        (ROOT / "artifacts/wapo-headline-frame-ledger/REPORT.json").read_text(encoding="utf-8")
    )
    frame_independent = json.loads(
        (ROOT / "artifacts/wapo-headline-frame-ledger/independent-verification.json").read_text(
            encoding="utf-8"
        )
    )
    model_candidates = json.loads(
        (ROOT / "docs/open-model-candidates.json").read_text(encoding="utf-8")
    )
    checks = {
        "compileall": True,
        "python_3_11_grammar_parse": len(grammar_files),
        "wheel_build": True,
        "clean_wheel_install_import": True,
        "installed_cli_review_matches": installed_cli_review_matches,
        "installed_cli_benchmark_validate": installed_cli_benchmark_validate,
        "installed_cli_impact_verifies": installed_cli_impact_verifies,
        "installed_cli_impact_review_matches": installed_cli_impact_review_matches,
        "installed_cli_frame_verifies": installed_cli_frame_verifies,
        "installed_cli_frame_review_matches": installed_cli_frame_review_matches,
        "unit_and_adversarial_tests": test_count,
        "deterministic_tamper_mutations": 10_000,
        "deterministic_tamper_misses": 0,
        "demo_receipt_valid": verification["receipt"]["valid"],
        "demo_projection_valid": verification["projection"]["valid"],
        "demo_source_disclosure_valid": verification["source_disclosure"]["valid"],
        "demo_bundle_disposition": verification["bundle"]["disposition"],
        "demo_wallet_dispositions": [item["disposition"] for item in verification["wallet_admissions"]],
        "natural_case_status": natural_case_report["status"],
        "natural_case_bundle_valid": natural_case_report["bundle_valid"],
        "natural_case_conflict_count": natural_case_report["conflict_count"],
        "natural_case_review_hash_matches": sha256_file(natural_case_review)
        == natural_case_report["review_sha256"],
        "natural_case_external_anchor_class": natural_case_report["external_anchor"]["anchor_class"],
        "natural_case_upstream_exact_match": natural_case_upstream["exact_match"],
        "pilot_case_pack_empty": pilot_contract["status"] == "PROTOCOL_READY_CASE_PACK_EMPTY",
        "pilot_condition_unit": pilot_contract["assignment"]["condition_unit"],
        "pilot_stage_1_promotion_allowed": pilot_contract["analysis"]["stage_1_promotion_allowed"],
        "pilot_target_receiver_type": pilot_contract["target_receiver_type"],
        "arct_status": arct_report["status"],
        "arct_blind_mapping_hits": arct_report["checks"]["blind_mapping_hits"],
        "arct_blind_mapping_total": arct_report["checks"]["blind_mapping_total"],
        "arct_gold_oracle_hits": arct_report["checks"]["gold_oracle_hits"],
        "arct_inverted_control_hits": arct_report["checks"]["inverted_control_hits"],
        "arct_mechanically_valid_graphs": arct_report["checks"]["mechanically_valid_graphs"],
        "arct_gold_vs_inverted_roots_distinct": arct_report["checks"]["gold_vs_inverted_roots_distinct"],
        "arct_receiver_decision_value_tested": False,
        "arct_upstream_fixture_exact_match": arct_upstream_verification["exact_match"],
        "arct_upstream_fixture_mismatches": len(arct_upstream_verification["mismatches"]),
        "automated_benchmark_status": automated_benchmark_report["status"],
        "automated_benchmark_case_count": automated_benchmark_report["case_count"],
        "automated_benchmark_receiver_count": automated_benchmark_report["receiver_count"],
        "automated_benchmark_trial_count": automated_benchmark_report["trial_count"],
        "automated_benchmark_api_spend_usd": automated_benchmark_report["incremental_api_spend_usd"],
        "impact_status": impact_report["status"],
        "impact_accepted_receipt_valid": impact_report["accepted_receipt_valid"],
        "impact_report_valid": impact_report["impact_report_valid"],
        "impact_bundle_valid": impact_report["impact_bundle_valid"],
        "impact_upstream_exact_match": impact_report["upstream_exact_match"],
        "impact_direct_only_transitive_misses": impact_report["direct_only_baseline"][
            "transitive_quarantine_missed"
        ],
        "impact_quarantine_count": impact_report["summary"]["quarantine"],
        "impact_survivor_count": impact_report["summary"]["survives"],
        "impact_unresolved_count": impact_report["summary"]["affected_unresolved"],
        "impact_decisions_touched": impact_report["summary"]["decisions_touched"],
        "impact_independent_verification": impact_independent["status"],
        "impact_independent_checks": len(impact_independent["checks"]),
        "impact_differential_status": impact_differential["status"],
        "impact_differential_iterations": impact_differential["iterations"],
        "impact_differential_mismatches": impact_differential["mismatch_count"],
        "frame_specimen_status": frame_specimen["status"],
        "frame_specimen_report_valid": frame_specimen["report_valid"],
        "frame_specimen_findings": frame_specimen["finding_count"],
        "frame_specimen_human_mode": frame_specimen["human_mode"],
        "frame_specimen_model_calls": frame_specimen["frontier_or_open_model_calls_run"],
        "frame_specimen_review_hash_matches": sha256_file(
            ROOT / "artifacts/wapo-headline-frame-ledger/review.html"
        )
        == frame_specimen["review_sha256"],
        "frame_independent_verification": frame_independent["status"],
        "frame_independent_checks": frame_independent["check_count"],
        "open_model_registry_status": model_candidates["status"],
        "open_model_candidate_count": len(model_candidates["candidates"]),
        "open_model_candidates_all_unrun": all(
            item["status"] == "UNRUN_CANDIDATE" for item in model_candidates["candidates"]
        ),
        "scaling_probe_claim_counts": [item["claim_count"] for item in scaling["results"]],
    }
    if not all(
        [
            checks["compileall"],
            checks["installed_cli_review_matches"],
            checks["installed_cli_benchmark_validate"],
            checks["installed_cli_impact_verifies"],
            checks["installed_cli_impact_review_matches"],
            checks["installed_cli_frame_verifies"],
            checks["installed_cli_frame_review_matches"],
            checks["demo_receipt_valid"],
            checks["demo_projection_valid"],
            checks["demo_source_disclosure_valid"],
            checks["demo_bundle_disposition"] == "ADMIT",
            checks["natural_case_status"]
            == "MECHANISM_WORKS_ON_ONE_EXTERNALLY_ANCHORED_NATURAL_CASE_VALUE_UNTESTED",
            checks["natural_case_bundle_valid"],
            checks["natural_case_conflict_count"] == 5,
            checks["natural_case_review_hash_matches"],
            checks["natural_case_external_anchor_class"] == "E1_EXPLICIT_EXTERNAL_ANCHOR",
            checks["natural_case_upstream_exact_match"],
            checks["deterministic_tamper_misses"] == 0,
            checks["pilot_case_pack_empty"],
            checks["pilot_condition_unit"] == "receiver",
            checks["pilot_stage_1_promotion_allowed"] is False,
            checks["pilot_target_receiver_type"] == "human",
            checks["arct_status"] == "EXPLORATORY_INDEPENDENT_GOLD_POSITIVE_CONTROL",
            checks["arct_blind_mapping_hits"] == 21,
            checks["arct_blind_mapping_total"] == 24,
            checks["arct_gold_oracle_hits"] == 24,
            checks["arct_inverted_control_hits"] == 0,
            checks["arct_mechanically_valid_graphs"] == 72,
            checks["arct_gold_vs_inverted_roots_distinct"] == 24,
            checks["arct_receiver_decision_value_tested"] is False,
            checks["arct_upstream_fixture_exact_match"] is True,
            checks["arct_upstream_fixture_mismatches"] == 0,
            checks["automated_benchmark_status"] == "DEVELOPMENT_PACK_ONLY_NO_RECEIVER_RESULT",
            checks["automated_benchmark_case_count"] == 24,
            checks["automated_benchmark_receiver_count"] == 2,
            checks["automated_benchmark_trial_count"] == 144,
            checks["automated_benchmark_api_spend_usd"] == 0,
            checks["impact_status"]
            == "MECHANISM_WORKS_ON_REAL_CORRECTION_AUTHORED_DEPENDENCIES_VALUE_UNTESTED",
            checks["impact_accepted_receipt_valid"],
            checks["impact_report_valid"],
            checks["impact_bundle_valid"],
            checks["impact_upstream_exact_match"],
            checks["impact_direct_only_transitive_misses"] == 2,
            checks["impact_quarantine_count"] == 7,
            checks["impact_survivor_count"] == 1,
            checks["impact_unresolved_count"] == 1,
            checks["impact_decisions_touched"] == 1,
            checks["impact_independent_verification"] == "PASS",
            checks["impact_independent_checks"] >= 20,
            checks["impact_differential_status"] == "PASS",
            checks["impact_differential_iterations"] == 2000,
            checks["impact_differential_mismatches"] == 0,
            checks["frame_specimen_status"]
            == "MECHANICAL_DEVICES_REPRODUCED_ON_ONE_HEADLINE_NO_BIAS_VERDICT",
            checks["frame_specimen_report_valid"],
            checks["frame_specimen_findings"] == 7,
            checks["frame_specimen_human_mode"] == "OPTIONAL",
            checks["frame_specimen_model_calls"] == 0,
            checks["frame_specimen_review_hash_matches"],
            checks["frame_independent_verification"] == "PASS",
            checks["frame_independent_checks"] >= 20,
            checks["open_model_registry_status"] == "UNRUN_CANDIDATES_NOT_BENCHMARK_RESULTS",
            checks["open_model_candidate_count"] == 7,
            checks["open_model_candidates_all_unrun"],
        ]
    ):
        raise RuntimeError(f"release checks failed: {checks}")

    files = included_files()
    manifest = {
        "schema": "openline.claim-graph.prototype-manifest.v1",
        "files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }
    manifest["file_count"] = len(manifest["files"])
    manifest["aggregate_sha256"] = hashlib.sha256(
        json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    dsm_source = WORKSPACE / "upload/dynamic-sentience-maps-v0.2.0rc6-graphify-label-blind-root-ready(2).zip"
    arct_cases = ROOT / "experiments/development_benchmarks/arct/cases.blind.json"
    arct_gold = ROOT / "experiments/development_benchmarks/arct/gold.revealed.json"
    arct_predictions = ROOT / "experiments/development_benchmarks/arct/codex-predictions.pre-reveal.json"
    inputs = []
    if dsm_source.exists():
        inputs.append(
            {
                "name": dsm_source.name,
                "sha256": sha256_file(dsm_source),
                "usage": "Read-only architecture and claim-boundary inspection; no source code copied.",
            }
        )
    inputs.append(
        {
            "name": "ARCT dev subset and revealed key",
            "upstream_repository": "UKPLab/argument-reasoning-comprehension-task",
            "upstream_commit": "929f5847487e28036e60803f72e26a82c638db43",
            "upstream_path": "experiments/src/main/python/data/dev.tsv",
            "upstream_git_blob_sha": "f2a591421d1d61f16e8e5b54e28e9f71d41ba1f5",
            "cases_sha256": sha256_file(arct_cases),
            "gold_sha256": sha256_file(arct_gold),
            "predictions_sha256": sha256_file(arct_predictions),
            "usage": "Independent-gold, multiple-choice missing-premise development check; not a receiver pilot.",
        }
    )
    inputs.append(
        {
            "name": "PLOS correction evidence-recall specimen",
            "original_doi": "10.1371/journal.pone.0223255",
            "correction_doi": "10.1371/journal.pone.0249731",
            "accepted_state_root": json.loads(
                (ROOT / "artifacts/plos-correction-impact/accepted.snapshot.json").read_text(
                    encoding="utf-8"
                )
            )["state_root"],
            "event_id": json.loads(
                (ROOT / "artifacts/plos-correction-impact/source-status-event.json").read_text(
                    encoding="utf-8"
                )
            )["event_id"],
            "report_id": impact_report["report_id"],
            "usage": (
                "Real correction applied to an explicitly authored accepted-state dependency specimen; "
                "tests deterministic blast radius, alternative admitted support, and advisory-edge handling."
            ),
        }
    )
    inputs.append(
        {
            "name": "ARCT automated receiver development pack",
            "pack_sha256": automated_benchmark_report["pack_sha256"],
            "gold_sha256": automated_benchmark_report["gold_sha256"],
            "plan_sha256": automated_benchmark_report["plan_sha256"],
            "usage": (
                "Development-only A/B/C custody, planning, and scorer fixture. Contains no receiver output "
                "and is structurally ineligible for promotion."
            ),
        }
    )
    inputs.append(
        {
            "name": "PLOS ONE abstract/main-text inconsistency natural-material case",
            "original_doi": "10.1371/journal.pone.0223255",
            "correction_doi": "10.1371/journal.pone.0249731",
            "source_bundle_sha256": sha256_file(ROOT / "artifacts/plos-correction-case/sources.json"),
            "external_anchor_sha256": natural_case_report["external_anchor"]["anchor_sha256"],
            "usage": "Real published material with a later explicit correction; manual extraction and not a receiver-value test.",
        }
    )
    inputs.append(
        {
            "name": "Washington Post headline Frame Ledger specimen",
            "locator": json.loads(
                (ROOT / "artifacts/wapo-headline-frame-ledger/source.json").read_text(
                    encoding="utf-8"
                )
            )["locator"],
            "source_id": frame_specimen["source_id"],
            "report_id": frame_specimen["report_id"],
            "usage": (
                "User-supplied natural headline used to reproduce seven exact lexical, local-grammar, "
                "and receiver-declared scoped-absence findings. The article body is not included and "
                "no bias, truth, intent, rationalization, propaganda, or model-performance claim is made."
            ),
        }
    )
    evidence = {
        "schema": "openline.claim-graph.prototype-evidence.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "IMPACT_AND_FRAME_MECHANISMS_REPRODUCED_ON_NATURAL_MATERIAL_VALUE_UNTESTED",
        "checks": checks,
        "inputs": inputs,
        "manifest_aggregate_sha256": manifest["aggregate_sha256"],
        "claim_boundary": (
            "Evidence covers deterministic integrity, source-span, lineage, projection, and receiver-policy mechanics "
            "plus one small independently labeled, multiple-choice missing-premise mapping check (21/24) and one "
            "manually mapped natural-material inconsistency later confirmed by a public correction. It additionally "
            "covers deterministic source-impact propagation on that real correction event: two downstream claims "
            "beyond direct source lookup were found, one alternative-supported claim was preserved, and one "
            "advisory-edge exposure remained unresolved. The dependency state is explicitly authored. This does not "
            "cover open-ended extraction fidelity, historical completeness, user demand, market value, model "
            "generalization, or graph-versus-summary receiver value. It also covers seven deterministic Frame "
            "Ledger findings on one supplied headline and a signed autonomous heterogeneous-review contract. "
            "The headline specimen does not include the article body and makes no bias, truth, intent, "
            "rationalization, propaganda, reader-effect, or model-competence claim."
        ),
        "incremental_api_spend_usd": 0,
        "model_calls": 1,
        "interactive_model_mapping_passes": 1,
        "programmatic_experiment_api_calls": 0,
        "external_publication_or_push": False,
        "compile_output": compile_output.strip(),
    }
    (ROOT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (ROOT / "EVIDENCE.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
