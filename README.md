# OpenLine Claim Graph — verified Decision Review prototype

This prototype tests one narrow idea from the earlier OLP/DSM work:

> A small receipt can commit to a much larger, versioned argument state while carrying only the graph slice and source commitments a receiver needs now.

It does **not** put truth in a receipt. It records representations, their declared relations, their source anchors, and their history.

Status: `EXPERIMENTAL_RECEIVER_REVIEW_PROTOTYPE`. It is not a promoted product, standard, or scientific result.

## What is implemented

- Typed claims: observations, measurements, source assertions, definitions, assumptions, inferences, causal hypotheses, predictions, value judgments, adjudications, outcomes, and unresolved questions.
- Typed relations: support, contradiction, dependence, definition, derivation, prediction, supersession, qualification, adjudication, and unresolved status.
- Content-addressed claim and relation IDs.
- Deterministic restricted canonical JSON. Floats are rejected rather than quietly canonicalized incorrectly.
- Exact UTF-8 source-span verification for records labeled `QUOTE`.
- Explicit warnings for `PARAPHRASE`, `INFERENCE`, and `AMBIGUOUS`; their semantic fidelity is not self-certified.
- Merkle graph roots and inclusion proofs for bounded projections.
- A separate source-manifest root so raw sources stay outside the portable receipt.
- Ed25519 graph-state receipts with receiver-pinned keys.
- Parent-state pointers and record-level deltas.
- Multi-parent merges that do not assume one lowest common ancestor.
- Mandatory conflict resolutions and reasons; parent records cannot disappear silently.
- An append-only wallet that preserves branches and merges.
- Deterministic branch comparison and disagreement reports without ranking a branch as true.
- A composed receiver verifier that checks every layer before returning `ADMIT`, `QUARANTINE`, or `DENY`.
- A fail-closed, self-contained HTML Decision Review that makes represented fault lines, exact source anchors, lineage, and verification limits readable without exposing raw graph JSON.

## The important trust split

| Layer | What it establishes | What it cannot establish |
|---|---|---|
| Source hash and span | The disclosed bytes and exact quote | Whether the source is honest |
| Claim ID and graph root | Exact represented structure | Semantic accuracy or truth |
| Signature with receiver pin | A pinned key signed that state | Wisdom, neutrality, or authority beyond the pin |
| Parent and delta | What was added, removed, or merged | Whether the revision improved the map |
| Projection proof | Records belong to the committed graph | That omitted context is irrelevant |
| Receiver policy | This receiver accepted the declared limitations | That another receiver should agree |

The actor-supplied label is never treated as its own proof. `QUOTE` is mechanically checked against the source bytes. Every other source-to-claim or source-to-relation mapping stays visibly unverified unless an independent process evaluates it later.

## Why this is smaller than the old architecture

There is no κ, Φ*, VKD, coherence score, truth score, reputation score, automatic extractor, RDF store, JSON-LD processor, ontology server, or W3C conformance claim.

The current core uses canonical JSON, SHA-256, Merkle proofs, and Ed25519. RDF Dataset Canonicalization, W3C Data Integrity, PROV-O, or nanopublication adapters would be interoperability work only. They inherit nothing until the minimal object demonstrates external value.

## Run it

Python 3.11+ and `cryptography` are required.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python examples/build_demo.py --output artifacts/demo
PYTHONPATH=src python examples/build_plos_correction_case.py --output artifacts/plos-correction-case
PYTHONPATH=src python scripts/scaling_probe.py
```

The demo creates a base policy state, two incompatible status branches, an explicit merge that preserves both conflicts, signed receipts, a receiver-scoped projection, source inclusion proofs, and an append-only wallet.

Complete receiver verification:

```bash
PYTHONPATH=src python -m openline_claim_graph verify-bundle \
  --snapshot artifacts/demo/merged.snapshot.json \
  --receipt artifacts/demo/merged.receipt.json \
  --sources artifacts/demo/sources.fixture.json \
  --projection artifacts/demo/projection.json \
  --disclosure artifacts/demo/source-disclosure.json \
  --policy artifacts/demo/receiver-policy.json \
  --public-key d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737 \
  --parent artifacts/demo/branch-a.snapshot.json \
  --parent artifacts/demo/branch-b.snapshot.json
