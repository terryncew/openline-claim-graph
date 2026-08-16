from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.build_pilot_assignments import ARMS, build_assignments, validate_assignments


class PilotAssignmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.receivers = [f"R{index:03d}" for index in range(1, 73)]
        self.cases = [f"C{index:02d}" for index in range(1, 13)]

    def test_assignment_is_deterministic_and_input_order_independent(self) -> None:
        first = build_assignments(self.receivers, self.cases, cases_per_receiver=4, seed="public-pulse-1")
        second = build_assignments(
            list(reversed(self.receivers)),
            list(reversed(self.cases)),
            cases_per_receiver=4,
            seed="public-pulse-1",
        )
        self.assertEqual(first, second)

    def test_receiver_never_crosses_arms_and_cases_are_balanced(self) -> None:
        document = build_assignments(self.receivers, self.cases, cases_per_receiver=4, seed="public-pulse-2")
        validate_assignments(document)
        by_receiver: dict[str, set[str]] = {}
        by_arm_case = {(arm, case_id): 0 for arm in ARMS for case_id in self.cases}
        for row in document["assignments"]:
            by_receiver.setdefault(row["receiver_id"], set()).add(row["arm"])
            by_arm_case[(row["arm"], row["case_id"])] += 1
        self.assertTrue(all(len(arms) == 1 for arms in by_receiver.values()))
        for arm in ARMS:
            counts = [by_arm_case[(arm, case_id)] for case_id in self.cases]
            self.assertLessEqual(max(counts) - min(counts), 1)

    def test_validator_rejects_cross_arm_receiver(self) -> None:
        document = build_assignments(self.receivers, self.cases, cases_per_receiver=4, seed="public-pulse-3")
        broken = copy.deepcopy(document)
        receiver_id = broken["assignments"][0]["receiver_id"]
        receiver_rows = [row for row in broken["assignments"] if row["receiver_id"] == receiver_id]
        receiver_rows[0]["arm"] = "B" if receiver_rows[0]["arm"] != "B" else "C"
        with self.assertRaisesRegex(ValueError, "exactly one arm"):
            validate_assignments(broken)

    def test_rejects_more_cases_per_receiver_than_exist(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and the number of cases"):
            build_assignments(self.receivers, self.cases[:3], cases_per_receiver=4, seed="public-pulse-4")

    def test_pilot_contract_cannot_promote_from_stage_one(self) -> None:
        root = Path(__file__).resolve().parents[1]
        contract = json.loads(
            (root / "experiments/receiver_discovery_pilot/pilot-contract.json").read_text(encoding="utf-8")
        )
        self.assertEqual(contract["status"], "PROTOCOL_READY_CASE_PACK_EMPTY")
        self.assertEqual(contract["target_receiver_type"], "human")
        self.assertEqual(contract["assignment"]["condition_unit"], "receiver")
        self.assertFalse(contract["analysis"]["stage_1_promotion_allowed"])
        self.assertTrue(contract["analysis"]["stage_2_requires_new_preregistration"])

    def test_all_pilot_json_templates_parse(self) -> None:
        root = Path(__file__).resolve().parents[1]
        template_dir = root / "experiments/receiver_discovery_pilot/templates"
        for path in sorted(template_dir.glob("*.json")):
            with self.subTest(path=path.name):
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)


if __name__ == "__main__":
    unittest.main()
