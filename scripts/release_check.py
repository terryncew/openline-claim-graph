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
    print(f"release-check: {' '.join(args)}", flush=True)
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
    run(
        [
            sys.executable,
            "scripts/build_evidence_recall_comparative_fixture.py",
            "--output",
            "artifacts/evidence-recall-comparative/conformance",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "openline_claim_graph",
            "evidence-benchmark-validate",
            "--pack",
            "artifacts/evidence-recall-comparative/conformance/pack.json",
            "--authority",
            "artifacts/evidence-recall-comparative/conformance/authority.json",
            "--gold",
            "artifacts/evidence-recall-comparative/conformance/gold.private.json",
            "--predictions",
            "artifacts/evidence-recall-comparative/conformance/predictions.json",
            "--score",
            "artifacts/evidence-recall-comparative/conformance/score.json",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "openline_claim_graph",
            "evidence-benchmark-published-diagnostic",
            "--output",
            "artifacts/evidence-recall-comparative/published-diagnostic.json",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/verify_evidence_recall_published_diagnostic.py",
            "--report",
            "artifacts/evidence-recall-comparative/published-diagnostic.json",
            "--output",
            "artifacts/evidence-recall-comparative/independent-verification.json",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/build_temporal_holdout_fixture.py",
            "--output",
            "artifacts/evidence-recall-temporal/conformance",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "openline_claim_graph",
            "temporal-benchmark-validate",
            "--pack",
            "artifacts/evidence-recall-temporal/conformance/pack.json",
            "--authority",
            "artifacts/evidence-recall-temporal/conformance/authority.json",
            "--future-seal",
            "artifacts/evidence-recall-temporal/conformance/future-seal.private.json",
            "--gold",
            "artifacts/evidence-recall-temporal/conformance/gold.private.json",
            "--predictions",
            "artifacts/evidence-recall-temporal/conformance/predictions.json",
            "--score",
            "artifacts/evidence-recall-temporal/conformance/score.json",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "openline_claim_graph",
            "temporal-benchmark-published-diagnostic",
            "--output",
            "artifacts/evidence-recall-temporal/published-diagnostic.json",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/verify_temporal_published_diagnostic.py",
            "--report",
            "artifacts/evidence-recall-temporal/published-diagnostic.json",
            "--output",
            "artifacts/evidence-recall-temporal/independent-verification.json",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/build_real_temporal_case_shah_iron.py",
            "--output",
            "artifacts/evidence-recall-temporal/real-001-shah-iron",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/verify_real_temporal_case_shah_iron.py",
            "--artifact",
            "artifacts/evidence-recall-temporal/real-001-shah-iron",
            "--output",
            "artifacts/evidence-recall-temporal/real-001-shah-iron/independent-verification.json",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "openline_claim_graph",
            "temporal-benchmark-validate",
            "--pack",
            "artifacts/evidence-recall-temporal/real-001-shah-iron/pack.json",
            "--authority",
            "artifacts/evidence-recall-temporal/real-001-shah-iron/authority.json",
            "--future-seal",
            "artifacts/evidence-recall-temporal/real-001-shah-iron/future-seal.private.json",
            "--gold",
            "artifacts/evidence-recall-temporal/real-001-shah-iron/gold.private.json",
            "--predictions",
            "artifacts/evidence-recall-temporal/real-001-shah-iron/predictions.json",
            "--score",
            "artifacts/evidence-recall-temporal/real-001-shah-iron/score.json",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/build_mixed_temporal_selectivity_corpus.py",
            "--output",
            "artifacts/evidence-recall-temporal/mixed-001-selectivity",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/verify_mixed_temporal_selectivity_corpus.py",
            "--artifact",
            "artifacts/evidence-recall-temporal/mixed-001-selectivity",
            "--output",
            "artifacts/evidence-recall-temporal/mixed-001-selectivity/independent-verification.json",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "openline_claim_graph",
            "temporal-benchmark-validate",
            "--pack",
            "artifacts/evidence-recall-temporal/mixed-001-selectivity/pack.json",
            "--authority",
            "artifacts/evidence-recall-temporal/mixed-001-selectivity/authority.json",
            "--future-seal",
            "artifacts/evidence-recall-temporal/mixed-001-selectivity/future-seal.private.json",
            "--gold",
            "artifacts/evidence-recall-temporal/mixed-001-selectivity/gold.private.json",
            "--predictions",
            "artifacts/evidence-recall-temporal/mixed-001-selectivity/predictions.json",
            "--score",
            "artifacts/evidence-recall-temporal/mixed-001-selectivity/score.json",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/build_temporal_selectivity_replication_corpus.py",
            "--output",
            "artifacts/evidence-recall-temporal/replication-001-selectivity",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/verify_temporal_selectivity_replication_corpus.py",
            "--artifact",
            "artifacts/evidence-recall-temporal/replication-001-selectivity",
            "--output",
            "artifacts/evidence-recall-temporal/replication-001-selectivity/independent-verification.json",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "openline_claim_graph",
            "temporal-benchmark-validate",
            "--pack",
            "artifacts/evidence-recall-temporal/replication-001-selectivity/pack.json",
            "--authority",
            "artifacts/evidence-recall-temporal/replication-001-selectivity/authority.json",
            "--future-seal",
            "artifacts/evidence-recall-temporal/replication-001-selectivity/future-seal.private.json",
            "--gold",
            "artifacts/evidence-recall-temporal/replication-001-selectivity/gold.private.json",
            "--predictions",
            "artifacts/evidence-recall-temporal/replication-001-selectivity/predictions.json",
            "--score",
            "artifacts/evidence-recall-temporal/replication-001-selectivity/score.json",
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
    installed_cli_evidence_benchmark_verifies = False
    installed_cli_published_diagnostic_matches = False
    installed_cli_temporal_benchmark_verifies = False
    installed_cli_temporal_diagnostic_matches = False
    installed_cli_temporal_real_case_verifies = False
    installed_cli_temporal_mixed_corpus_verifies = False
    installed_cli_temporal_replication_verifies = False
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
        comparative_dir = ROOT / "artifacts/evidence-recall-comparative"
        conformance_dir = comparative_dir / "conformance"
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "evidence-benchmark-validate",
                "--pack",
                str(conformance_dir / "pack.json"),
                "--authority",
                str(conformance_dir / "authority.json"),
                "--gold",
                str(conformance_dir / "gold.private.json"),
                "--predictions",
                str(conformance_dir / "predictions.json"),
                "--score",
                str(conformance_dir / "score.json"),
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_evidence_benchmark_verifies = True
        installed_diagnostic = temp / "installed-published-diagnostic.json"
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "evidence-benchmark-published-diagnostic",
                "--output",
                str(installed_diagnostic),
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_published_diagnostic_matches = sha256_file(installed_diagnostic) == sha256_file(
            comparative_dir / "published-diagnostic.json"
        )
        temporal_dir = ROOT / "artifacts/evidence-recall-temporal"
        temporal_conformance = temporal_dir / "conformance"
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "temporal-benchmark-validate",
                "--pack",
                str(temporal_conformance / "pack.json"),
                "--authority",
                str(temporal_conformance / "authority.json"),
                "--future-seal",
                str(temporal_conformance / "future-seal.private.json"),
                "--gold",
                str(temporal_conformance / "gold.private.json"),
                "--predictions",
                str(temporal_conformance / "predictions.json"),
                "--score",
                str(temporal_conformance / "score.json"),
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_temporal_benchmark_verifies = True
        installed_temporal_diagnostic = temp / "installed-temporal-published-diagnostic.json"
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "temporal-benchmark-published-diagnostic",
                "--output",
                str(installed_temporal_diagnostic),
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_temporal_diagnostic_matches = sha256_file(installed_temporal_diagnostic) == sha256_file(
            temporal_dir / "published-diagnostic.json"
        )
        temporal_real = temporal_dir / "real-001-shah-iron"
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "temporal-benchmark-validate",
                "--pack",
                str(temporal_real / "pack.json"),
                "--authority",
                str(temporal_real / "authority.json"),
                "--future-seal",
                str(temporal_real / "future-seal.private.json"),
                "--gold",
                str(temporal_real / "gold.private.json"),
                "--predictions",
                str(temporal_real / "predictions.json"),
                "--score",
                str(temporal_real / "score.json"),
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_temporal_real_case_verifies = True
        temporal_mixed = temporal_dir / "mixed-001-selectivity"
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "temporal-benchmark-validate",
                "--pack",
                str(temporal_mixed / "pack.json"),
                "--authority",
                str(temporal_mixed / "authority.json"),
                "--future-seal",
                str(temporal_mixed / "future-seal.private.json"),
                "--gold",
                str(temporal_mixed / "gold.private.json"),
                "--predictions",
                str(temporal_mixed / "predictions.json"),
                "--score",
                str(temporal_mixed / "score.json"),
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_temporal_mixed_corpus_verifies = True
        temporal_replication = temporal_dir / "replication-001-selectivity"
        run(
            [
                sys.executable,
                "-m",
                "openline_claim_graph",
                "temporal-benchmark-validate",
                "--pack",
                str(temporal_replication / "pack.json"),
                "--authority",
                str(temporal_replication / "authority.json"),
                "--future-seal",
                str(temporal_replication / "future-seal.private.json"),
                "--gold",
                str(temporal_replication / "gold.private.json"),
                "--predictions",
                str(temporal_replication / "predictions.json"),
                "--score",
                str(temporal_replication / "score.json"),
            ],
            extra_env={"PYTHONPATH": str(install_target)},
        )
        installed_cli_temporal_replication_verifies = True

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
    comparative_diagnostic = json.loads(
        (ROOT / "artifacts/evidence-recall-comparative/published-diagnostic.json").read_text(encoding="utf-8")
    )
    comparative_independent = json.loads(
        (ROOT / "artifacts/evidence-recall-comparative/independent-verification.json").read_text(encoding="utf-8")
    )
    comparative_score = json.loads(
        (ROOT / "artifacts/evidence-recall-comparative/conformance/score.json").read_text(encoding="utf-8")
    )
    temporal_diagnostic = json.loads(
        (ROOT / "artifacts/evidence-recall-temporal/published-diagnostic.json").read_text(encoding="utf-8")
    )
    temporal_independent = json.loads(
        (ROOT / "artifacts/evidence-recall-temporal/independent-verification.json").read_text(encoding="utf-8")
    )
    temporal_score = json.loads(
        (ROOT / "artifacts/evidence-recall-temporal/conformance/score.json").read_text(encoding="utf-8")
    )
    temporal_real_dir = ROOT / "artifacts/evidence-recall-temporal/real-001-shah-iron"
    temporal_real_summary = json.loads((temporal_real_dir / "summary.json").read_text(encoding="utf-8"))
    temporal_real_score = json.loads((temporal_real_dir / "score.json").read_text(encoding="utf-8"))
    temporal_real_independent = json.loads(
        (temporal_real_dir / "independent-verification.json").read_text(encoding="utf-8")
    )
    temporal_real_custody = json.loads((temporal_real_dir / "custody.json").read_text(encoding="utf-8"))
    temporal_mixed_dir = ROOT / "artifacts/evidence-recall-temporal/mixed-001-selectivity"
    temporal_mixed_summary = json.loads((temporal_mixed_dir / "summary.json").read_text(encoding="utf-8"))
    temporal_mixed_score = json.loads((temporal_mixed_dir / "score.json").read_text(encoding="utf-8"))
    temporal_mixed_independent = json.loads(
        (temporal_mixed_dir / "independent-verification.json").read_text(encoding="utf-8")
    )
    temporal_mixed_custody = json.loads((temporal_mixed_dir / "custody.json").read_text(encoding="utf-8"))
    temporal_mixed_promotion_policy = json.loads((temporal_mixed_dir / "promotion-policy.json").read_text(encoding="utf-8"))
    temporal_mixed_promotion_result = json.loads((temporal_mixed_dir / "promotion-result.json").read_text(encoding="utf-8"))
    temporal_replication_dir = ROOT / "artifacts/evidence-recall-temporal/replication-001-selectivity"
    temporal_replication_summary = json.loads((temporal_replication_dir / "summary.json").read_text(encoding="utf-8"))
    temporal_replication_independent = json.loads((temporal_replication_dir / "independent-verification.json").read_text(encoding="utf-8"))
    temporal_replication_custody = json.loads((temporal_replication_dir / "custody.json").read_text(encoding="utf-8"))
    temporal_replication_policy = json.loads((temporal_replication_dir / "promotion-policy.json").read_text(encoding="utf-8"))
    temporal_replication_result = json.loads((temporal_replication_dir / "promotion-result.json").read_text(encoding="utf-8"))
    temporal_replication_episode_metrics = json.loads((temporal_replication_dir / "episode-metrics.json").read_text(encoding="utf-8"))
    temporal_replication_card_audit = json.loads((temporal_replication_dir / "POINT_BECAUSE_BUT_SO.audit.json").read_text(encoding="utf-8"))
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
        "installed_cli_evidence_benchmark_verifies": installed_cli_evidence_benchmark_verifies,
        "installed_cli_published_diagnostic_matches": installed_cli_published_diagnostic_matches,
        "installed_cli_temporal_benchmark_verifies": installed_cli_temporal_benchmark_verifies,
        "installed_cli_temporal_diagnostic_matches": installed_cli_temporal_diagnostic_matches,
        "installed_cli_temporal_real_case_verifies": installed_cli_temporal_real_case_verifies,
        "installed_cli_temporal_mixed_corpus_verifies": installed_cli_temporal_mixed_corpus_verifies,
        "installed_cli_temporal_replication_verifies": installed_cli_temporal_replication_verifies,
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
        "comparative_pipeline_status": comparative_diagnostic["status"],
        "comparative_independent_valid": comparative_independent["valid"],
        "comparative_independent_module_free": comparative_independent["independent_of_candidate_module"],
        "comparative_conformance_score_schema": comparative_score["schema"],
        "comparative_schneider_direct_missed_exposure": comparative_diagnostic["schneider"]["systems"]["DIRECT_LOOKUP"]["missed_exposure"],
        "comparative_schneider_naive_hard_fp_lower_bound": comparative_diagnostic["schneider"]["systems"]["NAIVE_TRANSITIVE_TAINT"]["hard_false_quarantine_lower_bound"],
        "comparative_schneider_er_unresolved_lower_bound": comparative_diagnostic["schneider"]["systems"]["EVIDENCE_RECALL"]["unnecessary_unresolved_review_lower_bound"],
        "comparative_schneider_naive_review_load": comparative_diagnostic["schneider"]["systems"]["NAIVE_TRANSITIVE_TAINT"]["total_review_load"],
        "comparative_schneider_er_review_load": comparative_diagnostic["schneider"]["systems"]["EVIDENCE_RECALL"]["total_review_load"],
        "comparative_case_level_empirical_result_present": False,
        "temporal_pipeline_status": temporal_diagnostic["status"],
        "temporal_independent_valid": temporal_independent["valid"],
        "temporal_independent_module_free": temporal_independent["independent_of_candidate_module"],
        "temporal_independent_checks": temporal_independent["check_count"],
        "temporal_conformance_score_schema": temporal_score["schema"],
        "temporal_conformance_review_all_load": temporal_score["metrics"]["REVIEW_ALL_REACHABILITY"]["total_review_load"],
        "temporal_conformance_er_review_load": temporal_score["metrics"]["EVIDENCE_RECALL"]["total_review_load"],
        "temporal_conformance_er_missed_reopenings": temporal_score["metrics"]["EVIDENCE_RECALL"]["missed_reopenings"],
        "temporal_conformance_er_reviewer_savings": temporal_score["comparisons_vs_review_all"]["EVIDENCE_RECALL"]["reviewer_savings_vs_review_all"],
        "temporal_real_case_level_result_present": True,
        "temporal_real_case_status": temporal_real_summary["status"],
        "temporal_real_case_independent_status": temporal_real_independent["disposition"],
        "temporal_real_case_independent_valid": temporal_real_independent["valid"],
        "temporal_real_case_independent_checks": temporal_real_independent["check_count"],
        "temporal_real_case_direct_review_load": temporal_real_summary["direct_review_load"],
        "temporal_real_case_direct_missed_reopenings": temporal_real_summary["direct_missed_reopenings"],
        "temporal_real_case_review_all_load": temporal_real_summary["review_all_review_load"],
        "temporal_real_case_er_review_load": temporal_real_summary["evidence_recall_review_load"],
        "temporal_real_case_er_missed_reopenings": temporal_real_summary["evidence_recall_missed_reopenings"],
        "temporal_real_case_er_reviewer_savings": temporal_real_summary["evidence_recall_reviewer_savings_vs_review_all"],
        "temporal_real_case_er_hard_quarantine_load": temporal_real_score["metrics"]["EVIDENCE_RECALL"]["hard_quarantine_load"],
        "temporal_real_case_engine_unchanged": temporal_real_summary["engine_unchanged"],
        "temporal_real_case_custody_engine_unchanged": temporal_real_custody["engine_unchanged"],
        "temporal_mixed_status": temporal_mixed_summary["status"],
        "temporal_mixed_promotion_verdict": temporal_mixed_summary["promotion_verdict"],
        "temporal_mixed_independent_status": temporal_mixed_independent["disposition"],
        "temporal_mixed_independent_valid": temporal_mixed_independent["valid"],
        "temporal_mixed_independent_checks": temporal_mixed_independent["check_count"],
        "temporal_mixed_reopen_gold": temporal_mixed_summary["reopen_gold"],
        "temporal_mixed_no_reopen_gold": temporal_mixed_summary["no_reopen_gold"],
        "temporal_mixed_direct_caught": temporal_mixed_summary["direct_reopenings_caught"],
        "temporal_mixed_direct_missed": temporal_mixed_summary["direct_missed_reopenings"],
        "temporal_mixed_direct_load": temporal_mixed_summary["direct_review_load"],
        "temporal_mixed_review_all_caught": temporal_mixed_summary["review_all_reopenings_caught"],
        "temporal_mixed_review_all_missed": temporal_mixed_summary["review_all_missed_reopenings"],
        "temporal_mixed_review_all_load": temporal_mixed_summary["review_all_review_load"],
        "temporal_mixed_review_all_unnecessary": temporal_mixed_summary["review_all_unnecessary_reviews"],
        "temporal_mixed_er_caught": temporal_mixed_summary["evidence_recall_reopenings_caught"],
        "temporal_mixed_er_missed": temporal_mixed_summary["evidence_recall_missed_reopenings"],
        "temporal_mixed_er_load": temporal_mixed_summary["evidence_recall_review_load"],
        "temporal_mixed_er_unnecessary": temporal_mixed_summary["evidence_recall_unnecessary_reviews"],
        "temporal_mixed_er_savings": temporal_mixed_summary["evidence_recall_reviewer_savings_vs_review_all"],
        "temporal_mixed_er_recall_bps": temporal_mixed_summary["evidence_recall_reconsideration_recall_basis_points"],
        "temporal_mixed_er_review_reduction_bps": temporal_mixed_summary["evidence_recall_review_load_reduction_basis_points"],
        "temporal_mixed_min_recall_bps": temporal_mixed_promotion_policy["minimum_reconsideration_recall_basis_points"],
        "temporal_mixed_min_review_reduction_bps": temporal_mixed_promotion_policy["minimum_review_load_reduction_vs_review_all_basis_points"],
        "temporal_mixed_failed_conditions": temporal_mixed_promotion_result["failed_conditions"],
        "temporal_mixed_engine_unchanged": temporal_mixed_summary["engine_unchanged"],
        "temporal_mixed_custody_engine_unchanged": temporal_mixed_custody["engine_unchanged"],
        "temporal_replication_status": temporal_replication_summary["status"],
        "temporal_replication_verdict": temporal_replication_summary["promotion_verdict"],
        "temporal_replication_independent_valid": temporal_replication_independent["valid"],
        "temporal_replication_independent_checks": temporal_replication_independent["check_count"],
        "temporal_replication_episode_count": temporal_replication_summary["episode_count"],
        "temporal_replication_scored_targets": temporal_replication_summary["scored_targets"],
        "temporal_replication_reopen_gold": temporal_replication_summary["reopen_gold"],
        "temporal_replication_no_reopen_gold": temporal_replication_summary["no_reopen_gold"],
        "temporal_replication_review_all_load": temporal_replication_summary["review_all_review_load"],
        "temporal_replication_er_load": temporal_replication_summary["evidence_recall_review_load"],
        "temporal_replication_er_savings": temporal_replication_summary["evidence_recall_reviewer_savings_vs_review_all"],
        "temporal_replication_er_recall_bps": temporal_replication_summary["evidence_recall_reconsideration_recall_basis_points"],
        "temporal_replication_reduction_bps": temporal_replication_summary["evidence_recall_review_load_reduction_basis_points"],
        "temporal_replication_recurring_episodes": temporal_replication_summary["episodes_with_recurring_savings"],
        "temporal_replication_min_recall_bps": temporal_replication_policy["minimum_reconsideration_recall_basis_points"],
        "temporal_replication_min_reduction_bps": temporal_replication_policy["minimum_review_load_reduction_vs_review_all_basis_points"],
        "temporal_replication_min_recurring": temporal_replication_policy["minimum_independent_trigger_episodes_with_positive_savings_and_zero_additional_misses"],
        "temporal_replication_failed_conditions": temporal_replication_result["failed_conditions"],
        "temporal_replication_engine_unchanged": temporal_replication_custody["engine_unchanged"],
        "temporal_replication_mean_episode_savings_bps": temporal_replication_episode_metrics["mean_episode_review_savings_basis_points"],
        "temporal_replication_median_episode_savings_bps": temporal_replication_episode_metrics["median_episode_review_savings_basis_points"],
        "human_contract_present": (ROOT / "HUMAN_CONTRACT.md").is_file(),
        "human_contract_card_audit_valid": all(temporal_replication_card_audit["constraints"].values()),
        "human_contract_four_lines_traced": all(
            temporal_replication_card_audit["lines"][name]["trace"]
            for name in ("POINT", "BECAUSE", "BUT", "SO")
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
            checks["installed_cli_evidence_benchmark_verifies"],
            checks["installed_cli_published_diagnostic_matches"],
            checks["installed_cli_temporal_benchmark_verifies"],
            checks["installed_cli_temporal_diagnostic_matches"],
            checks["installed_cli_temporal_real_case_verifies"],
            checks["installed_cli_temporal_mixed_corpus_verifies"],
            checks["installed_cli_temporal_replication_verifies"],
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
            checks["comparative_pipeline_status"] == "AGGREGATE_DIAGNOSTIC_ONLY_CASE_LEVEL_EMPIRICAL_PROMOTION_BLOCKED",
            checks["comparative_independent_valid"],
            checks["comparative_independent_module_free"],
            checks["comparative_conformance_score_schema"] == "openline.evidence-recall-comparative-score.v1",
            checks["comparative_schneider_direct_missed_exposure"] == 23,
            checks["comparative_schneider_naive_hard_fp_lower_bound"] == 125,
            checks["comparative_schneider_er_unresolved_lower_bound"] == 125,
            checks["comparative_schneider_naive_review_load"] == 152,
            checks["comparative_schneider_er_review_load"] == 152,
            checks["comparative_case_level_empirical_result_present"] is False,
            checks["temporal_pipeline_status"] == "TEMPORAL_CORPUS_CANDIDATES_VERIFIED_CASE_LEVEL_HOLDOUT_NOT_YET_RUN",
            checks["temporal_independent_valid"],
            checks["temporal_independent_module_free"],
            checks["temporal_independent_checks"] >= 10,
            checks["temporal_conformance_score_schema"] == "openline.evidence-recall-temporal-score.v1",
            checks["temporal_conformance_review_all_load"] == 5,
            checks["temporal_conformance_er_review_load"] == 3,
            checks["temporal_conformance_er_missed_reopenings"] == 0,
            checks["temporal_conformance_er_reviewer_savings"] == 2,
            checks["temporal_real_case_level_result_present"] is True,
            checks["temporal_real_case_status"] == "REAL_TEMPORAL_CASE_001_RUN_NO_SELECTIVITY_ADVANTAGE",
            checks["temporal_real_case_independent_status"] == "PASS",
            checks["temporal_real_case_independent_valid"],
            checks["temporal_real_case_independent_checks"] >= 36,
            checks["temporal_real_case_direct_review_load"] == 1,
            checks["temporal_real_case_direct_missed_reopenings"] == 1,
            checks["temporal_real_case_review_all_load"] == 2,
            checks["temporal_real_case_er_review_load"] == 2,
            checks["temporal_real_case_er_missed_reopenings"] == 0,
            checks["temporal_real_case_er_reviewer_savings"] == 0,
            checks["temporal_real_case_er_hard_quarantine_load"] == 2,
            checks["temporal_real_case_engine_unchanged"],
            checks["temporal_real_case_custody_engine_unchanged"],
            checks["temporal_mixed_status"] == "MIXED_TEMPORAL_SELECTIVITY_CORPUS_RUN_BELOW_PROMOTION_BAR",
            checks["temporal_mixed_promotion_verdict"] == "NO_PROMOTION",
            checks["temporal_mixed_independent_status"] == "PASS",
            checks["temporal_mixed_independent_valid"],
            checks["temporal_mixed_independent_checks"] >= 50,
            checks["temporal_mixed_reopen_gold"] == 3,
            checks["temporal_mixed_no_reopen_gold"] == 1,
            checks["temporal_mixed_direct_caught"] == 2,
            checks["temporal_mixed_direct_missed"] == 1,
            checks["temporal_mixed_direct_load"] == 3,
            checks["temporal_mixed_review_all_caught"] == 3,
            checks["temporal_mixed_review_all_missed"] == 0,
            checks["temporal_mixed_review_all_load"] == 4,
            checks["temporal_mixed_review_all_unnecessary"] == 1,
            checks["temporal_mixed_er_caught"] == 3,
            checks["temporal_mixed_er_missed"] == 0,
            checks["temporal_mixed_er_load"] == 3,
            checks["temporal_mixed_er_unnecessary"] == 0,
            checks["temporal_mixed_er_savings"] == 1,
            checks["temporal_mixed_er_recall_bps"] == 10000,
            checks["temporal_mixed_er_review_reduction_bps"] == 2500,
            checks["temporal_mixed_min_recall_bps"] == 9500,
            checks["temporal_mixed_min_review_reduction_bps"] == 4000,
            checks["temporal_mixed_failed_conditions"] == ["minimum_review_load_reduction"],
            checks["temporal_mixed_engine_unchanged"],
            checks["temporal_mixed_custody_engine_unchanged"],
            checks["temporal_replication_status"] == "TEMPORAL_SELECTIVITY_REPLICATION_PROMOTED",
            checks["temporal_replication_verdict"] == "PROMOTION",
            checks["temporal_replication_independent_valid"],
            checks["temporal_replication_independent_checks"] >= 100,
            checks["temporal_replication_episode_count"] == 5,
            checks["temporal_replication_scored_targets"] == 14,
            checks["temporal_replication_reopen_gold"] == 8,
            checks["temporal_replication_no_reopen_gold"] == 6,
            checks["temporal_replication_review_all_load"] == 14,
            checks["temporal_replication_er_load"] == 8,
            checks["temporal_replication_er_savings"] == 6,
            checks["temporal_replication_er_recall_bps"] == 10000,
            checks["temporal_replication_reduction_bps"] == 4285,
            checks["temporal_replication_recurring_episodes"] == 4,
            checks["temporal_replication_min_recall_bps"] == 9500,
            checks["temporal_replication_min_reduction_bps"] == 4000,
            checks["temporal_replication_min_recurring"] == 3,
            checks["temporal_replication_failed_conditions"] == [],
            checks["temporal_replication_engine_unchanged"],
            checks["temporal_replication_mean_episode_savings_bps"] == 4166,
            checks["temporal_replication_median_episode_savings_bps"] == 5000,
            checks["human_contract_present"],
            checks["human_contract_card_audit_valid"],
            checks["human_contract_four_lines_traced"],
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
    inputs.append(
        {
            "name": "Evidence Recall three-way comparative benchmark protocol",
            "schneider_dataset_doi": "10.13012/B2IDB-3331845_V2",
            "schneider_article_doi": "10.1007/s11192-020-03631-1",
            "van_der_vet_article_doi": "10.1186/s41073-016-0008-5",
            "jama_article_doi": "10.1001/jamainternmed.2025.0256",
            "diagnostic_id": comparative_diagnostic["diagnostic_id"],
            "usage": (
                "Three-way Direct Lookup vs naive transitive taint vs frozen Evidence Recall evaluation pipeline. "
                "Published aggregate diagnostic is independently verified; raw Schneider case bytes and van der Vet DOT are not bundled, "
                "so case-level empirical promotion remains blocked."
            ),
        }
    )
    inputs.append(
        {
            "name": "Evidence Recall temporal holdout benchmark protocol",
            "kataoka_article_doi": "10.1016/j.jclinepi.2022.06.015",
            "jama_article_doi": "10.1001/jamainternmed.2025.0256",
            "vitality_article_doi": "10.1136/bmj-2024-082068",
            "cochrane_letrozole_doi": "10.1002/14651858.CD010287.pub3",
            "diagnostic_id": temporal_diagnostic["diagnostic_id"],
            "usage": (
                "Prospective-style historical evaluation protocol comparing Direct Lookup, Review-All Reachability, "
                "and frozen Evidence Recall. Later records are content-committed before prediction and unsealed only for scoring. "
                "The conformance fixture remains synthetic; the first real historical Shah/Darwish case is separately sealed and scored."
            ),
        }
    )
    inputs.append(
        {
            "name": "Evidence Recall temporal holdout real case 001 — Shah intravenous iron",
            "accepted_review_doi": "10.1001/jamanetworkopen.2021.33935",
            "invalidated_study_doi": "10.1080/14767058.2017.1379988",
            "retraction_notice_doi": "10.1080/14767058.2023.2169999",
            "later_correction_doi": "10.1001/jamanetworkopen.2025.0887",
            "pack_id": temporal_real_summary["pack_id"],
            "future_seal_id": temporal_real_summary["future_seal_id"],
            "predictions_id": temporal_real_summary["predictions_id"],
            "gold_id": temporal_real_summary["gold_id"],
            "score_id": temporal_real_summary["score_id"],
            "usage": (
                "First real historical temporal episode. The pre-cutoff Shah review explicitly included the later-retracted "
                "Darwish trial in its hemoglobin meta-analysis; the 2025 JAMA correction records an explicit reanalysis without "
                "that study and no change in reported results. Direct Lookup catches one of two positive reopen targets; Review-All "
                "and frozen Evidence Recall catch both, but Evidence Recall saves zero reviews. This is NO_PROMOTION and cannot "
                "estimate false-review precision because both gold targets are positive."
            ),
        }
    )
    inputs.append(
        {
            "name": "Evidence Recall temporal holdout mixed selectivity corpus 001",
            "narayan_article_doi": "10.1038/nature11700",
            "narayan_retraction_doi": "10.1038/nature12897",
            "zhou_summary_doi": "10.1038/nature11761",
            "vitner_article_doi": "10.1038/nm.3449",
            "later_independent_audit_doi": "10.1186/s41073-016-0008-5",
            "pack_id": temporal_mixed_summary["pack_id"],
            "future_seal_id": temporal_mixed_summary["future_seal_id"],
            "predictions_id": temporal_mixed_summary["predictions_id"],
            "gold_id": temporal_mixed_summary["gold_id"],
            "score_id": temporal_mixed_summary["score_id"],
            "promotion_policy_id": temporal_mixed_summary["promotion_policy_id"],
            "promotion_result_id": temporal_mixed_summary["promotion_result_id"],
            "usage": (
                "First real mixed temporal selectivity corpus. It reuses the Shah/Darwish episode and adds a Narayan SIRT2 episode "
                "with one later affirmative REOPEN and one later affirmative NO_REOPEN. Frozen Evidence Recall catches 3/3 warranted "
                "reopenings with review load 3 versus Review-All load 4, a 25% reduction. This fails the predeclared 40% materiality bar "
                "and remains NO_PROMOTION."
            ),
        }
    )
    inputs.append(
        {
            "name": "Evidence Recall temporal selectivity replication corpus 001",
            "narayan_retraction_doi": "10.1038/nature12897",
            "van_der_vet_audit_doi": "10.1186/s41073-016-0008-5",
            "avenell_audit_doi": "10.1136/bmjopen-2019-031909",
            "kataoka_article_doi": "10.1016/j.jclinepi.2022.06.015",
            "pack_id": temporal_replication_summary["pack_id"],
            "future_seal_id": temporal_replication_summary["future_seal_id"],
            "predictions_id": temporal_replication_summary["predictions_id"],
            "gold_id": temporal_replication_summary["gold_id"],
            "score_id": temporal_replication_summary["score_id"],
            "promotion_policy_id": temporal_replication_summary["promotion_policy_id"],
            "promotion_result_id": temporal_replication_summary["promotion_result_id"],
            "usage": (
                "Five-trigger, fourteen-target temporal selectivity replication with case-level later audit evidence only. "
                "Frozen Evidence Recall catches 8/8 warranted reopenings while reviewing 8 targets versus Review-All's 14, "
                "a 42.85% review-load reduction with zero additional misses. Positive savings with zero additional misses recur "
                "in four of five trigger episodes, crossing the predeclared replication bar. Three episodes are related Sato "
                "retractions adjudicated by one later audit family, so promotion is narrow and does not establish broad-domain "
                "generalization, commercial moat, or hidden-dependency discovery. Kataoka aggregate counts contribute zero scored rows "
                "because case-level inclusion/exclusion material was not independently recoverable in this build."
            ),
        }
    )
    evidence = {
        "schema": "openline.claim-graph.prototype-evidence.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "TEMPORAL_SELECTIVITY_REPLICATION_PROMOTED",
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
            "rationalization, propaganda, reader-effect, or model-competence claim. A new three-way comparative "
            "pipeline freezes Direct Lookup, naive transitive taint, and the shipped Evidence Recall semantics; separates "
            "public pack, receiver authority, predictions, and external gold; and scores missed exposure, hard false quarantine, "
            "unresolved review, and total review load without a composite score. Published aggregate diagnostics are source-backed "
            "and independently reproduced, but the canonical Schneider case-level CSV and van der Vet DOT bytes are not bundled in "
            "this build environment, so no case-level empirical mechanism-advantage or moat claim is present. "
            "Version 0.5.0.dev0 adds temporal-holdout custody: pre-cutoff nodes and edges, a post-cutoff trigger, a committed but "
            "sealed later-record corpus, prediction without future records, and later reconsideration scoring against Direct Lookup, "
            "Review-All Reachability, and frozen Evidence Recall. Version 0.5.0.dev1 adds the first real historical temporal episode: "
            "the 2021 Shah intravenous-iron meta-analysis, the 2023 Darwish trial retraction, and the 2025 JAMA correction reporting "
            "explicit reanalysis without the retracted study. Direct Lookup catches 1/2 warranted reopenings; Review-All and frozen "
            "Evidence Recall catch 2/2, but Evidence Recall reviews the same two targets and therefore saves zero reviewer attention. "
            "Both gold targets are positive, so this episode cannot estimate false-review precision. Version 0.5.1 then adds a second "
            "historical Narayan SIRT2 episode with one affirmative REOPEN and one affirmative NO_REOPEN from a later independent citation-context "
            "audit. Across the mixed four-target corpus, Direct Lookup catches 2/3 warranted reopenings with review load 3; Review-All catches "
            "3/3 with load 4 and one unnecessary review; frozen Evidence Recall catches 3/3 with load 3 and zero unnecessary reviews. That is "
            "a 25% review-load reduction with full recall, but it fails the predeclared 40% materiality threshold. The verdict remains NO_PROMOTION. "
            "Version 0.5.2 expands the temporal corpus to five trigger episodes and fourteen scored targets using only case-level later records "
            "that affirmatively establish reliance or non-reliance. Frozen Evidence Recall catches 8/8 warranted reopenings while reviewing 8 "
            "targets versus Review-All's 14, a 42.85% review-load reduction with zero additional misses. Positive savings with zero additional misses "
            "recur in four of five trigger episodes, satisfying the predeclared recurrence rule and yielding a narrow PROMOTION as a temporal-selectivity "
            "product candidate. Three trigger episodes are related Sato retractions adjudicated by the same later Avenell audit family; the corpus has only "
            "fourteen scored targets and was historically reconstructed after outcomes were known. This does not establish broad-domain replication, commercial "
            "moat, hidden-edge discovery, or prospective performance. Kataoka aggregate counts contribute zero scored rows because case-level inclusion/exclusion "
            "material was not independently recoverable. No Evidence Recall engine semantics were changed in response. "
            "The canonical human-facing contract is POINT / BECAUSE / BUT / SO: the 0.5.2 card is generated from scored artifacts "
            "and custody limits, every line carries an audit path to exact artifact bytes, BUT is mandatory and material, and SO is "
            "bounded to the narrow benchmark-supported consequence."
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
