"""Local Assessment Recall example. Public test keys: never use for deployment."""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path
from time import perf_counter_ns

from openline_claim_graph import (
    analyze_source_impact, build_source, create_claim, create_impact_policy,
    create_relation, create_snapshot, create_source_status_event,
    private_key_from_hex, provenance_anchor, public_key_hex, sign_snapshot,
    verify_receipt, verify_impact_bundle,
)
from openline_claim_graph.canonical import hash_object

TIME = "2026-10-17T00:00:00Z"
# Deliberately public fixture identities. Pins are application trust, not supplied by packets.
KEYS = {role: private_key_from_hex(seed * 32) for role, seed in
        (("evaluator", "11"), ("developer", "22"), ("receiver", "33"))}
PINS = {role: public_key_hex(key) for role, key in KEYS.items()}


def signed(record, role):
    source = build_source(json.dumps(record, sort_keys=True), locator=f"example:{role}")
    claim = create_claim(kind="SOURCE_ASSERTION", text=source["content"], asserted_by=role,
                         provenance=[provenance_anchor(source, source["content"],
                                                       mode="QUOTE", asserted_by=role)])
    snapshot = create_snapshot(claims=[claim], relations=[])
    sources = {source["source_id"]: source}
    receipt = sign_snapshot(snapshot, sources, private_key=KEYS[role], issuer=role,
                            issued_at=TIME, parent_snapshots=[])
    return dict(record=record, snapshot=snapshot, sources=sources, receipt=receipt)


def read(packet, role):
    check = verify_receipt(packet["receipt"], packet["snapshot"], packet["sources"],
                           pinned_public_key=PINS[role], parent_snapshots=[])
    if not check["valid"] or packet["receipt"]["issuer"] != role:
        raise ValueError(f"untrusted {role} record")
    text = json.dumps(packet["record"], sort_keys=True)
    if len(packet["sources"]) != 1 or next(iter(packet["sources"].values()))["content"] != text:
        raise ValueError("record not bound to receipt")
    return packet["record"]


def fixture(variant="relevant"):
    config = {"model": "synthetic-assistant-v1", "tool": "payments-v1",
              "safeguard": "human-confirmation-required", "conditions": "sandbox-only"}
    assessment = {"configuration": config, "configuration_hash": hash_object(config),
                  "scope": "payments confirmation in sandbox", "finding": "bounded test passed",
                  "limitations": "No production or general safety conclusion"}
    # A distinct, independently sufficient basis for the offline approval.
    offline = {"scope": "offline export", "finding": "no tool invocation permitted",
               "configuration": {"model": "synthetic-assistant-v1", "tool": "disabled"}}
    deps = {"payments": ["assessment"], "offline-export": ["assessment", "offline"]}
    if variant == "missing":
        deps["payments"] = []
    acceptance = {"approver": "enterprise:risk-owner", "dependencies": deps,
                  "evidence": {"assessment": hash_object(assessment), "offline": hash_object(offline)},
                  "complete": {"payments": variant != "missing", "offline-export": True},
                  "rule": "each listed basis is independently sufficient for this decision",
                  "status": {"payments": "APPROVED", "offline-export": "APPROVED"}}
    change = {"old_configuration_hash": hash_object(config),
              "new_configuration": {**config, "safeguard": "confirmation-removed"},
              "changed_field": "safeguard", "semantic_claim": "confirmation assumption no longer holds"}
    if variant == "unrelated":
        change["changed_field"] = "display_name"
        change["new_configuration"] = {**config, "display_name": "new label"}
        change["semantic_claim"] = "label only; evaluated controls unchanged"
    if variant == "ambiguous":
        change["semantic_claim"] = "operational meaning unknown"
    admission = {"change_hash": hash_object(change),
                 "affected_basis": [] if variant == "unrelated" else ["assessment"],
                 "meaning": "UNKNOWN" if variant == "ambiguous" else "ADMITTED",
                 "rationale": "Receiver judges scope against its accepted assumptions; developer cannot decide this."}
    return {"assessment": signed(assessment, "evaluator"), "offline": signed(offline, "evaluator"),
            "configuration": signed(config, "developer"), "acceptance": signed(acceptance, "receiver"),
            "change": signed(change, "developer"), "admission": signed(admission, "receiver")}


def inputs(packets):
    roles = {"assessment": "evaluator", "offline": "evaluator", "configuration": "developer",
             "acceptance": "receiver", "change": "developer", "admission": "receiver"}
    records = {name: read(packets[name], role) for name, role in roles.items()}
    a, c, change = records["assessment"], records["configuration"], records["change"]
    accept, admission = records["acceptance"], records["admission"]
    if (a["configuration"] != c or a["configuration_hash"] != hash_object(c)
            or change["old_configuration_hash"] != hash_object(c)
            or admission["change_hash"] != hash_object(change)):
        raise ValueError("configuration/change binding mismatch")
    if set(accept["dependencies"]) != {"payments", "offline-export"}:
        raise ValueError("decision inventory mismatch")
    for name in ("assessment", "offline"):
        if accept["evidence"][name] != hash_object(records[name]):
            raise ValueError("historical evidence binding mismatch")
    if not set(admission["affected_basis"]) <= {"assessment", "offline"}:
        raise ValueError("unknown event scope")
    if accept["approver"] != "enterprise:risk-owner":
        raise ValueError("unauthorized approver")
    return records


