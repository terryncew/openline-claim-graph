# OpenLine Human-Facing Contract

OpenLine mechanisms may be complicated underneath. Their canonical human-facing projection is four lines:

**POINT** — What is the narrowest conclusion justified right now?

**BECAUSE** — What reproducible facts make that conclusion warranted?

**BUT** — What is the strongest material reason it could be wrong, incomplete, or overstated?

**SO** — What is the smallest consequence justified by the first three lines?

This is a projection contract, not a new subsystem or ontology. Evidence Recall, Frame Ledger, Receipt Gate, Successor Gate, and later mechanisms can do different jobs underneath while answering the same four questions at the human boundary.

## Hard rules

1. The four lines are constrained outputs of the mechanism, not freehand prose added after the result is known.
2. Every line must carry an audit path to the artifacts and exact fields that produced it. The visible card may stay terse; the audit path must be able to descend to the committed bytes.
3. `POINT` cannot claim more certainty, scope, or modality than the evidence earns. If the evidence earns only “may,” the projection cannot silently promote it to “is.”
4. `BECAUSE` must state reproducible facts, not persuasive interpretation.
5. `BUT` is mandatory and must represent the strongest material challenge available inside the audited scope. Boilerplate uncertainty language is not a substitute.
6. `SO` cannot outrun `POINT` or erase `BUT`. The consequence must be the minimum action or disposition justified by the whole card.
7. No finding is a valid finding. The mechanism does not owe the user a verdict.

An honest failure form is therefore:

```text
POINT
There is not enough evidence to make a finding.

BECAUSE
The observed pattern is reproducible, but the necessary comparison is missing.

BUT
The pattern could still matter if unequal treatment is established later.

SO
Preserve the observation. Take no further action.
```

The philosophy is simple: do not ask the mechanism to narrate what it meant. Require it to show what happened, what materially challenges the conclusion, and what follows.

## Current 0.5.2 implementation

The temporal-selectivity replication builder emits `POINT_BECAUSE_BUT_SO.md` from the scored benchmark, promotion result, and custody limits. It also emits `POINT_BECAUSE_BUT_SO.audit.json`, which binds each visible line to the exact source artifacts and JSON pointers used to produce it. The independent verifier reconstructs the four lines from those artifacts and fails if the rendered card or audit bindings drift.

That makes the four-line card a checked projection of the machinery rather than a decorative summary.
