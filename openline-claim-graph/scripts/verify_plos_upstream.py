"""Re-check the natural-material excerpts against the public PLOS Search API."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE_SCRIPT = ROOT / "examples/build_plos_correction_case.py"


def _load_case_module():
    spec = importlib.util.spec_from_file_location("plos_case", CASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load natural-material case builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fetch(doi: str) -> tuple[str, dict]:
    query = urllib.parse.urlencode(
        {"q": f'id:"{doi}"', "fl": "id,title,abstract,body", "rows": "1", "wt": "json"}
    )
    url = f"https://api.plos.org/search?{query}"
    with urllib.request.urlopen(url, timeout=30) as response:  # nosec B310 - fixed HTTPS host
        payload = json.load(response)
    docs = payload["response"]["docs"]
    if len(docs) != 1 or docs[0].get("id") != doi:
        raise RuntimeError(f"unexpected PLOS response for {doi}")
    return url, docs[0]


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify() -> dict:
    case = _load_case_module()
    original_url, original = _fetch(case.ORIGINAL_DOI)
    correction_url, correction = _fetch(case.CORRECTION_DOI)
    abstract = str((original.get("abstract") or [""])[0])
    body = str(original.get("body", ""))
    correction_body = str(correction.get("body", ""))
    checks = {
        "abstract_excerpt_exact": case.ABSTRACT_RESULTS in abstract,
        "main_sample_excerpt_exact": case.MAIN_SAMPLE_RESULTS in body,
        "main_cost_excerpt_exact": case.MAIN_COST_RESULTS in body,
        "correction_anchor_exact": case.CORRECTION_ANCHOR in correction_body,
    }
    return {
        "schema": "openline.claim-graph.plos-upstream-verification.v1",
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "original_doi": case.ORIGINAL_DOI,
        "correction_doi": case.CORRECTION_DOI,
        "original_query": original_url,
        "correction_query": correction_url,
        "upstream_field_hashes": {
            "original_abstract_sha256": _sha(abstract),
            "original_body_sha256": _sha(body),
            "correction_body_sha256": _sha(correction_body),
        },
        "local_excerpt_hashes": {
            "abstract_sha256": _sha(case.ABSTRACT_RESULTS),
            "main_sample_sha256": _sha(case.MAIN_SAMPLE_RESULTS),
            "main_cost_sha256": _sha(case.MAIN_COST_RESULTS),
            "correction_anchor_sha256": _sha(case.CORRECTION_ANCHOR),
        },
        "checks": checks,
        "exact_match": all(checks.values()),
        "claim_boundary": (
            "This verifies exact excerpt presence in the current PLOS API record. It does not validate the "
            "manual claim mapping or the decision value of the rendered review."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["exact_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
