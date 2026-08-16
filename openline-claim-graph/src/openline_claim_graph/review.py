"""Human-readable review surfaces for verified receiver bundles.

The renderer deliberately does not infer claims, rank evidence, or decide truth.
It turns an already-built, receiver-verified projection into a static HTML review
that makes source anchors, represented conflicts, lineage, and warnings visible.
"""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

from .bundle import verify_bundle


class ReviewRenderError(ValueError):
    """Raised when an invalid bundle is presented for rendering."""


def _short(value: Any, length: int = 12) -> str:
    text = str(value)
    return text if len(text) <= length else f"{text[:length]}…"


def _source_quote(source: Mapping[str, Any], anchor: Mapping[str, Any]) -> str:
    encoded = str(source["content"]).encode("utf-8")
    span = dict(anchor["span"])
    return encoded[int(span["start"]) : int(span["end"])].decode("utf-8")


def _claim_label(index: int) -> str:
    return f"C{index + 1}"


def _warning_label(warning: str) -> str:
    if warning == "projection_does_not_prove_completeness":
        return "This is a bounded view, not proof that every relevant claim was included."
    if warning == "graph_state_receipt_authenticity_must_be_verified_separately":
        return "Source inclusion and receipt authenticity are separate checks; both ran for this review."
    if warning.startswith("semantic_mapping_unverified:"):
        return "A semantic mapping is represented but not mechanically proven: " + warning.split(":", 2)[-1]
    if warning.startswith("claim_unanchored:"):
        return "A claim has no source anchor: " + warning.split(":", 1)[-1]
    if warning.startswith("relation_unanchored:"):
        return "A relation has no source anchor: " + warning.split(":", 1)[-1]
    return warning


