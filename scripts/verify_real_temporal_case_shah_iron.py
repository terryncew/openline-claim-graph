from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from collections import deque
from pathlib import Path

EXPECTED_ENGINE_SHA256 = {
    "src/openline_claim_graph/temporal_holdout.py": "bc8f0011d65cb1c2c728ef374ebb82b86c3c08657e9919427ff5d80b2707886a",
    "src/openline_claim_graph/comparative_benchmark.py": "6c04e9e021cbc1c01aae78606acc6cd41393c99673185e1e8e3ee4ccaa06e4b1",
    "src/openline_claim_graph/impact.py": "1757340f69e919ff68d3cdfe4265fc1ac330bc99ff5bcd20b69058fa846905a2",
}
ROOT = Path(__file__).resolve().parents[1]


def norm(value):
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [norm(item) for item in value]
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", str(k)): norm(v) for k, v in value.items()}
    raise TypeError(type(value).__name__)


def canonical(value) -> bytes:
    return json.dumps(norm(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_object(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def content_id(namespace: str, value) -> str:
    return f"{namespace}:sha256:{digest_object(value)}"


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def without(value, key):
    out = dict(value)
    out.pop(key, None)
    return out


def reachable(origin: str, edges: list[dict]) -> set[str]:
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge["prerequisite_node_id"], []).append(edge["dependent_node_id"])
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
    parser = argparse.ArgumentParser(description="Independent stdlib-only verifier for real temporal case 001")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    base = Path(args.artifact)

    pack = load(base / "pack.json")
    authority = load(base / "authority.json")
    seal = load(base / "future-seal.private.json")
    gold = load(base / "gold.private.json")
    predictions = load(base / "predictions.json")
    score = load(base / "score.json")
    custody = load(base / "custody.json")
    summary = load(base / "summary.json")
    pre = load(base / "source-evidence/pre-cutoff.json")
    trigger = load(base / "source-evidence/trigger.json")
    later = load(base / "source-evidence/later.private.json")

    checks: list[dict] = []

    def check(name: str, condition: bool, detail=""):
        checks.append({"name": name, "pass": bool(condition), "detail": str(detail)})

    check("pack_content_id", pack["pack_id"] == content_id("evidence-recall-temporal-pack", without(pack, "pack_id")))
    check("authority_content_id", authority["authority_id"] == content_id("evidence-recall-temporal-authority", without(authority, "authority_id")))
    check("seal_content_id", seal["future_seal_id"] == content_id("evidence-recall-temporal-future-seal", without(seal, "future_seal_id")))
    check("gold_content_id", gold["gold_id"] == content_id("evidence-recall-temporal-gold", without(gold, "gold_id")))
    check("predictions_content_id", predictions["predictions_id"] == content_id("evidence-recall-temporal-predictions", without(predictions, "predictions_id")))
    check("score_content_id", score["score_id"] == content_id("evidence-recall-temporal-score", without(score, "score_id")))

    commitment = pack["future_seal_commitment"]
    record_ids = [r["record_id"] for r in seal["records"]]
    records_root = hashlib.sha256("\n".join(record_ids).encode("utf-8")).hexdigest()
    check("seal_commitment_id", commitment["future_seal_id"] == seal["future_seal_id"])
    check("seal_commitment_count", commitment["record_count"] == len(seal["records"]))
    check("seal_commitment_records_root", commitment["records_root"] == records_root)
    check("sealed_later_evidence_not_in_pack", "10.1001/jamanetworkopen.2025.0887" not in json.dumps(pack, sort_keys=True))

    episode = pack["episodes"][0]
    check("cutoff_before_trigger", episode["cutoff_at"] < episode["event_at"])
    check("all_nodes_pre_cutoff", all(node["available_at"] <= episode["cutoff_at"] for node in episode["nodes"]))
    check("all_edges_pre_cutoff", all(edge["available_at"] <= episode["cutoff_at"] for edge in episode["edges"]))
    check("later_record_after_trigger", all(record["available_at"] > episode["event_at"] for record in seal["records"]))

    check("pre_evidence_hash", custody["evidence_hashes"]["pre_cutoff"] == digest_object(pre))
    check("trigger_evidence_hash", custody["evidence_hashes"]["trigger"] == digest_object(trigger))
    check("later_evidence_hash", custody["evidence_hashes"]["later_record"] == digest_object(later))
    check("trigger_binding", episode["event"]["evidence_sha256"] == digest_object(trigger))
    check("later_record_binding", seal["records"][0]["evidence_sha256"] == digest_object(later))

    engine_actual = {path: file_sha(ROOT / path) for path in EXPECTED_ENGINE_SHA256}
    check("frozen_engine_unchanged", engine_actual == EXPECTED_ENGINE_SHA256, engine_actual)
    check("custody_agrees_engine_unchanged", custody["engine_unchanged"] is True)

    auth = {(x["episode_id"], x["edge_id"]): x["authority"] for x in authority["edge_authority"]}
    check("all_case_edges_hard", all(auth[(episode["episode_id"], edge["edge_id"])] == "HARD" for edge in episode["edges"]))

    reached = reachable(episode["invalidated_node_id"], episode["edges"])
    immediate = {
        edge["dependent_node_id"] for edge in episode["edges"]
        if edge["prerequisite_node_id"] == episode["invalidated_node_id"]
    }
    targets = set(episode["target_node_ids"])
    check("review_all_reaches_both_targets", reached & targets == targets, reached)
    check("direct_reaches_one_target", len(immediate & targets) == 1, immediate)

    pred_by_target = {row["target_node_id"]: row["predictions"] for row in predictions["rows"]}
    direct_reviews = sum(1 for target in targets if pred_by_target[target]["DIRECT_LOOKUP"]["review"])
    review_all_reviews = sum(1 for target in targets if pred_by_target[target]["REVIEW_ALL_REACHABILITY"]["review"])
    er_reviews = sum(1 for target in targets if pred_by_target[target]["EVIDENCE_RECALL"]["review"])
    check("prediction_direct_load_independent", direct_reviews == 1, direct_reviews)
    check("prediction_review_all_load_independent", review_all_reviews == 2, review_all_reviews)
    check("prediction_evidence_recall_load", er_reviews == 2, er_reviews)
    check(
        "evidence_recall_hard_required_chain",
        all(pred_by_target[t]["EVIDENCE_RECALL"]["classification"] == "QUARANTINE" for t in targets),
        {t: pred_by_target[t]["EVIDENCE_RECALL"] for t in sorted(targets)},
    )

    labels = {(x["episode_id"], x["target_node_id"]): x["outcome"] for x in gold["labels"]}
    check("gold_both_reopen", set(labels.values()) == {"REOPEN"} and len(labels) == 2, labels)
    check("gold_uses_positive_later_record", all(x["future_record_ids"] == [seal["records"][0]["record_id"]] for x in gold["labels"]))
    check("later_record_is_reanalysis_no_change", seal["records"][0]["record_type"] == "EXPLICIT_NO_CHANGE_AFTER_REANALYSIS")

    direct = score["metrics"]["DIRECT_LOOKUP"]
    review_all = score["metrics"]["REVIEW_ALL_REACHABILITY"]
    er = score["metrics"]["EVIDENCE_RECALL"]
    check("score_direct_expected", (direct["true_reopen_reviews"], direct["missed_reopenings"], direct["total_review_load"]) == (1, 1, 1), direct)
    check("score_review_all_expected", (review_all["true_reopen_reviews"], review_all["missed_reopenings"], review_all["total_review_load"]) == (2, 0, 2), review_all)
    check("score_er_expected", (er["true_reopen_reviews"], er["missed_reopenings"], er["total_review_load"]) == (2, 0, 2), er)
    check("er_zero_reviewer_savings", score["comparisons_vs_review_all"]["EVIDENCE_RECALL"]["reviewer_savings_vs_review_all"] == 0)
    check("summary_no_selectivity", summary["status"] == "REAL_TEMPORAL_CASE_001_RUN_NO_SELECTIVITY_ADVANTAGE")

    valid = all(item["pass"] for item in checks)
    result = {
        "schema": "openline.temporal-real-case-independent-verification.v1",
        "valid": valid,
        "disposition": "PASS" if valid else "FAIL",
        "check_count": len(checks),
        "checks": checks,
        "claim_boundary": (
            "This verifier independently checks artifact custody, temporal ordering, simple graph reachability, frozen engine hashes, "
            "and the exact first-case score. It does not independently reproduce publisher source bytes or establish generalization."
        ),
    }
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
