# Standing Recall

Standing Recall is an experimental Claim Graph research line about what should happen after a previously acceptable dependency changes standing.

The motivating distinction is:

> Provenance records what a decision depended on. Standing determines whether that dependency still earns the decision the right to remain closed.

This is not a claim that OpenLine invented dependency rollback, revocation propagation, or property-aware repair. DGRR-style dependency repair and MemoRepair-style cascade repair are prior-art-adjacent mechanisms. The OpenLine question is narrower: once a receiver has finalized a decision, can later changes in admissibility be propagated selectively enough to reopen only the state that truly lost sufficient support?

## What SRE-001 established

SRE-001 used pinned public LongMemEval-V2 trajectory excerpts as external source material and injected controlled `EXPIRE`, `REVOKE`, `SUPERSEDE`, and `CORRECT` events after initial acceptance.

The strong MemoRepair-style baseline was intentionally given exact property-aware validation. It therefore matched OpenLine on scored correctness. OpenLine's surviving difference was repair surface: 40 replayed decisions versus 120 for the accuracy-matching baseline, a 66.67% reduction.

Verdict: `EXTERNAL_STANDING_SEPARATION_ADAPTED_LONGMEMEVAL_V2`.

This does not make the lifecycle events natural; they were controlled adaptations over real external trajectory material.

## What SRE-002 added

SRE-002 replaced the controlled event source with eight real public lifecycle events across scientific corrections, PKI/certificate revocations, standards or policy supersessions, and certificate expirations.

Across 24 scored target dispositions, OpenLine and the strong MemoRepair-style baseline both reached 12/12 warranted reopenings and preserved 12/12 survivals. OpenLine replayed 12 targets; the baseline replayed 24.

Verdict: `NATURAL_STANDING_SELECTIVITY`.

The important limitation is representation: event occurrence and target disposition are public-record anchored, but dependency/facet mappings were retrospectively authored. The corpus is not blinded, prospective, random, or representative of natural event frequency.

## Earned claim

The experiments do not earn “OpenLine repairs better than MemoRepair.”

They support a smaller statement:

> On these frozen evaluations, receiver-owned standing semantics preserved the same scored correctness as a strong property-aware repair baseline while reducing how much previously valid state had to be reopened.

The candidate contribution is therefore **selective reconsideration**, not generic rollback.

## Stop condition

No SRE-003 is planned merely to enlarge the same internally curated evidence line.

The next meaningful evidence should come from one of two outside conditions:

1. an author-released or third-party dependency/rollback implementation that can be run substantially unchanged against the frozen standing events; or
2. a real consequential user system in which evidence naturally expires, is revoked, is superseded, or is corrected after decisions have already been finalized.

Until then, SRE-001 and SRE-002 are frozen.

The stable OpenLine Claim Graph product release remains `0.5.2`; Standing Recall has not been promoted into the stable production API.
