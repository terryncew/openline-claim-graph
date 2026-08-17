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
EXPECTED_STATUS = "MIXED_TEMPORAL_SELECTIVITY_CORPUS_RUN_BELOW_PROMOTION_BAR"


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def reachable(episode: dict) -> set[str]:
    adjacency: dict[str, list[str]] = {}
    for edge in episode["edges"]:
        adjacency.setdefault(edge["prerequisite_node_id"], []).append(edge["dependent_node_id"])
    origin = episode["invalidated_node_id"]
    seen = {origin}
    queue = deque([origin])
    while queue:
        current = queue.popleft()
        for nxt in adjacency.get(current, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen - {origin}


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently verify mixed temporal selectivity corpus")
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
    custody = load(artifact / "custody.json")
    summary = load(artifact / "summary.json")

    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"name": name, "pass": bool(condition), "detail": detail})

    check("status", summary.get("status") == EXPECTED_STATUS, summary.get("status"))
    check("two_episodes", len(pack.get("episodes", [])) == 2, len(pack.get("episodes", [])))
    check("four_scored_targets", summary.get("scored_targets") == 4, summary.get("scored_targets"))
    check("mixed_gold", summary.get("reopen_gold") == 3 and summary.get("no_reopen_gold") == 1)
    check("pack_id", pack.get("pack_id") == content_id("evidence-recall-temporal-pack", without_id(pack, "pack_id")))
    check("authority_id", authority.get("authority_id") == content_id("evidence-recall-temporal-authority", without_id(authority, "authority_id")))
    check("future_seal_id", seal.get("future_seal_id") == content_id("evidence-recall-temporal-future-seal", without_id(seal, "future_seal_id")))
    check("gold_id", gold.get("gold_id") == content_id("evidence-recall-temporal-gold", without_id(gold, "gold_id")))
    check("predictions_id", predictions.get("predictions_id") == content_id("evidence-recall-temporal-predictions", without_id(predictions, "predictions_id")))
    check("score_id", score.get("score_id") == content_id("evidence-recall-temporal-score", without_id(score, "score_id")))
    check("promotion_policy_id", policy.get("promotion_policy_id") == content_id("temporal-promotion-policy", without_id(policy, "promotion_policy_id")))
    promotion_body = dict(result)
    stored_promotion_result_id = promotion_body.pop("promotion_result_id", None)
    check("promotion_result_id", stored_promotion_result_id == content_id("temporal-promotion-result", promotion_body))

    check("pack_future_binding", pack["future_seal_commitment"]["future_seal_id"] == seal["future_seal_id"])
    expected_records_root = hashlib.sha256("\n".join(item["record_id"] for item in seal["records"]).encode()).hexdigest()
    check("future_records_root", pack["future_seal_commitment"]["records_root"] == expected_records_root)
    check("future_record_count", pack["future_seal_commitment"]["record_count"] == 3)
    check("authority_pack_binding", authority.get("pack_id") == pack.get("pack_id"))
    check("gold_pack_binding", gold.get("pack_id") == pack.get("pack_id"))
    check("gold_seal_binding", gold.get("future_seal_id") == seal.get("future_seal_id"))
    check("prediction_pack_binding", predictions.get("pack_id") == pack.get("pack_id"))
    check("prediction_authority_binding", predictions.get("authority_id") == authority.get("authority_id"))
    check("score_prediction_binding", score.get("predictions_id") == predictions.get("predictions_id"))
    check("score_gold_binding", score.get("gold_id") == gold.get("gold_id"))

    episode_by_name = {episode["episode_name"]: episode for episode in pack["episodes"]}
    shah = next(ep for ep in pack["episodes"] if "Darwish" in ep["episode_name"])
    narayan = next(ep for ep in pack["episodes"] if "Narayan" in ep["episode_name"])
    check("shah_target_count", len(shah["target_node_ids"]) == 2)
    check("narayan_target_count", len(narayan["target_node_ids"]) == 2)
    check("narayan_cutoff_before_event", narayan["cutoff_at"] < narayan["event_at"], (narayan["cutoff_at"], narayan["event_at"]))
    check("all_nodes_pre_cutoff", all(node["available_at"] <= ep["cutoff_at"] for ep in pack["episodes"] for node in ep["nodes"]))
    check("all_edges_pre_cutoff", all(edge["available_at"] <= ep["cutoff_at"] for ep in pack["episodes"] for edge in ep["edges"]))
    check("future_after_event", all(record["available_at"] > next(ep["event_at"] for ep in pack["episodes"] if ep["episode_id"] == record["episode_id"]) for record in seal["records"]))

    narayan_authority = {item["edge_id"]: item["authority"] for item in authority["edge_authority"] if item["episode_id"] == narayan["episode_id"]}
    edge_by_target = {edge["dependent_node_id"]: edge for edge in narayan["edges"]}
    check("zhou_hard", narayan_authority[edge_by_target["zhou2012:death-by-deacetylation-summary"]["edge_id"]] == "HARD")
    check("vitner_unadmitted", narayan_authority[edge_by_target["vitner2014:gaucher-main-conclusion"]["edge_id"]] == "UNADMITTED")
    check("narayan_both_reachable", reachable(narayan) == set(narayan["target_node_ids"]), sorted(reachable(narayan)))

    labels = {(item["episode_id"], item["target_node_id"]): item["outcome"] for item in gold["labels"]}
    check("zhou_gold_reopen", labels[(narayan["episode_id"], "zhou2012:death-by-deacetylation-summary")] == "REOPEN")
    check("vitner_gold_no_reopen", labels[(narayan["episode_id"], "vitner2014:gaucher-main-conclusion")] == "NO_REOPEN")
    check("gold_counts_independent", list(labels.values()).count("REOPEN") == 3 and list(labels.values()).count("NO_REOPEN") == 1)

    rows = {(row["episode_id"], row["target_node_id"]): row["predictions"] for row in predictions["rows"]}
    zhou_pred = rows[(narayan["episode_id"], "zhou2012:death-by-deacetylation-summary")]
    vitner_pred = rows[(narayan["episode_id"], "vitner2014:gaucher-main-conclusion")]
    check("review_all_reviews_zhou", zhou_pred["REVIEW_ALL_REACHABILITY"]["review"] is True)
    check("review_all_reviews_vitner", vitner_pred["REVIEW_ALL_REACHABILITY"]["review"] is True)
    check("er_reviews_zhou", zhou_pred["EVIDENCE_RECALL"]["review"] is True, zhou_pred["EVIDENCE_RECALL"])
    check("er_skips_vitner", vitner_pred["EVIDENCE_RECALL"]["review"] is False, vitner_pred["EVIDENCE_RECALL"])
    check("direct_reviews_both_narayan_targets", zhou_pred["DIRECT_LOOKUP"]["review"] is True and vitner_pred["DIRECT_LOOKUP"]["review"] is True)

    direct = score["metrics"]["DIRECT_LOOKUP"]
    review_all = score["metrics"]["REVIEW_ALL_REACHABILITY"]
    er = score["metrics"]["EVIDENCE_RECALL"]
    cmp_er = score["comparisons_vs_review_all"]["EVIDENCE_RECALL"]
    check("direct_metrics", direct["true_reopen_reviews"] == 2 and direct["missed_reopenings"] == 1 and direct["total_review_load"] == 3)
    check("review_all_metrics", review_all["true_reopen_reviews"] == 3 and review_all["missed_reopenings"] == 0 and review_all["total_review_load"] == 4)
    check("er_metrics", er["true_reopen_reviews"] == 3 and er["missed_reopenings"] == 0 and er["total_review_load"] == 3)
    check("review_all_one_unnecessary", review_all["unnecessary_reviews"] == 1)
    check("er_zero_unnecessary", er["unnecessary_reviews"] == 0)
    check("er_full_recall", er["reconsideration_recall"]["basis_points"] == 10000)
    check("er_full_precision", er["reconsideration_precision"]["basis_points"] == 10000)
    check("reviewer_savings_one", cmp_er["reviewer_savings_vs_review_all"] == 1)
    check("no_additional_misses", cmp_er["additional_missed_reopenings_vs_review_all"] == 0)
    check("observed_reduction_25pct", result["observed_review_load_reduction_vs_review_all_basis_points"] == 2500)
    check("predeclared_min_recall_95pct", policy["minimum_reconsideration_recall_basis_points"] == 9500)
    check("predeclared_min_reduction_40pct", policy["minimum_review_load_reduction_vs_review_all_basis_points"] == 4000)
    check("promotion_fails", result["verdict"] == "NO_PROMOTION")
    check("promotion_failure_is_attention_only", result["failed_conditions"] == ["minimum_review_load_reduction"], result["failed_conditions"])

    for relative, expected in FROZEN_ENGINE_SHA256.items():
        actual = sha256_file(root / relative)
        check(f"frozen_engine:{relative}", actual == expected, actual)
    check("custody_engine_unchanged", custody.get("engine_unchanged") is True)
    check("summary_engine_unchanged", summary.get("engine_unchanged") is True)

    evidence_paths = {
        "pre_cutoff": artifact / "source-evidence/narayan-pre-cutoff.json",
        "trigger": artifact / "source-evidence/narayan-trigger.json",
        "later_record": artifact / "source-evidence/narayan-later.private.json",
    }
    for key, path in evidence_paths.items():
        check(f"evidence_hash:{key}", hash_object(load(path)) == custody["narayan_evidence_hashes"][key])

    failed = [item for item in checks if not item["pass"]]
    verification = {
        "schema": "openline.temporal-mixed-selectivity-independent-verification.v1",
        "valid": not failed,
        "disposition": "PASS" if not failed else "FAIL",
        "check_count": len(checks),
        "failed_count": len(failed),
        "module_free": True,
        "checks": checks,
        "claim_boundary": (
            "This verifier uses only Python standard library and artifact bytes. It verifies custody, frozen engine hashes, "
            "the mixed positive/negative gold shape, deterministic baseline reachability, declared authority, reported scores, "
            "and the predeclared promotion threshold. It does not independently adjudicate the scientific meaning of source text."
        ),
    }
    text = json.dumps(verification, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if verification["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
