# OpenLine Claim Graph — Evidence Recall

> Something you relied on changed. Compute what depended on it, preserve what still has an admitted basis, and show what still requires review.

OpenLine Claim Graph is an open-source Python system for tracing which accepted claims and decisions need reconsideration when upstream evidence changes.

The core job is deliberately narrow: given an accepted dependency graph, an exact source-status event, and a receiver-owned relation policy, compute the downstream consequence without pretending the graph settled truth.

**Latest stable release: `0.5.2`.** In a five-episode historical replication with 14 explicitly scored targets, frozen Evidence Recall caught **8/8 warranted reopenings** while reviewing **8 targets instead of 14** under Review-All Reachability: a **42.85% reduction in review load with zero additional misses**. Three trigger episodes are related Sato retractions evaluated through the same later Avenell audit, so this is a small historical replication, not broad-domain proof.

## Experimental Standing Recall result

The repository now also contains two frozen Standing Recall experiments asking a later question: **when evidence that once legitimately supported a finalized decision later loses standing, how little previously valid state must be reopened?**

The result narrowed the claim rather than expanding it. A strong property-aware MemoRepair-style baseline matched OpenLine on scored correctness in both evaluations. The surviving distinction was repair selectivity.

| Evaluation | OpenLine recall | OpenLine preservation | OpenLine replay surface | Accuracy-matching MemoRepair-style surface |
|---|---:|---:|---:|---:|
| SRE-001: external LongMemEval-V2 adaptation | 100% | 100% | 40 | 120 |
| SRE-002: 8 natural public lifecycle events | 100% | 100% | 12 | 24 |

SRE-001 therefore showed a **66.67%** smaller replay surface on its controlled lifecycle adaptation. SRE-002 showed a **50%** smaller replay surface across 24 target dispositions drawn from eight natural public-record events.

The boundary is important. DGRR and MemoRepair comparisons are contract abstractions, not author implementations. SRE-001's lifecycle events are controlled adaptations. SRE-002's event occurrence and target dispositions are public-record anchored, but its dependency/facet mappings are retrospective human-authored representations. Standing Recall is **experimental** and has not been promoted into the stable production API.

See [`docs/STANDING_RECALL.md`](docs/STANDING_RECALL.md) and the permanent evidence ledger under [`artifacts/standing-recall/`](artifacts/standing-recall/).

## What it does

Evidence Recall answers a practical question: **if evidence changes, what downstream state must be reconsidered?**

The model may propose claims and relations. It cannot directly grant those relations authority. The receiver decides which relation IDs are `HARD`, `ADVISORY`, or unadmitted. The deterministic engine then computes the blast radius of the exact event against that accepted state.

For each reachable claim, the engine distinguishes:

- `QUARANTINE` — no admitted basis survives;
- `SURVIVE` — an admitted alternative basis remains;
- `AFFECTED_UNRESOLVED` — an advisory path makes human review necessary; and
- unaffected claims outside the admitted blast radius.

The output includes reproducible witness paths and content-addressed artifacts so the visible consequence can be audited back to the committed inputs.

See [`docs/EVIDENCE_RECALL.md`](docs/EVIDENCE_RECALL.md) for the mechanism contract and [`artifacts/plos-correction-impact/review.html`](artifacts/plos-correction-impact/review.html) for a checked-in event specimen.

## Human-facing contract

Every mechanism should be able to project its result through the same four questions:

**POINT** — What is the narrowest conclusion justified right now?  
**BECAUSE** — What reproducible facts make that conclusion warranted?  
**BUT** — What is the strongest material reason it could be wrong, incomplete, or overstated?  
**SO** — What is the smallest consequence justified by the first three lines?

These are constrained outputs, not an after-the-fact summary. `POINT` cannot claim more certainty than the evidence earns. `BUT` cannot be replaced by boilerplate uncertainty language. `SO` cannot outrun `POINT` or erase `BUT`. A valid result may be that there is not enough evidence to make a finding.

The full contract is in [`HUMAN_CONTRACT.md`](HUMAN_CONTRACT.md). The 0.5.2 replication emits both a visible [`POINT_BECAUSE_BUT_SO.md`](artifacts/evidence-recall-temporal/replication-001-selectivity/POINT_BECAUSE_BUT_SO.md) card and a [`POINT_BECAUSE_BUT_SO.audit.json`](artifacts/evidence-recall-temporal/replication-001-selectivity/POINT_BECAUSE_BUT_SO.audit.json) sidecar that binds each line to the scored artifacts and fields that produced it. The independent verifier reconstructs the projection and fails if the card or trace bindings drift.

## Stable 0.5.2 result

Version `0.5.2` changes the historical evaluation corpus, not the Evidence Recall inference semantics.

| System | Warranted reopenings caught | Missed | Review load | Unnecessary reviews |
|---|---:|---:|---:|---:|
| Direct Lookup | 7/8 | 1 | 13 | 6 |
| Review-All Reachability | 8/8 | 0 | 14 | 6 |
| Frozen Evidence Recall | 8/8 | 0 | 8 | 0 |

The predeclared promotion rule required at least 95% reconsideration recall, at least 40% review-load reduction versus Review-All, zero additional misses, and positive savings with zero additional misses in at least three trigger episodes.

Observed result:

- reconsideration recall: **100%**;
- review-load reduction: **42.85%**;
- additional misses versus Review-All: **0**;
- trigger episodes with positive savings and zero additional misses: **4/5**;
- verdict: **`PROMOTION`**.

