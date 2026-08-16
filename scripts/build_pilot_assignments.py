from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ARMS = ("A", "B", "C")
SCHEMA = "openline.claim-graph.receiver-pilot.assignments.v1"


def _unique_strings(values: list[Any], label: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{label} must be a non-empty JSON array")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{label} must contain non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must not contain duplicates")
    return sorted(values)


def _seed_integer(seed: str) -> int:
    if not isinstance(seed, str) or not seed:
        raise ValueError("seed must be a non-empty string from the declared public event")
    return int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest(), "big")


def build_assignments(
    receiver_ids: list[str],
    case_ids: list[str],
    *,
    cases_per_receiver: int,
    seed: str,
) -> dict[str, Any]:
    receivers = _unique_strings(receiver_ids, "receiver_ids")
    cases = _unique_strings(case_ids, "case_ids")
    if not isinstance(cases_per_receiver, int) or isinstance(cases_per_receiver, bool):
        raise ValueError("cases_per_receiver must be an integer")
    if cases_per_receiver < 1 or cases_per_receiver > len(cases):
        raise ValueError("cases_per_receiver must be between 1 and the number of cases")
    if len(receivers) < len(ARMS):
        raise ValueError("at least three receivers are required")

    rng = random.Random(_seed_integer(seed))
    shuffled_receivers = receivers[:]
    rng.shuffle(shuffled_receivers)

    arm_slots = [ARMS[index % len(ARMS)] for index in range(len(receivers))]
    rng.shuffle(arm_slots)
    receiver_arm = dict(zip(shuffled_receivers, arm_slots, strict=True))

    receivers_by_arm: dict[str, list[str]] = {arm: [] for arm in ARMS}
    for receiver_id in shuffled_receivers:
        receivers_by_arm[receiver_arm[receiver_id]].append(receiver_id)

    rows: list[dict[str, Any]] = []
    for arm in ARMS:
        case_counts = Counter({case_id: 0 for case_id in cases})
        arm_receivers = receivers_by_arm[arm][:]
        rng.shuffle(arm_receivers)
        for receiver_id in arm_receivers:
            chosen: list[str] = []
            for _ in range(cases_per_receiver):
                eligible = [case_id for case_id in cases if case_id not in chosen]
                lowest_count = min(case_counts[case_id] for case_id in eligible)
                tied = [case_id for case_id in eligible if case_counts[case_id] == lowest_count]
                case_id = rng.choice(tied)
                chosen.append(case_id)
                case_counts[case_id] += 1
            rng.shuffle(chosen)
            for order, case_id in enumerate(chosen, start=1):
                rows.append(
                    {
                        "arm": arm,
                        "case_id": case_id,
                        "order": order,
                        "receiver_id": receiver_id,
                    }
                )

    rows.sort(key=lambda row: (row["receiver_id"], row["order"]))
    result = {
        "assignments": rows,
        "case_ids": cases,
        "cases_per_receiver": cases_per_receiver,
        "receiver_ids": receivers,
        "schema": SCHEMA,
        "seed_sha256": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
    }
    validate_assignments(result)
    return result


def validate_assignments(document: dict[str, Any]) -> None:
    if document.get("schema") != SCHEMA:
        raise ValueError("unexpected assignment schema")
    receivers = _unique_strings(document.get("receiver_ids"), "receiver_ids")
    cases = _unique_strings(document.get("case_ids"), "case_ids")
    cases_per_receiver = document.get("cases_per_receiver")
    rows = document.get("assignments")
    if not isinstance(rows, list):
        raise ValueError("assignments must be an array")

    by_receiver: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_arm_case: Counter[tuple[str, str]] = Counter()
    receiver_arms: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("every assignment must be an object")
        receiver_id = row.get("receiver_id")
        case_id = row.get("case_id")
        arm = row.get("arm")
        order = row.get("order")
        if receiver_id not in receivers or case_id not in cases or arm not in ARMS:
            raise ValueError("assignment contains an unknown receiver, case, or arm")
        if not isinstance(order, int) or isinstance(order, bool):
            raise ValueError("assignment order must be an integer")
        by_receiver[receiver_id].append(row)
        receiver_arms[receiver_id].add(arm)
        by_arm_case[(arm, case_id)] += 1

    if set(by_receiver) != set(receivers):
        raise ValueError("every receiver must have assignments")
    for receiver_id in receivers:
        receiver_rows = by_receiver[receiver_id]
        if len(receiver_rows) != cases_per_receiver:
            raise ValueError("every receiver must have the configured number of cases")
        if len(receiver_arms[receiver_id]) != 1:
            raise ValueError("a receiver must be assigned to exactly one arm")
        if len({row["case_id"] for row in receiver_rows}) != cases_per_receiver:
            raise ValueError("a receiver cannot see the same case twice")
        if sorted(row["order"] for row in receiver_rows) != list(range(1, cases_per_receiver + 1)):
            raise ValueError("receiver order values must be contiguous from one")

    receiver_counts = Counter(next(iter(receiver_arms[receiver_id])) for receiver_id in receivers)
    if max(receiver_counts.values()) - min(receiver_counts.values()) > 1:
        raise ValueError("receiver counts are not balanced across arms")
    for arm in ARMS:
        counts = [by_arm_case[(arm, case_id)] for case_id in cases]
        if max(counts) - min(counts) > 1:
            raise ValueError(f"case observations are not balanced within Arm {arm}")


def _load_string_array(path: Path, key: str) -> list[str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get(key)
    return _unique_strings(value, key)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic, between-receiver pilot assignments.")
    parser.add_argument("--receivers", required=True, type=Path, help="JSON array or object with receiver_ids")
    parser.add_argument("--cases", required=True, type=Path, help="JSON array or object with case_ids")
    parser.add_argument("--cases-per-receiver", type=int, default=4)
    parser.add_argument("--seed", required=True, help="Raw value from the predeclared public randomness event")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    document = build_assignments(
        _load_string_array(args.receivers, "receiver_ids"),
        _load_string_array(args.cases, "case_ids"),
        cases_per_receiver=args.cases_per_receiver,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
