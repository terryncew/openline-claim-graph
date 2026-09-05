# CLAIMGRAPH-VERIFICATION-CONTRACT-001 — prospective verification dependency

Status: `FROZEN_PROTOCOL`

Frozen base: `b238f6f1c0a9025cfdccc7367b3c256ab4d50792`

Decision Recall source blob: `7c1ad6e23411364008a3abb41fa662e966880e89`

## Earned question

`CLAIMGRAPH-UNOBSERVED-STATE-001` proved that current Decision Recall silently
`SURVIVE`s when a consequential external state was never represented in the
accepted dependency record, even after fresh verification is supplied.

Can the smallest prospective contract close that hole without retroactive graph
mutation, polling, verifier self-authorization, or over-REOPEN?

## Candidate primitive

At decision acceptance, record the **verification obligation**, not the live
external state:

- dependency id;
- external subject id;
- required predicate/value;
- receiver-recognized verifier id;
- freshness budget;
- receiver-admission requirement;
- materiality;
- matching `LOSS_OF_STANDING` invalidation condition.

The target manifest contains that verification-contract dependency before any
later result exists. The external registry's current state is deliberately not
embedded in the manifest.

A receiver-side admission gate may later produce a normal
`LOSS_OF_STANDING` event for the predeclared dependency only when all frozen
contract checks pass.

## Frozen arms

1. `WITHIN_BUDGET_NO_RESULT` — no polling obligation is due yet. Target
   `SURVIVE`; control `SURVIVE`.
2. `MISSED_DEADLINE_NO_RESULT` — freshness budget expires with no result.
   Target `ESCALATE`; control `SURVIVE`.
3. `UNADMITTED_FRESH_FAILURE` — even a fresh failure cannot authorize its own
   consequence. Target `ESCALATE`.
4. `UNRECOGNIZED_VERIFIER_FAILURE` — foreign verifier output is not standing
   evidence. Target `ESCALATE`.
5. `STALE_ADMITTED_FAILURE` — receiver admission cannot make stale evidence
   fresh. Target `ESCALATE`.
6. `FRESH_ADMITTED_PASS` — verified predicate still holds. Target `SURVIVE`.
7. `FRESH_ADMITTED_FAILURE` — fresh result from the recognized verifier,
   receiver-admitted, predicate fails. The gate emits `LOSS_OF_STANDING`;
   existing Decision Recall must `REOPEN` the target while the unrelated control
   `SURVIVE`s.

## Falsifiers

The candidate fails if any of these occur:

- an unadmitted, unrecognized, or stale result causes `REOPEN`;
- a missed verification deadline silently `SURVIVE`s;
- a fresh receiver-admitted predicate failure does not `REOPEN` the target;
- the unrelated control reopens;
- the accepted manifest changes after observation;
- any dependency edge is added after the outcome;
- the experiment modifies production semantics.

## Pass boundary

A pass earns only this narrow conclusion:

> A prospectively declared verification obligation plus receiver-owned admission
> is sufficient, in this injected case, to bridge previously external state into
> existing selective Decision Recall semantics without retroactive graph edits.

It does not establish automatic hidden-dependency discovery, verifier truth,
polling infrastructure, market demand, or production integration.
