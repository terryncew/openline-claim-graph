# OpenLine Claim Graph — Evidence Recall + Frame Ledger

> Something you relied on changed. Or a surface framed it in a consequential way. Show the exact mechanism, its source, and the receiver policy—without pretending the machine settled truth.

This prototype tests one narrow idea from the earlier OLP/DSM work:

> A small receipt can commit to a much larger, versioned argument state while carrying only the graph slice and source commitments a receiver needs now.

It does **not** put truth in a receipt. It records representations, their declared relations, their source anchors, and their history.

Status: `IMPACT_AND_FRAME_MECHANISMS_REPRODUCED_ON_NATURAL_MATERIAL_VALUE_UNTESTED`. It is not a promoted product, standard, bias oracle, or scientific result.

## What works now

The graph now has a native computational job: deterministic blast-radius analysis when accepted evidence is corrected, retracted, withdrawn, superseded, or revoked.

Input is one accepted graph state, one exact source-status event, and one receiver-owned edge policy. Output is a content-addressed report that separates:

- claims proposed for `QUARANTINE` because no admitted basis survives;
- claims that `SURVIVE` because an admitted alternative basis remains;
- claims that are `AFFECTED_UNRESOLVED` because the path includes an advisory edge; and
- claims outside the event's admitted blast radius.

The model cannot directly mutate accepted state. It may propose claims and edges; the receiver decides which relation IDs have hard authority, which are advisory, and which are ignored. The deterministic engine then computes the consequences of that admitted state.

See [the Evidence Recall contract](docs/EVIDENCE_RECALL.md) and open [`artifacts/plos-correction-impact/review.html`](artifacts/plos-correction-impact/review.html) for the checked-in real-event specimen.

The second native job is `Frame Ledger`: reproduce narrow framing devices from exact text, then keep any semantic interpretation under an explicit receiver-owned admission policy. The checked-in headline specimen identifies the exact conflict word, context cue, secrecy/security lexemes, a narrow local-attribution pattern, and two declared scoped absences. It refuses to convert those observations into a truth, intent, fairness, propaganda, rationalization, or bias verdict.

Models can run the advisory layer autonomously. A proposer emits exact-quote-anchored candidates; distinct receiver-pinned reviewers independently confirm, challenge, or abstain; signed heterogeneous-family quorum controls admission; and a proposer can never approve itself. Human confirmation is an explicit `OPTIONAL`, `REQUIRED`, or `DISABLED` receiver-policy choice.

See [the Frame Ledger contract](docs/FRAME_LEDGER.md) and open [`artifacts/wapo-headline-frame-ledger/review.html`](artifacts/wapo-headline-frame-ledger/review.html).

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
- A sealed automated receiver benchmark harness with gold/pack separation, deterministic full-factorial planning, fresh-process execution, resumable spend caps, strict identifier responses, and code-only scoring.
- Content-addressed source-status events with exact affected byte scopes and exact notice anchors.
- Receiver-owned hard/advisory edge authority; unadmitted relations are ignored and disclosed.
- Deterministic, cycle-safe support-path propagation with admitted-alternative preservation.
- Reproducible downstream witness paths and a fail-closed Evidence Recall HTML surface.
- A content-addressed Frame Ledger ruleset for exact epistemic lexemes, context cues, declared issue-frame lexemes, narrow local-attribution patterns, and scoped term-set absences.
- Signed AI proposal and review records with receiver-pinned keys, non-self-review, distinct-family quorum, challenge blocking, and optional/required/disabled human confirmation.
- Strict exact-quote import for model proposals; invented source text is rejected after schema-constrained generation.
- Provider-neutral OpenAI-compatible adapters for vLLM, SGLang, llama.cpp, and hosted open models, plus an official Responses API adapter using Structured Outputs with storage disabled.
- A fully unattended proposal → independent review → receiver-policy admission pipeline.

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
PYTHONPATH=src python examples/build_plos_correction_impact.py \
  --base artifacts/plos-correction-case \
  --output artifacts/plos-correction-impact
PYTHONPATH=src python scripts/verify_plos_correction_impact.py \
  --artifact artifacts/plos-correction-impact
PYTHONPATH=src python scripts/impact_differential_probe.py --iterations 2000
PYTHONPATH=src python scripts/scaling_probe.py
PYTHONPATH=src python scripts/build_arct_automated_receiver_pack.py \
  --output artifacts/automated-receiver-benchmark
PYTHONPATH=src python examples/build_wapo_frame_ledger.py \
  --output artifacts/wapo-headline-frame-ledger
PYTHONPATH=src python scripts/verify_wapo_frame_ledger.py \
  --artifact artifacts/wapo-headline-frame-ledger
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

