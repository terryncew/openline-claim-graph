"""Fail-closed human surface for a verified claim-impact report."""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

from .impact import verify_impact_bundle


class ImpactReviewError(ValueError):
    """Raised when an impact report cannot be verified before rendering."""


def _short(value: str, length: int = 16) -> str:
    return value if len(value) <= length else value[:length] + "…"


def _path_text(path: Mapping[str, Any] | None, claims: Mapping[str, Mapping[str, Any]]) -> str:
    if not path:
        return "No reproducible witness path."
    origin = str(path["origin_claim_id"])
    pieces = [str(claims.get(origin, {}).get("text", origin))]
    for step in path.get("steps", []):
        authority = f" [{step['authority']}]" if "authority" in step else ""
        target = str(step["to_claim_id"])
        pieces.append(
            f"{step['relation']}{authority} → {claims.get(target, {}).get('text', target)}"
        )
    return " → ".join(pieces) if pieces else "Direct source exposure."


def _cards(items: list[Mapping[str, Any]], css_class: str, claims: Mapping[str, Mapping[str, Any]]) -> str:
    if not items:
        return '<p class="empty">None.</p>'
    rendered = []
    for item in items:
        details = ""
        if item.get("witness_path") is not None:
            details = f'<div class="path"><strong>Path</strong> {escape(_path_text(item["witness_path"], claims))}</div>'
        retained = item.get("retained_support_claim_ids", [])
        if retained:
            retained_text = "; ".join(str(claims.get(value, {}).get("text", value)) for value in retained)
            details += f'<div class="path"><strong>Retained support</strong> {escape(retained_text)}</div>'
        rendered.append(
            f'<article class="claim {css_class}">'
            f'<div class="eyebrow">{escape(str(item.get("classification", "UNAFFECTED")))}</div>'
            f'<h3>{escape(str(item["text"]))}</h3>'
            f'<p>{escape(str(item.get("reason", "No event path reaches this claim.")))}</p>'
            f'{details}<code>{escape(str(item["claim_id"]))}</code></article>'
        )
    return "".join(rendered)


def render_impact_review(
    *,
    report: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    event: Mapping[str, Any],
    policy: Mapping[str, Any],
    accepted_receipt: Mapping[str, Any],
    pinned_public_key: str,
    parent_snapshots: Sequence[Mapping[str, Any]] | None = None,
    title: str = "Evidence Recall",
) -> str:
    verification = verify_impact_bundle(
        report,
        snapshot,
        sources,
        event,
        policy,
        accepted_receipt,
        pinned_public_key=pinned_public_key,
        parent_snapshots=parent_snapshots,
    )
    if not verification["valid"]:
        raise ImpactReviewError("impact report verification failed: " + ", ".join(verification["errors"]))

    claims = {str(item["claim_id"]): item for item in snapshot.get("claims", [])}
    evidence_quotes = []
    for anchor in event.get("evidence", []):
        source = sources[str(anchor["source_id"])]
        encoded = str(source["content"]).encode("utf-8")
        start, end = int(anchor["span"]["start"]), int(anchor["span"]["end"])
        quote = encoded[start:end].decode("utf-8")
        evidence_quotes.append(
            {
                "quote": quote,
                "locator": str(source.get("locator", source["source_id"])),
            }
        )
    evidence_html = "".join(
        f'<blockquote>{escape(item["quote"])}<cite>{escape(item["locator"])}</cite></blockquote>'
        for item in evidence_quotes
    )
    summary = report["summary"]
    classifications = report["classifications"]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