def conventional(records):
    """Flat table comparator, no calls to OpenLine impact analysis."""
    accept, admission = records["acceptance"], records["admission"]
    lost = set(admission["affected_basis"])
    statuses, scans = {}, 0
    for decision, bases in accept["dependencies"].items():
        scans += len(bases)
        if not accept["complete"][decision] or not bases or admission["meaning"] != "ADMITTED":
            statuses[decision] = "REVIEW REQUIRED"
        elif set(bases) - lost:
            statuses[decision] = "APPROVED"
        else:
            statuses[decision] = "REVIEW REQUIRED"
    return statuses, scans


def graph(records):
    sources, claims, basis = {}, [], {}
    for name in ("assessment", "offline"):
        s = build_source(json.dumps(records[name], sort_keys=True), locator=f"example:{name}")
        sources[s["source_id"]] = s
        claim = create_claim(kind="SOURCE_ASSERTION", text=s["content"], asserted_by="evaluator",
                             provenance=[provenance_anchor(s, s["content"], mode="QUOTE", asserted_by="evaluator")])
        claims.append(claim)
        basis[name] = (claim, s)
    decisions, relations = {}, []
    for decision, bases in records["acceptance"]["dependencies"].items():
        claim = create_claim(kind="ASSUMPTION", text=f"Enterprise approval: {decision}", asserted_by="receiver")
        claims.append(claim)
        decisions[decision] = claim["claim_id"]
        for name in bases:
            if name not in basis:
                raise ValueError("unknown dependency")
            relations.append(create_relation(source_claim_id=basis[name][0]["claim_id"],
                                             target_claim_id=claim["claim_id"], relation="SUPPORTS", asserted_by="receiver"))
    snapshot = create_snapshot(claims=claims, relations=relations)
    policy = create_impact_policy(snapshot, hard_relation_ids=[r["relation_id"] for r in relations],
                                  decision_claim_ids=decisions.values())
    # No event for an admitted unrelated change: preserve initial accepted state.
    affected = records["admission"]["affected_basis"]
    report = event = None
    statuses = {d: "APPROVED" for d in decisions}
    if affected:
        notice = build_source(json.dumps(records["admission"], sort_keys=True), locator="example:receiver-admission")
        sources[notice["source_id"]] = notice
        event = create_source_status_event(status="SUPERSEDED",
            affected=[{"source_id": basis[name][1]["source_id"]} for name in affected],
            evidence=[provenance_anchor(notice, notice["content"], mode="QUOTE", asserted_by="receiver")],
            asserted_by="receiver", effective_at=TIME,
            reason="Receiver withdraws applicability of old assessment to changed configuration, not its historical finding.")
        report = analyze_source_impact(snapshot, sources, event, policy)
        review = {e["claim_id"] for category in ("quarantine", "affected_unresolved")
                  for e in report["classifications"][category]}
        statuses = {d: "REVIEW REQUIRED" if cid in review else "APPROVED" for d, cid in decisions.items()}
    # Explicit application completeness gate; the engine cannot discover omitted dependencies.
    for d, bases in records["acceptance"]["dependencies"].items():
        if not records["acceptance"]["complete"][d] or not bases or records["admission"]["meaning"] != "ADMITTED":
            statuses[d] = "REVIEW REQUIRED"
    receipt = sign_snapshot(snapshot, sources, private_key=KEYS["receiver"], issuer="receiver",
                            issued_at=TIME, parent_snapshots=[])
    if report:
        check = verify_impact_bundle(report, snapshot, sources, event, policy, receipt,
                                     pinned_public_key=PINS["receiver"], parent_snapshots=[])
        if not check["valid"]:
            raise ValueError(check["errors"])
    return statuses, dict(snapshot=snapshot, sources=sources, policy=policy, event=event,
                          report=report, receipt=receipt, decision_ids=decisions)


def execute(packets):
    records = inputs(packets)
    start = perf_counter_ns()
    baseline, scans = conventional(records)
    baseline_ns = perf_counter_ns() - start
    start = perf_counter_ns()
    statuses, evidence = graph(records)
    graph_ns = perf_counter_ns() - start
    checkpoint = hash_object(packets)
    decision_record = {"checkpoint": checkpoint, "statuses": statuses,
                       "next_authority": "enterprise:risk-owner", "event": hash_object(records["change"]),
                       "original_approval": hash_object(records["acceptance"]),
                       "kind": "review-status; not new deployment authorization"}
    return {"packets": packets, "graph": evidence, "current": signed(decision_record, "receiver"),
            "baseline": {"statuses": baseline, "dependency_rows_scanned": scans,
                         "audit": [hash_object(records["acceptance"]), hash_object(records["change"]),
                                   hash_object(records["admission"]), hash_object(decision_record)]},
            "measurements": {"baseline_ns": baseline_ns, "graph_build_sign_replay_ns": graph_ns}}


