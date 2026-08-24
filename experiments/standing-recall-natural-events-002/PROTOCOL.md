# SRE-002 — Standing Recall: Natural Standing Events

Status at installation: `NATURAL_CORPUS_READY_UNRUN`

## Frozen question

When evidence or authority **actually changed standing in the world**, can the frozen SRE-001 standing mechanism reopen every represented finalized decision that lost sufficient support while preserving represented decisions that retained sufficient support — and can it do so with a smaller repair surface than a strong barrier-first repair baseline?

SRE-002 does not add a new standing algorithm. It carries the frozen SRE-001 mechanism into a retrospective public-record corpus whose lifecycle events are natural rather than injected.

## Why this experiment exists

SRE-001's LongMemEval-V2 lane used real external trajectory material, but `EXPIRE`, `REVOKE`, `SUPERSEDE`, and `CORRECT` were controlled lifecycle injections. SRE-002 removes that particular weakness.

The event universe is frozen before the first repository-visible benchmark result:

- 2 `CORRECT` events;
- 2 `REVOKE` events;
- 2 `SUPERSEDE` events;
- 2 `EXPIRE` events.

These are **8 independent historical events**, represented by **24 scored target dispositions**. The 24 targets must never be described as 24 independent events.

## Natural corpus

The frozen registry is `NATURAL_CASES.json`.

It covers:

1. BMJ correction/reanalysis of Hemkens et al. — `CORRECT`;
2. NEJM correction to the GM-1 spinal-cord injury trial — `CORRECT`;
3. Mozilla removal of DigiNotar trust — `REVOKE`;
4. browser distrust of the legacy Symantec PKI — `REVOKE`;
5. RFC 8996 deprecation of TLS 1.0 and TLS 1.1 — `SUPERSEDE`;
6. NIST transition away from SHA-1 digital-signature generation while retaining limited legacy uses — `SUPERSEDE`;
7. DST Root CA X3 expiration — `EXPIRE`;
8. Ericsson/O2 hardcoded security-certificate expiration — `EXPIRE`.

Every event has three layers that must remain distinct:

**Public event record.** Authoritative or first-party sources establish that the lifecycle event occurred and support the target disposition used as gold.

**Authored dependency representation.** SRE-002 represents relevant evidence facets and finalized decisions as an explicit dependency graph. This mapping is human-authored and retrospective. It is not automatically discovered and can be incomplete or wrong.

**Frozen consequence mechanism.** The already-merged SRE-001 standing evaluator receives the represented before/after state. SRE-002 may not change that evaluator to improve this corpus.

## Gold

Gold is external to the candidate evaluator.

For each target, `NATURAL_CASES.json` stores an explicit public-record disposition:

- `REOPEN` — the natural event removes the represented basis needed for the target to remain closed;
- `SURVIVE` — the public record establishes that the target remained supportable, often because a correction left the conclusion intact, an exception remained trusted, a replacement path existed, or the policy continued to permit the exact use.

The frozen corpus contains 12 `REOPEN` and 12 `SURVIVE` targets.

The benchmark **must score against these stored dispositions**. It must not derive gold from `StandingOracle`, OpenLine output, DGRR output, or MemoRepair output.

## Systems

### DGRR-style contract baseline

`DGRR_CONTRACT_NODE_SUPPORT_NATURAL_V1`

A diagnosed-root/node-support abstraction: trace the affected descendant set and preserve an affected node only when support exists outside the invalidated/affected region. This is intentionally node-level.

This is not DGRR author code and is not a reproduction of the paper's reported benchmark.

### Strong MemoRepair-style contract baseline

`MEMOREPAIR_CONTRACT_PROPERTY_VALIDATION_NATURAL_V1`

Barrier-first repair withdraws the complete represented affected descendant set. Reconstruction then receives the same exact property-aware validator used to determine whether a represented target can stand after the event.

This is deliberately strong. OpenLine cannot win merely because the comparison system lacks property semantics.

Replay surface is the complete barrier-first withdrawn set.

This is not MemoRepair author code, its min-cut implementation, or its reported benchmark.

### Frozen OpenLine standing propagation

`OPENLINE_STANDING_PROPAGATION_NATURAL_V1`

The mechanism is the SRE-001 implementation already merged before this corpus was installed. SRE-002 only renames the output system ID. It does not alter standing semantics.

A target is replayed only when its finalized standing flips from standing to non-standing. Computing standing may inspect additional nodes; inspection is not counted as replay.

## Primary measurements

Only three performance measurements are primary:

1. **Affected-decision recall** — fraction of public-record `REOPEN` targets correctly reopened.
2. **Unaffected-state preservation** — fraction of public-record `SURVIVE` targets correctly left closed.
3. **Repair surface** — number of represented finalized decisions the system says must be replayed/repaired.

Analysis surface is recorded diagnostically but is not a promotion metric.

## Frozen promotion rule

The promotion policy is in `promotion-policy.json` and predates the first repository-visible run.

At minimum:

- all four lifecycle families are present with at least two natural events each;
- at least 8 natural events and 24 scored targets exist;
- at least 10 targets are `REOPEN` and at least 10 are `SURVIVE`;
- at least 6 surviving targets contain direct mixed support from an affected root and an alternative basis;
- OpenLine recall is at least 95%;
- OpenLine preservation is at least 95%;
- OpenLine adds zero misses and zero false reopenings versus the strongest baseline by target error;
- if an accuracy-matching baseline exists, OpenLine must reduce repair surface by at least 25%;
- independent replay must report zero mismatches.

Possible result classes:

- `NATURAL_STANDING_SELECTIVITY`
- `NO_NATURAL_REPAIR_SURFACE_SEPARATION`
- `NATURAL_STANDING_SELECTIVITY_NOT_EARNED`
- `INCOMPLETE_NATURAL_CORPUS`

## Falsifier

If a MemoRepair-compatible barrier-first repair matches OpenLine on public-record target recall and preservation **and** reaches the same or smaller repair surface without receiver-owned standing semantics, no distinct natural-event mechanism is promoted.

If OpenLine misses a warranted reopening or unnecessarily reopens a target that the public record says survives, the result must narrow or fail according to the frozen policy. No post-result repair of the corpus, thresholds, baselines, or standing mechanism is permitted under SRE-002.

## Independent replay

CI rebuilds the fixture from the frozen natural registry, runs the three systems, and then invokes `verify_benchmark.py` under `python -I`.

The independent verifier is stdlib-only and does not import `natural_common.py`. It independently reconstructs dependency traversal, exact facet/value standing, system predictions, score arithmetic, and promotion logic, then compares its result with the primary runner.

## Claim boundary

A successful SRE-002 result would support only this statement:

> On this frozen retrospective corpus of eight natural lifecycle events, the frozen standing mechanism preserved the represented public-record target dispositions while reducing the represented repair surface relative to the best accuracy-matching tested contract baseline, if the frozen gate fires.

It would **not** establish:

- automatic dependency discovery;
- semantic truth of the authored dependency graph;
- author-implementation superiority over DGRR or MemoRepair;
- prospective performance;
- population generality;
- natural correction/revocation/expiry frequency;
- rollback of irreversible external effects;
- execution or policy authority.

`policy_authority: NONE`