```

The fixture public key is also recorded in `artifacts/demo/fixture-public-key.json`. It is deterministic test material, not a production identity.

Render a verified bundle as a static Decision Review:

```bash
PYTHONPATH=src python -m openline_claim_graph render-review \
  --snapshot artifacts/plos-correction-case/snapshot.json \
  --receipt artifacts/plos-correction-case/receipt.json \
  --sources artifacts/plos-correction-case/sources.json \
  --projection artifacts/plos-correction-case/projection.json \
  --disclosure artifacts/plos-correction-case/source-disclosure.json \
  --policy artifacts/plos-correction-case/receiver-policy.json \
  --public-key 17cb79fb2b4120f2b1ec65e4198d6e08b28e813feb01e4a400839b85e18080ce \
  --output /tmp/decision-review.html \
  --title "Published abstract vs. main results"
```

Rendering fails closed when the source, receipt, graph, projection, policy binding, or receiver key pin is invalid. `ADMIT` means only that the verified bundle satisfies the declared receiver policy; the page states this beside the disposition.

## Evidence generated here

- 36 offline unit/adversarial/protocol/development tests.
- 10,000 deterministic tamper mutations detected with zero misses.
- Exact-quote mislabeling is rejected.
- Paraphrase/inference labels remain admitted only as disclosed, semantically unverified mappings.
- Silent parent-record deletion is rejected.
- Conflicting branches cannot merge without an explicit resolution record.
- A 1,000-claim controlled graph produced a roughly 1.4 KB signed state receipt and a roughly 3.7 KB one-claim projection. The full snapshot was roughly 643 KB.

Those are mechanical results. The controlled fixture was designed here, so it is not evidence that the graph improves decisions on natural material.

### Natural-material review check

`artifacts/plos-correction-case/` applies the same mechanism to the abstract results and two main-results passages from a published PLOS ONE article. The generated Decision Review exposes five numerical conflicts. A later PLOS correction explicitly states that numbers in the abstract were inconsistent with the main text. The correction is kept outside the receiver bundle and recorded as an E1 external anchor.

This establishes that the review surface can carry a real, independently confirmed fault line without collapsing it into a score. It does **not** establish automated extraction, completeness, or an advantage over ordinary prose. Extraction for this case is manual and disclosed.

The checked-in upstream verification records exact excerpt matches against the PLOS Search API. Re-run it when auditing or updating the example:

```bash
PYTHONPATH=src python scripts/verify_plos_upstream.py \
  --output artifacts/plos-correction-case/upstream-verification.json
```

### Independent-gold development check

`experiments/development_benchmarks/arct/` adds a constrained real-data check against the independently annotated Argument Reasoning Comprehension Task. A deterministic 24-case subset was selected before labels were shown to the mapper. One frozen interactive pass chose the correct implicit warrant in 21 cases. The three errors are retained.

The executable check builds the blind mapping, the upstream gold mapping, and the opposite-warrant control for every case. All 72 graph states verify; the gold and opposite controls score 24/24 and 0/24; and the chosen warrant changes the committed root in every case.

This is a positive control for source-to-structure signal, not evidence of receiver value. It is multiple-choice, small, potentially exposed in model pretraining, and lacks an independent public prediction precommit. It does not enter the human pilot.

## Decision-value pilot

`experiments/receiver_discovery_pilot/` contains the push-ready protocol and custody templates for the first human receiver pilot. It separates three effects:

- ordinary summarization;
- claim-level extraction rendered as prose;
- the same extraction rendered as a graph.

Condition is assigned between receivers, case selection is locked before mapping, positive keys require an explicit external anchor, and no-conflict cases measure false discovery. Stage 1 is an effect-size and operations pilot only; it cannot promote or archive the value claim.

The analyzed pilot case pack is intentionally empty. The ARCT development fixture is not an admitted Stage 1 case pack. No human trials or decision-value results exist yet.

## Promotion status

`UNPROMOTED_EXTERNAL_VALUE_UNTESTED`

The existing DSM “Same Word, Different Rules” example is structurally useful but cannot serve as extraction-fidelity evidence: it explicitly paraphrases an anonymized exchange and does not include the raw source spans needed for independent recovery.

The unresolved claim is the only one that matters commercially or intellectually:

> Does a source-anchored argument graph help an independent receiver locate a consequential disagreement, revision, or missing premise better than the original sources plus an ordinary summary?

Nothing in this repository answers that yet.
