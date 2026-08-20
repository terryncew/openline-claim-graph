# OpenLine Claim Graph — Evidence Recall

> Something you relied on changed. Compute what depended on it, preserve what still has an admitted basis, and show what still requires review.

OpenLine Claim Graph is an open-source Python system for tracing which accepted claims and decisions need reconsideration when upstream evidence changes.

The core job is deliberately narrow: given an accepted dependency graph, an exact source-status event, and a receiver-owned relation policy, compute the downstream consequence without pretending the graph settled truth.

**Latest stable release: `0.5.2`.** In a five-episode historical replication with 14 explicitly scored targets, frozen Evidence Recall caught **8/8 warranted reopenings** while reviewing **8 targets instead of 14** under Review-All Reachability: a **42.85% reduction in review load with zero additional misses**. Three trigger episodes are related Sato retractions evaluated through the same later Avenell audit, so this is a small historical replication, not broad-domain proof.

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

## 0.5.2 result

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

## Next experiment: prospective Decision Recall

The development line does not add another Evidence Recall rescue mechanism. It attacks the upstream assumption that 0.5.2 could not test: **can useful dependency state be captured cheaply when a decision is accepted, before anyone knows what will later break?**

`experiments/decision-recall-prospective-001/PROTOCOL.md` freezes the next empirical bar. Each accepted software decision gets a small receiver-confirmed dependency manifest. The benchmark separately seals the conventional full pre-trigger record and an independent eligible-basis catalog, then selects controlled revocations only after the stream is sealed. This matters because the challenge universe is **not limited to dependencies the manifest declared**; an omitted material dependency can become a real miss.

Gold is produced from a prediction- and manifest-blind packet containing the conventional pre-trigger record plus the new revocation event. Full History and Flat Search are **human baselines, not the oracle**: their blinded reviewers return `REOPEN` / `SURVIVE` / `ESCALATE` outcomes that are scored against separate independent gold. The conformance scorer can therefore discover that Decision Recall caught a warranted reopening that a Full History reviewer missed.

The frozen protocol also requires the promotion policy to predate the first accepted decision, rejects duplicate/tampered score artifacts, requires manifest-blind catalog custody and role separation, binds baseline-review outcomes to exact review packets, separates baseline reviewers from the gold adjudicator, and requires mixed REOPEN/SURVIVE controlled events so an all-positive corpus cannot pass.

The checked `artifacts/decision-recall-prospective/conformance/` corpus is intentionally hostile: it contains an omitted dependency that Decision Recall misses, proving the evaluator can expose the central failure mode. The eligible-basis challenge universe now carries explicit custody and must be enumerated from conventional records by a manifest-blind role separate from the manifest capture actors. System-specific review workloads are also content-addressed, so measured review time can be bound to exactly what Full History, Flat Search, or Decision Recall surfaced. A stdlib-only verifier runs under `python -I` and independently reproduces the fixture's content IDs, dispositions, blind packets, baseline-review outcomes, review packets, timing bindings, and score arithmetic without importing the product package. Its status is **`MECHANICS_ONLY_NOT_PRODUCT_EVIDENCE`**. No prospective product promotion has been earned.

The frozen first-run bar is at least 30 real accepted decisions and 10 post-seal controlled revocations; policy frozen before capture; zero additional missed warranted reopenings versus the actual blinded Full History reviewer outcomes; at least 40% lower review load than Full History; at least 10% lower review load than Flat Search; median human capture under 60 seconds; no silent survival or forced reopening of gold-ambiguous cases; manifest-blind role-separated basis-catalog custody; bound human baseline outcomes; role-separated blinded gold; reproducible post-seal selection; independently replayed score bundles; and positive instrumented conditional attention savings on at least three revocations. Controlled revocations can estimate conditional attention payback, not natural revocation frequency or annual ROI.

The first empirical stream is now designated as **Cohort 001: this repository's own natural development stream**. The install commit does not count. The cohort starts at zero after installation, admits only decisions that would have happened anyway, classifies every substantive post-activation commit as observed or explicitly excluded, and restarts if any frozen instrument file changes during accumulation. No empirical promotion is claimed until the existing gate fires. See [`experiments/decision-recall-prospective-001/cohort-001/COHORT.md`](experiments/decision-recall-prospective-001/cohort-001/COHORT.md).

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

Rebuild and independently verify the 0.5.2 temporal replication:

```bash
PYTHONPATH=src python scripts/build_temporal_selectivity_replication_corpus.py \
  --output artifacts/evidence-recall-temporal/replication-001-selectivity

python scripts/verify_temporal_selectivity_replication_corpus.py \
  --artifact artifacts/evidence-recall-temporal/replication-001-selectivity \
  --output artifacts/evidence-recall-temporal/replication-001-selectivity/independent-verification.json

PYTHONPATH=src python -m openline_claim_graph temporal-benchmark-validate \
  --pack artifacts/evidence-recall-temporal/replication-001-selectivity/pack.json \
  --authority artifacts/evidence-recall-temporal/replication-001-selectivity/authority.json \
  --future-seal artifacts/evidence-recall-temporal/replication-001-selectivity/future-seal.private.json \
  --gold artifacts/evidence-recall-temporal/replication-001-selectivity/gold.private.json \
  --predictions artifacts/evidence-recall-temporal/replication-001-selectivity/predictions.json \
  --score artifacts/evidence-recall-temporal/replication-001-selectivity/score.json
```

The historical protocol withholds the future record and gold from the prediction-visible pack. Because the cases are retrospective reconstructions, this establishes artifact separation and reproducibility; it does not prove the human constructor was psychologically blind to later history.

## Repository map

- `src/openline_claim_graph/` — deterministic graph, verification, impact, and evaluation code.
- `tests/` — unit, adversarial, custody, and regression tests.
- `artifacts/` — checked outputs and independent-verification records.
- `experiments/` — benchmark protocols and historical evaluation material, including the frozen prospective Decision Recall protocol.
- `docs/EVIDENCE_RECALL.md` — current Evidence Recall mechanism contract.
- `HUMAN_CONTRACT.md` — canonical human-facing projection contract.
- `CLAIM_BOUNDARY.md` / `CLAIM_BOUNDARY_TEMPORAL.md` — explicit non-claims and evaluation boundaries.
- `ASSESSMENT.md` — research assessment and older experimental context.
- `CHANGELOG.md` — development history.
- `RELEASE.md` — current release disposition.
- `MANIFEST.json` / `EVIDENCE.json` — release closure and verification receipts.

The README intentionally describes the current public surface rather than reproducing the full development archaeology. Older benchmark history and failed or below-threshold runs remain preserved in the assessment, changelog, experiment protocols, and checked artifacts.

## Related experimental work

The repository also contains **Frame Ledger**, an experimental exact-text framing-analysis path with its own contract and receiver-owned admission policy. It is not part of the 0.5.2 Evidence Recall promotion claim and should not be read as having the same empirical status.

See [`docs/FRAME_LEDGER.md`](docs/FRAME_LEDGER.md) and its checked artifact under `artifacts/wapo-headline-frame-ledger/`.

## Scope

OpenLine Claim Graph does not claim to determine truth, discover every hidden dependency, infer intent, replace domain review, or establish broad generality from 14 historical targets.

The current supported claim is smaller: **in this frozen historical replication, typed receiver-owned dependency authority preserved all observed warranted reopenings while reducing review load relative to reviewing every reachable target.**

That claim is falsifiable. A broader corpus with new evidence families, prospective construction, or materially different graph structure can break it.

## License

MIT.
