# SRE-001 — Standing Recall Test: External Lifecycle

Status: `FROZEN_PROTOCOL_CONFORMANCE_PASS_EXTERNAL_ADAPTATION_UNRUN`  
Policy authority: `NONE`  
Repository role: experiment inside OpenLine Claim Graph; no production inference semantics change.

## Question

Can a system preserve an already-finalized decision when enough admissible support
survives, while reopening a downstream decision that depended on a narrower property
whose support later lost standing?

The experiment begins **after** every scored decision was validly finalized.

At `t0`, all admitted evidence used by the scored decisions has acceptable standing.
At `t1`, finalized decisions create downstream state.
At `t2`, one previously acceptable external evidence item receives a lifecycle event:
`EXPIRE`, `REVOKE`, `SUPERSEDE`, or `CORRECT`.
At `t3`, each system must identify exactly which finalized decisions are no longer
entitled to remain closed.

The root evidence need not become false. SRE-001 changes receiver-admissible standing,
not historical bytes.

## Frozen novelty boundary

OpenLine does **not** claim to invent dependency rollback, cascade withdrawal,
selective replay, or revocation propagation.

Dependency-Guided Rollback Repair (DGRR; arXiv:2608.10502) already traces a typed
memory-to-action graph after diagnosed faulty memories, preserves independently
supported state, and selectively replays affected computation.

MemoRepair (arXiv:2605.07242) already withdraws descendants of invalidated memory
artifacts, reconstructs successors from retained support, and republishes validated
predecessor-closed state.

The candidate contribution tested here is narrower:

> receiver-owned standing over already-finalized decisions, where an evidence artifact
> may remain factually unchanged yet cease to be admissible for a particular use, and
> where downstream reliance is evaluated at the exact property/value relied upon rather
> than only at whole-node reachability.

If a faithful DGRR or MemoRepair implementation handles the frozen delayed-standing
cases with equal recall, preservation, and repair surface **without adding a
receiver-owned property-standing primitive**, the candidate mechanism is not novel
enough to promote.

## Why the published benchmarks are not being claimed

No author implementation or public benchmark repository was linked from the arXiv
records when this protocol was frozen. The checked conformance corpus therefore uses
the published problem shapes but is **not** either authors' benchmark, ToolBench,
MemoryArena, or LongMemEval-V2.

The external benchmark claim remains unrun until an author artifact can be executed or
a reproduction is constructed from source material with a separately frozen adaptation
manifest.

## Centerpiece adversarial case

```
E1 + E2 -> D1

E1 later loses standing.
E2 independently still supports every property required for D1 itself.
D1 therefore remains closed.

D1 exports:
  core     <- E1 or E2
  special  <- E1 only

D2 relies specifically on D1.special.
D2 must reopen.

D3 relies on D1.core.
D3 must remain closed.
```

A whole-node graph can see that `D1` survived and incorrectly preserve both descendants.
SRE-001 asks whether the system retains the distinction between the surviving decision
and the narrower exported property whose basis disappeared.

## Event semantics

All four event classes occur after finalization.

- `EXPIRE`: receiver policy no longer accepts the evidence after its validity window.
- `REVOKE`: an authoritative revocation removes admissibility for future reliance.
- `SUPERSEDE`: the old artifact is displaced by a successor; SRE-001 does not silently
  substitute a successor into a finalized basis that did not use it at `t0`.
- `CORRECT`: a correction removes standing from the old artifact; historical bytes remain
  part of the record.

The conformance fixture intentionally keeps the invalidated root's bytes unchanged so
truth-change and standing-change are not conflated.

## Compared systems

### 1. `DGRR_STYLE_NODE_SUPPORT_V1`

A paper-inspired abstraction, not the authors' code or reported result.

It starts from the diagnosed/invalidation root, traces downstream nodes, and preserves
a candidate when an unaffected or already-preserved predecessor remains trusted.
The adaptation stays at whole-node granularity. It is deliberately denied OpenLine's
property/value standing primitive.

### 2. `MEMOREPAIR_STYLE_CASCADE_V1`

A paper-inspired abstraction, not the authors' code, min-cut selector, or validation
suite.

It withdraws the full affected cascade first, then republishes a decision when a
servable predecessor remains available. It preserves the barrier/predecessor-closure
shape while remaining at whole-artifact granularity.

### 3. `OPENLINE_STANDING_PROPAGATION_V1`

Receiver-owned recomputation at the exact facet/value named by a finalized dependency.
A decision may remain standing while one exported facet loses standing. Only decisions
whose complete required support becomes insufficient are reopened.

No output from this experiment has execution authority.

## Primary metrics

For the scored decision universe:

1. **Affected-decision recall**  
   `TP / (TP + FN)` for decisions whose standing truly changed from valid to invalid.

2. **Unaffected-state preservation**  
   `TN / (TN + FP)` for finalized decisions that still have sufficient admitted support.

3. **Replay surface**  
   Count of decision nodes a method marks for replay/repair/withdrawal. Standing
   recomputation itself is not counted as replay.

`analysis_surface` is recorded as a diagnostic only.

## Conformance corpus

The checked deterministic corpus contains 64 episodes:

- 16 `EXPIRE`
- 16 `REVOKE`
- 16 `SUPERSEDE`
- 16 `CORRECT`

Each event type crosses four support patterns and four topology variants:

- sole support,
- complete independent alternative support,
- partial-facet alternative support,
- reachable but non-required affected facet.

The corpus is a hostile mechanics check. It is constructed to contain cases where
whole-node preservation is insufficient. Passing it earns **no external performance
claim**.

## External promotion gate

The external adaptation must be frozen before its outcomes are scored and must contain:

- at least 40 post-finalization lifecycle episodes,
- at least 10 episodes for each of the four event classes,
- both `REOPEN` and `SURVIVE` gold outcomes,
- at least 10 cases with independent alternative support,
- at least 10 cases where a surviving upstream decision has a narrower downstream
  property dependency,
- a source-to-adaptation manifest identifying every transformed episode,
- gold generated independently of system predictions.

Promotion requires all of the following:

- OpenLine affected-decision recall >= 0.95;
- OpenLine unaffected-state preservation >= 0.95;
- zero additional missed reopenings versus the strongest comparison baseline;
- zero additional false reopenings versus the strongest comparison baseline;
- replay surface at least 10% lower than the best baseline that matches OpenLine on
  both recall and preservation;
- independent verifier reproduces every primary metric with zero mismatches.

If no baseline matches OpenLine on recall and preservation, replay-surface advantage is
reported descriptively and does not substitute for the accuracy requirement.

## Explicit falsifiers

Stop or narrow the mechanism claim if any of these occurs:

1. A faithful unmodified MemoRepair implementation handles the delayed standing cases
   with the same decision precision and replay surface.
2. DGRR's published independent-support representation already carries the exact
   property/value semantics needed for the centerpiece case.
3. OpenLine preserves a decision whose required property has no admitted surviving
   basis.
4. OpenLine reopens an independently supported branch merely because an ancestor was
   reachable from the event.
5. The external result depends on post-outcome threshold changes, event redefinition,
   or adding support edges after predictions are inspected.

## Non-claims

SRE-001 does not establish truth, hidden-dependency discovery, broad agent reliability,
irreversible side-effect rollback, natural revocation frequency, commercial value, or
superiority over the authors' systems.

The checked status remains:

`FROZEN_PROTOCOL_CONFORMANCE_PASS_EXTERNAL_ADAPTATION_UNRUN`
