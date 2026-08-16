# Evidence Recall: source-impact contract

## The job

> Something you relied on changed. Show exactly what must be reconsidered, what still has an admitted alternative basis, and why.

This is not a claim that graphs are easier to read than prose. It is a deterministic operation over an accepted dependency state. A corrected, retracted, withdrawn, superseded, or revoked source-status event enters the system; the engine computes the downstream exposure implied by the exact graph and the receiver's exact admission policy.

The accepted graph is never mutated by this operation. The output is a proposed review surface.

## Conditional guarantee

Given:

1. one content-addressed accepted graph state;
2. one content-addressed source-status event with an exact evidence anchor;
3. one receiver-owned policy identifying hard and advisory relation IDs;

the implementation reproducibly classifies event-touched claims as:

- `QUARANTINE`: no admitted basis survives, or a required dependency was lost;
- `SURVIVES`: an admitted alternative basis remains;
- `AFFECTED_UNRESOLVED`: the exposure path includes an advisory edge;
- `UNAFFECTED`: no admitted event path reaches the claim.

This guarantee is conditional on the declared graph and policy. It does not establish that a claim, relation, source, or event scope is true or complete.

## Dependency semantics

Only three relation types carry source impact in v1:

| Relation record | Propagation direction | Meaning in this operation |
|---|---|---|
| `evidence SUPPORTS claim` | evidence → claim | Alternative support path |
| `claim DEPENDS_ON prerequisite` | prerequisite → claim | Required dependency |
| `claim DERIVED_FROM prerequisite` | prerequisite → claim | Required derivation |

All other relation types are ignored and disclosed. This is deliberate; `CONTRADICTS`, `QUALIFIES`, or `SUPERSEDES` do not have one safe propagation meaning without another policy decision.

Relation authority is not inferred from the relation's author. The receiver policy lists relation IDs as:

- **hard** — allowed to cause quarantine;
- **advisory** — allowed only to cause an unresolved review warning;
- **unadmitted** — ignored and reported.

An LLM may propose an edge. It cannot promote its own edge into hard authority.

## Support-path rule

Citation count is not the unit. Admitted support paths are.

- Five citations that all depend on one withdrawn experiment may collapse together.
- One corrected source does not kill a claim that retains a separate admitted source or supporter.
- A support cycle with no surviving grounded basis cannot keep itself alive.
- A required dependency is conjunctive: losing one admitted prerequisite reopens the dependent claim.

The engine computes the least fixed point of grounded surviving support, then propagates required-dependency loss and quarantines only event-touched claims that no longer have an admitted basis. This avoids both silent under-propagation and automatic poisoning of claims with an admitted alternative path. “Alternative” is conditional on the graph; the engine cannot discover an omitted common upstream source.

## Accepted state versus proposed state

The source-impact report binds:

- the accepted state root;
- the source-status event ID;
- the receiver policy ID;
- the exact classifications and witness paths.

It does not delete claims or advance the wallet. A receiver can use the report to construct a later candidate state, but only an explicit receiver action can admit that state.

## Real-event specimen

`artifacts/plos-correction-impact/` applies the operation to a real PLOS correction. The correction states that numbers in the article abstract were inconsistent with the main text.

The signed accepted-state specimen includes five abstract measurements, five main-text measurements, and explicitly authored downstream review/decision dependencies. On the admitted correction event:

- direct source lookup exposes 5 claims;
- graph propagation proposes 7 claims for quarantine, including 2 downstream claims direct lookup misses;
- 1 related claim survives because a main-text support path remains;
- 1 claim remains unresolved because its path contains an advisory edge;
- 1 accepted decision is touched;
- 6 claims remain outside the event's blast radius.

An independent verifier that does not import the impact engine reproduces the graph roots, Ed25519 receipt binding, event/policy/report IDs, exposure sets, witness paths, survival on an admitted alternative basis, and rendered review hash.

The article and correction are natural material. The downstream dependency state is an authored specimen. Therefore the earned result is implementation and mechanism evidence, not extraction accuracy, historical completeness, user demand, or scientific adjudication.

## Reusable validation playbook

1. Start with a real external status event.
2. Bind an accepted pre-event state before applying the event.
3. Make dependency direction and edge authority explicit.
4. Compare against direct-only source lookup.
5. Include a separately admitted support path to test over-quarantine.
6. Include an advisory edge to test authority laundering.
7. Recompute with independent code.
8. Run randomized differential tests across cycles and alternative paths.
9. Present the result as a proposed review, never an automatic mutation.
10. State separately what is real, authored, mechanically proven, and still untested.

That playbook can be reused for retracted studies, restated financials, superseded regulations, overturned precedents, revoked threat intelligence, or any bounded accepted state whose upstream evidence can later change.
