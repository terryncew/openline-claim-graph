from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from openline_claim_graph.benchmark import (
    GOLD_SCHEMA,
    PACK_SCHEMA,
    build_plan,
    render_inventory_as_prose,
    validate_gold,
)
from openline_claim_graph.canonical import hash_object


ROOT = Path(__file__).resolve().parents[1]
ARCT = ROOT / "experiments/development_benchmarks/arct"


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_documents() -> tuple[dict[str, Any], dict[str, Any]]:
    blind = json.loads((ARCT / "cases.blind.json").read_text(encoding="utf-8"))
    revealed = json.loads((ARCT / "gold.revealed.json").read_text(encoding="utf-8"))
    labels = {item["case_id"]: item["warrant_index"] for item in revealed["gold"]}
    cases = []
    gold_cases = []
    for source in sorted(blind["cases"], key=lambda item: item["case_id"]):
        case_id = source["case_id"]
        inventory = {
            "records": [
                {
                    "record_id": "PREMISE",
                    "record_type": "premise",
                    "text": source["premise"],
                    "source_ids": ["ARCT_ROW"],
                },
                {
                    "record_id": "CLAIM",
                    "record_type": "claim",
                    "text": source["claim"],
                    "source_ids": ["ARCT_ROW"],
                },
                {
                    "record_id": "WARRANT_0",
                    "record_type": "candidate_premise",
                    "text": source["warrant_0"],
                    "source_ids": ["ARCT_ROW"],
                },
                {
                    "record_id": "WARRANT_1",
                    "record_type": "candidate_premise",
                    "text": source["warrant_1"],
                    "source_ids": ["ARCT_ROW"],
                },
            ],
            "relations": [
                {
                    "relation_id": "MISSING_BRIDGE",
                    "from": "PREMISE",
                    "to": "CLAIM",
                    "relation_type": "requires_bridge",
                    "candidate_ids": ["WARRANT_0", "WARRANT_1"],
                }
            ],
        }
        inventory_root = hash_object(inventory)
        source_packet = {
            "sources": [
                {
                    "source_id": "ARCT_ROW",
                    "debate_title": source["debate_title"],
                    "debate_info": source["debate_info"],
                    "premise": source["premise"],
                    "claim": source["claim"],
                    "warrant_0": source["warrant_0"],
                    "warrant_1": source["warrant_1"],
                }
            ]
        }
        ordinary = {
            "instruction": "Choose the candidate warrant that best connects the premise to the claim.",
            "debate_title": source["debate_title"],
            "context": source["debate_info"],
            "premise": source["premise"],
            "claim": source["claim"],
            "candidate_warrants": [
                {"candidate_id": "WARRANT_0", "text": source["warrant_0"]},
                {"candidate_id": "WARRANT_1", "text": source["warrant_1"]},
            ],
        }
        cases.append(
            {
                "case_id": case_id,
                "dataset_id": "ARCT_DEV_PUBLIC_SUBSET",
                "source_packet": source_packet,
                "source_manifest_root": hash_object(source_packet),
                "inventory": inventory,
                "inventory_root": inventory_root,
                "arms": {
                    "A": {"surface_type": "ordinary_summary", "payload": ordinary},
                    "B": {
                        "surface_type": "extracted_prose",
                        "payload": {"text": render_inventory_as_prose(inventory)},
                        "inventory_root": inventory_root,
                    },
                    "C": {
                        "surface_type": "structured_state",
                        "payload": inventory,
                        "inventory_root": inventory_root,
                    },
                },
            }
        )
        gold_cases.append(
            {
                "case_id": case_id,
                "label": f"WARRANT_{labels[case_id]}",
                "evidence_ids": [],
                "premise_ids": [],
            }
        )

    pack = {
        "schema": PACK_SCHEMA,
        "benchmark_id": "arct-dev-24-automated-receiver-v1",
        "status": "DEVELOPMENT_ONLY",
        "task_contract": {
            "task_id": "missing-premise-choice",
            "instruction": "Return the candidate warrant ID that best supplies the missing premise.",
            "allowed_labels": ["WARRANT_0", "WARRANT_1"],
            "negative_label": None,
        },
        "analysis_contract": {
            "primary_metric": "joint_hit",
            "c_minus_a_min_ppm": 100_000,
            "c_minus_b_min_ppm": 50_000,
            "max_false_conflict_increase_ppm": 0,
            "min_datasets": 2,
            "min_receivers": 2,
            "require_complete": True,
            "require_positive_ci": True,
        },
        "cases": cases,
        "metadata": {
            "source": "UKPLab Argument Reasoning Comprehension Task dev.tsv",
            "upstream_commit": "929f5847487e28036e60803f72e26a82c638db43",
            "license": "Apache-2.0; see experiments/development_benchmarks/arct",
            "limitations": [
                "Public benchmark with possible model-pretraining contamination.",
                "The source subset and gold were already used in development.",
                "One dataset, multiple choice, and no negative-control label.",
                "This pack validates benchmark mechanics and can estimate local effects only.",
            ],
        },
    }
    gold = {
        "schema": GOLD_SCHEMA,
        "benchmark_id": pack["benchmark_id"],
        "pack_sha256": hash_object(pack),
        "cases": gold_cases,
        "metadata": {
            "custody": "Stored separately from pack.json. Public upstream labels; development use only.",
            "source_field": "correctLabelW0orW1",
        },
    }
    validate_gold(gold, pack)
    return pack, gold


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the development-only ARCT automated receiver pack")
    parser.add_argument("--output", default="artifacts/automated-receiver-benchmark")
    parser.add_argument("--receiver", action="append", default=[])
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()
    output = Path(args.output)
    pack, gold = build_documents()
    receivers = args.receiver or ["fixture-receiver-a", "fixture-receiver-b"]
    plan = build_plan(pack, receivers, args.repetitions)
    _write(output / "pack.json", pack)
    _write(output / "gold.private.json", gold)
    _write(output / "plan.json", plan)
    _write(
        output / "report.json",
        {
            "status": "DEVELOPMENT_PACK_ONLY_NO_RECEIVER_RESULT",
            "pack_sha256": hash_object(pack),
            "gold_sha256": hash_object(gold),
            "plan_sha256": hash_object(plan),
            "case_count": len(pack["cases"]),
            "receiver_count": len(plan["receivers"]),
            "trial_count": len(plan["trials"]),
            "incremental_api_spend_usd": 0,
            "claim_boundary": (
                "This checked-in pack exercises sealed custody and planning. It contains no automated receiver "
                "result and is ineligible for product promotion."
            ),
        },
    )
    print(json.dumps({"valid": True, "output": str(output), "trials": len(plan["trials"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
