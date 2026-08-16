# OpenLine Claim Graph — mechanical prototype

This prototype tests one narrow idea from the earlier OLP/DSM work:

> A small receipt can commit to a much larger, versioned argument state while carrying only the graph slice and source commitments a receiver needs now.

It does **not** put truth in a receipt. It records representations, their declared relations, their source anchors, and their history.

Status: `EXPERIMENTAL_MECHANICAL_PROTOTYPE`. It is not a promoted product, standard, or scientific result.

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

## Evidence generated here

- 23 offline unit/adversarial tests.
- 10,000 deterministic tamper mutations detected with zero misses.
- Exact-quote mislabeling is rejected.
- Paraphrase/inference labels remain admitted only as disclosed, semantically unverified mappings.
- Silent parent-record deletion is rejected.
- Conflicting branches cannot merge without an explicit resolution record.
- A 1,000-claim controlled graph produced a roughly 1.4 KB signed state receipt and a roughly 3.7 KB one-claim projection. The full snapshot was roughly 643 KB.

Those are mechanical results. The controlled fixture was designed here, so it is not evidence that the graph improves decisions on natural material.

## Promotion status

`UNPROMOTED_EXTERNAL_VALUE_UNTESTED`

The existing DSM “Same Word, Different Rules” example is structurally useful but cannot serve as extraction-fidelity evidence: it explicitly paraphrases an anonymized exchange and does not include the raw source spans needed for independent recovery.

The unresolved claim is the only one that matters commercially or intellectually:

> Does a source-anchored argument graph help an independent receiver locate a consequential disagreement, revision, or missing premise better than the original sources plus an ordinary summary?

Nothing in this repository answers that yet.
