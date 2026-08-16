"""Build a one-headline natural-material Frame Ledger specimen.

The headline text was supplied by the repository maintainer and has a public
locator.  Only the headline is audited.  No article body, author intent, truth,
fairness, propaganda, or rationalization claim is represented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from openline_claim_graph import (
    FRAME_RULESET,
    build_source,
    create_frame_policy,
    create_proposal_task,
    detect_mechanical_frame_devices,
    evaluate_frame_ledger,
    render_frame_ledger,
    verify_frame_report,
)


HEADLINE = (
    "Contradicting public statements, Trump took secret flight from Turkey amid Iranian threat"
)
LOCATOR = (
    "https://www.washingtonpost.com/national-security/2026/08/10/"
    "trump-flew-secrecy-amid-iran-threat-air-force-one-became-decoy/"
)
ABSENCE_SETS = [
    {
        "set_id": "falsity_or_deception_terms",
        "terms": ["false", "falsely", "misleading", "lie", "lied", "lying"],
    },
    {
        "set_id": "named_institutional_attribution_terms",
        "terms": ["White House", "administration", "officials", "spokesperson"],
    },
]


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def build(output: Path) -> dict[str, Any]:
    source = build_source(HEADLINE, locator=LOCATOR)
    findings = detect_mechanical_frame_devices(source, absence_sets=ABSENCE_SETS)
    policy = create_frame_policy(
        mechanical_auto_admit=True,
        advisory_min_confirmations=2,
        advisory_min_distinct_families=2,
        challenge_blocks=True,
        human_mode="OPTIONAL",
    )
    report = evaluate_frame_ledger(source, findings, policy)
    verification = verify_frame_report(report, source, findings, policy)
    rendered = render_frame_ledger(
        report=report,
        source=source,
        findings=findings,
        policy=policy,
        title="Frame Ledger — one headline, no verdict",
    )
    proposal_task = create_proposal_task(source)

    device_counts: dict[str, int] = {}
    for finding in findings:
        device = str(finding["device_type"])
        device_counts[device] = device_counts.get(device, 0) + 1
    summary = {
        "schema": "openline.frame-ledger-specimen-report.v1",
        "status": "MECHANICAL_DEVICES_REPRODUCED_ON_ONE_HEADLINE_NO_BIAS_VERDICT",
        "source_id": source["source_id"],
        "report_id": report["report_id"],
        "report_valid": verification["valid"],
        "finding_count": len(findings),
        "device_counts": dict(sorted(device_counts.items())),
        "human_mode": policy["human_mode"],
        "frontier_or_open_model_calls_run": 0,
        "incremental_api_spend_usd": 0,
        "review_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "claim_boundary": (
            "This specimen reproduces exact lexical, local-grammar, and declared scoped-absence "
            "findings on one supplied headline. It does not audit the article body, validate the "
            "ruleset against a framing corpus, or establish truth, deception, fairness, intent, "
            "rationalization, propaganda, reader effect, product value, or model competence."
        ),
    }
    readme = f"""# Frame Ledger — Washington Post headline specimen

Open `review.html` for the readable surface.

Status: `{summary['status']}`

The exact headline supplied by the maintainer is scanned under the checked-in mechanical ruleset. Seven findings reproduce: one conflict lexeme, one co-occurrence cue, two issue-frame lexemes, one narrow local-attribution-pattern absence, and two receiver-declared term-set absences.

The green status means those operations reproduce from exact UTF-8 bytes. It does not mean the article is biased, fair, false, propaganda, or rationalizing anyone. The article body is not in this specimen.

No frontier or open-weight model was called while building this artifact. `proposal-task.json` is the exact bounded task that may be sent through `scripts/frame_agent_adapter.py`; any returned inference still needs the receiver's signed heterogeneous-review quorum.

## Reproduce

```bash
PYTHONPATH=src python examples/build_wapo_frame_ledger.py \\
  --output artifacts/wapo-headline-frame-ledger

PYTHONPATH=src python -m openline_claim_graph verify-frame \\
  --report artifacts/wapo-headline-frame-ledger/report.json \\
  --source artifacts/wapo-headline-frame-ledger/source.json \\
  --findings artifacts/wapo-headline-frame-ledger/findings.json \\
  --policy artifacts/wapo-headline-frame-ledger/policy.json
```

Report: `{report['report_id']}`
"""

    _write(output / "source.json", source)
    _write(output / "findings.json", {"schema": "openline.frame-findings.v1", "findings": findings})
    _write(output / "policy.json", policy)
    _write(output / "ruleset.json", FRAME_RULESET)
    _write(output / "report.json", report)
    _write(output / "verification.json", verification)
    _write(output / "proposal-task.json", proposal_task)
    _write(output / "review.html", rendered)
    _write(output / "REPORT.json", summary)
    _write(output / "README.md", readme)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = build(args.output)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
