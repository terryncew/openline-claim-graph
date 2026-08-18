from __future__ import annotations

"""Self-hosted natural-stream operator for Prospective Decision Recall Cohort 001.

This script does not change Decision Recall semantics. It turns the frozen
0.6.0.dev0 protocol into a cohort instrument for ordinary repository work.

The setup commit is never eligible. A cohort observation binds a prospectively
captured manifest and a conventional pre-trigger record to a canonical change
set that excludes cohort bookkeeping and generated release metadata, avoiding a
self-referential commit hash cycle. After push, the same digest can be rebuilt
from Git history.
"""

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DESIGNATION_REL = Path("experiments/decision-recall-prospective-001/cohort-001/DESIGNATION.json")
COHORT_DATA_REL = Path("artifacts/decision-recall-prospective/cohort-001")

OBSERVATION_SCHEMA = "openline.decision-recall-cohort-observation.v1"
EXCLUSION_SCHEMA = "openline.decision-recall-cohort-exclusion.v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        raise TypeError("floating-point values are not canonical")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical object keys must be strings")
            nkey = unicodedata.normalize("NFC", key)
            if nkey in normalized:
                raise TypeError("duplicate key after NFC normalization")
            normalized[nkey] = _normalize(item)
        return normalized
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_id(prefix: str, body: dict[str, Any]) -> str:
    return f"{prefix}:sha256:{sha256_bytes(canonical_bytes(body))}"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_git(root: Path, args: list[str], *, binary: bool = False) -> bytes | str:
    completed = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=False, text=not binary
    )
    if completed.returncode:
        stderr = completed.stderr.decode("utf-8", "replace") if binary else completed.stderr
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return completed.stdout


def git_available(root: Path) -> bool:
    try:
        output = run_git(root, ["rev-parse", "--is-inside-work-tree"])
        return str(output).strip() == "true"
    except Exception:
        return False


def designation(root: Path) -> dict[str, Any]:
    path = root / DESIGNATION_REL
    if not path.exists():
        raise RuntimeError(f"cohort designation missing: {path}")
    value = load(path)
    if value.get("cohort_id") != "decision-recall-cohort-001":
        raise RuntimeError("unexpected cohort designation")
    return value


def is_excluded_path(relative: str, patterns: Iterable[str]) -> bool:
    normalized = relative.replace(os.sep, "/")
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def _tree_files(root: Path, patterns: Iterable[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in {".git", "__pycache__", ".pytest_cache", "build", "dist"} for part in path.relative_to(root).parts):
            continue
        if any(part.endswith(".egg-info") for part in path.relative_to(root).parts):
            continue
        if is_excluded_path(rel, patterns):
            continue
        result[rel] = path
    return result


def change_set_from_dirs(base: Path, candidate: Path, patterns: Iterable[str]) -> dict[str, Any]:
    before = _tree_files(base, patterns)
    after = _tree_files(candidate, patterns)
    entries = []
    for rel in sorted(set(before) | set(after)):
        b = before.get(rel)
        a = after.get(rel)
        b_hash = sha256_file(b) if b else ""
        a_hash = sha256_file(a) if a else ""
        if b_hash == a_hash:
            continue
        status = "A" if b is None else "D" if a is None else "M"
        entries.append({
            "path": rel,
            "status": status,
            "before_sha256": b_hash,
            "after_sha256": a_hash,
            "after_size_bytes": a.stat().st_size if a else 0,
        })
    body = {"schema": "openline.cohort-change-set.v1", "entries": entries}
    return {**body, "change_set_sha256": sha256_bytes(canonical_bytes(body))}


def _blob_hash(root: Path, ref: str, path: str) -> tuple[str, int]:
    completed = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=root, capture_output=True, check=False)
    if completed.returncode:
        return "", 0
    data = completed.stdout
    return sha256_bytes(data), len(data)


