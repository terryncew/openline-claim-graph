# Assessment

## Verdict

The idea survives as a working integrity and lineage mechanism. It has not earned standing as a useful extraction or decision system.

The durable correction to Coherence Dynamics is architectural:

> Do not compress reasoning into a sender-certified scalar. Preserve its typed structure, version it, and let a receiver decide what that structure earns.

## What the implementation established

The prototype can create a small signed commitment to a larger graph state; reproduce its deterministic root; bind it to source commitments; disclose and verify a bounded graph/source slice; retain branches; expose incompatible slots; and prevent a merge from silently deleting or reconciling conflicting claims.

It also closes the easiest provenance forgery. A producer cannot label a paraphrase as `QUOTE` unless the claim text exactly matches the declared UTF-8 source span. This is narrower than semantic extraction fidelity but materially stronger than trusting `EXTRACTED` because the producer typed it.

The receipt-size design initially contained every source commitment and every warning, which made it grow with the graph. That failed the stated efficiency goal. Both collections were replaced with Merkle roots, counts, and compact warning categories. Only projection-relevant source commitments travel with inclusion proofs.

## What remains outside the instrument

The prototype cannot verify that:

- a paraphrase preserves meaning;
- an inferred relation follows from its cited material;
- the ontology divides the subject fairly;
- a bounded projection did not omit decisive context;
- the resulting map improves a real receiver's judgment.

An extraction-process receipt containing a model ID, prompt digest, and source digest would improve reproducibility. It would **not** prove semantic fidelity. It identifies the machine that made the translation; it does not make the translation correct.

## Relation to the prior work

DSM already contained the useful beginning: explicit nodes and edges, temporal graph hashes, previous-state references, and separate provenance channels. Its scalar stress/coherence layer did not survive external testing. The prototype keeps the graph and custody ideas and removes the scores.

The original OLP receipt idea also survives, but in a narrower form. The receipt does not carry the whole graph or certify a global state of knowledge. It commits to one graph state and provides a receiver-scoped projection with verifiable lineage.

The wallet is therefore not a truth ledger. It is custody for evolving representations—closer to Git history for arguments than a database of certified facts.

## Current disposition

`KEEP_AS_EXPERIMENTAL_ARTIFACT`

`DO_NOT_CLAIM_EXTERNAL_DECISION_VALUE`

`DO_NOT_ADD_RDF_OR_STANDARDS_INFRASTRUCTURE_YET`

The receiver-discovery pilot protocol is now included, but its case pack is empty and it has not been run. It fixes the case-admission, custody, three-arm estimand, between-receiver assignment, scoring, and Stage 1/Stage 2 boundaries before any result exists. That is experimental discipline, not evidence of value.

No experiment API calls, paid executions, receiver trials, or model-based grading were performed during this build.