Compute and render source impact from an accepted state:

```bash
openline-claim-graph impact \
  --snapshot artifacts/plos-correction-impact/accepted.snapshot.json \
  --sources artifacts/plos-correction-impact/sources.json \
  --event artifacts/plos-correction-impact/source-status-event.json \
  --policy artifacts/plos-correction-impact/impact-policy.json \
  --output /tmp/impact-report.json

openline-claim-graph render-impact \
  --report /tmp/impact-report.json \
  --snapshot artifacts/plos-correction-impact/accepted.snapshot.json \
  --sources artifacts/plos-correction-impact/sources.json \
  --event artifacts/plos-correction-impact/source-status-event.json \
  --policy artifacts/plos-correction-impact/impact-policy.json \
  --receipt artifacts/plos-correction-impact/accepted.receipt.json \
  --public-key d759793bbc13a2819a827c76adb6fba8a49aee007f49f2d0992d99b825ad2c48 \
  --output /tmp/evidence-recall.html
```

Impact computation fails closed on invalid graph, source, event, or policy commitments. Verification and rendering additionally require the signed accepted-state receipt and receiver-pinned key. Rendering does not mutate the accepted graph.

Reproduce and render the Frame Ledger specimen:

```bash
openline-claim-graph verify-frame \
  --report artifacts/wapo-headline-frame-ledger/report.json \
  --source artifacts/wapo-headline-frame-ledger/source.json \
  --findings artifacts/wapo-headline-frame-ledger/findings.json \
  --policy artifacts/wapo-headline-frame-ledger/policy.json

openline-claim-graph render-frame \
  --report artifacts/wapo-headline-frame-ledger/report.json \
  --source artifacts/wapo-headline-frame-ledger/source.json \
  --findings artifacts/wapo-headline-frame-ledger/findings.json \
  --policy artifacts/wapo-headline-frame-ledger/policy.json \
  --output /tmp/frame-ledger.html
```

The autonomous model lane is optional and unrun in this release. `scripts/run_autonomous_frame_pipeline.py` can call an official frontier endpoint or three separately served open-weight families, sign every proposal/review under configured execution keys, apply the receiver policy, and render the result without a mandatory human tap. Model-card candidates and their honest deployment tiers are recorded in [`docs/open-model-candidates.json`](docs/open-model-candidates.json); none is labeled as a benchmark winner.

## Evidence generated here

- 73 offline unit/adversarial/protocol/development/benchmark tests.
- 10,000 deterministic tamper mutations detected with zero misses.
- Exact-quote mislabeling is rejected.
- Paraphrase/inference labels remain admitted only as disclosed, semantically unverified mappings.
- Silent parent-record deletion is rejected.
- Conflicting branches cannot merge without an explicit resolution record.
- A 1,000-claim controlled graph produced a roughly 1.4 KB signed state receipt and a roughly 3.7 KB one-claim projection. The full snapshot was roughly 643 KB.

Those are mechanical results. The controlled fixture was designed here, so it is not evidence that the graph improves decisions on natural material.

### Frame Ledger on one natural headline

`artifacts/wapo-headline-frame-ledger/` audits the exact headline supplied by the maintainer. Seven findings reproduce: one conflict lexeme, one co-occurrence cue, two issue-frame lexemes, one local-attribution-pattern absence, and two receiver-declared term-set absences. An independent verifier that does not import the candidate Frame Ledger code reproduces 20 content, span, rule, policy, classification, and rendered-output checks.

The specimen includes only the headline, not the article body. It validates a deterministic mechanism on natural text. It does not validate the general ruleset against Media Frames Corpus or NewsWCL50, model competence, political neutrality, author intent, fairness, factual truth, rationalization, propaganda, reader effect, usefulness, or demand. No frontier/open-model call or incremental API spend was used to create it.

### Evidence Recall on a real correction event

`artifacts/plos-correction-impact/` starts from a signed accepted-state specimen and admits the later PLOS correction as a source-status event. Direct source lookup finds 5 exposed abstract claims. Dependency propagation proposes 7 claims for quarantine, including 2 downstream claims direct lookup misses. It preserves 1 related claim with an admitted alternative main-text basis, routes 1 advisory-edge exposure to unresolved review rather than hard quarantine, leaves 6 claims untouched, and identifies 1 accepted decision to reopen.

An independent verifier that does not import the impact engine reproduces the content hashes, accepted-state root, Ed25519 binding, event/policy/report IDs, classification sets, witness paths, and review hash. A separate 2,000-case randomized differential probe covers cycles, alternative support, required dependencies, advisory paths, and exact affected spans with zero oracle mismatches.

