# CLAIMGRAPH-UNOBSERVED-STATE-001 — unobserved external state

Status: `FROZEN_PROTOCOL`

Frozen base: `e5b272bb048bd6b224eb430ebd9931713698cc13`

Current Decision Recall source blob: `7c1ad6e23411364008a3abb41fa662e966880e89`

## Question

Can OpenLine selectively reconsider an already-accepted decision when a materially relevant external tool/system state changes **outside the decision's frozen recorded dependency closure**, and that state is later supplied first as declared replay state and then as fresh verification evidence?

This is a discriminating test, not a feature build. The experiment must not add the missing external state to the accepted manifest after outcome inspection.

## Historical anchor

The injected target decision is anchored to the existing accepted PLOS Claim Graph state:

- receipt: `artifacts/plos-correction-impact/accepted.receipt.json`
- graph state root: `4486fb3f7333b9cc29003066be6aa4a0ee633e392529190527b21c96ef2f072c`
- target accepted claim: `claim:sha256:d14f3b5beeebd36bcc2e59b0860612455b6b018ec5bf52100d5ab3b0067d283c`
  - “Use $3,675 as the adjusted TRD versus non-MDD cost difference in downstream planning.”
- unrelated control claim: `claim:sha256:0056fca46714576870c52cae36ad84d394c6c0c3e93f4e03c3588158edacce53`

The experiment does not rewrite that historical graph or receipt. It injects a Decision Recall manifest whose recorded support is frozen and deliberately omits the external registry state under test.

## Unobserved state

A hypothetical receiver-recognized planning-policy registry has state:

- `t0`: `ELIGIBLE`
- `t1`: `WITHDRAWN`

The registry state is materially relevant to continued use of the target planning decision, but it was not represented in the accepted dependency manifest at `t0`.

This is intentionally the DNative-Twin failure shape: a consequential tool/system state changes outside the represented graph.

## Three frozen arms

### A — GRAPH_ONLY

Input: frozen accepted dependency record only.

Expected diagnostic: the system cannot observe the external divergence from graph structure alone. The target therefore remains `SURVIVE`; unresolved-divergence recall is 0 for this injected case.

This arm is not itself the falsifier. A graph cannot react to state it has never been shown.

### B — GRAPH_PLUS_DECLARED_REPLAY_STATE

Input: frozen record plus a declared state divergence referring to the previously unrepresented external registry state, without verification sufficient to change standing.

Desired behavior: target becomes `ESCALATE` / affected-unresolved; unrelated control remains `SURVIVE`.

A system that still returns `SURVIVE` has no representation for “newly surfaced but not yet verified material state.”

### C — GRAPH_PLUS_FRESH_VERIFICATION

Input: frozen record plus fresh receiver-admissible verification that the external registry moved from `ELIGIBLE` to `WITHDRAWN` and that this state is required for continued standing of the target decision.

Desired behavior: target `REOPEN`; unrelated control `SURVIVE`.

This is the falsifier arm.

## Current-code binding

The experiment calls the existing `openline_claim_graph.decision_recall._decision_recall_disposition` function without changing production semantics.

At the frozen base, that function explicitly returns `SURVIVE` when the event basis is absent from the accepted dependency record. The experiment tests whether that rule causes fresh verification about previously unrepresented material state to be silently kept.

## Metrics

For each arm record:

- target disposition;
- unrelated-control disposition;
- unresolved/reopen recall for the target;
- unrelated-state preservation;
- whether the accepted manifest changed;
- whether any post-outcome dependency edge was added.

## Falsifier

`CLAIMGRAPH_UNOBSERVED_STATE_FALSIFIED` if fresh admissible verification of a materially relevant external state is supplied, the target dependency was absent from the frozen accepted record, and current Decision Recall still returns `SURVIVE` for the affected decision.

If triggered, the earned conclusion is narrow:

> Current Claim Graph / Decision Recall can propagate standing changes over dependencies it prospectively represented, but it lacks a prospective contract for verification obligations over consequential state that was not represented in the accepted dependency closure.

The next candidate primitive is an explicit **verification dependency / replay contract**. Do not patch propagation logic to smuggle the missing dependency in after the fact.

## Non-claims

This experiment does not claim automatic hidden-dependency discovery, truth, authority of arbitrary verifier output, autonomous rollback, or superiority over DNative-Twin. It tests one missing contract boundary only.
