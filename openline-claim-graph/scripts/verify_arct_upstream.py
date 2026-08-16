from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "experiments/development_benchmarks/arct/cases.blind.json"
DEFAULT_GOLD = ROOT / "experiments/development_benchmarks/arct/gold.revealed.json"


def fnv1a_32(value: str) -> int:
    result = 0x811C9DC5
    for byte in value.encode("utf-8"):
        result ^= byte
        result = (result * 0x01000193) & 0xFFFFFFFF
    return result


def parse_upstream(path: Path) -> list[dict[str, str]]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError("upstream TSV is empty")
    header = lines[0].removeprefix("#").split("\t")
    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        columns = line.split("\t")
        if len(columns) != len(header):
            raise ValueError(f"line {line_number}: expected {len(header)} columns, found {len(columns)}")
        rows.append(dict(zip(header, columns, strict=True)))
    return rows


def verify_upstream(upstream_tsv: Path, cases_path: Path = DEFAULT_CASES, gold_path: Path = DEFAULT_GOLD) -> dict[str, Any]:
    case_document = json.loads(cases_path.read_text(encoding="utf-8"))
    gold_document = json.loads(gold_path.read_text(encoding="utf-8"))
    rows = parse_upstream(upstream_tsv)
    seed = case_document["selection"]["seed"]
    selected_count = case_document["selection"]["selected_rows"]
    selected = sorted(rows, key=lambda row: (fnv1a_32(f"{seed}|{row['id']}"), row["id"]))[:selected_count]
    local_cases = {row["case_id"]: row for row in case_document["cases"]}
    local_gold = {row["case_id"]: row["warrant_index"] for row in gold_document["gold"]}
    field_map = {
        "premise": "reason",
        "claim": "claim",
        "warrant_0": "warrant0",
        "warrant_1": "warrant1",
        "debate_title": "debateTitle",
        "debate_info": "debateInfo",
    }
    mismatches: list[dict[str, Any]] = []
    selected_ids = {row["id"] for row in selected}
    for row in selected:
        case_id = row["id"]
        local = local_cases.get(case_id)
        if local is None:
            mismatches.append({"case_id": case_id, "error": "selected_case_missing_locally"})
            continue
        for local_field, upstream_field in field_map.items():
            if local[local_field] != row[upstream_field]:
                mismatches.append({"case_id": case_id, "field": local_field, "error": "text_mismatch"})
        if local_gold.get(case_id) != int(row["correctLabelW0orW1"]):
            mismatches.append({"case_id": case_id, "field": "gold", "error": "label_mismatch"})
    for case_id in sorted(set(local_cases) - selected_ids):
        mismatches.append({"case_id": case_id, "error": "local_case_not_in_deterministic_selection"})
    expected_rows = case_document["selection"]["upstream_rows"]
    if len(rows) != expected_rows:
        mismatches.append({"error": "upstream_row_count_changed", "expected": expected_rows, "actual": len(rows)})
    return {
        "schema": "openline.claim-graph.arct-upstream-verification.v1",
        "upstream_rows": len(rows),
        "selected_rows": len(selected),
        "local_rows": len(local_cases),
        "exact_match": not mismatches,
        "mismatches": mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the frozen ARCT fixture against an upstream dev.tsv file.")
    parser.add_argument("--upstream-tsv", required=True, type=Path)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    args = parser.parse_args()
    report = verify_upstream(args.upstream_tsv, args.cases, args.gold)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["exact_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