def change_set_from_commit(root: Path, commit: str, patterns: Iterable[str]) -> dict[str, Any]:
    commit = str(run_git(root, ["rev-parse", commit])).strip()
    parent_line = str(run_git(root, ["rev-list", "--parents", "-n", "1", commit])).strip().split()
    if len(parent_line) < 2:
        parent = ""
        names = str(run_git(root, ["ls-tree", "-r", "--name-only", commit])).splitlines()
        raw_entries = [("A", name) for name in names]
    else:
        parent = parent_line[1]
        output = str(run_git(root, ["diff", "--no-renames", "--name-status", parent, commit]))
        raw_entries = []
        for line in output.splitlines():
            if not line.strip():
                continue
            status, path = line.split("\t", 1)
            raw_entries.append((status[0], path))
    entries = []
    for status, rel in sorted(raw_entries, key=lambda item: item[1]):
        if is_excluded_path(rel, patterns):
            continue
        before_hash, _ = _blob_hash(root, parent, rel) if parent and status != "A" else ("", 0)
        after_hash, after_size = _blob_hash(root, commit, rel) if status != "D" else ("", 0)
        entries.append({
            "path": rel,
            "status": status,
            "before_sha256": before_hash,
            "after_sha256": after_hash,
            "after_size_bytes": after_size,
        })
    body = {"schema": "openline.cohort-change-set.v1", "entries": entries}
    return {**body, "change_set_sha256": sha256_bytes(canonical_bytes(body))}


