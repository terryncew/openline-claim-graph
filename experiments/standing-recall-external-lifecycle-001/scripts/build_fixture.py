from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path

from standing_recall import StandingOracle, canonical_bytes, sha256_bytes, write_json

EVENT_AFTER = {
    "EXPIRE": "EXPIRED",
    "REVOKE": "REVOKED",
    "SUPERSEDE": "SUPERSEDED",
    "CORRECT": "CORRECTED",
}


def ev(eid: str, before_facets: dict, after_standing: str = "ACCEPTED", after_facets: dict | None = None):
    return {
        "id": eid,
        "kind": "evidence",
        "before": {"standing": "ACCEPTED", "facets": dict(before_facets)},
        "after": {
            "standing": after_standing,
            "facets": dict(before_facets if after_facets is None else after_facets),
        },
    }


def req(name: str, value, *bindings: tuple[str, str]):
    return {
        "name": name,
        "equals": value,
        "bindings": [{"source": source, "facet": facet} for source, facet in bindings],
    }


def out(value, *bindings):
    normalized = []
    for binding in bindings:
        if len(binding) == 2:
            source, facet = binding
            normalized.append({"source": source, "facet": facet})
        elif len(binding) == 3:
            source, facet, source_equals = binding
            normalized.append({"source": source, "facet": facet, "equals": source_equals})
        else:
            raise ValueError("output binding must have 2 or 3 items")
    return {"value": value, "bindings": normalized}


def decision(did: str, requires: list[dict], outputs: dict[str, dict]):
    return {"id": did, "kind": "decision", "requires": requires, "outputs": outputs}


def make_base(event_type: str, pattern: str, variant: int, ordinal: int) -> dict:
    after = EVENT_AFTER[event_type]
    evidence = [
        ev("E1", {"core": "yes", "special": "blue"}, after_standing=after),
        ev("E2", {"core": "yes", "special": "blue"}),
        ev("E3", {"core": "yes", "special": "green"}),
    ]
    # Replacement/correction material exists after the event but was not a
    # support actually used by the finalized decisions. SRE-001 v1 does not
    # retroactively substitute unseen evidence into a finalized basis.
    if event_type in {"SUPERSEDE", "CORRECT"}:
        evidence.append(
            {
                "id": "E1R",
                "kind": "evidence",
                "before": {"standing": "ABSENT", "facets": {}},
                "after": {
                    "standing": "ACCEPTED",
                    "facets": {"core": "yes", "special": "red"},
                },
            }
        )

    if pattern == "sole":
        d1 = decision(
            "D1",
            [req("core", "yes", ("E1", "core"))],
            {
                "core": out("yes", ("E1", "core")),
                "special": out("blue", ("E1", "special")),
            },
        )
        d2 = decision(
            "D2",
            [req("special", "blue", ("D1", "special"))],
            {"permit": out("yes", ("D1", "special", "blue"))},
        )
    elif pattern == "full_alt":
        d1 = decision(
            "D1",
            [req("core", "yes", ("E1", "core"), ("E2", "core"))],
            {
                "core": out("yes", ("E1", "core"), ("E2", "core")),
                "special": out("blue", ("E1", "special"), ("E2", "special")),
            },
        )
        d2 = decision(
            "D2",
            [req("special", "blue", ("D1", "special"))],
            {"permit": out("yes", ("D1", "special", "blue"))},
        )
    elif pattern == "partial_facet":
        # Centerpiece adversarial case:
        # D1 survives through E2's core support, but its exported special facet
        # loses standing because only E1 supported that facet. D2 must reopen.
        d1 = decision(
            "D1",
            [req("core", "yes", ("E1", "core"), ("E2", "core"))],
            {
                "core": out("yes", ("E1", "core"), ("E2", "core")),
                "special": out("blue", ("E1", "special")),
            },
        )
        d2 = decision(
            "D2",
            [req("special", "blue", ("D1", "special"))],
            {"permit": out("yes", ("D1", "special", "blue"))},
        )
    elif pattern == "irrelevant_facet":
        # E1 influenced a non-required exported facet, so graph reachability
        # alone reaches D1/D2 even though their standing is fully supported by E2.
        d1 = decision(
            "D1",
            [req("core", "yes", ("E2", "core"))],
            {
                "core": out("yes", ("E2", "core")),
                "audit_note": out("blue", ("E1", "special")),
            },
        )
        d2 = decision(
            "D2",
            [req("core", "yes", ("D1", "core"))],
            {"permit": out("yes", ("D1", "core"))},
        )
    else:
        raise ValueError(pattern)

    decisions = [d1, d2]

    if variant == 1:
        decisions.append(
            decision(
                "D3",
                [req("independent", "yes", ("E3", "core"))],
                {"independent": out("yes", ("E3", "core"))},
            )
        )
    elif variant == 2:
        # Extend the affected chain. D3 inherits D2's standing.
        decisions.append(
            decision(
                "D3",
                [req("permit", "yes", ("D2", "permit"))],
                {"continue": out("yes", ("D2", "permit"))},
            )
        )
    elif variant == 3:
        # Branch from D1's core facet. In partial_facet, D2 must reopen while
        # D3 stays closed because D1.core still has E2 support.
        decisions.append(
            decision(
                "D3",
                [req("core", "yes", ("D1", "core"))],
                {"continue": out("yes", ("D1", "core"))},
            )
        )

    event = {
        "type": event_type,
        "roots": ["E1"],
        "occurred_after_finalization": True,
        "content_bytes_changed": False,
        "standing_transition": {"E1": {"before": "ACCEPTED", "after": after}},
    }
    if event_type in {"SUPERSEDE", "CORRECT"}:
        event["replacement_evidence"] = "E1R"

    episode = {
        "episode_id": f"{event_type.lower()}-{pattern}-{variant}-{ordinal:03d}",
        "pattern": pattern,
        "variant": variant,
        "event": event,
        "evidence": evidence,
        "decisions": decisions,
    }

    before = StandingOracle(episode, "before").standings()
    if not all(before.values()):
        raise AssertionError(f"non-standing finalized fixture: {episode['episode_id']} {before}")
    return episode


