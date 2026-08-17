from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from collections import deque
from pathlib import Path
from typing import Any

FROZEN_ENGINE_SHA256 = {
    "src/openline_claim_graph/temporal_holdout.py": "bc8f0011d65cb1c2c728ef374ebb82b86c3c08657e9919427ff5d80b2707886a",
    "src/openline_claim_graph/comparative_benchmark.py": "6c04e9e021cbc1c01aae78606acc6cd41393c99673185e1e8e3ee4ccaa06e4b1",
    "src/openline_claim_graph/impact.py": "1757340f69e919ff68d3cdfe4265fc1ac330bc99ff5bcd20b69058fa846905a2",
}


def normalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        raise ValueError("float forbidden")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", str(k)): normalize(v) for k, v in value.items()}
    raise TypeError(type(value).__name__)


def canonical_json(value: Any) -> bytes:
    return json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def hash_object(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def content_id(namespace: str, value: Any) -> str:
    return f"{namespace}:sha256:{hash_object(value)}"


def without_id(value: dict, field: str) -> dict:
    body = dict(value)
    body.pop(field, None)
    return body


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def reachable(episode: dict) -> set[str]:
    adjacency: dict[str, list[str]] = {}
    for edge in episode["edges"]:
        adjacency.setdefault(edge["prerequisite_node_id"], []).append(edge["dependent_node_id"])
    origin = episode["invalidated_node_id"]
    seen = {origin}
    queue = deque([origin])
    while queue:
        cur = queue.popleft()
        for nxt in adjacency.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen - {origin}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    artifact = Path(args.artifact)
    root = Path(__file__).resolve().parents[1]

    pack = load(artifact / "pack.json")
    authority = load(artifact / "authority.json")
    seal = load(artifact / "future-seal.private.json")
    gold = load(artifact / "gold.private.json")
    predictions = load(artifact / "predictions.json")
    score = load(artifact / "score.json")
    policy = load(artifact / "promotion-policy.json")
    result = load(artifact / "promotion-result.json")
    episode_metrics = load(artifact / "episode-metrics.json")
    ledger = load(artifact / "target-ledger.json")
    custody = load(artifact / "custody.json")
    summary = load(artifact / "summary.json")
    kataoka = load(artifact / "source-evidence/kataoka-case-level-admission.json")
    card = (artifact / "POINT_BECAUSE_BUT_SO.md").read_text(encoding="utf-8")

    checks: list[dict[str, Any]] = []
    def check(name: str, ok: bool, detail: Any = None):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    check("status", summary["status"] == "TEMPORAL_SELECTIVITY_REPLICATION_PROMOTED", summary["status"])
    check("episode_count", len(pack["episodes"]) == 5)
    check("target_count", summary["scored_targets"] == 14)
    check("gold_mix", summary["reopen_gold"] == 8 and summary["no_reopen_gold"] == 6)
    check("kataoka_zero_rows", kataoka["scored_rows_admitted"] == 0)
    check("kataoka_no_synthetic_rows", "not" in kataoka["reason"].lower() or "No rows" in kataoka["reason"])

    check("pack_id", pack["pack_id"] == content_id("evidence-recall-temporal-pack", without_id(pack, "pack_id")))
    check("authority_id", authority["authority_id"] == content_id("evidence-recall-temporal-authority", without_id(authority, "authority_id")))
    check("seal_id", seal["future_seal_id"] == content_id("evidence-recall-temporal-future-seal", without_id(seal, "future_seal_id")))
    check("gold_id", gold["gold_id"] == content_id("evidence-recall-temporal-gold", without_id(gold, "gold_id")))
    check("predictions_id", predictions["predictions_id"] == content_id("evidence-recall-temporal-predictions", without_id(predictions, "predictions_id")))
    check("score_id", score["score_id"] == content_id("evidence-recall-temporal-score", without_id(score, "score_id")))
    check("policy_id", policy["promotion_policy_id"] == content_id("temporal-replication-promotion-policy", without_id(policy, "promotion_policy_id")))
    result_body = dict(result); result_id = result_body.pop("promotion_result_id")
    check("result_id", result_id == content_id("temporal-replication-promotion-result", result_body))
    metrics_body = dict(episode_metrics); metrics_id = metrics_body.pop("episode_metrics_id")
    check("episode_metrics_id", metrics_id == content_id("temporal-selectivity-episode-metrics", metrics_body))
    ledger_body = dict(ledger); ledger_id = ledger_body.pop("target_ledger_id")
    check("ledger_id", ledger_id == content_id("temporal-selectivity-target-ledger", ledger_body))

    check("pack_seal_binding", pack["future_seal_commitment"]["future_seal_id"] == seal["future_seal_id"])
    records_root = hashlib.sha256("\n".join(item["record_id"] for item in seal["records"]).encode()).hexdigest()
    check("records_root", pack["future_seal_commitment"]["records_root"] == records_root)
    check("record_count", pack["future_seal_commitment"]["record_count"] == len(seal["records"]))
    check("authority_pack_binding", authority["pack_id"] == pack["pack_id"])
    check("gold_pack_binding", gold["pack_id"] == pack["pack_id"])
    check("gold_seal_binding", gold["future_seal_id"] == seal["future_seal_id"])
    check("prediction_pack_binding", predictions["pack_id"] == pack["pack_id"])
    check("prediction_authority_binding", predictions["authority_id"] == authority["authority_id"])
    check("score_gold_binding", score["gold_id"] == gold["gold_id"])
    check("score_prediction_binding", score["predictions_id"] == predictions["predictions_id"])

    for ep in pack["episodes"]:
        check(f"cutoff_before_event:{ep['episode_id'][-12:]}", ep["cutoff_at"] < ep["event_at"])
        check(f"nodes_pre_cutoff:{ep['episode_id'][-12:]}", all(n["available_at"] <= ep["cutoff_at"] for n in ep["nodes"]))
        check(f"edges_pre_cutoff:{ep['episode_id'][-12:]}", all(e["available_at"] <= ep["cutoff_at"] for e in ep["edges"]))
        check(f"targets_reachable:{ep['episode_id'][-12:]}", set(ep["target_node_ids"]).issubset(reachable(ep)))

    episode_by_id = {ep["episode_id"]: ep for ep in pack["episodes"]}
    check("future_records_after_trigger", all(r["available_at"] > episode_by_id[r["episode_id"]]["event_at"] for r in seal["records"]))

    labels = {(x["episode_id"], x["target_node_id"]): x["outcome"] for x in gold["labels"]}
    check("label_count", len(labels) == 14)
    check("reopen_count", sum(v == "REOPEN" for v in labels.values()) == 8)
    check("no_reopen_count", sum(v == "NO_REOPEN" for v in labels.values()) == 6)
    valid_record_ids = {r["record_id"] for r in seal["records"]}
    check("all_gold_has_future_record", all(x["future_record_ids"] and set(x["future_record_ids"]).issubset(valid_record_ids) for x in gold["labels"]))

    auth = {(x["episode_id"], x["edge_id"]): x["authority"] for x in authority["edge_authority"]}
    pred_rows = {(r["episode_id"], r["target_node_id"]): r["predictions"] for r in predictions["rows"]}
    for ep in pack["episodes"]:
        if "Darwish" in ep["episode_name"]:
            continue
        edge_by_target = {e["dependent_node_id"]: e for e in ep["edges"]}
        for target in ep["target_node_ids"]:
            level = auth[(ep["episode_id"], edge_by_target[target]["edge_id"])]
            outcome = labels[(ep["episode_id"], target)]
            row = pred_rows[(ep["episode_id"], target)]
            check(f"review_all_reviews:{target}", row["REVIEW_ALL_REACHABILITY"]["review"] is True)
            check(f"direct_reviews:{target}", row["DIRECT_LOOKUP"]["review"] is True)
            if level == "HARD":
                check(f"hard_maps_reopen:{target}", outcome == "REOPEN")
                check(f"hard_er_reviews:{target}", row["EVIDENCE_RECALL"]["review"] is True)
            elif level == "UNADMITTED":
                check(f"unadmitted_maps_negative:{target}", outcome == "NO_REOPEN")
                check(f"unadmitted_er_skips:{target}", row["EVIDENCE_RECALL"]["review"] is False)
            else:
                check(f"unexpected_authority:{target}", False, level)

    direct = score["metrics"]["DIRECT_LOOKUP"]
    ra = score["metrics"]["REVIEW_ALL_REACHABILITY"]
    er = score["metrics"]["EVIDENCE_RECALL"]
    cmp_er = score["comparisons_vs_review_all"]["EVIDENCE_RECALL"]
    check("direct_metrics", direct["true_reopen_reviews"] == 7 and direct["missed_reopenings"] == 1 and direct["total_review_load"] == 13)
    check("review_all_metrics", ra["true_reopen_reviews"] == 8 and ra["missed_reopenings"] == 0 and ra["total_review_load"] == 14 and ra["unnecessary_reviews"] == 6)
    check("er_metrics", er["true_reopen_reviews"] == 8 and er["missed_reopenings"] == 0 and er["total_review_load"] == 8 and er["unnecessary_reviews"] == 0)
    check("er_recall", er["reconsideration_recall"]["basis_points"] == 10000)
    check("er_savings", cmp_er["reviewer_savings_vs_review_all"] == 6)
    check("er_no_extra_misses", cmp_er["additional_missed_reopenings_vs_review_all"] == 0)
    check("pooled_reduction", result["observed_review_load_reduction_vs_review_all_basis_points"] == 4285)

    check("policy_recall_bar", policy["minimum_reconsideration_recall_basis_points"] == 9500)
    check("policy_savings_bar", policy["minimum_review_load_reduction_vs_review_all_basis_points"] == 4000)
    check("policy_extra_misses_bar", policy["maximum_additional_missed_reopenings_vs_review_all"] == 0)
    check("policy_recurrence", policy["minimum_independent_trigger_episodes_with_positive_savings_and_zero_additional_misses"] == 3)
    check("episode_metric_count", episode_metrics["episode_count"] == 5)
    check("recurring_savings_count", episode_metrics["episodes_with_positive_savings_and_zero_additional_misses"] == 4)
    check("mean_episode_savings", episode_metrics["mean_episode_review_savings_basis_points"] == 4166)
    check("median_episode_savings", episode_metrics["median_episode_review_savings_basis_points"] == 5000)
    check("promotion", result["verdict"] == "PROMOTION")
    check("no_failed_conditions", result["failed_conditions"] == [])
    check("all_conditions_true", all(result["conditions"].values()))

    per_ep = {x["episode_name"]: x for x in episode_metrics["episodes"]}
    check("shah_zero_savings", next(v for k,v in per_ep.items() if "Shah" in k)["reviewer_savings"] == 0)
    check("narayan_positive_savings", next(v for k,v in per_ep.items() if "Narayan" in k)["reviewer_savings"] == 1)
    sato_rows = [v for k,v in per_ep.items() if "Sato" in k]
    check("three_sato_episodes", len(sato_rows) == 3)
    check("all_sato_positive_savings", all(v["reviewer_savings"] > 0 for v in sato_rows))
    check("all_sato_no_extra_misses", all(v["additional_missed_reopenings_vs_review_all"] == 0 for v in sato_rows))

    for rel, expected in FROZEN_ENGINE_SHA256.items():
        actual = sha256_file(root / rel)
        check(f"frozen_engine:{rel}", actual == expected, actual)
    check("custody_engine_unchanged", custody["engine_unchanged"] is True)
    check("summary_engine_unchanged", summary["engine_unchanged"] is True)

    check("card_has_point", "POINT\nEvidence Recall did save meaningful review work." in card)
    check("card_has_because", "BECAUSE\nIt caught 8/8 warranted reopenings while reviewing 8 instead of 14 items" in card)
    check("card_has_but", "BUT\nSavings recurred in 4/5 trigger episodes" in card)
    check("card_has_so", card.rstrip().endswith("SO\nPROMOTION"))
    check("report_exists", (artifact / "REPORT.md").is_file())

    failed = [x for x in checks if not x["pass"]]
    verification = {
        "schema": "openline.temporal-selectivity-replication-independent-verification.v1",
        "valid": not failed,
        "disposition": "PASS" if not failed else "FAIL",
        "check_count": len(checks),
        "failed_count": len(failed),
        "module_free": True,
        "checks": checks,
        "claim_boundary": "Stdlib-only verifier checks artifact custody, temporal ordering, content-addressed bindings, frozen engine bytes, explicit gold shape, authority/prediction consistency for added one-edge episodes, pooled and episode-level metrics, and the predeclared promotion rule. It does not independently adjudicate the scientific content of the source records.",
    }
    text = json.dumps(verification, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if verification["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