def render_review(
    *,
    snapshot: Mapping[str, Any],
    receipt: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
    projection: Mapping[str, Any],
    source_disclosure: Mapping[str, Any],
    receiver_policy: Mapping[str, Any],
    pinned_public_key: str,
    parent_snapshots: Sequence[Mapping[str, Any]] | None = None,
    title: str = "Decision Review",
) -> str:
    """Render one verified receiver projection as deterministic static HTML.

    Invalid bundles fail closed and produce no surface. A valid bundle may still
    be QUARANTINED when its warnings exceed receiver policy; the HTML preserves
    that disposition visibly rather than converting it into an approval.
    """

    verification = verify_bundle(
        snapshot=snapshot,
        receipt=receipt,
        sources=sources,
        projection=projection,
        source_disclosure=source_disclosure,
        receiver_policy=receiver_policy,
        pinned_public_key=pinned_public_key,
        parent_snapshots=parent_snapshots,
    )
    if not verification["valid"]:
        raise ReviewRenderError("bundle verification failed: " + ", ".join(verification["errors"]))

    entries = sorted(
        (dict(item["record"]) for item in projection.get("claims", [])),
        key=lambda item: str(item.get("claim_id", "")),
    )
    labels = {str(item["claim_id"]): _claim_label(index) for index, item in enumerate(entries)}
    claim_by_id = {str(item["claim_id"]): item for item in entries}
    relations = sorted(
        (dict(item["record"]) for item in projection.get("relations", [])),
        key=lambda item: str(item.get("relation_id", "")),
    )

    disposition = str(verification["disposition"])
    disposition_class = {
        "ADMIT": "admit",
        "QUARANTINE": "quarantine",
        "DENY": "deny",
    }.get(disposition, "quarantine")
    disposition_label = {
        "ADMIT": "BUNDLE ADMITTED",
        "QUARANTINE": "BUNDLE QUARANTINED",
        "DENY": "BUNDLE DENIED",
    }.get(disposition, disposition)

    relation_rows: list[str] = []
    for relation in relations:
        source_id = str(relation.get("source_claim_id", ""))
        target_id = str(relation.get("target_claim_id", ""))
        source_claim = claim_by_id.get(source_id, {})
        target_claim = claim_by_id.get(target_id, {})
        source_text = str(source_claim.get("text", source_id))
        target_text = str(target_claim.get("text", target_id))
        source_slot = str(source_claim.get("slot", "unscoped"))
        target_slot = str(target_claim.get("slot", "unscoped"))
        scope = source_slot if source_slot == target_slot else f"{source_slot} ↔ {target_slot}"
        relation_rows.append(
            "<li><p class='slot'>Scope: {}</p><div class='fault-line'>"
            "<div><span class='claim-ref'>{}</span><p>{}</p></div>"
            "<strong>{}</strong>"
            "<div><span class='claim-ref'>{}</span><p>{}</p></div></div></li>".format(
                escape(scope),
                escape(labels.get(source_id, _short(source_id))),
                escape(source_text),
                escape(str(relation.get("relation", "UNSPECIFIED")).replace("_", " ")),
                escape(labels.get(target_id, _short(target_id))),
                escape(target_text),
            )
        )

    claim_cards: list[str] = []
    for claim in entries:
        claim_id = str(claim["claim_id"])
        provenance = list(claim.get("provenance", []))
        anchors: list[str] = []
        for anchor in provenance:
            source_id = str(anchor.get("source_id", ""))
            source = sources.get(source_id)
            if source is None:
                continue
            quote = _source_quote(source, anchor)
            locator = str(source.get("locator", source_id))
            anchors.append(
                "<div class='anchor'><div class='anchor-meta'><span class='mode'>{}</span> "
                "<span>{}</span></div><blockquote>{}</blockquote></div>".format(
                    escape(str(anchor.get("mode", "UNKNOWN"))),
                    escape(locator),
                    escape(quote),
                )
            )
        slot = str(claim.get("slot", "unscoped"))
        kind = str(claim.get("kind", "UNSPECIFIED"))
        claim_cards.append(
            "<article class='claim-card' id='{}'><header><span class='claim-ref'>{}</span>"
            "<span class='kind'>{}</span></header><h3>{}</h3><p class='slot'>Scope: {}</p>{}</article>".format(
                escape(claim_id),
                escape(labels[claim_id]),
                escape(kind.replace("_", " ")),
                escape(str(claim.get("text", ""))),
                escape(slot),
                "".join(anchors) or "<p class='missing'>No source anchor disclosed.</p>",
            )
        )

    warning_items = "".join(
        f"<li>{escape(_warning_label(item))}</li>" for item in verification.get("warnings", [])
    ) or "<li>No warnings were emitted.</li>"
    unaccepted_items = "".join(
        f"<li>{escape(_warning_label(item))}</li>" for item in verification.get("unaccepted_warnings", [])
    ) or "<li>Every emitted warning is explicitly accepted by the receiver policy.</li>"
    parent_items = "".join(
        f"<li><code>{escape(str(root))}</code></li>" for root in snapshot.get("parent_state_roots", [])
    ) or "<li>Genesis state: no parent.</li>"

    source_sections: list[str] = []
    referenced_source_ids = sorted(
        {
            str(anchor["source_id"])
            for claim in entries
            for anchor in claim.get("provenance", [])
            if "source_id" in anchor
        }
    )
    for source_id in referenced_source_ids:
        source = sources[source_id]
        locator = str(source.get("locator", source_id))
        source_sections.append(
            "<details><summary>{}</summary><pre>{}</pre><p class='hash'>Commitment: {}</p></details>".format(
                escape(locator),
                escape(str(source.get("content", ""))),
                escape(source_id),
            )
        )

    purpose = escape(str(projection.get("purpose", "Receiver review")))
    html = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root{{--ink:#172033;--muted:#657086;--paper:#f5f6f8;--card:#fff;--line:#d9dee7;--navy:#182a50;--amber:#9a5b00;--red:#a52a2a;--green:#176b45}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1040px;margin:auto;padding:28px 18px 64px}} h1{{font-size:clamp(2rem,5vw,3.5rem);line-height:1.02;margin:.2em 0}} h2{{margin-top:2.2rem}} h3{{font-size:1.05rem;margin:.75rem 0 .25rem}} code{{font-size:.78rem;overflow-wrap:anywhere}}
.eyebrow{{text-transform:uppercase;letter-spacing:.12em;font-weight:800;color:var(--navy)}} .purpose{{font-size:1.2rem;max-width:760px;color:#39445a}}
.status{{display:inline-flex;align-items:center;gap:.5rem;border-radius:999px;padding:.5rem .8rem;font-weight:800;border:1px solid currentColor}}
.status.admit{{color:var(--green);background:#eaf7f0}} .status.quarantine{{color:var(--amber);background:#fff4dd}} .status.deny{{color:var(--red);background:#ffecec}}
.boundary,.panel{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin:18px 0;box-shadow:0 5px 18px rgba(22,34,58,.05)}}
.boundary{{border-left:6px solid var(--navy)}} .boundary strong{{display:block;margin-bottom:.35rem}}
.relations{{list-style:none;padding:0;display:grid;gap:.8rem}} .relations li{{padding:.9rem 1rem;background:#f0f3f8;border-radius:10px}} .fault-line{{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:1rem;align-items:center}} .fault-line p{{margin:.35rem 0 0}} .fault-line strong{{color:var(--red);font-size:.78rem;letter-spacing:.04em}}
.claim-ref{{font-weight:900;color:var(--navy)}} .claim-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px}}
.claim-card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;min-width:0}} .claim-card header{{display:flex;justify-content:space-between;gap:1rem}}
.kind,.mode{{font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}} .slot,.hash{{font-size:.78rem;color:var(--muted);overflow-wrap:anywhere}}
.anchor{{margin-top:1rem;border-top:1px solid var(--line);padding-top:.8rem}} .anchor-meta{{display:flex;justify-content:space-between;gap:1rem;font-size:.75rem;color:var(--muted);overflow-wrap:anywhere}}
blockquote{{margin:.5rem 0 0;padding:.75rem 1rem;border-left:4px solid #8da4d0;background:#f4f7fc}} .missing{{color:var(--red)}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}} details{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:.75rem 1rem;margin:.65rem 0}} summary{{font-weight:750;cursor:pointer}} pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}}
footer{{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--line);color:var(--muted);font-size:.82rem}}
@media(max-width:640px){{.fault-line{{grid-template-columns:1fr}}.fault-line strong{{padding:.35rem 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}}}
</style>
</head>
<body><main>
<p class="eyebrow">Receiver-owned review</p>
<h1>{title}</h1>
<p class="purpose">{purpose}</p>
<p><span class="status {disposition_class}">{disposition_label}</span></p>
<section class="boundary"><strong>What this status means</strong>{claim_boundary}</section>
<section><h2>Represented fault lines</h2><div class="panel"><ul class="relations">{relations}</ul></div></section>
<section><h2>Claims and exact source anchors</h2><div class="claim-grid">{claims}</div></section>
<section><h2>Verification limits</h2><div class="two"><div class="panel"><h3>All emitted warnings</h3><ul>{warnings}</ul></div><div class="panel"><h3>Not accepted by policy</h3><ul>{unaccepted}</ul></div></div></section>
<section><h2>Lineage</h2><div class="panel"><p>Current state: <code>{state}</code></p><p>Receipt: <code>{payload}</code></p><p>Parents:</p><ul>{parents}</ul></div></section>
<section><h2>Disclosed sources</h2>{sources}</section>
<footer>Generated from a verified OpenLine claim-graph bundle. Integrity and receiver-policy result only; not a truth, completeness, or decision-wisdom certificate.</footer>
</main></body></html>
""".format(
        title=escape(title),
        purpose=purpose,
        disposition_class=disposition_class,
        disposition=escape(disposition),
        disposition_label=escape(disposition_label),
        claim_boundary=escape(str(verification["claim_boundary"])),
        relations="".join(relation_rows) or "<li>No relation was included in this projection.</li>",
        claims="".join(claim_cards),
        warnings=warning_items,
        unaccepted=unaccepted_items,
        state=escape(str(snapshot.get("state_root", ""))),
        payload=escape(str(receipt.get("payload_hash", ""))),
        parents=parent_items,
        sources="".join(source_sections),
    )
    return html