def verify(bundle, expected_checkpoint):
    current = read(bundle["current"], "receiver")
    if current["checkpoint"] != expected_checkpoint or hash_object(bundle["packets"]) != expected_checkpoint:
        raise ValueError("stale or substituted receiver checkpoint")
    replay = execute(bundle["packets"])
    if current != replay["current"]["record"]:
        raise ValueError("decision record differs from replay")
    if bundle["graph"] != replay["graph"] or bundle["baseline"] != replay["baseline"]:
        raise ValueError("protected output differs from replay")
    return current


def authorize(bundle, checkpoint, actor):
    current = verify(bundle, checkpoint)
    if actor != "receiver":
        raise ValueError("only enterprise decision maker can authorize")
    if "REVIEW REQUIRED" in current["statuses"].values():
        raise ValueError("fresh evidence and a new receiver decision are required; historical approval cannot be replayed")
    return signed({"checkpoint": checkpoint, "authorization": "continued use within accepted scope"}, "receiver")


def page(bundle):
    records = inputs(bundle["packets"])
    current = bundle["current"]["record"]
    esc = lambda x: html.escape(json.dumps(x, indent=2, sort_keys=True))
    sections = [("Original bounded evaluation and exact configuration", records["assessment"]),
                ("Enterprise acceptance and independently sufficient bases", records["acceptance"]),
                ("Authenticated developer change: recorded fact and semantic assertion", records["change"]),
                ("Receiver's separate scope judgment", records["admission"]),
                ("Current approval review record", current),
                ("Matched conventional result", bundle["baseline"])]
    return """<!doctype html><html lang="en"><meta charset="utf-8"><title>Assessment Recall review</title>
<style>body{font:18px system-ui;max-width:960px;margin:3rem auto;padding:1rem;line-height:1.5}pre{white-space:pre-wrap;background:#f3f5f7;padding:1rem}h2{margin-top:2rem}</style>
<h1>Payments approval requires enterprise review</h1>
<p>The accepted payments assessment applied to a sandbox configuration requiring human confirmation.
The developer reports that safeguard was removed. The receiver admitted this change as relevant.
The old assessment remains a valid historical record; its applicability to this changed deployment requires review.</p>
<p><strong>This does not prove the system is unsafe.</strong> Operational impact is asserted, not independently tested here.
Only <strong>enterprise:risk-owner</strong> can approve continued use after fresh review.</p>
<p>The offline-export approval retains the separately accepted no-tool basis. That basis does not depend on the changed safeguard.
Both approvals had sufficient support before the change.</p>
<p>Missing dependencies or ambiguous meaning require review. Undeclared dependencies falsely marked complete remain undetectable.
All identities and findings in this page are synthetic.</p>
<p><a href="bundle.json">Evidence bundle</a> · <a href="checkpoint.json">Receiver checkpoint</a> · <a href="comparison.json">Comparison</a></p>
<p>Verify: <code>python examples/assessment_recall/verify.py --output OUTPUT --checkpoint OUTPUT/checkpoint.json</code>.
Obtain the current checkpoint separately from the enterprise; a bundled checkpoint alone cannot establish freshness.</p>
""" + "".join(f"<h2>{html.escape(title)}</h2><pre>{esc(value)}</pre>" for title, value in sections) + "</html>"


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}
    for variant in ("relevant", "unrelated", "missing", "ambiguous"):
        bundle = execute(fixture(variant))
        verify(bundle, hash_object(bundle["packets"]))
        expected = {"payments": "APPROVED" if variant == "unrelated" else "REVIEW REQUIRED",
                    "offline-export": "REVIEW REQUIRED" if variant == "ambiguous" else "APPROVED"}
        actual = bundle["current"]["record"]["statuses"]
        if actual != expected or bundle["baseline"]["statuses"] != expected:
            raise ValueError(f"comparison failed: {variant}")
        results[variant] = dict(expected=expected, openline=actual, conventional=bundle["baseline"]["statuses"],
                                measurements=bundle["measurements"], dependency_rows=bundle["baseline"]["dependency_rows_scanned"])
        write(args.output / f"{variant}.json", bundle)
    bundle = execute(fixture())
    write(args.output / "bundle.json", bundle)
    write(args.output / "checkpoint.json", {"checkpoint": hash_object(bundle["packets"])})
    write(args.output / "comparison.json", {"verdict": "PARITY", "cases": results,
        "scored_dispositions": 8, "missed_warranted_reviews": {"openline": 0, "conventional": 0},
        "unnecessary_reviews": {"openline": 0, "conventional": 0},
        "human_capture_time": "NOT MEASURED", "human_review_time": "NOT MEASURED",
        "limitations": "Synthetic author-known labels, not independent gold; no productivity or distinctiveness claim."})
    (args.output / "review.html").write_text(page(bundle))
    print("PARITY: 8/8 dispositions each; bundle and review.html written")


if __name__ == "__main__":
    main()
