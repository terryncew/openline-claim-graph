"""Fail-closed, self-contained review surface for a Frame Ledger report."""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

from .frame import verify_frame_report


class FrameReviewError(ValueError):
    """Raised when a frame report cannot be reproduced before rendering."""


def _quote(source: Mapping[str, Any], finding: Mapping[str, Any]) -> str:
    anchor = finding["anchors"][0]
    span = anchor["span"]
    data = str(source["content"]).encode("utf-8")
    return data[int(span["start"]):int(span["end"])].decode("utf-8")


def _highlight(source: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]) -> str:
    data = str(source["content"]).encode("utf-8")
    ranges: list[tuple[int, int, str]] = []
    for finding in findings:
        if finding["device_type"] == "DECLARED_TERM_SET_ABSENCE":
            continue
        anchor = finding["anchors"][0]
        start, end = int(anchor["span"]["start"]), int(anchor["span"]["end"])
        ranges.append((start, end, str(finding["device_type"])))
    accepted: list[tuple[int, int, str]] = []
    for item in sorted(ranges, key=lambda value: (value[0], value[1] - value[0])):
        if any(item[0] < other[1] and other[0] < item[1] for other in accepted):
            continue
        accepted.append(item)
    cursor = 0
    pieces: list[str] = []
    for start, end, device in sorted(accepted):
        pieces.append(escape(data[cursor:start].decode("utf-8")))
        pieces.append(
            f'<mark class="device" title="{escape(device)}">'
            f'{escape(data[start:end].decode("utf-8"))}</mark>'
        )
        cursor = end
    pieces.append(escape(data[cursor:].decode("utf-8")))
    return "".join(pieces)


def _finding_cards(
    rows: Sequence[Mapping[str, Any]],
    findings: Mapping[str, Mapping[str, Any]],
    source: Mapping[str, Any],
    css_class: str,
) -> str:
    if not rows:
        return '<p class="empty">None.</p>'
    cards: list[str] = []
    for row in rows:
        finding = findings[str(row["finding_id"])]
        parameters = dict(finding.get("parameters", {}))
        if finding["device_type"] == "DECLARED_TERM_SET_ABSENCE":
            evidence = " · ".join(str(item) for item in parameters.get("terms", []))
            evidence_label = "Declared terms absent from this surface"
        else:
            evidence = _quote(source, finding)
            evidence_label = "Exact anchored span"
        extra = ""
        if "confirmations" in row:
            extra = (
                f'<p class="quorum">{int(row["confirmations"])} confirmations · '
                f'{int(row["distinct_confirming_families"])} declared model families · '
                f'{int(row["challenges"])} challenges</p>'
            )
        cards.append(
            f'<article class="finding {css_class}">'
            f'<div class="tag">{escape(str(row["disposition"]))}</div>'
            f'<h3>{escape(str(finding["device_type"]).replace("_", " "))}</h3>'
            f'<p>{escape(str(finding["observation"]))}</p>'
            f'<div class="evidence"><b>{escape(evidence_label)}</b><q>{escape(evidence)}</q></div>'
            f'{extra}<code>{escape(str(finding["finding_id"]))}</code></article>'
        )
    return "".join(cards)


def render_frame_ledger(
    *,
    report: Mapping[str, Any],
    source: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    finding_attestations: Sequence[Mapping[str, Any]] = (),
    reviews: Sequence[Mapping[str, Any]] = (),
    review_attestations: Sequence[Mapping[str, Any]] = (),
    title: str = "Frame Ledger",
) -> str:
    verification = verify_frame_report(
        report,
        source,
        findings,
        policy,
        finding_attestations=finding_attestations,
        reviews=reviews,
        review_attestations=review_attestations,
    )
    if not verification["valid"]:
        raise FrameReviewError("frame report verification failed: " + ", ".join(verification["errors"]))

    by_id = {str(item["finding_id"]): item for item in findings}
    classifications = report["classifications"]
    established_findings = [by_id[str(row["finding_id"])] for row in classifications["established"]]
    headline = _highlight(source, established_findings)
    summary = report["summary"]
    human_label = {
        "OPTIONAL": "optional by receiver policy",
        "REQUIRED": "required by receiver policy",
        "DISABLED": "not part of this receiver policy",
    }[str(policy["human_mode"])]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>
