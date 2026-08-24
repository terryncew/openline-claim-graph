from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify frozen SRE-001 external adaptation instrument hashes")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    status = json.loads((root / "STATUS.json").read_text(encoding="utf-8"))
    mismatches = []
    for rel, expected in sorted(status["frozen_instrument_sha256"].items()):
        path = root / rel
        observed = sha256_file(path) if path.exists() else "MISSING"
        if observed != expected:
            mismatches.append({"path": rel, "expected": expected, "observed": observed})
    parent = root.parent
    for rel, expected in sorted(status.get("parent_frozen_sha256", {}).items()):
        path = parent / rel
        observed = sha256_file(path) if path.exists() else "MISSING"
        if observed != expected:
            mismatches.append({"path": f"parent/{rel}", "expected": expected, "observed": observed})
    payload = {
        "valid": not mismatches,
        "status": status["status"],
        "external_run": status["external_run"],
        "mismatches": mismatches,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not mismatches else 2


if __name__ == "__main__":
    raise SystemExit(main())
