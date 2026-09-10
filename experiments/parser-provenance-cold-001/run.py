"""PARSER-PROVENANCE-COLD-001.

Cold external probe derived from the failure shape in arXiv:2609.06702v1.
No model calls and no production mutation.  The fixture is a controlled
synthetic adaptation, not a reproduction of the paper's dataset.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from openline_claim_graph import (
    GraphValidationError,
    build_source,
    create_claim,
    create_projection,
    create_relation,
    create_snapshot,
    private_key_from_hex,
    provenance_anchor,
    public_key_hex,
    sign_snapshot,
    validate_snapshot,
    verify_projection,
    verify_receipt,
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
FIXTURE_PATH = HERE / "fixture.json"
AIRLOCK_UNUSED = None
BASE_COMMIT = "559d179dcb30417f7e453edf3ed5778ba99733a0"
EXPERIMENT_ID = "PARSER-PROVENANCE-COLD-001"
ISSUED_AT = "2026-09-10T21:45:00Z"
KEY_HEX = "31" * 32


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_fixture() -> dict[str, Any]:
    value = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if value.get("experiment_id") != EXPERIMENT_ID:
        raise AssertionError("fixture experiment id mismatch")
    if value.get("adaptation") != "controlled_synthetic_not_paper_dataset":
        raise AssertionError("fixture scope widened")
    return value


def _source_store(fixture: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, content in fixture["sources"].items():
        source = build_source(content, locator=f"synthetic://parser-provenance/{name}")
        result[source["source_id"]] = source
    return result


def _find_source(sources: dict[str, dict[str, Any]], locator_suffix: str) -> dict[str, Any]:
    for source in sources.values():
        if str(source.get("locator", "")).endswith(locator_suffix):
            return source
    raise AssertionError(f"source not found: {locator_suffix}")


def _quote_claim(*, source: dict[str, Any], actor: str, slot: str, value: str) -> dict[str, Any]:
    text = str(source["content"])
    anchor = provenance_anchor(source, text, mode="QUOTE", asserted_by=actor)
    return create_claim(
        kind="SOURCE_ASSERTION",
        text=text,
        asserted_by=actor,
        provenance=[anchor],
        slot=slot,
        value=value,
    )


def _classify(cases: dict[str, dict[str, Any]]) -> str:
    hard_fail = (
        not cases["source_anchor_tamper"]["tamper_rejected"]
        or not cases["parallel_conflict"]["silent_merge_rejected"]
        or not cases["receipt_binding"]["tamper_rejected"]
    )
    if hard_fail:
        return "PROVENANCE_OR_LINEAGE_BARRIER_FAILED"

    semantic_guard = cases["semantic_identity_boundary"]["misbound_representation_rejected_or_quarantined"]
    if semantic_guard:
        return "SEMANTIC_IDENTITY_GUARD_ALREADY_PRESENT"

    if (
        cases["parallel_conflict"]["preserve_all_valid"]
        and cases["semantic_identity_boundary"]["wrong_selection_receipt_valid"]
        and cases["semantic_identity_boundary"]["wrong_selection_projection_disposition"] == "ADMIT"
    ):
        return "PROVENANCE_BARRIER_HELD_IDENTITY_SEMANTICS_UNEARNED"

    return "INCONCLUSIVE_EXISTING_BOUNDARY"


def run_probe() -> dict[str, Any]:
    fixture = _load_fixture()
    sources = _source_store(fixture)
    correct_source = _find_source(sources, "/correct")
    misleading_source = _find_source(sources, "/misleading")
    slot = str(fixture["target_slot"])

    correct = _quote_claim(
        source=correct_source,
        actor="parallel-reader-correct",
        slot=slot,
        value=str(fixture["expected_values"]["correct"]),
    )
    # Deliberately preserve the misleading chunk's exact bytes while assigning
    # its finding to the target person's slot.  This is the paper's failure
    # shape: local grounding can be exact while entity binding is wrong.
    misleading = _quote_claim(
        source=misleading_source,
        actor="parallel-reader-local",
        slot=slot,
        value=str(fixture["expected_values"]["misleading_local"]),
    )

    correct_parent = create_snapshot(claims=[correct], relations=[])
    misleading_parent = create_snapshot(claims=[misleading], relations=[])
    correct_check = validate_snapshot(correct_parent, sources)
    misleading_check = validate_snapshot(misleading_parent, sources)
    if not correct_check["valid"] or not misleading_check["valid"]:
        raise AssertionError("cold parent premise invalid")

    # Case 1: source/quote integrity must fail closed.
    tampered_sources = copy.deepcopy(sources)
    bad_source = tampered_sources[misleading_source["source_id"]]
    bad_source["content"] = str(bad_source["content"]) + " altered"
    tamper_check = validate_snapshot(misleading_parent, tampered_sources)
    source_case = {
        "tamper_rejected": not tamper_check["valid"],
        "errors": tamper_check["errors"],
    }

    # Case 2: two parallel parents carrying different values for the same slot
    # must not collapse silently.
    silent_merge_rejected = False
    silent_merge_error = ""
    try:
        create_snapshot(
            claims=[correct, misleading],
            relations=[],
            parent_snapshots=[correct_parent, misleading_parent],
        )
    except GraphValidationError as exc:
        silent_merge_error = str(exc)
        silent_merge_rejected = f"merge_conflict_unresolved:{slot}" in silent_merge_error

    contradiction = create_relation(
        source_claim_id=correct["claim_id"],
        target_claim_id=misleading["claim_id"],
        relation="CONTRADICTS",
        asserted_by="lead-aggregation",
    )
    preserve_resolution = {
        "slot": slot,
        "action": "PRESERVE_ALL",
        "parent_claim_ids": sorted([correct["claim_id"], misleading["claim_id"]]),
        "reason": "parallel findings disagree on the represented husband slot",
    }
    preserve_all = create_snapshot(
        claims=[correct, misleading],
        relations=[contradiction],
        parent_snapshots=[correct_parent, misleading_parent],
        merge_resolutions=[preserve_resolution],
    )
    preserve_check = validate_snapshot(
        preserve_all,
        sources,
        parent_snapshots=[correct_parent, misleading_parent],
    )
    parallel_case = {
        "silent_merge_rejected": silent_merge_rejected,
        "silent_merge_error": silent_merge_error,
        "preserve_all_valid": preserve_check["valid"],
        "preserve_all_warnings": preserve_check["warnings"],
        "explicit_contradiction_relation_id": contradiction["relation_id"],
    }

    # Case 3: choose the misleading finding explicitly.  Current OpenLine is not
    # a semantic truth oracle, so this may be structurally valid.  The test asks
    # whether the choice is at least explicit and cryptographically bound.
    select_wrong_resolution = {
        "slot": slot,
        "action": "SELECT",
        "parent_claim_ids": sorted([correct["claim_id"], misleading["claim_id"]]),
        "selected_claim_id": misleading["claim_id"],
        "reason": "controlled negative control: lead selects the locally direct answer",
    }
    wrong_selected = create_snapshot(
        claims=[misleading],
        relations=[],
        parent_snapshots=[correct_parent, misleading_parent],
        merge_resolutions=[select_wrong_resolution],
        removal_reasons={correct["claim_id"]: "controlled negative control selection"},
    )
    wrong_check = validate_snapshot(
        wrong_selected,
        sources,
        parent_snapshots=[correct_parent, misleading_parent],
    )

    key = private_key_from_hex(KEY_HEX)
    receipt = sign_snapshot(
        wrong_selected,
        sources,
        private_key=key,
        issuer="parser-provenance-cold-receiver",
        issued_at=ISSUED_AT,
        parent_snapshots=[correct_parent, misleading_parent],
    )
    receipt_check = verify_receipt(
        receipt,
        wrong_selected,
        sources,
        pinned_public_key=public_key_hex(key),
        parent_snapshots=[correct_parent, misleading_parent],
    )

    projection = create_projection(
        wrong_selected,
        claim_ids=[misleading["claim_id"]],
        purpose="controlled same-name identity-selection probe",
        selected_by="lead-aggregation",
    )
    projection_check = verify_projection(
        projection,
        {
            "required_slots": [slot],
            "deny_unanchored_claims": True,
            "allowed_provenance_modes": ["QUOTE"],
            "quarantine_on_warnings": False,
        },
    )

    semantic_case = {
        "misleading_parent_valid": misleading_check["valid"],
        "misleading_parent_warnings": misleading_check["warnings"],
        "wrong_selection_snapshot_valid": wrong_check["valid"],
        "wrong_selection_receipt_valid": receipt_check["valid"],
        "receipt_validation_warning_count": receipt.get("validation_warning_count"),
        "wrong_selection_projection_disposition": projection_check["disposition"],
        "wrong_selection_projection_warnings": projection_check["warnings"],
        "misbound_representation_rejected_or_quarantined": (
            not misleading_check["valid"]
            or not wrong_check["valid"]
            or not receipt_check["valid"]
            or projection_check["disposition"] in {"DENY", "QUARANTINE"}
        ),
        "boundary": (
            "Exact quote provenance authenticates bytes, not the semantic mapping from those bytes "
            "to the target slot/value. An explicit SELECT can therefore commit a wrong identity "
            "choice if the receiver signs it."
        ),
    }

    # Case 4: mutate the explicit merge reason after signing.  The original
    # receipt must no longer verify against the mutated state.
    mutated = copy.deepcopy(wrong_selected)
    mutated["merge_resolutions"][0]["reason"] = "silently changed after acceptance"
    mutated_check = validate_snapshot(
        mutated,
        sources,
        parent_snapshots=[correct_parent, misleading_parent],
    )
    mutated_receipt = verify_receipt(
        receipt,
        mutated,
        sources,
        pinned_public_key=public_key_hex(key),
        parent_snapshots=[correct_parent, misleading_parent],
    )
    receipt_case = {
        "tamper_rejected": (not mutated_check["valid"]) and (not mutated_receipt["valid"]),
        "snapshot_errors": mutated_check["errors"],
        "receipt_errors": mutated_receipt["errors"],
    }

    cases = {
        "source_anchor_tamper": source_case,
        "parallel_conflict": parallel_case,
        "semantic_identity_boundary": semantic_case,
        "receipt_binding": receipt_case,
    }
    verdict = _classify(cases)

    return {
        "schema": "openline.parser-provenance-cold-001.result.v1",
        "experiment_id": EXPERIMENT_ID,
        "base_commit": BASE_COMMIT,
        "external_trigger": fixture["external_trigger"],
        "adaptation": fixture["adaptation"],
        "fixture_sha256": _sha256_file(FIXTURE_PATH),
        "source_ids": sorted(sources),
        "target_slot": slot,
        "claim_ids": {
            "correct": correct["claim_id"],
            "misleading": misleading["claim_id"],
        },
        "cases": cases,
        "wrong_selection_state_root": wrong_selected["state_root"],
        "wrong_selection_receipt_payload_hash": receipt["payload_hash"],
        "verdict": verdict,
        "earned_claim": (
            "Current OpenLine preserves exact source/quote integrity and refuses a silent same-slot "
            "collapse across represented parallel findings; an explicit conflicting selection is "
            "bound into lineage and receipt state."
        ),
        "negative_result": (
            "Current OpenLine does not mechanically establish that a QUOTE-backed slot/value identity "
            "mapping is semantically correct. A receiver can explicitly select and sign the wrong "
            "same-name mapping."
        ),
        "nonclaims": [
            "not a reproduction of PARSER model accuracy",
            "not a semantic entity-resolution benchmark",
            "not proof that OpenLine chooses the correct answer",
            "not proof that provenance alone prevents same-name mistakes",
            "not a runtime feature or production identity resolver",
        ],
    }


def reproduce(output: Path) -> dict[str, Any]:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    result = run_probe()
    (output / "result.json").write_bytes(_canonical_bytes(result) + b"\n")
    hashes = {
        "result.json": _sha256_file(output / "result.json"),
        "fixture.json": _sha256_file(FIXTURE_PATH),
    }
    (output / "SHA256SUMS.json").write_bytes(_canonical_bytes(hashes) + b"\n")
    return result


def self_test() -> None:
    base = {
        "source_anchor_tamper": {"tamper_rejected": True},
        "parallel_conflict": {"silent_merge_rejected": True, "preserve_all_valid": True},
        "receipt_binding": {"tamper_rejected": True},
        "semantic_identity_boundary": {
            "misbound_representation_rejected_or_quarantined": False,
            "wrong_selection_receipt_valid": True,
            "wrong_selection_projection_disposition": "ADMIT",
        },
    }
    assert _classify(base) == "PROVENANCE_BARRIER_HELD_IDENTITY_SEMANTICS_UNEARNED"
    broken = copy.deepcopy(base)
    broken["parallel_conflict"]["silent_merge_rejected"] = False
    assert _classify(broken) == "PROVENANCE_OR_LINEAGE_BARRIER_FAILED"
    guarded = copy.deepcopy(base)
    guarded["semantic_identity_boundary"]["misbound_representation_rejected_or_quarantined"] = True
    assert _classify(guarded) == "SEMANTIC_IDENTITY_GUARD_ALREADY_PRESENT"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        print("PARSER-PROVENANCE-COLD-001 classifier self-test: PASS")
        return 0
    if not args.output:
        parser.error("--output is required unless --self-test is used")
    result = reproduce(Path(args.output).resolve())
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "verdict": result["verdict"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