:root {{ color-scheme: light; --ink:#172033; --muted:#5b6475; --line:#dfe4ec; --paper:#f6f8fb;
--red:#a8292f; --red-bg:#fff1f1; --amber:#8a5b00; --amber-bg:#fff8e6; --green:#176a44;
--green-bg:#edf9f2; --blue:#1e5ca8; }}
* {{ box-sizing:border-box }} body {{ margin:0; font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;
background:var(--paper); color:var(--ink); line-height:1.45 }} main {{ max-width:980px; margin:auto; padding:44px 22px 80px }}
.status {{ display:inline-block; padding:6px 10px; border-radius:999px; color:var(--green); background:var(--green-bg);
font-size:12px; font-weight:800; letter-spacing:.06em }} h1 {{ margin:14px 0 6px; font-size:clamp(32px,5vw,54px); line-height:1.02 }}
.lede {{ max-width:760px; font-size:19px; color:var(--muted) }} .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:12px; margin:28px 0 }}
.metric,.panel,.claim {{ background:white; border:1px solid var(--line); border-radius:14px; box-shadow:0 5px 18px rgba(28,39,61,.04) }}
.metric {{ padding:18px }} .metric b {{ display:block; font-size:34px }} .metric span {{ color:var(--muted); font-size:13px }}
.panel {{ padding:22px; margin:18px 0 }} h2 {{ margin:38px 0 12px; font-size:24px }} blockquote {{ margin:10px 0; padding:16px 18px; background:#f1f5fb; border-left:4px solid var(--blue); border-radius:8px }}
cite {{ display:block; margin-top:8px; font-size:12px; color:var(--muted); overflow-wrap:anywhere }} .claim {{ padding:18px; margin:10px 0; border-left-width:5px }}
.claim h3 {{ margin:5px 0 6px; font-size:17px }} .claim p {{ margin:0 0 8px; color:var(--muted) }} .quarantine {{ border-left-color:var(--red); background:var(--red-bg) }}
.survives {{ border-left-color:var(--green); background:var(--green-bg) }} .review {{ border-left-color:var(--amber); background:var(--amber-bg) }}
.unaffected {{ border-left-color:#9aa3b2 }} .eyebrow {{ font-size:11px; letter-spacing:.08em; font-weight:800 }} .path {{ padding:10px 0; font-size:13px }}
code {{ display:block; color:var(--muted); font-size:10px; overflow-wrap:anywhere }} table {{ width:100%; border-collapse:collapse }} th,td {{ text-align:left; padding:10px; border-bottom:1px solid var(--line); vertical-align:top }}
.boundary {{ border:2px solid var(--ink) }} .ids {{ font-size:11px; overflow-wrap:anywhere; color:var(--muted) }} .empty {{ color:var(--muted) }}
</style>
</head>
<body><main>
<span class="status">STATE RECEIPT + IMPACT REPRODUCED · NOT A TRUTH VERDICT</span>
<h1>{escape(title)}</h1>
<p class="lede">Something in the accepted evidence changed. This page shows the exact downstream exposure implied by the receiver-admitted graph—and what remains supported.</p>
<div class="grid">
  <div class="metric"><b>{summary['source_exposed']}</b><span>direct source claims exposed</span></div>
  <div class="metric"><b>{summary['quarantine']}</b><span>proposed for quarantine</span></div>
  <div class="metric"><b>{summary['survives']}</b><span>admitted support remains</span></div>
  <div class="metric"><b>{summary['affected_unresolved']}</b><span>requires review</span></div>
  <div class="metric"><b>{summary['decisions_touched']}</b><span>accepted decisions touched</span></div>
</div>
<section class="panel"><h2>Admitted source-status event</h2><p><strong>{escape(str(event['status']))}</strong> · {escape(str(event['reason']))}</p>{evidence_html}</section>
<h2>Proposed quarantine</h2>{_cards(classifications['quarantine'], 'quarantine', claims)}
<h2>Survives on an admitted alternative basis</h2>{_cards(classifications['survives'], 'survives', claims)}
<h2>Affected, unresolved</h2>{_cards(classifications['affected_unresolved'], 'review', claims)}
<h2>Not reached by this event</h2>{_cards(classifications['unaffected'], 'unaffected', claims)}
<section class="panel boundary"><h2>What the green status means</h2>
<table><tr><th>Established</th><th>Not established</th></tr>
<tr><td>The report exactly reproduces from the committed state, event, and receiver policy.</td><td>The claims, edges, event scope, or sources are true or complete.</td></tr>
<tr><td>Hard and advisory edges were kept separate during propagation.</td><td>The receiver should automatically change its accepted state.</td></tr>
<tr><td>No accepted graph mutation occurred.</td><td>Market value, extraction accuracy, or decision improvement.</td></tr></table>
<p>{escape(str(report['claim_boundary']))}</p></section>
<p class="ids">Accepted state: {escape(str(report['accepted_state_root']))}<br>Event: {escape(str(report['event_id']))}<br>Policy: {escape(str(report['policy_id']))}<br>Report: {escape(str(report['report_id']))}</p>
</main></body></html>"""