Gold is intentionally strict. A target is scored only when a later case-level record establishes explicit reliance/reconsideration or affirmative non-reliance/scope exclusion. Silence is `UNASSESSED`, not `NO_REOPEN`. Aggregate counts that could not be reproduced at case level were not converted into gold.

The result and its limits are in [`artifacts/evidence-recall-temporal/replication-001-selectivity/REPORT.md`](artifacts/evidence-recall-temporal/replication-001-selectivity/REPORT.md). The frozen release boundary is in [`CLAIM_BOUNDARY_TEMPORAL.md`](CLAIM_BOUNDARY_TEMPORAL.md).

## Current research boundary: prospective Decision Recall

The prospective Decision Recall line attacks an upstream assumption that the historical Evidence Recall work could not test: **can useful dependency state be captured cheaply when a decision is accepted, before anyone knows what will later break?**

`experiments/decision-recall-prospective-001/PROTOCOL.md` freezes the empirical bar. Each accepted software decision gets a small receiver-confirmed dependency manifest, while separate conventional records and role-separated gold preserve the possibility that the manifest omitted something material.

The first empirical stream is **Cohort 001: this repository's own natural development stream**. It admits only decisions that would have happened anyway, classifies every substantive post-activation commit as observed or explicitly excluded, and restarts if a frozen instrument file changes during accumulation. No prospective product promotion has been earned.

Standing Recall does not replace this prospective line. SRE-001 and SRE-002 test what happens **after represented support changes standing**; Decision Recall tests whether the representation can be captured prospectively and cheaply enough to deserve reliance.

See [`experiments/decision-recall-prospective-001/cohort-001/COHORT.md`](experiments/decision-recall-prospective-001/cohort-001/COHORT.md).

## Trust boundary

The system separates representation, authority, and consequence.

| Layer | What it establishes | What it does not establish |
|---|---|---|
| Source hash and span | The disclosed bytes and exact quote | Whether the source is honest |
| Claim and relation IDs | The exact represented structure | Semantic truth |
| Receiver policy | Which relations this receiver admits | What another receiver should admit |
| Graph-state receipt | The committed state and lineage | That the state is wise or complete |
| Deterministic impact analysis | What follows from the admitted state and event | Hidden dependencies that were never represented |
| Human projection | A bounded, traceable conclusion and consequence | Permission to exceed the underlying evidence |

`QUOTE` records are mechanically checked against source bytes. Other semantic mappings remain claims about representation unless an independent process evaluates them. Signatures authenticate committed state; they do not turn judgment into truth.

## Install and test

Python 3.11+ is required.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Build the checked Evidence Recall specimen:

```bash
PYTHONPATH=src python examples/build_plos_correction_case.py \
  --output artifacts/plos-correction-case
PYTHONPATH=src python examples/build_plos_correction_impact.py \
  --base artifacts/plos-correction-case \
  --output artifacts/plos-correction-impact
python scripts/verify_plos_correction_impact.py \
  --artifact artifacts/plos-correction-impact
```

Verify the permanent Standing Recall evidence ledger:

```bash
python scripts/verify_standing_recall_evidence.py
```

## Repository map

- `src/openline_claim_graph/` — deterministic graph, verification, impact, and evaluation code.
- `tests/` — unit, adversarial, custody, and regression tests.
- `artifacts/` — checked outputs and independent-verification records.
- `artifacts/standing-recall/` — frozen SRE-001/SRE-002 CI evidence ledger.
- `experiments/` — benchmark protocols and historical evaluation material, including the frozen prospective Decision Recall protocol.
- `docs/EVIDENCE_RECALL.md` — current Evidence Recall mechanism contract.
- `docs/STANDING_RECALL.md` — experimental Standing Recall result and boundary.
- `HUMAN_CONTRACT.md` — canonical human-facing projection contract.
- `CLAIM_BOUNDARY.md` / `CLAIM_BOUNDARY_TEMPORAL.md` — explicit non-claims and evaluation boundaries.
- `ASSESSMENT.md` — research assessment and older experimental context.
- `CHANGELOG.md` — development history.
- `RELEASE.md` — current stable release disposition.
- `MANIFEST.json` / `EVIDENCE.json` — stable-release closure and verification receipts.

The README intentionally describes the current public surface rather than reproducing the full development archaeology. Older benchmark history and failed or below-threshold runs remain preserved in the assessment, changelog, experiment protocols, and checked artifacts.

## Related experimental work

The repository also contains **Frame Ledger**, an experimental exact-text framing-analysis path with its own contract and receiver-owned admission policy. It is not part of the 0.5.2 Evidence Recall promotion claim and should not be read as having the same empirical status.

See [`docs/FRAME_LEDGER.md`](docs/FRAME_LEDGER.md) and its checked artifact under `artifacts/wapo-headline-frame-ledger/`.

## Scope

OpenLine Claim Graph does not claim to determine truth, discover every hidden dependency, infer intent, replace domain review, or establish broad generality from the existing historical and Standing Recall corpora.

The current stable product claim remains the 0.5.2 Evidence Recall result: **in its frozen historical replication, typed receiver-owned dependency authority preserved all observed warranted reopenings while reducing review load relative to reviewing every reachable target.**

The additional experimental Standing Recall result is narrower: **on two frozen evaluations, a strong property-aware repair baseline matched OpenLine on scored correctness, while OpenLine reduced the amount of previously valid state that had to be reopened.**

Both claims are falsifiable. A broader corpus, prospective construction, third-party implementation, or materially different graph structure can break them.

## License

MIT.