def frozen_health(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    mismatches = []
    for rel, expected in sorted(spec.get("frozen_instrument_sha256", {}).items()):
        path = root / rel
        observed = sha256_file(path) if path.exists() else "MISSING"
        if observed != expected:
            mismatches.append({"path": rel, "expected": expected, "observed": observed})
    return {"valid": not mismatches, "mismatches": mismatches}


def activation_commit(root: Path) -> str | None:
    if not git_available(root):
        return None
    output = str(run_git(root, ["log", "--diff-filter=A", "--format=%H", "--", DESIGNATION_REL.as_posix()])).splitlines()
    if not output:
        return None
    return output[-1].strip()


def _cohort_json_files(root: Path, kind: str) -> list[Path]:
    directory = root / COHORT_DATA_REL / kind
    if not directory.exists():
        return []
    return sorted(path for path in directory.glob("*.json") if path.is_file())


def _verify_record_id(value: dict[str, Any], id_field: str, prefix: str) -> bool:
    claimed = value.get(id_field, "")
    body = dict(value)
    body.pop(id_field, None)
    return claimed == content_id(prefix, body)


def status_payload(root: Path) -> dict[str, Any]:
    spec = designation(root)
    health = frozen_health(root, spec)
    activation = activation_commit(root)
    observations = [load(path) for path in _cohort_json_files(root, "observations")]
    exclusions = [load(path) for path in _cohort_json_files(root, "exclusions")]
    invalid_entries = []
    for path, value, id_field, prefix in [
        *[(path, load(path), "cohort_observation_id", "decision-recall-cohort-observation") for path in _cohort_json_files(root, "observations")],
        *[(path, load(path), "cohort_exclusion_id", "decision-recall-cohort-exclusion") for path in _cohort_json_files(root, "exclusions")],
    ]:
        if not _verify_record_id(value, id_field, prefix):
            invalid_entries.append(path.relative_to(root).as_posix())

    unclassified: list[dict[str, Any]] = []
    if activation and health["valid"]:
        represented = {item.get("subject_change_set_sha256", "") for item in observations + exclusions}
        commits = str(run_git(root, ["rev-list", "--reverse", f"{activation}..HEAD"])).splitlines()
        patterns = spec.get("change_set_exclude_globs", [])
        for commit in commits:
            change = change_set_from_commit(root, commit, patterns)
            if not change["entries"]:
                continue
            if change["change_set_sha256"] not in represented:
                message = str(run_git(root, ["show", "-s", "--format=%s", commit])).strip()
                unclassified.append({
                    "commit": commit,
                    "subject": message,
                    "change_set_sha256": change["change_set_sha256"],
                    "changed_path_count": len(change["entries"]),
                })

    required = int(spec.get("minimum_real_accepted_decisions", 30))
    state = "AWAITING_INSTALL_COMMIT"
    if activation:
        state = "ACCUMULATING"
    if not health["valid"]:
        state = "RESTART_REQUIRED_INSTRUMENT_MUTATED"
    if invalid_entries:
        state = "INVALID_COHORT_LEDGER"
    if len(observations) >= required and not unclassified and health["valid"] and not invalid_entries:
        state = "READY_TO_SEAL"

    return {
        "schema": "openline.decision-recall-cohort-status.v1",
        "cohort_id": spec["cohort_id"],
        "state": state,
        "activation_commit": activation,
        "setup_commit_counts": False,
        "real_accepted_decisions": len(observations),
        "excluded_or_nonqualifying_commits": len(exclusions),
        "minimum_real_accepted_decisions": required,
        "remaining_decisions": max(0, required - len(observations)),
        "unclassified_post_activation_commits": unclassified,
        "instrument_health": health,
        "invalid_ledger_entries": invalid_entries,
        "claim_boundary": "Cohort count and custody status are instrument state only. They are not evidence that Decision Recall is accurate, useful, or commercially valuable.",
    }


def make_observation(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    spec = designation(root)
    health = frozen_health(root, spec)
    if not health["valid"]:
        raise SystemExit(f"frozen instrument changed; cohort restart required: {health['mismatches']}")
    manifest = load(Path(args.manifest))
    record = load(Path(args.pre_trigger_record))
    if manifest.get("schema") != "openline.decision-recall-manifest.v1":
        raise SystemExit("unexpected manifest schema")
    if record.get("schema") != "openline.decision-recall-pre-trigger-record.v1":
        raise SystemExit("unexpected pre-trigger record schema")
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        from openline_claim_graph.decision_recall import validate_manifest
        validation = validate_manifest(manifest)
    except Exception as exc:
        raise SystemExit(f"could not independently validate prospective manifest structure: {exc}") from exc
    if not validation.get("valid"):
        raise SystemExit(f"invalid prospective manifest: {validation.get('errors', [])}")
    record_body = dict(record)
    claimed_record_id = record_body.pop("pre_trigger_record_id", "")
    if claimed_record_id != content_id("decision-recall-pre-trigger-record", record_body):
        raise SystemExit("pre-trigger record content ID mismatch")
    if manifest.get("decision_id") != record.get("decision_id"):
        raise SystemExit("manifest and conventional record decision_id differ")
    if not args.would_have_happened_anyway:
        raise SystemExit("non-natural or benchmark-manufactured decisions cannot enter Cohort 001")
    if args.instrument_setup:
        raise SystemExit("cohort/instrument setup decisions are never eligible")
    if str(manifest.get("capture", {}).get("timing_source", "")).upper() not in set(spec.get("acceptable_capture_timing_sources", [])):
        raise SystemExit("capture timing source is not accepted by the frozen cohort contract")

    subject_digest = args.change_set_sha256
    if args.base_dir and args.candidate_dir:
        computed = change_set_from_dirs(Path(args.base_dir).resolve(), Path(args.candidate_dir).resolve(), spec.get("change_set_exclude_globs", []))
        if subject_digest and subject_digest != computed["change_set_sha256"]:
            raise SystemExit("provided change-set digest disagrees with base/candidate trees")
        subject_digest = computed["change_set_sha256"]
    if not subject_digest:
        raise SystemExit("a canonical subject change-set digest is required")
    artifact_hash = str(manifest.get("resulting_artifact", {}).get("sha256", ""))
    if artifact_hash != subject_digest:
        raise SystemExit("manifest resulting_artifact.sha256 must bind the canonical subject change set")

    body = {
        "schema": OBSERVATION_SCHEMA,
        "cohort_id": spec["cohort_id"],
        "decision_id": manifest["decision_id"],
        "manifest_id": manifest.get("manifest_id", ""),
        "pre_trigger_record_id": record.get("pre_trigger_record_id", ""),
        "subject_change_set_sha256": subject_digest,
        "eligibility": "NATURAL_ACCEPTED_DECISION",
        "would_have_happened_without_benchmark": True,
        "consequentiality_basis": str(args.consequentiality_basis).strip(),
        "recorded_at": args.recorded_at or now(),
        "capture_timing_source": str(manifest.get("capture", {}).get("timing_source", "")).upper(),
        "setup_or_instrument_change": False,
    }
    body["cohort_observation_id"] = content_id("decision-recall-cohort-observation", body)
    out_dir = root / COHORT_DATA_REL
    write(out_dir / "manifests" / f"{manifest['decision_id']}.json", manifest)
    write(out_dir / "pre-trigger-records" / f"{manifest['decision_id']}.json", record)
    write(out_dir / "observations" / f"{manifest['decision_id']}.json", body)
    print(json.dumps({"valid": True, "cohort_observation_id": body["cohort_observation_id"], "decision_id": manifest["decision_id"]}, indent=2))
    return 0


def make_exclusion(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    spec = designation(root)
    allowed = set(spec.get("allowed_exclusion_reasons", []))
    reason = str(args.reason).upper()
    if reason not in allowed:
        raise SystemExit(f"unsupported exclusion reason: {reason}")
    digest = args.change_set_sha256
    if args.commit:
        change = change_set_from_commit(root, args.commit, spec.get("change_set_exclude_globs", []))
        if digest and digest != change["change_set_sha256"]:
            raise SystemExit("provided change-set digest disagrees with commit")
        digest = change["change_set_sha256"]
    if not digest:
        raise SystemExit("change-set digest or --commit is required")
    body = {
        "schema": EXCLUSION_SCHEMA,
        "cohort_id": spec["cohort_id"],
        "subject_change_set_sha256": digest,
        "reason": reason,
        "detail": str(args.detail or "").strip(),
        "recorded_at": args.recorded_at or now(),
    }
    body["cohort_exclusion_id"] = content_id("decision-recall-cohort-exclusion", body)
    filename = f"{body['cohort_exclusion_id'].split(':')[-1][:16]}.json"
    write(root / COHORT_DATA_REL / "exclusions" / filename, body)
    print(json.dumps({"valid": True, "cohort_exclusion_id": body["cohort_exclusion_id"], "reason": reason}, indent=2))
    return 0


def cmd_changeset(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    spec = designation(root)
    if args.commit:
        result = change_set_from_commit(root, args.commit, spec.get("change_set_exclude_globs", []))
    else:
        if not args.base_dir or not args.candidate_dir:
            raise SystemExit("use --commit or both --base-dir and --candidate-dir")
        result = change_set_from_dirs(Path(args.base_dir).resolve(), Path(args.candidate_dir).resolve(), spec.get("change_set_exclude_globs", []))
    if args.output:
        write(Path(args.output), result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    payload = status_payload(Path(args.root).resolve())
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload["state"] in {"RESTART_REQUIRED_INSTRUMENT_MUTATED", "INVALID_COHORT_LEDGER"}:
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prospective Decision Recall Cohort 001 operator")
    parser.add_argument("--root", default=str(ROOT), help="repository root")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="show cohort activation, count, health, and unclassified post-activation commits")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("changeset", help="compute the canonical decision change-set digest")
    p.add_argument("--commit")
    p.add_argument("--base-dir")
    p.add_argument("--candidate-dir")
    p.add_argument("--output")
    p.set_defaults(func=cmd_changeset)

    p = sub.add_parser("append", help="append one real prospectively captured accepted decision")
    p.add_argument("--manifest", required=True)
    p.add_argument("--pre-trigger-record", required=True)
    p.add_argument("--change-set-sha256", default="")
    p.add_argument("--base-dir")
    p.add_argument("--candidate-dir")
    p.add_argument("--consequentiality-basis", required=True)
    p.add_argument("--would-have-happened-anyway", action="store_true")
    p.add_argument("--instrument-setup", action="store_true")
    p.add_argument("--recorded-at")
    p.set_defaults(func=make_observation)

    p = sub.add_parser("exclude", help="classify a real post-activation commit that is not an eligible accepted decision")
    p.add_argument("--commit")
    p.add_argument("--change-set-sha256", default="")
    p.add_argument("--reason", required=True)
    p.add_argument("--detail")
    p.add_argument("--recorded-at")
    p.set_defaults(func=make_exclusion)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