def build_fixture() -> dict:
    episodes = []
    ordinal = 0
    for event_type in ("EXPIRE", "REVOKE", "SUPERSEDE", "CORRECT"):
        for pattern in ("sole", "full_alt", "partial_facet", "irrelevant_facet"):
            for variant in range(4):
                ordinal += 1
                episodes.append(make_base(event_type, pattern, variant, ordinal))
    body = {
        "schema": "openline.standing-recall-external-lifecycle-fixture.v1",
        "experiment": "standing-recall-external-lifecycle-001",
        "fixture_role": "MECHANISM_CONFORMANCE_ONLY",
        "source_adaptation": {
            "dgrr": "arXiv:2608.10502",
            "memorepair": "arXiv:2605.07242",
            "note": "Uses the published dependency/cascade problem shapes but does not reproduce either authors' benchmark or code.",
        },
        "event_types": ["EXPIRE", "REVOKE", "SUPERSEDE", "CORRECT"],
        "episodes": episodes,
        "claim_boundary": [
            "Every decision is valid at t0 before the injected lifecycle event.",
            "The lifecycle event occurs only after finalization.",
            "Evidence content is unchanged; only receiver-admissible standing changes for the invalidated root.",
            "Replacement evidence, when present, is not silently substituted into a basis that did not use it at finalization.",
            "This fixture cannot establish external transport or novelty over author implementations.",
        ],
    }
    body["fixture_sha256"] = sha256_bytes(canonical_bytes(body))
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    fixture = build_fixture()
    write_json(args.output, fixture)
    print(json.dumps({"valid": True, "episodes": len(fixture["episodes"]), "fixture_sha256": fixture["fixture_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
