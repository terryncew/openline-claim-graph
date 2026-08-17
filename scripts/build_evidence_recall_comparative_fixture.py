from __future__ import annotations

import argparse
import json
from pathlib import Path

from openline_claim_graph.comparative_benchmark import (
    create_authority,
    create_case,
    create_gold,
    create_pack,
    run_comparative,
    score_comparative,
)


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the deterministic three-system conformance fixture")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    root, direct, indirect, no_exposure, alternate, backup = (
        "fixture:root",
        "fixture:direct",
        "fixture:indirect",
        "fixture:no-exposure",
        "fixture:alternate",
        "fixture:backup",
    )
    nodes = [
        {"node_id": root, "label": "invalidated root", "text": "invalidated root"},
        {"node_id": direct, "label": "direct dependent", "text": "direct dependent"},
        {"node_id": indirect, "label": "indirect dependent", "text": "indirect dependent"},
        {"node_id": no_exposure, "label": "reachable but externally negative", "text": "reachable but externally negative"},
        {"node_id": alternate, "label": "alternative support survivor", "text": "alternative support survivor"},
        {"node_id": backup, "label": "independent backup", "text": "independent backup", "independent_basis": True},
    ]
    root_direct = {"prerequisite_node_id": root, "dependent_node_id": direct, "relation": "DERIVED_FROM", "evidence": ["fixture direct"]}
    direct_indirect = {"prerequisite_node_id": direct, "dependent_node_id": indirect, "relation": "DEPENDS_ON", "evidence": ["fixture advisory"]}
    direct_no_exposure = {"prerequisite_node_id": direct, "dependent_node_id": no_exposure, "relation": "DEPENDS_ON", "evidence": ["fixture advisory"]}
    root_alternate = {"prerequisite_node_id": root, "dependent_node_id": alternate, "relation": "SUPPORTS", "evidence": ["fixture support"]}
    backup_alternate = {"prerequisite_node_id": backup, "dependent_node_id": alternate, "relation": "SUPPORTS", "evidence": ["fixture independent support"]}
    cases = [
        create_case(stratum="CONFORMANCE", invalidated_node_id=root, target_node_id=direct, nodes=nodes, edges=[root_direct]),
        create_case(stratum="CONFORMANCE", invalidated_node_id=root, target_node_id=indirect, nodes=nodes, edges=[root_direct, direct_indirect]),
        create_case(stratum="CONFORMANCE", invalidated_node_id=root, target_node_id=no_exposure, nodes=nodes, edges=[root_direct, direct_no_exposure]),
        create_case(stratum="CONFORMANCE", invalidated_node_id=root, target_node_id=alternate, nodes=nodes, edges=[root_alternate, backup_alternate]),
    ]
    pack = create_pack(
        benchmark_id="three-way-conformance-fixture",
        cases=cases,
        source_manifest=[{"role": "conformance_only", "identifier": "self-authored-fixture"}],
        construction_rule="Synthetic fixture that exercises direct, transitive, advisory, and alternative-support behavior; not empirical evidence.",
        status="CONFORMANCE_ONLY",
    )
    authority_map = {}
    for case in cases:
        for edge in case["edges"]:
            authority_map[edge["edge_id"]] = "ADVISORY" if "fixture advisory" in edge["evidence"] else "HARD"
    authority = create_authority(
        pack,
        edge_authority=authority_map,
        declared_by="conformance-fixture",
        construction_rule="advisory edges are fixed by fixture name; all others hard",
    )
    labels = {
        cases[0]["case_id"]: "EXPOSED",
        cases[1]["case_id"]: "EXPOSED",
        cases[2]["case_id"]: "NO_EXPOSURE",
        cases[3]["case_id"]: "NO_EXPOSURE",
    }
    gold = create_gold(pack, labels, source="self-authored fixture", label_definition="conformance only")
    predictions = run_comparative(pack, authority)
    score = score_comparative(pack, authority, gold, predictions)
    write(output / "pack.json", pack)
    write(output / "authority.json", authority)
    write(output / "gold.private.json", gold)
    write(output / "predictions.json", predictions)
    write(output / "score.json", score)
    print(json.dumps({"valid": True, "pack_id": pack["pack_id"], "score_id": score["score_id"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