:root{{--ink:#131a28;--muted:#697181;--paper:#f4f6f9;--line:#dce1e8;--blue:#2359c4;--cyan:#dff6ff;
--green:#15704a;--green-bg:#edf9f3;--amber:#8a5b00;--amber-bg:#fff7df;--red:#a52c35;--red-bg:#fff0f1}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}}
main{{max-width:1000px;margin:auto;padding:42px 20px 80px}} .status{{display:inline-flex;gap:8px;align-items:center;padding:7px 11px;border-radius:999px;background:var(--green-bg);color:var(--green);font-size:11px;font-weight:900;letter-spacing:.07em}}
h1{{font-size:clamp(38px,7vw,68px);line-height:.95;margin:18px 0 12px;letter-spacing:-.045em}} .lede{{font-size:20px;max-width:790px;color:var(--muted)}}
.surface{{margin:32px 0;padding:26px;border-radius:18px;background:#0e1420;color:white;box-shadow:0 18px 45px rgba(15,22,35,.18)}}
.surface .label,.tag{{font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}} .headline{{font:700 clamp(25px,4vw,42px)/1.22 Georgia,serif;margin:14px 0}}
mark.device{{background:#7ee0ff;color:#0d1721;border-radius:4px;padding:1px 3px}} .locator{{font-size:12px;color:#aeb8c9;overflow-wrap:anywhere}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px;margin:24px 0}} .metric,.panel,.finding{{background:white;border:1px solid var(--line);border-radius:14px;box-shadow:0 5px 18px rgba(25,32,47,.04)}}
.metric{{padding:18px}} .metric b{{font-size:34px;display:block}} .metric span{{font-size:12px;color:var(--muted)}} h2{{margin:36px 0 12px;font-size:24px}}
.finding{{padding:19px;margin:11px 0;border-left:5px solid #9ba4b4}} .finding.established{{border-left-color:var(--green);background:var(--green-bg)}}
.finding.advisory{{border-left-color:var(--amber);background:var(--amber-bg)}} .finding.blocked{{border-left-color:var(--red);background:var(--red-bg)}}
.finding h3{{margin:5px 0 7px;font-size:18px}} .finding p{{margin:0 0 10px;color:var(--muted)}} .evidence{{background:rgba(255,255,255,.7);border-radius:9px;padding:10px 12px}}
.evidence b{{display:block;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}} q{{display:block;margin-top:4px;font-family:ui-monospace,SFMono-Regular,monospace;font-size:13px}}
code{{display:block;margin-top:9px;font-size:9px;color:var(--muted);overflow-wrap:anywhere}} .panel{{padding:22px;margin:18px 0}} table{{border-collapse:collapse;width:100%}} th,td{{padding:11px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
.boundary{{border:2px solid var(--ink)}} .empty{{color:var(--muted)}} .quorum{{font-weight:700}}
</style></head><body><main>
<span class="status">REPRODUCED FROM EXACT BYTES · NOT A BIAS OR TRUTH VERDICT</span>
<h1>{escape(title)}</h1>
<p class="lede">This ledger separates what the audited surface literally does from what a model or reader may infer about it. The receiver—not the proposer—owns admission.</p>
<section class="surface"><div class="label">Audited surface · headline only</div><div class="headline">{headline}</div><div class="locator">{escape(str(source.get("locator", source["source_id"])))}</div></section>
<div class="metrics"><div class="metric"><b>{summary['established']}</b><span>mechanical devices established</span></div><div class="metric"><b>{summary['advisory']}</b><span>semantic findings admitted as advisory</span></div><div class="metric"><b>{summary['blocked']}</b><span>blocked by challenge</span></div><div class="metric"><b>{summary['unadmitted']}</b><span>not admitted</span></div></div>
<h2>Mechanically established</h2>{_finding_cards(classifications['established'],by_id,source,'established')}
<h2>Advisory interpretations admitted under receiver policy</h2>{_finding_cards(classifications['advisory'],by_id,source,'advisory')}
<h2>Blocked or not admitted</h2>{_finding_cards(classifications['blocked'],by_id,source,'blocked')}{_finding_cards(classifications['unadmitted'],by_id,source,'')}
<section class="panel"><h2>Autonomy contract</h2><table>
<tr><th>Mechanical layer</th><td>{'auto-admitted after deterministic reproduction' if policy['mechanical_auto_admit'] else 'requires separate admission'}</td></tr>
<tr><th>Semantic layer</th><td>{int(policy['advisory_min_confirmations'])} signed confirmations from {int(policy['advisory_min_distinct_families'])} declared model families; {'any challenge blocks' if policy['challenge_blocks'] else 'challenges are recorded but do not automatically block'}</td></tr>
<tr><th>Human confirmation</th><td>{escape(human_label)}</td></tr>
<tr><th>Self-approval</th><td>forbidden; a proposer cannot review its own finding</td></tr>
</table></section>
<section class="panel boundary"><h2>What this page refuses to launder</h2><table><tr><th>Established</th><th>Not established</th></tr>
<tr><td>Exact words, local grammar matches, declared term-set absences, source bytes, ruleset, policy, and report reproduction.</td><td>Whether the underlying statements were false; whether anyone lied; author intent; fairness; rationalization; propaganda; completeness of the article; or effects on readers.</td></tr>
<tr><td>A semantic finding may be admitted only under the displayed receiver policy.</td><td>That two model names imply genuine epistemic independence, or that reviewer agreement makes an interpretation true.</td></tr></table>
<p>{escape(str(report['claim_boundary']))}</p></section>
<p class="locator">Source: {escape(str(report['source_id']))}<br>Ruleset: {escape(str(report['ruleset_hash']))}<br>Policy: {escape(str(report['policy_id']))}<br>Report: {escape(str(report['report_id']))}</p>
</main></body></html>"""
