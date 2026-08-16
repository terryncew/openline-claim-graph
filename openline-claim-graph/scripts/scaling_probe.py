from __future__ import annotations

import json
from pathlib import Path

from openline_claim_graph import (
    build_source,
    create_claim,
    create_projection,
    create_snapshot,
    private_key_from_hex,
    provenance_anchor,
    sign_snapshot,
)
from openline_claim_graph.canonical import canonical_json


def measure(count: int) -> dict:
    lines = [f"Declared statement {index:04d} has value {index:04d}." for index in range(count)]
    source = build_source("\n".join(lines), locator="fixture://scaling.txt")
    claims = [
        create_claim(
            kind="SOURCE_ASSERTION",
            text=line,
            asserted_by="fixture:scaling-extractor",
            provenance=[
                provenance_anchor(source, line, mode="QUOTE", asserted_by="fixture:scaling-extractor")
            ],
            slot=f"fixture.value.{index:04d}",
            value=index,
        )
        for index, line in enumerate(lines)
    ]
    snapshot = create_snapshot(claims=claims, relations=[])
    sources = {source["source_id"]: source}
    receipt = sign_snapshot(
        snapshot,
        sources,
        private_key=private_key_from_hex("33" * 32),
        issuer="fixture:scaling-probe",
        issued_at="2026-08-15T08:00:00Z",
        parent_snapshots=[],
    )
    projection = create_projection(
        snapshot,
        claim_ids=[claims[-1]["claim_id"]],
        purpose="Measure one-record projection growth.",
        selected_by="fixture:scaling-probe",
    )
    return {
        "claim_count": count,
        "snapshot_bytes": len(canonical_json(snapshot)),
        "receipt_bytes": len(canonical_json(receipt)),
        "one_claim_projection_bytes": len(canonical_json(projection)),
        "source_manifest_root_bytes": len(bytes.fromhex(receipt["source_manifest_root"])),
    }


def main() -> int:
    report = {
        "schema": "openline.claim-graph.scaling-probe.v1",
        "results": [measure(count) for count in (1, 10, 100, 1000)],
        "interpretation": (
            "The signed receipt remains approximately constant-size because sources and validation warnings are "
            "committed by roots and counts; a bounded projection grows logarithmically with the committed record "
            "count because it carries a Merkle inclusion path."
        ),
        "claim_boundary": "Controlled serialization-size probe only; no production throughput or cost claim.",
    }
    output = Path("artifacts/scaling-probe.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
