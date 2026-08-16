"""Sealed, deterministic evaluation for automated claim-graph receivers.

The benchmark deliberately separates four authorities:

* a public pack contains task surfaces but never the answer key;
* a gold file is cryptographically bound to that exact public pack;
* a receiver process sees one arm of one case in a fresh process;
* a deterministic scorer compares strict identifiers with external gold.

No model grades another model's prose.  Passing this harness can support a
narrow machine-receiver result; it cannot establish human comprehension or
semantic truth.
"""

from __future__ import annotations

import json
import random
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from .canonical import canonical_json, canonical_value, hash_object, sha256_hex


PACK_SCHEMA = "openline.automated-receiver-benchmark.pack.v1"
GOLD_SCHEMA = "openline.automated-receiver-benchmark.gold.v1"
PLAN_SCHEMA = "openline.automated-receiver-benchmark.plan.v1"
TRIAL_SCHEMA = "openline.automated-receiver-benchmark.trial.v1"
ANSWER_SCHEMA = "openline.automated-receiver-benchmark.answer.v1"
RESPONSES_SCHEMA = "openline.automated-receiver-benchmark.responses.v1"
SCORE_SCHEMA = "openline.automated-receiver-benchmark.score.v1"

ARMS = ("A", "B", "C")
SURFACE_TYPES = {
    "A": "ordinary_summary",
    "B": "extracted_prose",
    "C": "structured_state",
}
PACK_STATUSES = {"DEVELOPMENT_ONLY", "VALIDATION_ELIGIBLE"}
DISPOSITIONS = {"ADMIT", "QUARANTINE", "DENY"}
RESERVED_PUBLIC_KEYS = {
    "answer",
    "answer_key",
    "correct",
    "correct_label",
    "gold",
    "gold_label",
    "required_evidence_ids",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{name} keys mismatch; missing={missing}, extra={extra}")


def _token(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if len(value) > 200:
        raise ValueError(f"{name} is too long")
    return value


def _string_list(value: Any, name: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    result = [_token(item, f"{name}[{index}]") for index, item in enumerate(value)]
    if nonempty and not result:
        raise ValueError(f"{name} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} contains duplicates")
    return result


def _reject_reserved_public_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in RESERVED_PUBLIC_KEYS:
                raise ValueError(f"{path}.{key}: reserved answer-key field in public pack")
            _reject_reserved_public_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_reserved_public_keys(child, f"{path}[{index}]")


def _validate_analysis_contract(contract: Any) -> dict[str, Any]:
    value = _require_dict(contract, "analysis_contract")
    _exact_keys(
        value,
        {
            "primary_metric",
            "c_minus_a_min_ppm",
            "c_minus_b_min_ppm",
            "max_false_conflict_increase_ppm",
            "min_datasets",
            "min_receivers",
            "require_complete",
            "require_positive_ci",
        },
        "analysis_contract",
    )
    if value["primary_metric"] != "joint_hit":
        raise ValueError("analysis_contract.primary_metric must be 'joint_hit'")
    for key in (
        "c_minus_a_min_ppm",
        "c_minus_b_min_ppm",
        "max_false_conflict_increase_ppm",
    ):
        if not isinstance(value[key], int) or not -1_000_000 <= value[key] <= 1_000_000:
            raise ValueError(f"analysis_contract.{key} must be an integer in [-1000000, 1000000]")
    for key in ("min_datasets", "min_receivers"):
        if not isinstance(value[key], int) or value[key] < 1:
            raise ValueError(f"analysis_contract.{key} must be a positive integer")
    for key in ("require_complete", "require_positive_ci"):
        if not isinstance(value[key], bool):
            raise ValueError(f"analysis_contract.{key} must be boolean")
    return value


def validate_inventory(inventory: Any) -> dict[str, Any]:
    """Validate the common B/C inventory used to isolate presentation format."""

    value = _require_dict(canonical_value(inventory), "inventory")
    _exact_keys(value, {"records", "relations"}, "inventory")
    if not isinstance(value["records"], list) or not value["records"]:
        raise ValueError("inventory.records must be a non-empty array")
    if not isinstance(value["relations"], list):
        raise ValueError("inventory.relations must be an array")
    record_ids: set[str] = set()
    for index, raw_record in enumerate(value["records"]):
        record = _require_dict(raw_record, f"inventory.records[{index}]")
        _exact_keys(
            record,
            {"record_id", "record_type", "text", "source_ids"},
            f"inventory.records[{index}]",
        )
        record_id = _token(record["record_id"], f"inventory.records[{index}].record_id")
        if record_id in record_ids:
            raise ValueError(f"duplicate inventory record_id: {record_id}")
        record_ids.add(record_id)
        _token(record["record_type"], f"inventory.records[{index}].record_type")
        _token(record["text"], f"inventory.records[{index}].text")
        _string_list(record["source_ids"], f"inventory.records[{index}].source_ids")
    relation_ids: set[str] = set()
    for index, raw_relation in enumerate(value["relations"]):
        relation = _require_dict(raw_relation, f"inventory.relations[{index}]")
        _exact_keys(
            relation,
            {"relation_id", "from", "to", "relation_type", "candidate_ids"},
            f"inventory.relations[{index}]",
        )
        relation_id = _token(relation["relation_id"], f"inventory.relations[{index}].relation_id")
        if relation_id in relation_ids:
            raise ValueError(f"duplicate inventory relation_id: {relation_id}")
        relation_ids.add(relation_id)
        for endpoint in ("from", "to"):
            if relation[endpoint] not in record_ids:
                raise ValueError(f"inventory relation {relation_id} has unknown {endpoint} record")
        _token(relation["relation_type"], f"inventory.relations[{index}].relation_type")
        candidates = _string_list(
            relation["candidate_ids"], f"inventory.relations[{index}].candidate_ids"
        )
        if any(candidate not in record_ids for candidate in candidates):
            raise ValueError(f"inventory relation {relation_id} has an unknown candidate record")
    return value


def render_inventory_as_prose(inventory: Any) -> str:
    """Render the shared inventory deterministically without graph structure."""

    value = validate_inventory(inventory)
    lines = ["Records:"]
    for record in sorted(value["records"], key=lambda item: item["record_id"]):
        sources = ", ".join(record["source_ids"]) if record["source_ids"] else "none"
        lines.append(
            f"- {record['record_id']} [{record['record_type']}]: {record['text']} (sources: {sources})"
        )
    lines.append("Relations:")
    if not value["relations"]:
        lines.append("- none")
    for relation in sorted(value["relations"], key=lambda item: item["relation_id"]):
        candidates = ", ".join(relation["candidate_ids"]) if relation["candidate_ids"] else "none"
        lines.append(
            f"- {relation['relation_id']}: {relation['from']} --{relation['relation_type']}--> "
            f"{relation['to']} (candidates: {candidates})"
        )
    return "\n".join(lines)


def validate_pack(pack: Any) -> dict[str, Any]:
    """Validate a public benchmark pack and return its binding hash."""

    value = _require_dict(canonical_value(pack), "pack")
    _exact_keys(
        value,
        {"schema", "benchmark_id", "status", "task_contract", "analysis_contract", "cases", "metadata"},
        "pack",
    )
    if value["schema"] != PACK_SCHEMA:
        raise ValueError(f"unsupported pack schema: {value['schema']!r}")
    benchmark_id = _token(value["benchmark_id"], "benchmark_id")
    if value["status"] not in PACK_STATUSES:
        raise ValueError(f"unsupported pack status: {value['status']!r}")
    task = _require_dict(value["task_contract"], "task_contract")
    _exact_keys(
        task,
        {"task_id", "instruction", "allowed_labels", "negative_label"},
        "task_contract",
    )
    _token(task["task_id"], "task_contract.task_id")
    _token(task["instruction"], "task_contract.instruction")
    allowed_labels = _string_list(task["allowed_labels"], "task_contract.allowed_labels", nonempty=True)
    negative_label = task["negative_label"]
    if negative_label is not None and negative_label not in allowed_labels:
        raise ValueError("task_contract.negative_label must be null or an allowed label")
    _validate_analysis_contract(value["analysis_contract"])
    _require_dict(value["metadata"], "metadata")
    if not isinstance(value["cases"], list) or not value["cases"]:
        raise ValueError("cases must be a non-empty array")

    seen_cases: set[str] = set()
    for index, raw_case in enumerate(value["cases"]):
        case = _require_dict(raw_case, f"cases[{index}]")
        _exact_keys(
            case,
            {
                "case_id",
                "dataset_id",
                "source_packet",
                "source_manifest_root",
                "inventory",
                "inventory_root",
                "arms",
            },
            f"cases[{index}]",
        )
        case_id = _token(case["case_id"], f"cases[{index}].case_id")
        if case_id in seen_cases:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen_cases.add(case_id)
        _token(case["dataset_id"], f"cases[{index}].dataset_id")
        source_packet = _require_dict(case["source_packet"], f"cases[{index}].source_packet")
        inventory = validate_inventory(case["inventory"])
        for root_name in ("source_manifest_root", "inventory_root"):
            if not _is_sha256(case[root_name]):
                raise ValueError(f"cases[{index}].{root_name} must be a lowercase SHA-256 hex digest")
        if case["source_manifest_root"] != hash_object(source_packet):
            raise ValueError(f"cases[{index}].source_manifest_root does not match source_packet")
        if case["inventory_root"] != hash_object(inventory):
            raise ValueError(f"cases[{index}].inventory_root does not match inventory")
        arms = _require_dict(case["arms"], f"cases[{index}].arms")
        if set(arms) != set(ARMS):
            raise ValueError(f"cases[{index}].arms must contain exactly A, B, and C")
        for arm in ARMS:
            surface = _require_dict(arms[arm], f"cases[{index}].arms.{arm}")
            expected = {"surface_type", "payload"} if arm == "A" else {
                "surface_type",
                "payload",
                "inventory_root",
            }
            _exact_keys(surface, expected, f"cases[{index}].arms.{arm}")
            if surface["surface_type"] != SURFACE_TYPES[arm]:
                raise ValueError(
                    f"cases[{index}].arms.{arm}.surface_type must be {SURFACE_TYPES[arm]!r}"
                )
            _require_dict(surface["payload"], f"cases[{index}].arms.{arm}.payload")
            _reject_reserved_public_keys(surface["payload"], f"cases[{index}].arms.{arm}.payload")
            if arm != "A" and surface["inventory_root"] != case["inventory_root"]:
                raise ValueError(f"cases[{index}]: B/C inventory roots must match the case inventory_root")
        if arms["B"]["payload"] != {"text": render_inventory_as_prose(inventory)}:
            raise ValueError(f"cases[{index}]: arm B is not the deterministic prose rendering of inventory")
        if arms["C"]["payload"] != inventory:
            raise ValueError(f"cases[{index}]: arm C is not the exact structured inventory")

    return {
        "valid": True,
        "benchmark_id": benchmark_id,
        "pack_sha256": hash_object(value),
        "case_count": len(value["cases"]),
        "dataset_count": len({case["dataset_id"] for case in value["cases"]}),
    }


def validate_gold(gold: Any, pack: Any) -> dict[str, Any]:
    """Validate an answer key and its binding to a public pack."""

    pack_result = validate_pack(pack)
    pack_value = canonical_value(pack)
    value = _require_dict(canonical_value(gold), "gold")
    _exact_keys(value, {"schema", "benchmark_id", "pack_sha256", "cases", "metadata"}, "gold")
    if value["schema"] != GOLD_SCHEMA:
        raise ValueError(f"unsupported gold schema: {value['schema']!r}")
    if value["benchmark_id"] != pack_value["benchmark_id"]:
        raise ValueError("gold benchmark_id does not match pack")
    if value["pack_sha256"] != pack_result["pack_sha256"]:
        raise ValueError("gold pack_sha256 does not match the exact public pack")
    _require_dict(value["metadata"], "gold.metadata")
    if not isinstance(value["cases"], list):
        raise ValueError("gold.cases must be an array")
    allowed_labels = set(pack_value["task_contract"]["allowed_labels"])
    expected_case_ids = {case["case_id"] for case in pack_value["cases"]}
    seen: set[str] = set()
    for index, raw_case in enumerate(value["cases"]):
        case = _require_dict(raw_case, f"gold.cases[{index}]")
        _exact_keys(case, {"case_id", "label", "evidence_ids", "premise_ids"}, f"gold.cases[{index}]")
        case_id = _token(case["case_id"], f"gold.cases[{index}].case_id")
        if case_id in seen:
            raise ValueError(f"duplicate gold case_id: {case_id}")
        seen.add(case_id)
        if case["label"] not in allowed_labels:
            raise ValueError(f"gold.cases[{index}].label is not allowed")
        _string_list(case["evidence_ids"], f"gold.cases[{index}].evidence_ids")
        _string_list(case["premise_ids"], f"gold.cases[{index}].premise_ids")
    if seen != expected_case_ids:
        raise ValueError(
            f"gold case set does not match pack; missing={sorted(expected_case_ids - seen)}, "
            f"extra={sorted(seen - expected_case_ids)}"
        )
    return {
        "valid": True,
        "benchmark_id": value["benchmark_id"],
        "pack_sha256": pack_result["pack_sha256"],
        "gold_sha256": hash_object(value),
        "case_count": len(value["cases"]),
    }


def _trial_id(
    benchmark_id: str,
    pack_sha256: str,
    receiver_id: str,
    case_id: str,
    arm: str,
    repetition: int,
) -> str:
    return "trial:sha256:" + hash_object(
        {
            "benchmark_id": benchmark_id,
            "pack_sha256": pack_sha256,
            "receiver_id": receiver_id,
            "case_id": case_id,
            "arm": arm,
            "repetition": repetition,
        }
    )


def build_plan(pack: Any, receiver_ids: Iterable[str], repetitions: int = 1) -> dict[str, Any]:
    """Build a deterministic full-factorial plan over receivers, cases, and arms."""

    pack_result = validate_pack(pack)
    pack_value = canonical_value(pack)
    receivers = sorted({_token(item, "receiver_id") for item in receiver_ids})
    if not receivers:
        raise ValueError("at least one receiver_id is required")
    if not isinstance(repetitions, int) or not 1 <= repetitions <= 100:
        raise ValueError("repetitions must be an integer between 1 and 100")
    cases_by_id = {case["case_id"]: case for case in pack_value["cases"]}
    trials = []
    for receiver_id in receivers:
        for repetition in range(repetitions):
            for case_id in sorted(cases_by_id):
                case = cases_by_id[case_id]
                for arm in ARMS:
                    trials.append(
                        {
                            "trial_id": _trial_id(
                                pack_value["benchmark_id"],
                                pack_result["pack_sha256"],
                                receiver_id,
                                case_id,
                                arm,
                                repetition,
                            ),
                            "receiver_id": receiver_id,
                            "case_id": case_id,
                            "dataset_id": case["dataset_id"],
                            "arm": arm,
                            "repetition": repetition,
                            "surface_sha256": hash_object(case["arms"][arm]),
                        }
                    )
    return {
        "schema": PLAN_SCHEMA,
        "benchmark_id": pack_value["benchmark_id"],
        "pack_sha256": pack_result["pack_sha256"],
        "receivers": receivers,
        "repetitions": repetitions,
        "trials": trials,
    }


def validate_plan(plan: Any, pack: Any) -> dict[str, Any]:
    value = _require_dict(canonical_value(plan), "plan")
    _exact_keys(
        value,
        {"schema", "benchmark_id", "pack_sha256", "receivers", "repetitions", "trials"},
        "plan",
    )
    if value["schema"] != PLAN_SCHEMA:
        raise ValueError(f"unsupported plan schema: {value['schema']!r}")
    expected = build_plan(pack, value["receivers"], value["repetitions"])
    if value != expected:
        raise ValueError("plan does not match the deterministic full-factorial plan for this pack")
    return {
        "valid": True,
        "benchmark_id": value["benchmark_id"],
        "pack_sha256": value["pack_sha256"],
        "plan_sha256": hash_object(value),
        "trial_count": len(value["trials"]),
        "receiver_count": len(value["receivers"]),
    }


def build_trial_payload(pack: Any, plan: Any, trial_id: str) -> dict[str, Any]:
    """Return exactly what a receiver may see for one planned trial."""

    validate_plan(plan, pack)
    pack_value = canonical_value(pack)
    plan_value = canonical_value(plan)
    trial = next((item for item in plan_value["trials"] if item["trial_id"] == trial_id), None)
    if trial is None:
        raise ValueError(f"unknown trial_id: {trial_id}")
    case = next(item for item in pack_value["cases"] if item["case_id"] == trial["case_id"])
    surface = case["arms"][trial["arm"]]
    if hash_object(surface) != trial["surface_sha256"]:
        raise ValueError("planned surface hash no longer matches the pack")
    return {
        "schema": TRIAL_SCHEMA,
        "benchmark_id": pack_value["benchmark_id"],
        "trial_id": trial["trial_id"],
        "receiver_id": trial["receiver_id"],
        "case_id": trial["case_id"],
        "dataset_id": trial["dataset_id"],
        "repetition": trial["repetition"],
        "task_contract": pack_value["task_contract"],
        "source_packet": case["source_packet"],
        "surface": surface,
    }


def validate_answer(answer: Any, trial: dict[str, Any], pack: Any) -> dict[str, Any]:
    value = _require_dict(canonical_value(answer), "answer")
    _exact_keys(
        value,
        {"schema", "trial_id", "label", "evidence_ids", "premise_ids", "disposition", "usage"},
        "answer",
    )
    if value["schema"] != ANSWER_SCHEMA:
        raise ValueError(f"unsupported answer schema: {value['schema']!r}")
    if value["trial_id"] != trial["trial_id"]:
        raise ValueError("answer trial_id does not match the assigned trial")
    labels = set(canonical_value(pack)["task_contract"]["allowed_labels"])
    if value["label"] not in labels:
        raise ValueError("answer label is not allowed by the task contract")
    _string_list(value["evidence_ids"], "answer.evidence_ids")
    _string_list(value["premise_ids"], "answer.premise_ids")
    if value["disposition"] is not None and value["disposition"] not in DISPOSITIONS:
        raise ValueError("answer.disposition must be ADMIT, QUARANTINE, DENY, or null")
    usage = _require_dict(value["usage"], "answer.usage")
    _exact_keys(usage, {"input_tokens", "output_tokens", "cost_microusd"}, "answer.usage")
    for key in usage:
        if not isinstance(usage[key], int) or usage[key] < 0:
            raise ValueError(f"answer.usage.{key} must be a non-negative integer")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _validate_response_document(document: Any, pack: Any, plan: Any) -> dict[str, Any]:
    value = _require_dict(canonical_value(document), "responses")
    _exact_keys(
        value,
        {
            "schema",
            "benchmark_id",
            "pack_sha256",
            "plan_sha256",
            "receiver_id",
            "command_sha256",
            "started_at",
            "updated_at",
            "status",
            "cumulative_cost_microusd",
            "responses",
        },
        "responses",
    )
    pack_result = validate_pack(pack)
    plan_result = validate_plan(plan, pack)
    if value["schema"] != RESPONSES_SCHEMA:
        raise ValueError(f"unsupported responses schema: {value['schema']!r}")
    if value["benchmark_id"] != pack_result["benchmark_id"]:
        raise ValueError("responses benchmark_id mismatch")
    if value["pack_sha256"] != pack_result["pack_sha256"]:
        raise ValueError("responses pack_sha256 mismatch")
    if value["plan_sha256"] != plan_result["plan_sha256"]:
        raise ValueError("responses plan_sha256 mismatch")
    if value["receiver_id"] not in canonical_value(plan)["receivers"]:
        raise ValueError("responses receiver_id is not in the plan")
    if not _is_sha256(value["command_sha256"]):
        raise ValueError("responses command_sha256 must be a SHA-256 digest")
    if value["status"] not in {"PARTIAL", "COMPLETE", "BUDGET_EXHAUSTED"}:
        raise ValueError("unsupported responses status")
    if not isinstance(value["cumulative_cost_microusd"], int) or value["cumulative_cost_microusd"] < 0:
        raise ValueError("responses cumulative cost must be a non-negative integer")
    if not isinstance(value["responses"], list):
        raise ValueError("responses.responses must be an array")
    planned = {item["trial_id"]: item for item in canonical_value(plan)["trials"]}
    seen: set[str] = set()
    cost = 0
    for index, raw_record in enumerate(value["responses"]):
        record = _require_dict(raw_record, f"responses.responses[{index}]")
        _exact_keys(
            record,
            {
                "trial_id",
                "valid",
                "answer",
                "error",
                "exit_code",
                "latency_ms",
                "stdout_sha256",
                "stderr_sha256",
            },
            f"responses.responses[{index}]",
        )
        trial_id = record["trial_id"]
        if trial_id in seen:
            raise ValueError(f"duplicate response trial_id: {trial_id}")
        seen.add(trial_id)
        trial = planned.get(trial_id)
        if trial is None or trial["receiver_id"] != value["receiver_id"]:
            raise ValueError(f"response is not assigned to receiver {value['receiver_id']}: {trial_id}")
        if not isinstance(record["valid"], bool):
            raise ValueError("response valid field must be boolean")
        if not isinstance(record["exit_code"], int) or not isinstance(record["latency_ms"], int):
            raise ValueError("response exit_code and latency_ms must be integers")
        if record["latency_ms"] < 0:
            raise ValueError("response latency_ms must be non-negative")
        for digest_name in ("stdout_sha256", "stderr_sha256"):
            if not _is_sha256(record[digest_name]):
                raise ValueError(f"response {digest_name} must be a SHA-256 digest")
        if record["valid"]:
            if record["error"] is not None:
                raise ValueError("valid response cannot contain an error")
            answer = validate_answer(record["answer"], trial, pack)
            cost += answer["usage"]["cost_microusd"]
        else:
            if record["answer"] is not None or not isinstance(record["error"], str):
                raise ValueError("invalid response must contain an error and no answer")
    if cost != value["cumulative_cost_microusd"]:
        raise ValueError("responses cumulative cost does not equal answer usage")
    expected_ids = {
        item["trial_id"]
        for item in canonical_value(plan)["trials"]
        if item["receiver_id"] == value["receiver_id"]
    }
    if value["status"] == "COMPLETE" and seen != expected_ids:
        raise ValueError("COMPLETE responses document does not contain every assigned trial")
    return value


def run_receiver_command(
    pack: Any,
    plan: Any,
    *,
    receiver_id: str,
    command: Sequence[str],
    output_path: Path,
    timeout_seconds: int = 120,
    max_cost_microusd: int = 0,
) -> dict[str, Any]:
    """Run one receiver command in a new process for every assigned trial.

    The command receives one trial document on stdin and must emit exactly one
    JSON answer on stdout.  Existing output is validated and resumed.
    ``max_cost_microusd=0`` means no paid cost is permitted.
    """

    pack_result = validate_pack(pack)
    plan_result = validate_plan(plan, pack)
    receiver_id = _token(receiver_id, "receiver_id")
    if receiver_id not in canonical_value(plan)["receivers"]:
        raise ValueError(f"receiver_id is not in plan: {receiver_id}")
    if not command or any(not isinstance(item, str) or not item for item in command):
        raise ValueError("command must be a non-empty argv sequence")
    if not isinstance(timeout_seconds, int) or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    if not isinstance(max_cost_microusd, int) or max_cost_microusd < 0:
        raise ValueError("max_cost_microusd must be a non-negative integer")
    command_sha256 = hash_object(list(command))
    if output_path.exists():
        document = _validate_response_document(
            json.loads(output_path.read_text(encoding="utf-8")), pack, plan
        )
        if document["receiver_id"] != receiver_id:
            raise ValueError("existing output belongs to a different receiver")
        if document["command_sha256"] != command_sha256:
            raise ValueError("existing output was produced by a different command")
    else:
        now = _utc_now()
        document = {
            "schema": RESPONSES_SCHEMA,
            "benchmark_id": pack_result["benchmark_id"],
            "pack_sha256": pack_result["pack_sha256"],
            "plan_sha256": plan_result["plan_sha256"],
            "receiver_id": receiver_id,
            "command_sha256": command_sha256,
            "started_at": now,
            "updated_at": now,
            "status": "PARTIAL",
            "cumulative_cost_microusd": 0,
            "responses": [],
        }
    completed_ids = {item["trial_id"] for item in document["responses"]}
    assigned = [
        item for item in canonical_value(plan)["trials"] if item["receiver_id"] == receiver_id
    ]
    for trial in assigned:
        if trial["trial_id"] in completed_ids:
            continue
        if max_cost_microusd > 0 and document["cumulative_cost_microusd"] >= max_cost_microusd:
            document["status"] = "BUDGET_EXHAUSTED"
            break
        payload = build_trial_payload(pack, plan, trial["trial_id"])
        started = time.monotonic_ns()
        try:
            completed = subprocess.run(
                list(command),
                input=json.dumps(payload, sort_keys=True),
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
            stdout = completed.stdout.encode("utf-8")
            stderr = completed.stderr.encode("utf-8")
            elapsed_ms = max(0, (time.monotonic_ns() - started) // 1_000_000)
            try:
                if completed.returncode != 0:
                    raise ValueError(f"receiver exited with code {completed.returncode}")
                answer = validate_answer(json.loads(completed.stdout), trial, pack)
                record = {
                    "trial_id": trial["trial_id"],
                    "valid": True,
                    "answer": answer,
                    "error": None,
                    "exit_code": completed.returncode,
                    "latency_ms": elapsed_ms,
                    "stdout_sha256": sha256_hex(stdout),
                    "stderr_sha256": sha256_hex(stderr),
                }
                document["cumulative_cost_microusd"] += answer["usage"]["cost_microusd"]
            except (json.JSONDecodeError, ValueError) as exc:
                record = {
                    "trial_id": trial["trial_id"],
                    "valid": False,
                    "answer": None,
                    "error": str(exc),
                    "exit_code": completed.returncode,
                    "latency_ms": elapsed_ms,
                    "stdout_sha256": sha256_hex(stdout),
                    "stderr_sha256": sha256_hex(stderr),
                }
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else (exc.stdout or b"")
            stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else (exc.stderr or b"")
            if isinstance(stdout, str):
                stdout = stdout.encode("utf-8")
            if isinstance(stderr, str):
                stderr = stderr.encode("utf-8")
            record = {
                "trial_id": trial["trial_id"],
                "valid": False,
                "answer": None,
                "error": f"receiver timed out after {timeout_seconds} seconds",
                "exit_code": -1,
                "latency_ms": max(0, (time.monotonic_ns() - started) // 1_000_000),
                "stdout_sha256": sha256_hex(stdout),
                "stderr_sha256": sha256_hex(stderr),
            }
        document["responses"].append(record)
        document["updated_at"] = _utc_now()
        _write_json(output_path, document)
        if document["cumulative_cost_microusd"] > max_cost_microusd:
            document["status"] = "BUDGET_EXHAUSTED"
            break
    expected_ids = {item["trial_id"] for item in assigned}
    completed_ids = {item["trial_id"] for item in document["responses"]}
    if completed_ids == expected_ids:
        document["status"] = "COMPLETE"
    elif document["status"] != "BUDGET_EXHAUSTED":
        document["status"] = "PARTIAL"
    document["updated_at"] = _utc_now()
    _write_json(output_path, document)
    _validate_response_document(document, pack, plan)
    return document


def _set_f1_permyriad(predicted: set[str], expected: set[str]) -> int | None:
    if not expected:
        return None
    if not predicted:
        return 0
    intersection = len(predicted & expected)
    return (20_000 * intersection) // (len(predicted) + len(expected))


def _rate_ppm(numerator: int, denominator: int) -> int | None:
    if denominator == 0:
        return None
    return (1_000_000 * numerator) // denominator


def _mean_int(values: list[int]) -> int | None:
    if not values:
        return None
    return sum(values) // len(values)


def _paired_bootstrap(differences: list[int], *, seed: str, samples: int = 5_000) -> dict[str, Any]:
    if not differences:
        return {"pair_count": 0, "difference_ppm": None, "ci95_low_ppm": None, "ci95_high_ppm": None}
    point = _mean_int([value * 1_000_000 for value in differences])
    if len(differences) == 1:
        return {
            "pair_count": 1,
            "difference_ppm": point,
            "ci95_low_ppm": None,
            "ci95_high_ppm": None,
        }
    rng = random.Random(int(hash_object(seed), 16))
    draws: list[int] = []
    for _ in range(samples):
        total = sum(differences[rng.randrange(len(differences))] for _ in differences)
        draws.append((1_000_000 * total) // len(differences))
    draws.sort()
    return {
        "pair_count": len(differences),
        "difference_ppm": point,
        "ci95_low_ppm": draws[(samples * 25) // 1000],
        "ci95_high_ppm": draws[(samples * 975) // 1000 - 1],
    }


def score_responses(
    pack: Any,
    gold: Any,
    plan: Any,
    response_documents: Sequence[Any],
) -> dict[str, Any]:
    """Score all planned trials, counting missing or invalid trials as misses."""

    pack_result = validate_pack(pack)
    gold_result = validate_gold(gold, pack)
    plan_result = validate_plan(plan, pack)
    pack_value = canonical_value(pack)
    plan_value = canonical_value(plan)
    gold_by_case = {item["case_id"]: item for item in canonical_value(gold)["cases"]}
    records: dict[str, dict[str, Any]] = {}
    for raw_document in response_documents:
        document = _validate_response_document(raw_document, pack, plan)
        for record in document["responses"]:
            if record["trial_id"] in records:
                raise ValueError(f"duplicate trial across response documents: {record['trial_id']}")
            records[record["trial_id"]] = record

    negative_label = pack_value["task_contract"]["negative_label"]
    scored = []
    for trial in plan_value["trials"]:
        record = records.get(trial["trial_id"])
        valid = bool(record and record["valid"])
        answer = record["answer"] if valid else None
        key = gold_by_case[trial["case_id"]]
        label_correct = int(bool(answer and answer["label"] == key["label"]))
        evidence_f1 = _set_f1_permyriad(
            set(answer["evidence_ids"] if answer else []), set(key["evidence_ids"])
        )
        premise_f1 = _set_f1_permyriad(
            set(answer["premise_ids"] if answer else []), set(key["premise_ids"])
        )
        applicable = [label_correct]
        if evidence_f1 is not None:
            applicable.append(int(evidence_f1 == 10_000))
        if premise_f1 is not None:
            applicable.append(int(premise_f1 == 10_000))
        joint_hit = int(valid and all(applicable))
        false_conflict = None
        if negative_label is not None and key["label"] == negative_label:
            false_conflict = int(not answer or answer["label"] != negative_label)
        usage = answer["usage"] if answer else {"input_tokens": 0, "output_tokens": 0, "cost_microusd": 0}
        scored.append(
            {
                **trial,
                "response_valid": valid,
                "label_correct": label_correct,
                "evidence_f1_permyriad": evidence_f1,
                "premise_f1_permyriad": premise_f1,
                "joint_hit": joint_hit,
                "false_conflict": false_conflict,
                "latency_ms": record["latency_ms"] if record else 0,
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "cost_microusd": usage["cost_microusd"],
            }
        )

    by_arm: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        rows = [item for item in scored if item["arm"] == arm]
        evidence = [item["evidence_f1_permyriad"] for item in rows if item["evidence_f1_permyriad"] is not None]
        premises = [item["premise_f1_permyriad"] for item in rows if item["premise_f1_permyriad"] is not None]
        negatives = [item["false_conflict"] for item in rows if item["false_conflict"] is not None]
        by_arm[arm] = {
            "expected_trials": len(rows),
            "valid_responses": sum(item["response_valid"] for item in rows),
            "joint_hits": sum(item["joint_hit"] for item in rows),
            "joint_hit_rate_ppm": _rate_ppm(sum(item["joint_hit"] for item in rows), len(rows)),
            "label_accuracy_ppm": _rate_ppm(sum(item["label_correct"] for item in rows), len(rows)),
            "mean_evidence_f1_permyriad": _mean_int(evidence),
            "mean_premise_f1_permyriad": _mean_int(premises),
            "false_conflict_rate_ppm": _rate_ppm(sum(negatives), len(negatives)),
            "mean_latency_ms": _mean_int([item["latency_ms"] for item in rows]),
            "input_tokens": sum(item["input_tokens"] for item in rows),
            "output_tokens": sum(item["output_tokens"] for item in rows),
            "cost_microusd": sum(item["cost_microusd"] for item in rows),
        }

    keyed = {
        (item["receiver_id"], item["case_id"], item["repetition"], item["arm"]): item
        for item in scored
    }
    pairs: dict[str, Any] = {}
    for left, right in (("C", "A"), ("C", "B")):
        differences = []
        for receiver_id in plan_value["receivers"]:
            for case in pack_value["cases"]:
                for repetition in range(plan_value["repetitions"]):
                    differences.append(
                        keyed[(receiver_id, case["case_id"], repetition, left)]["joint_hit"]
                        - keyed[(receiver_id, case["case_id"], repetition, right)]["joint_hit"]
                    )
        pairs[f"{left}_minus_{right}"] = _paired_bootstrap(
            differences,
            seed=f"{pack_result['pack_sha256']}:{left}:{right}",
        )

    complete = len(records) == len(plan_value["trials"]) and all(item["response_valid"] for item in scored)
    datasets = {case["dataset_id"] for case in pack_value["cases"]}
    contract = pack_value["analysis_contract"]
    blockers = []
    if pack_value["status"] != "VALIDATION_ELIGIBLE":
        blockers.append("PACK_IS_DEVELOPMENT_ONLY")
    if contract["require_complete"] and not complete:
        blockers.append("INCOMPLETE_OR_INVALID_RESPONSES")
    if len(datasets) < contract["min_datasets"]:
        blockers.append("INSUFFICIENT_DATASETS")
    if len(plan_value["receivers"]) < contract["min_receivers"]:
        blockers.append("INSUFFICIENT_RECEIVERS")
    if negative_label is None or any(by_arm[arm]["false_conflict_rate_ppm"] is None for arm in ARMS):
        blockers.append("NO_NEGATIVE_CONTROLS")
    c_minus_a = pairs["C_minus_A"]
    c_minus_b = pairs["C_minus_B"]
    if c_minus_a["difference_ppm"] is None or c_minus_a["difference_ppm"] < contract["c_minus_a_min_ppm"]:
        blockers.append("C_MINUS_A_EFFECT_BELOW_BAR")
    if c_minus_b["difference_ppm"] is None or c_minus_b["difference_ppm"] < contract["c_minus_b_min_ppm"]:
        blockers.append("C_MINUS_B_EFFECT_BELOW_BAR")
    if contract["require_positive_ci"]:
        if c_minus_a["ci95_low_ppm"] is None or c_minus_a["ci95_low_ppm"] <= 0:
            blockers.append("C_MINUS_A_CI_NOT_POSITIVE")
        if c_minus_b["ci95_low_ppm"] is None or c_minus_b["ci95_low_ppm"] <= 0:
            blockers.append("C_MINUS_B_CI_NOT_POSITIVE")
    if negative_label is not None and by_arm["C"]["false_conflict_rate_ppm"] is not None:
        increase = by_arm["C"]["false_conflict_rate_ppm"] - by_arm["A"]["false_conflict_rate_ppm"]
        if increase > contract["max_false_conflict_increase_ppm"]:
            blockers.append("FALSE_CONFLICT_SAFETY_GATE_FAILED")

    return {
        "schema": SCORE_SCHEMA,
        "valid": True,
        "benchmark_id": pack_result["benchmark_id"],
        "pack_sha256": pack_result["pack_sha256"],
        "gold_sha256": gold_result["gold_sha256"],
        "plan_sha256": plan_result["plan_sha256"],
        "scored_at": _utc_now(),
        "complete": complete,
        "expected_trials": len(plan_value["trials"]),
        "received_trials": len(records),
        "dataset_count": len(datasets),
        "receiver_count": len(plan_value["receivers"]),
        "by_arm": by_arm,
        "paired_effects": pairs,
        "gate": {
            "status": "PASS" if not blockers else "NOT_PASSED",
            "blockers": sorted(set(blockers)),
            "contract": contract,
        },
        "trial_scores": scored,
        "claim_boundary": (
            "This report measures strict machine-receiver outputs against the bound external key. "
            "It does not establish human comprehension, open-domain truth, or production safety."
        ),
    }
