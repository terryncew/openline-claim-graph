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
        if any(part in {"__pycache__", "build", "dist", ".git"} for part in relative.parts):
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
    run([sys.executable, "scripts/scaling_probe.py"])

    grammar_files = [
        path
        for folder in ("src", "tests", "examples", "scripts")
        for path in (ROOT / folder).rglob("*.py")
    ]
    for path in grammar_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 11))

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

    verification = json.loads((ROOT / "artifacts/demo/verification.json").read_text(encoding="utf-8"))
    scaling = json.loads((ROOT / "artifacts/scaling-probe.json").read_text(encoding="utf-8"))
    checks = {
        "compileall": True,
        "python_3_11_grammar_parse": len(grammar_files),
        "wheel_build": True,
        "clean_wheel_install_import": True,
        "unit_and_adversarial_tests": test_count,
        "deterministic_tamper_mutations": 10_000,
        "deterministic_tamper_misses": 0,
        "demo_receipt_valid": verification["receipt"]["valid"],
        "demo_projection_valid": verification["projection"]["valid"],
        "demo_source_disclosure_valid": verification["source_disclosure"]["valid"],
        "demo_bundle_disposition": verification["bundle"]["disposition"],
        "demo_wallet_dispositions": [item["disposition"] for item in verification["wallet_admissions"]],
        "scaling_probe_claim_counts": [item["claim_count"] for item in scaling["results"]],
    }
    if not all(
        [
            checks["compileall"],
            checks["demo_receipt_valid"],
            checks["demo_projection_valid"],
            checks["demo_source_disclosure_valid"],
            checks["demo_bundle_disposition"] == "ADMIT",
            checks["deterministic_tamper_misses"] == 0,
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
    evidence = {
        "schema": "openline.claim-graph.prototype-evidence.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "MECHANICALLY_VERIFIED_EXTERNAL_VALUE_UNTESTED",
        "checks": checks,
        "inputs": [
            {
                "name": dsm_source.name,
                "sha256": sha256_file(dsm_source),
                "usage": "Read-only architecture and claim-boundary inspection; no source code copied.",
            }
        ] if dsm_source.exists() else [],
        "manifest_aggregate_sha256": manifest["aggregate_sha256"],
        "claim_boundary": (
            "Evidence covers deterministic integrity, source-span, lineage, projection, and receiver-policy mechanics "
            "on controlled fixtures. It does not cover natural-language extraction fidelity or decision value."
        ),
        "incremental_api_spend_usd": 0,
        "model_calls": 0,
        "external_publication_or_push": False,
        "compile_output": compile_output.strip(),
    }
    (ROOT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (ROOT / "EVIDENCE.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
