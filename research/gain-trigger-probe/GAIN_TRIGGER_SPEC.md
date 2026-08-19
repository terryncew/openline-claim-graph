# Decision Recall Gain Trigger — Earned Extension Spec

Status: EXPERIMENTAL / NOT PRODUCTION
Earned by: pre-registered gain-trigger recomputation probe

## Narrow capability

Add a second standing transition direction to Decision Recall:

- `LOSS_OF_STANDING`: existing behavior; may force REOPEN/ESCALATE/SURVIVE.
- `GAIN_OF_STANDING`: new candidate behavior; recomputes whether a previously blocked decision has any complete sufficient support set and no independent unresolved blocker.

The trigger traverses the same prerequisite→dependent direction. The asymmetry is logical, not directional.

## Required state

A gain trigger cannot be evaluated from path existence alone. The evaluator must be bound to an explicit pre-trigger standing state containing:

- standing/non-standing status for every dependency referenced by the decision manifest;
- unresolved blocker identifiers that are independently receiver-owned (e.g. unresolved objection, ceiling, policy hold);
- a content-addressed state root so the event cannot be applied to a stale or caller-invented blocker state.

The accepted decision manifest remains immutable. Standing state is a separate runtime/adjudication object.

## Sufficient-support semantics

For one decision manifest, define its declared sufficient support sets exactly as the incumbent does:

- the complete `required_dependencies` set, if non-empty;
- each declared `alternative_support[].dependency_ids` group.

A support set is complete iff every dependency in that set is currently standing.

## Gain evaluation

Given exact pre-trigger state S and exact `GAIN_OF_STANDING(A)` event:

1. Require A to exist in the bound dependency universe.
2. Require A to be non-standing in S; otherwise return NO_CHANGE / replay-safe.
3. Produce S' by changing only A to standing.
4. For each decision that declares A in at least one support set, recompute all support sets from S'.
5. If no complete sufficient support set exists, decision remains blocked.
6. If at least one complete support set exists but any independent unresolved blocker remains open, decision is `AFFECTED_UNRESOLVED` / review-only.
7. Only if a complete support set exists and no independent blocker remains may the engine emit an auto-clean *projection*.
8. The projection does not mutate accepted state or confer execution authority. Receiver-owned admission remains separate.

## Output discipline

Do not add a new branded subsystem or scoring layer. Reuse existing review semantics where possible.

Candidate output distinctions:

- `NO_CHANGE`: restoration did not remove the decision's last relevant blocker.
- `AFFECTED_UNRESOLVED`: support completeness changed but another blocker remains.
- `RECONSIDERABLE`: all recorded blockers are closed under the exact bound state.

`RECONSIDERABLE` means eligible for receiver re-adjudication/admission, not automatically true, correct, executable, or authorized.

## Security / boundary invariants

- Exact basis binding: an event for A cannot satisfy B or an alias.
- Exact state binding: stale/caller-supplied standing state cannot be silently substituted.
- Single-effect transition: one gain event changes one basis standing fact.
- No blocker laundering: gain cannot clear objections, ceilings, or policy holds.
- Idempotence: replaying the same gain against already-restored state cannot create a second effect.
- No self-certification: producer/model assertions cannot mark their own blockers resolved unless receiver policy already grants that authority.
- No accepted-state mutation: output is a proposed re-adjudication surface.

## Kill boundary

If the incumbent can already reproduce these gain-side distinctions from existing bound state without new standing/blocker state, do not add this extension.
