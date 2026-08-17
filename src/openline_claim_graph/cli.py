from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .benchmark import (
    build_plan,
    run_receiver_command,
    score_responses,
    validate_gold,
    validate_pack,
)
from .bundle import verify_bundle
from .frame import FrameValidationError, evaluate_frame_ledger, verify_frame_report
from .frame_review import FrameReviewError, render_frame_ledger
from .graph import verify_projection
from .impact import (
    ImpactValidationError,
    analyze_adjudication_impact,
    analyze_source_impact,
    verify_adjudication_impact_bundle,
    verify_impact_bundle,
)
from .impact_review import ImpactReviewError, render_impact_review
from .receipts import verify_receipt, verify_source_disclosure
from .review import ReviewRenderError, render_review


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(value: Any) -> int:
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0 if value.get("valid") else 1


def _write(path: str, value: Any) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _collection(path: str | None, key: str) -> list[Any]:
    if path is None:
        return []
    value = _load(path)
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get(key), list):
        return value[key]
    raise ValueError(f"{path} must be a JSON array or an object containing {key!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify OpenLine claim-graph prototype artifacts")
    sub = parser.add_subparsers(dest="command", required=True)

    receipt = sub.add_parser("verify-receipt", help="verify a signed graph-state receipt")
    receipt.add_argument("--snapshot", required=True)
    receipt.add_argument("--receipt", required=True)
    receipt.add_argument("--sources", required=True)
    receipt.add_argument("--public-key", required=True)
    receipt.add_argument("--parent", action="append", default=[])

    projection = sub.add_parser("verify-projection", help="verify a bounded graph projection")
    projection.add_argument("--projection", required=True)
    projection.add_argument("--policy")

    disclosure = sub.add_parser("verify-source-disclosure", help="verify projected source commitments")
    disclosure.add_argument("--disclosure", required=True)
    disclosure.add_argument("--projection", required=True)
    disclosure.add_argument("--receipt", required=True)

    bundle = sub.add_parser("verify-bundle", help="verify the complete receiver-scoped bundle")
    bundle.add_argument("--snapshot", required=True)
    bundle.add_argument("--receipt", required=True)
    bundle.add_argument("--sources", required=True)
    bundle.add_argument("--projection", required=True)
    bundle.add_argument("--disclosure", required=True)
    bundle.add_argument("--policy", required=True)
    bundle.add_argument("--public-key", required=True)
    bundle.add_argument("--parent", action="append", default=[])

    review = sub.add_parser("render-review", help="render a verified bundle as self-contained HTML")
    review.add_argument("--snapshot", required=True)
    review.add_argument("--receipt", required=True)
    review.add_argument("--sources", required=True)
    review.add_argument("--projection", required=True)
    review.add_argument("--disclosure", required=True)
    review.add_argument("--policy", required=True)
    review.add_argument("--public-key", required=True)
    review.add_argument("--parent", action="append", default=[])
    review.add_argument("--output", required=True)
    review.add_argument("--title", default="Decision Review")

    benchmark_validate = sub.add_parser(
        "benchmark-validate",
        help="validate a sealed automated receiver pack and optional gold key",
    )
    benchmark_validate.add_argument("--pack", required=True)
    benchmark_validate.add_argument("--gold")

    benchmark_plan = sub.add_parser(
        "benchmark-plan",
        help="build a deterministic full-factorial automated receiver plan",
    )
    benchmark_plan.add_argument("--pack", required=True)
    benchmark_plan.add_argument("--receiver", action="append", required=True)
    benchmark_plan.add_argument("--repetitions", type=int, default=1)
    benchmark_plan.add_argument("--output", required=True)

    benchmark_run = sub.add_parser(
        "benchmark-run",
        help="run one isolated receiver command across its planned trials",
    )
    benchmark_run.add_argument("--pack", required=True)
    benchmark_run.add_argument("--plan", required=True)
    benchmark_run.add_argument("--receiver-id", required=True)
    benchmark_run.add_argument("--output", required=True)
    benchmark_run.add_argument("--timeout-seconds", type=int, default=120)
    benchmark_run.add_argument("--max-cost-microusd", type=int, default=0)
    benchmark_run.add_argument(
        "receiver_command",
        nargs=argparse.REMAINDER,
        help="receiver argv after '--'; one fresh process is used per trial",
    )

    benchmark_score = sub.add_parser(
        "benchmark-score",
        help="deterministically score receiver outputs against bound external gold",
    )
    benchmark_score.add_argument("--pack", required=True)
    benchmark_score.add_argument("--gold", required=True)
    benchmark_score.add_argument("--plan", required=True)
    benchmark_score.add_argument("--responses", action="append", required=True)
    benchmark_score.add_argument("--output", required=True)

    impact = sub.add_parser(
        "impact",
        help="compute downstream exposure from a source-status event under receiver policy",
    )
    impact.add_argument("--snapshot", required=True)
    impact.add_argument("--sources", required=True)
    impact.add_argument("--event", required=True)
    impact.add_argument("--policy", required=True)
    impact.add_argument("--output", required=True)

    impact_verify = sub.add_parser(
        "verify-impact",
        help="independently reproduce and verify a claim-impact report",
    )
    impact_verify.add_argument("--report", required=True)
    impact_verify.add_argument("--snapshot", required=True)
    impact_verify.add_argument("--sources", required=True)
    impact_verify.add_argument("--event", required=True)
    impact_verify.add_argument("--policy", required=True)
    impact_verify.add_argument("--receipt", required=True)
    impact_verify.add_argument("--public-key", required=True)
    impact_verify.add_argument("--parent", action="append", default=[])

    impact_render = sub.add_parser(
        "render-impact",
        help="render a verified claim-impact report as self-contained HTML",
    )
    impact_render.add_argument("--report", required=True)
    impact_render.add_argument("--snapshot", required=True)
    impact_render.add_argument("--sources", required=True)
    impact_render.add_argument("--event", required=True)
    impact_render.add_argument("--policy", required=True)
    impact_render.add_argument("--receipt", required=True)
    impact_render.add_argument("--public-key", required=True)
    impact_render.add_argument("--parent", action="append", default=[])
    impact_render.add_argument("--output", required=True)
    impact_render.add_argument("--title", default="Evidence Recall")

    adjudication_impact = sub.add_parser(
        "adjudication-impact",
        help="compute the single-edge counterfactual review surface for advisory relations",
    )
    adjudication_impact.add_argument("--snapshot", required=True)
    adjudication_impact.add_argument("--sources", required=True)
    adjudication_impact.add_argument("--event", required=True)
    adjudication_impact.add_argument("--policy", required=True)
    adjudication_impact.add_argument("--output", required=True)

    adjudication_impact_verify = sub.add_parser(
        "verify-adjudication-impact",
        help="authenticate accepted state and reproduce an adjudication-impact report",
    )
    adjudication_impact_verify.add_argument("--report", required=True)
    adjudication_impact_verify.add_argument("--snapshot", required=True)
    adjudication_impact_verify.add_argument("--sources", required=True)
    adjudication_impact_verify.add_argument("--event", required=True)
    adjudication_impact_verify.add_argument("--policy", required=True)
    adjudication_impact_verify.add_argument("--receipt", required=True)
    adjudication_impact_verify.add_argument("--public-key", required=True)
    adjudication_impact_verify.add_argument("--parent", action="append", default=[])

    frame = sub.add_parser(
        "frame-audit",
        help="apply receiver policy to exact framing-device findings",
    )
    frame.add_argument("--source", required=True)
    frame.add_argument("--findings", required=True)
    frame.add_argument("--policy", required=True)
    frame.add_argument("--finding-attestations")
    frame.add_argument("--reviews")
    frame.add_argument("--review-attestations")
    frame.add_argument("--output", required=True)

    frame_verify = sub.add_parser(
        "verify-frame",
        help="reproduce and verify a Frame Ledger report",
    )
    frame_verify.add_argument("--report", required=True)
    frame_verify.add_argument("--source", required=True)
    frame_verify.add_argument("--findings", required=True)
    frame_verify.add_argument("--policy", required=True)
    frame_verify.add_argument("--finding-attestations")
    frame_verify.add_argument("--reviews")
    frame_verify.add_argument("--review-attestations")

    frame_render = sub.add_parser(
        "render-frame",
        help="render a reproduced Frame Ledger as self-contained HTML",
    )
    frame_render.add_argument("--report", required=True)
    frame_render.add_argument("--source", required=True)
    frame_render.add_argument("--findings", required=True)
    frame_render.add_argument("--policy", required=True)
    frame_render.add_argument("--finding-attestations")
    frame_render.add_argument("--reviews")
    frame_render.add_argument("--review-attestations")
    frame_render.add_argument("--output", required=True)
    frame_render.add_argument("--title", default="Frame Ledger")

    args = parser.parse_args(argv)
    if args.command in {"frame-audit", "verify-frame", "render-frame"}:
        source = _load(args.source)
        findings = _collection(args.findings, "findings")
        policy = _load(args.policy)
        finding_attestations = _collection(args.finding_attestations, "attestations")
        reviews = _collection(args.reviews, "reviews")
        review_attestations = _collection(args.review_attestations, "attestations")
        if args.command == "frame-audit":
            try:
                result = evaluate_frame_ledger(
                    source,
                    findings,
                    policy,
                    finding_attestations=finding_attestations,
                    reviews=reviews,
                    review_attestations=review_attestations,
                )
            except FrameValidationError as exc:
                return _emit({"valid": False, "errors": [str(exc)]})
            _write(args.output, result)
            return _emit(
                {
                    "valid": True,
                    "output": args.output,
                    "report_id": result["report_id"],
                    "summary": result["summary"],
                }
            )
        report = _load(args.report)
        if args.command == "verify-frame":
            return _emit(
                verify_frame_report(
                    report,
                    source,
                    findings,
                    policy,
                    finding_attestations=finding_attestations,
                    reviews=reviews,
                    review_attestations=review_attestations,
                )
            )
        try:
            rendered = render_frame_ledger(
                report=report,
                source=source,
                findings=findings,
                policy=policy,
                finding_attestations=finding_attestations,
                reviews=reviews,
                review_attestations=review_attestations,
                title=args.title,
            )
        except FrameReviewError as exc:
            return _emit({"valid": False, "errors": [str(exc)]})
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        return _emit(
            {
                "valid": True,
                "output": str(output),
                "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            }
        )
    if args.command == "benchmark-validate":
        pack = _load(args.pack)
        result = validate_gold(_load(args.gold), pack) if args.gold else validate_pack(pack)
        return _emit(result)
    if args.command == "benchmark-plan":
        plan = build_plan(_load(args.pack), args.receiver, args.repetitions)
        _write(args.output, plan)
        return _emit(
            {
                "valid": True,
                "output": args.output,
                "plan_sha256": hashlib.sha256(
                    json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
                "trial_count": len(plan["trials"]),
            }
        )
    if args.command == "benchmark-run":
        receiver_command = list(args.receiver_command)
        if receiver_command and receiver_command[0] == "--":
            receiver_command = receiver_command[1:]
        if not receiver_command:
            parser.error("benchmark-run requires a receiver command after '--'")
        result = run_receiver_command(
            _load(args.pack),
            _load(args.plan),
            receiver_id=args.receiver_id,
            command=receiver_command,
            output_path=Path(args.output),
            timeout_seconds=args.timeout_seconds,
            max_cost_microusd=args.max_cost_microusd,
        )
        return _emit(
            {
                "valid": True,
                "output": args.output,
                "status": result["status"],
                "responses": len(result["responses"]),
                "cumulative_cost_microusd": result["cumulative_cost_microusd"],
            }
        )
    if args.command == "benchmark-score":
        result = score_responses(
            _load(args.pack),
            _load(args.gold),
            _load(args.plan),
            [_load(path) for path in args.responses],
        )
        _write(args.output, result)
        return _emit(result)
    if args.command == "impact":
        sources_doc = _load(args.sources)
        sources = {item["source_id"]: item for item in sources_doc["sources"]}
        try:
            result = analyze_source_impact(
                _load(args.snapshot),
                sources,
                _load(args.event),
                _load(args.policy),
            )
        except ImpactValidationError as exc:
            return _emit({"valid": False, "errors": [str(exc)]})
        _write(args.output, result)
        return _emit(
            {
                "valid": True,
                "output": args.output,
                "report_id": result["report_id"],
                "summary": result["summary"],
            }
        )
    if args.command == "verify-impact":
        sources_doc = _load(args.sources)
        sources = {item["source_id"]: item for item in sources_doc["sources"]}
        return _emit(
            verify_impact_bundle(
                _load(args.report),
                _load(args.snapshot),
                sources,
                _load(args.event),
                _load(args.policy),
                _load(args.receipt),
                pinned_public_key=args.public_key,
                parent_snapshots=[_load(path) for path in args.parent],
            )
        )
    if args.command == "adjudication-impact":
        sources_doc = _load(args.sources)
        sources = {item["source_id"]: item for item in sources_doc["sources"]}
        try:
            result = analyze_adjudication_impact(
                _load(args.snapshot),
                sources,
                _load(args.event),
                _load(args.policy),
            )
        except ImpactValidationError as exc:
            return _emit({"valid": False, "errors": [str(exc)]})
        _write(args.output, result)
        return _emit(
            {
                "valid": True,
                "output": args.output,
                "report_id": result["report_id"],
                "summary": result["summary"],
            }
        )
    if args.command == "verify-adjudication-impact":
        sources_doc = _load(args.sources)
        sources = {item["source_id"]: item for item in sources_doc["sources"]}
        return _emit(
            verify_adjudication_impact_bundle(
                _load(args.report),
                _load(args.snapshot),
                sources,
                _load(args.event),
                _load(args.policy),
                _load(args.receipt),
                pinned_public_key=args.public_key,
                parent_snapshots=[_load(path) for path in args.parent],
            )
        )
    if args.command == "render-impact":
        sources_doc = _load(args.sources)
        sources = {item["source_id"]: item for item in sources_doc["sources"]}
        try:
            rendered = render_impact_review(
                report=_load(args.report),
                snapshot=_load(args.snapshot),
                sources=sources,
                event=_load(args.event),
                policy=_load(args.policy),
                accepted_receipt=_load(args.receipt),
                pinned_public_key=args.public_key,
                parent_snapshots=[_load(path) for path in args.parent],
                title=args.title,
            )
        except ImpactReviewError as exc:
            return _emit({"valid": False, "errors": [str(exc)]})
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        return _emit(
            {
                "valid": True,
                "output": str(output),
                "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            }
        )
    if args.command == "verify-receipt":
        sources_doc = _load(args.sources)
        sources = {item["source_id"]: item for item in sources_doc["sources"]}
        return _emit(
            verify_receipt(
                _load(args.receipt),
                _load(args.snapshot),
                sources,
                pinned_public_key=args.public_key,
                parent_snapshots=[_load(path) for path in args.parent],
            )
        )
    if args.command == "verify-projection":
        policy = _load(args.policy) if args.policy else None
        return _emit(verify_projection(_load(args.projection), policy))
    if args.command == "verify-bundle":
        sources_doc = _load(args.sources)
        sources = {item["source_id"]: item for item in sources_doc["sources"]}
        return _emit(
            verify_bundle(
                snapshot=_load(args.snapshot),
                receipt=_load(args.receipt),
                sources=sources,
                projection=_load(args.projection),
                source_disclosure=_load(args.disclosure),
                receiver_policy=_load(args.policy),
                pinned_public_key=args.public_key,
                parent_snapshots=[_load(path) for path in args.parent],
            )
        )
    if args.command == "render-review":
        sources_doc = _load(args.sources)
        sources = {item["source_id"]: item for item in sources_doc["sources"]}
        try:
            rendered = render_review(
                snapshot=_load(args.snapshot),
                receipt=_load(args.receipt),
                sources=sources,
                projection=_load(args.projection),
                source_disclosure=_load(args.disclosure),
                receiver_policy=_load(args.policy),
                pinned_public_key=args.public_key,
                parent_snapshots=[_load(path) for path in args.parent],
                title=args.title,
            )
        except ReviewRenderError as exc:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
            return 1
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(
            json.dumps(
                {
                    "valid": True,
                    "output": str(output),
                    "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    return _emit(
        verify_source_disclosure(
            _load(args.disclosure),
            _load(args.projection),
            _load(args.receipt),
        )
    )
