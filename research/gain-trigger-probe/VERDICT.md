# Gain-Trigger Recompute Probe — Verdict

## Result

**PASS-EXTENSION / FAIL-NAIVE**

The pre-registered fixture separated naive forward reachability from blocker-complete recomputation exactly as predicted:

- X, blocked only by A: becomes RECONSIDERABLE after A is restored.
- Y, blocked by A + B: remains blocked because B is still open.
- Z, blocked by A + unresolved objection O: becomes AFFECTED_UNRESOLVED, not auto-clean.

Naive reachability surfaced X, Y, and Z. It therefore failed the frozen FAIL-NAIVE criterion on Y and Z.

## Incumbent comparison

The current Decision Recall implementation is loss-only at the trigger layer:

- EVENT_TYPES contains only LOSS_OF_STANDING.
- create_revocation_event() creates only LOSS_OF_STANDING events.
- run_predictions() validates only revocation events.
- disposition logic evaluates one basis-loss event against the accepted decision manifest.

The manifest already contains the important positive structure — required dependency sets and alternative sufficient support groups — so the gain-side extension should reuse that structure. What it does not currently bind is the time-varying pre-trigger standing/blocker state required to distinguish “A restored and everything else satisfied” from “A restored but B/objection/policy blocker still open.”

Therefore KILL-EXTENSION did not fire: gain-side blocker completeness is not currently represented/evaluated by the incumbent trigger state machine.

## Adversarial finding and repair

The first experimental gain evaluator had a real attribution bug: if an independent alternative support set C was already sufficient before A returned, restoring A caused the decision to be surfaced as RECONSIDERABLE even though A changed nothing material.

Repair: gain output is now a **before/after state delta**, not a post-state classification dump. A decision is surfaced only when restoration changes its recorded blocker/support state.

After repair, 8/8 adversarial checks passed:

1. sole blocker restoration;
2. second HARD blocker not laundered;
3. unresolved objection not laundered;
4. already-sufficient alternative not falsely credited to gain;
5. idempotent replay;
6. stale state root rejected;
7. unknown basis has no effect;
8. exact basis binding.

## Earned implementation scope

Only this is earned:

1. a content-addressed runtime standing/blocker state bound to the accepted manifest/stream;
2. a GAIN_OF_STANDING event changing exactly one basis fact;
3. before/after recomputation of existing sufficient-support sets;
4. review-only AFFECTED_UNRESOLVED when independent blockers remain;
5. RECONSIDERABLE only when the restoration actually closes the final recorded blocker set;
6. no automatic accepted-state mutation or execution authority.

No new product/module name, leverage score, opportunity ranking, or cancer/science framework is earned.

## Repository status

No repository mutation was made. The GitHub integration could read `terryncew/openline-claim-graph` but returned HTTP 403 when creating the experiment branch. Production implementation should not be claimed until the repo write path is available and the extension is run through the repository's full release/adversarial suite.
