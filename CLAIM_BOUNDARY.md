# Claim boundary

This is an experimental receiver-review prototype, not a promoted OpenLine product.

It demonstrates that a receiver can verify:

- deterministic identities for typed claims and relations;
- exact UTF-8 source spans for records labeled `QUOTE`;
- disclosure when a source-to-claim mapping is a paraphrase, inference, or ambiguity;
- signed graph-state commitments under a receiver-pinned Ed25519 key;
- explicit parent pointers, record-level deltas, and multi-parent conflict handling;
- bounded graph projections and source-manifest inclusion proofs;
- append-only custody of branches and merges.
- fail-closed rendering of a verified bundle as a static human-readable review.

It does **not** demonstrate:

- open-ended automated extraction accuracy on natural material;
- semantic fidelity of paraphrases, inferences, or relation labels;
- completeness or neutrality of a selected graph projection;
- ontology neutrality;
- improved human or agent decisions versus a source bundle or ordinary summary;
- RDF, JSON-LD, JCS, W3C Data Integrity, or PROV-O conformance;
- truth, coherence, reputation, consciousness, safety, or authorization.

The graph records representations and relations among representations. Reality remains outside the receipt.

## Natural-material contact

Version `0.1.0.dev3` renders one real PLOS ONE abstract/main-text inconsistency. The receiver bundle exposes five numerical conflicts from the original article; a later correction explicitly confirms that abstract numbers were inconsistent with the main text. The correction stays outside the receiver bundle.

This demonstrates that the verified surface can preserve an independently confirmed natural-material fault line. The mapping is manual, the case count is one, and no blinded receiver comparison exists. It is not evidence that graphs outperform careful prose, that extraction can be automated reliably, or that the surface improves decisions.

## Independent-gold development check

Version `0.1.0.dev2` adds one narrow outside-labeled positive control. A single interactive model pass chose between two proposed missing premises for 24 deterministically selected ARCT arguments while the gold labels were withheld. It matched 21/24 upstream labels. The graph code then committed the chosen premise, reproduced the 21/24 score, made the upstream oracle score 24/24, made the opposite-warrant control score 0/24, and produced distinct gold/decoy roots for every case.

That result shows non-random signal in one small multiple-choice source-to-structure check. It does not establish open-ended extraction fidelity, model generalization, graph usefulness to a receiver, or any claim in the unrun three-arm pilot. ARCT is public and old enough that model-training contamination cannot be excluded. The prediction vector was ordered before label reveal in the build conversation, but it did not receive an independent public timestamped precommit.
