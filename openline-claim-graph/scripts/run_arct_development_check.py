from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping

from openline_claim_graph import (
    build_source,
    create_claim,
    create_relation,
    create_snapshot,
    provenance_anchor,
    validate_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "experiments/development_benchmarks/arct/cases.blind.json"
DEFAULT_GOLD = ROOT / "experiments/development_benchmarks/arct/gold.revealed.json"
DEFAULT_PREDICTIONS = ROOT / "experiments/development_benchmarks/arct/codex-predictions.pre-reveal.json"
DEFAULT_OUTPUT = ROOT / "artifacts/arct-development-check/report.json"

CASE_SCHEMA = "openline.claim-graph.arct-development-cases.v1"
GOLD_SCHEMA = "openline.claim-graph.arct-development-gold.v1"
PREDICTION_SCHEMA = "openline.claim-graph.arct-development-predictions.v1"
REPORT_SCHEMA = "openline.claim-graph.arct-development-report.v1"
ACTOR = "development:arct-warrant-mapper"


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _index_binary_labels(document: Mapping[str, Any], *, schema: str, label: str) -> dict[str, int]:
    if document.get("schema") != schema:
        raise ValueError(f"unexpected {label} schema")
    rows = document.get(label)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{label} must be a non-empty array")
    result: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"every {label} entry must be an object")
        case_id = row.get("case_id")
        value = row.get("warrant_index")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"every {label} entry needs a case_id")
        if case_id in result:
            raise ValueError(f"duplicate {label} case_id: {case_id}")
        if value not in (0, 1) or isinstance(value, bool):
            raise ValueError(f"{label} warrant_index must be 0 or 1")
        result[case_id] = value
    return result


def load_check_inputs(
    cases_path: Path = DEFAULT_CASES,
    gold_path: Path = DEFAULT_GOLD,
    predictions_path: Path = DEFAULT_PREDICTIONS,
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, int], dict[str, int]]:
    case_document = _read_object(cases_path)
    gold_document = _read_object(gold_path)
    prediction_document = _read_object(predictions_path)
    if case_document.get("schema") != CASE_SCHEMA:
        raise ValueError("unexpected case schema")
    cases = case_document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty array")
    required = {"case_id", "premise", "claim", "warrant_0", "warrant_1", "debate_title", "debate_info"}
    normalized: list[dict[str, str]] = []
    ids: set[str] = set()
    for row in cases:
        if not isinstance(row, Mapping) or set(row) != required:
            raise ValueError("every case must contain exactly the frozen public fields")
        item = {key: row[key] for key in required}
        if any(not isinstance(value, str) or not value for value in item.values()):
            raise ValueError("case fields must be non-empty strings")
        if item["case_id"] in ids:
            raise ValueError(f"duplicate case_id: {item['case_id']}")
        ids.add(item["case_id"])
        normalized.append(item)
    normalized.sort(key=lambda item: item["case_id"])

    gold = _index_binary_labels(gold_document, schema=GOLD_SCHEMA, label="gold")
    predictions = _index_binary_labels(
        prediction_document,
        schema=PREDICTION_SCHEMA,
        label="predictions",
    )
    if set(gold) != ids or set(predictions) != ids:
        raise ValueError("case, gold, and prediction identifiers must match exactly")
    return case_document, normalized, gold, predictions


def _quote_claim(source: Mapping[str, Any], text: str, *, kind: str, slot: str, value: Any) -> dict[str, Any]:
    return create_claim(
        kind=kind,
        text=text,
        asserted_by=ACTOR,
        provenance=[provenance_anchor(source, text, mode="QUOTE", asserted_by=ACTOR)],
        slot=slot,
        value=value,
    )