The PLOS article and correction are real. The downstream accepted-state dependencies are explicitly authored for the specimen. This earns a mechanical claim: **given this admitted graph, event, and policy, the blast radius is exact and reproducible.** It does not earn claims about extraction accuracy, historical completeness, scientific truth, user demand, or commercial value.

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

## Automated receiver benchmark

`experiments/automated_receiver_benchmark/` defines the immediate external-value
test for machine receivers. It preserves three arms:

- ordinary summarization;
- one frozen claim inventory rendered as prose; and
- the identical inventory rendered as verified structured state.

The public pack never contains the answer key. The separately stored gold file
is bound to the exact pack hash. Each trial starts a fresh receiver process,
passes one case and one arm on stdin, and requires strict JSON identifiers on
stdout. The deterministic scorer counts missing, malformed, timed-out, and
skipped trials as misses. No LLM judge is involved.

The common source packet and extracted inventory are included in the public
case. Their roots are recomputed. Arm B must equal the harness's deterministic
prose rendering of that inventory; Arm C must equal the inventory itself. This
closes accidental B/C content drift while leaving the honest remaining limit:
no hash can prove that the case author included every relevant fact.

Build and validate the checked-in development pack:

```bash
PYTHONPATH=src python scripts/build_arct_automated_receiver_pack.py \
  --output artifacts/automated-receiver-benchmark

PYTHONPATH=src python -m openline_claim_graph benchmark-validate \
  --pack artifacts/automated-receiver-benchmark/pack.json \
  --gold artifacts/automated-receiver-benchmark/gold.private.json
```

Create a plan, then run each frozen receiver command separately:

```bash
PYTHONPATH=src python -m openline_claim_graph benchmark-plan \
  --pack artifacts/automated-receiver-benchmark/pack.json \
  --receiver model-family-a@version \
  --receiver model-family-b@version \
  --output /tmp/receiver-plan.json

PYTHONPATH=src python -m openline_claim_graph benchmark-run \
  --pack artifacts/automated-receiver-benchmark/pack.json \
  --plan /tmp/receiver-plan.json \
  --receiver-id model-family-a@version \
  --output /tmp/model-a-responses.json \
  --max-cost-microusd 5000000 \
  -- python path/to/receiver_adapter.py
```

The receiver command is deliberately provider-neutral. It receives one trial
document on stdin and emits the strict answer schema on stdout. API keys and
provider SDKs stay outside the trusted core.

Finally, score all receiver files against the bound key:

```bash
PYTHONPATH=src python -m openline_claim_graph benchmark-score \
  --pack artifacts/automated-receiver-benchmark/pack.json \
  --gold artifacts/automated-receiver-benchmark/gold.private.json \
  --plan /tmp/receiver-plan.json \
  --responses /tmp/model-a-responses.json \
  --responses /tmp/model-b-responses.json \
  --output /tmp/receiver-score.json
```

The checked-in ARCT pack is `DEVELOPMENT_ONLY`. It is one public,
multiple-choice dataset with possible pretraining contamination and no negative
controls. It validates the harness and cannot pass the promotion gate. No
completed receiver efficacy result is included in this branch.

## Dormant human receiver protocol

`experiments/receiver_discovery_pilot/` contains the push-ready protocol and custody templates for the first human receiver pilot. It separates three effects:

- ordinary summarization;
- claim-level extraction rendered as prose;
- the same extraction rendered as a graph.

Condition is assigned between receivers, case selection is locked before mapping, positive keys require an explicit external anchor, and no-conflict cases measure false discovery. Stage 1 is an effect-size and operations pilot only; it cannot promote or archive the value claim.

The analyzed pilot case pack is intentionally empty. The ARCT development fixture is not an admitted Stage 1 case pack. No human trials or decision-value results exist yet.

This human protocol is not the immediate roadmap. It becomes relevant only if
a later claim concerns human comprehension; source-impact correctness does not
inherit that claim.

## Promotion status

`SOURCE_IMPACT_MECHANISM_VERIFIED_ON_REAL_EVENT_AUTHORED_DEPENDENCIES_VALUE_UNTESTED`

The existing DSM “Same Word, Different Rules” example is structurally useful but cannot serve as extraction-fidelity evidence: it explicitly paraphrases an anonymized exchange and does not include the raw source spans needed for independent recovery.

The deterministic source-impact mechanism now stands independently of the unresolved presentation claim:

> Given an accurate enough accepted dependency state, does catching downstream exposure after real corrections save enough missed-review cost to justify maintaining that state?

Nothing in this repository answers adoption or economic value yet. It does answer the narrower engineering question: the graph can perform exact, receiver-policy-bound evidence recall that a direct source lookup misses, without over-quarantining a branch with an admitted alternative basis.
