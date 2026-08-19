# Decision Recall Gain-Trigger Recompute Probe — Pre-Registered Protocol

Frozen before implementation: 2026-08-19

## Question

Does a gain/restoration trigger require per-node blocker recomputation beyond naive forward reachability and beyond the current Decision Recall loss-only state machine?

## Fixtures

A restored basis `A` is applied to three dependent nodes:

1. `X`: blocked solely by missing HARD prerequisite `A`.
2. `Y`: blocked by missing HARD prerequisites `A` and `B`, where `B` remains missing.
3. `Z`: blocked by missing HARD prerequisite `A` and an unresolved advisory/objection blocker `O`, where `O` remains open.

All other conditions are fixed.

## Competing procedures

### Naive reachability

Mark every node downstream of restored `A` as eligible.

### Condition-set recomputation

For each downstream node, remove only the blocker resolved by the restoration event and recompute the complete remaining blocker set. A node is auto-clean only if no HARD prerequisite, unresolved objection/advisory blocker, ceiling, or policy blocker remains.

## Frozen outcomes

### FAIL-NAIVE

Naive reachability marks any node eligible while a non-`A` blocker remains open.

This kills naive reachability as the gain-trigger algorithm. It does not by itself establish that a new subsystem is needed.

### KILL-EXTENSION

Condition-set recomputation produces no behavioral distinction not already represented and evaluated by the incumbent Decision Recall state machine.

### PASS-EXTENSION

Condition-set recomputation admits `X` after `A` is restored, withholds `Y` because `B` remains open, and withholds `Z` because `O` remains open; and the incumbent Decision Recall state machine does not currently represent/evaluate this gain-side blocker state.

## Scope boundary

A PASS earns only a narrow LOSS/GAIN trigger extension inside the existing Decision Recall state machine. It does not earn a new module, new brand, leverage score, opportunity-ranking system, or automatic authorization semantics.

## Adversarial boundary

Restoration can make a node reconsiderable only when all remaining blockers are closed. Restoration never upgrades evidence, overrides receiver policy, clears an unresolved objection, raises a ceiling, or self-certifies a dependent state.
