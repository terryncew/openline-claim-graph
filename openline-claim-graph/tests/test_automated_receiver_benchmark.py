from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from openline_claim_graph.benchmark import (
    ANSWER_SCHEMA,
    GOLD_SCHEMA,
    PACK_SCHEMA,
    RESPONSES_SCHEMA,
    build_plan,
    build_trial_payload,
    render_inventory_as_prose,
    run_receiver_command,
    score_responses,
    validate_gold,
    validate_pack,
    validate_plan,
)
from openline_claim_graph.canonical import hash_object, sha256_hex


def fixture_pack(*, status: str = "VALIDATION_ELIGIBLE") -> dict:
    cases = []
    for case_id, dataset_id, text in (
        ("C1", "D1", "alpha"),
        ("C2", "D2", "beta"),
    ):
        inventory = {
            "records": [
                {
                    "record_id": case_id,
                    "record_type": "claim",
                    "text": text,
                    "source_ids": [f"{case_id}-SOURCE"],
                },
                {
                    "record_id": f"{case_id}-E1",
                    "record_type": "evidence",
                    "text": f"evidence for {text}",
                    "source_ids": [f"{case_id}-SOURCE"],
                },
            ],
            "relations": [
                {
                    "relation_id": f"{case_id}-R1",
                    "from": f"{case_id}-E1",
                    "to": case_id,
                    "relation_type": "supports",
                    "candidate_ids": [],
                }
            ],
        }
        source_packet = {
            "sources": [{"source_id": f"{case_id}-SOURCE", "text": f"source material {text}"}]
        }
        inventory_root = hash_object(inventory)
        cases.append(
            {
                "case_id": case_id,
                "dataset_id": dataset_id,
                "source_packet": source_packet,
                "source_manifest_root": hash_object(source_packet),
                "inventory": inventory,
                "inventory_root": inventory_root,
                "arms": {
                    "A": {
                        "surface_type": "ordinary_summary",
                        "payload": {"text": f"Ordinary summary of {text}"},
                    },
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
    return {
        "schema": PACK_SCHEMA,
        "benchmark_id": "fixture-v1",
        "status": status,
        "task_contract": {
            "task_id": "fixture-task",
            "instruction": "Classify the case and cite evidence IDs.",
            "allowed_labels": ["SUPPORT", "CONFLICT", "NO_CONFLICT"],
            "negative_label": "NO_CONFLICT",
        },
        "analysis_contract": {
            "primary_metric": "joint_hit",
            "c_minus_a_min_ppm": 100_000,
            "c_minus_b_min_ppm": 50_000,
            "max_false_conflict_increase_ppm": 0,
            "min_datasets": 2,
            "min_receivers": 2,
            "require_complete": True,
            "require_positive_ci": False,
        },
        "cases": cases,
        "metadata": {"purpose": "unit test"},
    }


def fixture_gold(pack: dict) -> dict:
    return {
        "schema": GOLD_SCHEMA,
        "benchmark_id": pack["benchmark_id"],
        "pack_sha256": hash_object(pack),
        "cases": [
            {"case_id": "C1", "label": "SUPPORT", "evidence_ids": ["C1-E1"], "premise_ids": []},
            {"case_id": "C2", "label": "NO_CONFLICT", "evidence_ids": [], "premise_ids": []},
        ],
        "metadata": {"custody": "fixture"},
    }


def answer_for(trial: dict, pack: dict, gold_by_case: dict, *, correct: bool) -> dict:
    key = gold_by_case[trial["case_id"]]
    label = key["label"] if correct else "CONFLICT"
    evidence = key["evidence_ids"] if correct else []
    return {
        "schema": ANSWER_SCHEMA,
        "trial_id": trial["trial_id"],
        "label": label,
        "evidence_ids": evidence,
        "premise_ids": key["premise_ids"],
        "disposition": "ADMIT" if correct else "QUARANTINE",
        "usage": {"input_tokens": 10, "output_tokens": 3, "cost_microusd": 0},
    }


def response_document(pack: dict, plan: dict, gold: dict, receiver_id: str) -> dict:
    gold_by_case = {item["case_id"]: item for item in gold["cases"]}
    records = []
    for trial in plan["trials"]:
        if trial["receiver_id"] != receiver_id:
            continue
        correct = trial["arm"] == "C" or (trial["arm"] == "B" and trial["case_id"] == "C2")
        answer = answer_for(trial, pack, gold_by_case, correct=correct)
        records.append(
            {
                "trial_id": trial["trial_id"],
                "valid": True,
                "answer": answer,
                "error": None,
                "exit_code": 0,
                "latency_ms": 5,
                "stdout_sha256": sha256_hex(json.dumps(answer).encode("utf-8")),
                "stderr_sha256": sha256_hex(b""),
            }
        )
    return {
        "schema": RESPONSES_SCHEMA,
        "benchmark_id": pack["benchmark_id"],
        "pack_sha256": hash_object(pack),
        "plan_sha256": hash_object(plan),
        "receiver_id": receiver_id,
        "command_sha256": hash_object(["fixture"]),
        "started_at": "2026-08-15T00:00:00Z",
        "updated_at": "2026-08-15T00:00:01Z",
        "status": "COMPLETE",
        "cumulative_cost_microusd": 0,
        "responses": records,
    }


class AutomatedReceiverBenchmarkTest(unittest.TestCase):
    def test_pack_and_gold_binding(self) -> None:
        pack = fixture_pack()
        gold = fixture_gold(pack)
        self.assertTrue(validate_pack(pack)["valid"])
        self.assertTrue(validate_gold(gold, pack)["valid"])
        tampered = copy.deepcopy(pack)
        tampered["cases"][0]["arms"]["A"]["payload"]["text"] = "changed"
        with self.assertRaisesRegex(ValueError, "pack_sha256"):
            validate_gold(gold, tampered)

    def test_public_pack_rejects_answer_key_fields(self) -> None:
        pack = fixture_pack()
        pack["cases"][0]["arms"]["A"]["payload"]["gold_label"] = "SUPPORT"
        with self.assertRaisesRegex(ValueError, "reserved answer-key"):
            validate_pack(pack)

    def test_pack_rejects_b_c_inventory_mismatch(self) -> None:
        pack = fixture_pack()
        pack["cases"][0]["arms"]["C"]["inventory_root"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "inventory roots"):
            validate_pack(pack)
        pack = fixture_pack()
        pack["cases"][0]["arms"]["B"]["payload"]["text"] += "\nextra"
        with self.assertRaisesRegex(ValueError, "deterministic prose rendering"):
            validate_pack(pack)

    def test_plan_is_deterministic_full_factorial_and_payload_has_no_gold(self) -> None:
        pack = fixture_pack()
        first = build_plan(pack, ["receiver-b", "receiver-a"], repetitions=2)
        second = build_plan(pack, ["receiver-a", "receiver-b"], repetitions=2)
        self.assertEqual(first, second)
        self.assertEqual(len(first["trials"]), 2 * 2 * 3 * 2)
        self.assertTrue(validate_plan(first, pack)["valid"])
        payload = build_trial_payload(pack, first, first["trials"][0]["trial_id"])
        self.assertNotIn("gold", json.dumps(payload).lower())

    def test_score_is_deterministic_and_missing_trials_count_as_misses(self) -> None:
        pack = fixture_pack()
        gold = fixture_gold(pack)
        plan = build_plan(pack, ["receiver-a", "receiver-b"])
        documents = [
            response_document(pack, plan, gold, "receiver-a"),
            response_document(pack, plan, gold, "receiver-b"),
        ]
        report = score_responses(pack, gold, plan, documents)
        self.assertTrue(report["complete"])
        self.assertEqual(report["by_arm"]["C"]["joint_hit_rate_ppm"], 1_000_000)
        self.assertGreater(report["paired_effects"]["C_minus_A"]["difference_ppm"], 0)
        partial = copy.deepcopy(documents[0])
        partial["responses"] = partial["responses"][:-1]
        partial["status"] = "PARTIAL"
        report = score_responses(pack, gold, plan, [partial, documents[1]])
        self.assertFalse(report["complete"])
        self.assertEqual(report["received_trials"], len(plan["trials"]) - 1)
        self.assertIn("INCOMPLETE_OR_INVALID_RESPONSES", report["gate"]["blockers"])

    def test_duplicate_trial_across_response_files_is_rejected(self) -> None:
        pack = fixture_pack()
        gold = fixture_gold(pack)
        plan = build_plan(pack, ["receiver-a"])
        document = response_document(pack, plan, gold, "receiver-a")
        with self.assertRaisesRegex(ValueError, "duplicate trial"):
            score_responses(pack, gold, plan, [document, document])

    def test_runner_uses_fresh_processes_and_resumes_free_trials(self) -> None:
        pack = fixture_pack(status="DEVELOPMENT_ONLY")
        plan = build_plan(pack, ["receiver-a"])
        with tempfile.TemporaryDirectory(prefix="automated-receiver-") as temporary:
            directory = Path(temporary)
            receiver = directory / "receiver.py"
            receiver.write_text(
                """
import json, sys
trial = json.load(sys.stdin)
print(json.dumps({
  "schema": "openline.automated-receiver-benchmark.answer.v1",
  "trial_id": trial["trial_id"],
  "label": "SUPPORT",
  "evidence_ids": [],
  "premise_ids": [],
  "disposition": "QUARANTINE",
  "usage": {"input_tokens": 0, "output_tokens": 0, "cost_microusd": 0}
}))
""".strip()
                + "\n",
                encoding="utf-8",
            )
            output = directory / "responses.json"
            first = run_receiver_command(
                pack,
                plan,
                receiver_id="receiver-a",
                command=[sys.executable, str(receiver)],
                output_path=output,
                max_cost_microusd=0,
            )
            self.assertEqual(first["status"], "COMPLETE")
            self.assertEqual(len(first["responses"]), len(plan["trials"]))
            second = run_receiver_command(
                pack,
                plan,
                receiver_id="receiver-a",
                command=[sys.executable, str(receiver)],
                output_path=output,
                max_cost_microusd=0,
            )
            self.assertEqual(first["responses"], second["responses"])


if __name__ == "__main__":
    unittest.main()