def build_mapping_graph(case: Mapping[str, str], warrant_index: int) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if warrant_index not in (0, 1) or isinstance(warrant_index, bool):
        raise ValueError("warrant_index must be 0 or 1")
    case_id = case["case_id"]
    fields = ("premise", "claim", "warrant_0", "warrant_1")
    sources = {
        field: build_source(
            case[field],
            locator=(
                "https://github.com/UKPLab/argument-reasoning-comprehension-task/"
                f"blob/929f5847487e28036e60803f72e26a82c638db43/"
                f"experiments/src/main/python/data/dev.tsv#case={case_id}&field={field}"
            ),
        )
        for field in fields
    }
    source_store = {source["source_id"]: source for source in sources.values()}
    premise = _quote_claim(
        sources["premise"],
        case["premise"],
        kind="SOURCE_ASSERTION",
        slot=f"arct.{case_id}.premise",
        value=case["premise"],
    )
    conclusion = _quote_claim(
        sources["claim"],
        case["claim"],
        kind="SOURCE_ASSERTION",
        slot=f"arct.{case_id}.claim",
        value=case["claim"],
    )
    selected_field = f"warrant_{warrant_index}"
    warrant = _quote_claim(
        sources[selected_field],
        case[selected_field],
        kind="ASSUMPTION",
        slot=f"arct.{case_id}.selected_warrant_index",
        value=warrant_index,
    )
    premise_relation_anchor = provenance_anchor(
        sources["premise"],
        case["premise"],
        mode="INFERENCE",
        asserted_by=ACTOR,
    )
    warrant_relation_anchor = provenance_anchor(
        sources[selected_field],
        case[selected_field],
        mode="INFERENCE",
        asserted_by=ACTOR,
    )
    relations = [
        create_relation(
            source_claim_id=premise["claim_id"],
            target_claim_id=conclusion["claim_id"],
            relation="SUPPORTS",
            asserted_by=ACTOR,
            provenance=[premise_relation_anchor],
        ),
        create_relation(
            source_claim_id=warrant["claim_id"],
            target_claim_id=conclusion["claim_id"],
            relation="SUPPORTS",
            asserted_by=ACTOR,
            provenance=[warrant_relation_anchor],
        ),
    ]
    snapshot = create_snapshot(claims=[premise, conclusion, warrant], relations=relations)
    return snapshot, source_store


def build_report(
    cases_path: Path = DEFAULT_CASES,
    gold_path: Path = DEFAULT_GOLD,
    predictions_path: Path = DEFAULT_PREDICTIONS,
) -> dict[str, Any]:
    case_document, cases, gold, predictions = load_check_inputs(cases_path, gold_path, predictions_path)
    details: list[dict[str, Any]] = []
    valid_graphs = 0
    distinct_gold_decoy_roots = 0
    blind_hits = 0
    oracle_hits = 0
    inverted_hits = 0
    for case in cases:
        case_id = case["case_id"]
        gold_index = gold[case_id]
        predicted_index = predictions[case_id]
        inverted_index = 1 - gold_index
        roots: dict[str, str] = {}
        warning_counts: dict[str, int] = {}
        for label, index in (
            ("blind_prediction", predicted_index),
            ("gold_oracle", gold_index),
            ("inverted_control", inverted_index),
        ):
            snapshot, sources = build_mapping_graph(case, index)
            validation = validate_snapshot(snapshot, sources, parent_snapshots=[])
            if not validation["valid"]:
                raise RuntimeError(f"{case_id}/{label}: graph did not validate: {validation}")
            valid_graphs += 1
            roots[label] = snapshot["state_root"]
            warning_counts[label] = len(validation["warnings"])
        if roots["gold_oracle"] != roots["inverted_control"]:
            distinct_gold_decoy_roots += 1
        blind_correct = predicted_index == gold_index
        blind_hits += int(blind_correct)
        oracle_hits += 1
        inverted_hits += 0
        details.append(
            {
                "blind_correct": blind_correct,
                "case_id": case_id,
                "gold_warrant_index": gold_index,
                "predicted_warrant_index": predicted_index,
                "roots": roots,
                "validation_warning_counts": warning_counts,
            }
        )

    total = len(cases)
    checks = {
        "blind_mapping_hits": blind_hits,
        "blind_mapping_total": total,
        "gold_oracle_hits": oracle_hits,
        "inverted_control_hits": inverted_hits,
        "mechanically_valid_graphs": valid_graphs,
        "gold_vs_inverted_roots_distinct": distinct_gold_decoy_roots,
    }
    if checks != {
        "blind_mapping_hits": 21,
        "blind_mapping_total": 24,
        "gold_oracle_hits": 24,
        "inverted_control_hits": 0,
        "mechanically_valid_graphs": 72,
        "gold_vs_inverted_roots_distinct": 24,
    }:
        raise RuntimeError(f"frozen ARCT development result changed: {checks}")
    return {
        "schema": REPORT_SCHEMA,
        "status": "EXPLORATORY_INDEPENDENT_GOLD_POSITIVE_CONTROL",
        "source": copy.deepcopy(case_document["source"]),
        "selection": copy.deepcopy(case_document["selection"]),
        "checks": checks,
        "details": details,
        "claim_boundary": (
            "This small, multiple-choice development check shows that one blinded model mapping pass recovered "
            "21 of 24 independently annotated implicit warrants and that the graph commitment distinguishes the "
            "gold choice from its decoy. It does not test graph-versus-summary receiver value, open-ended extraction, "
            "generalization, or Stage 1 continuation."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen ARCT missing-premise development check.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report(args.cases, args.gold, args.predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["checks"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
