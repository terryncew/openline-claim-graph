# Running the prospective benchmark

This directory is the next empirical ratchet, not a new stable subsystem. `0.5.2` remains the shipped Evidence Recall result.

The workflow intentionally separates the consequential roles:

1. an agent drafts the tiny dependency manifest;
2. the receiver confirms/corrects it through an instrumented capture surface;
3. conventional full decision materials are bound separately;
4. a role-separated catalog builder receives only those conventional records and enumerates the eligible-basis catalog without seeing the prospective manifests;
5. after the stream seal exists, a separate selector chooses controlled revocations and blinded adjudicators create gold without seeing the manifest or predictions.

## Capture one accepted decision

Copy `decision-manifest-draft.template.json`, let the working agent fill it from the actual decision, and run:

```bash
PYTHONPATH=src python scripts/decision_recall_benchmark.py capture \
  --draft path/to/draft.json \
  --confirmed-by receiver-id \
  --output path/to/manifests/decision-001.json
```

The timer starts when the receiver-facing summary is shown and stops on acceptance. Editing increments the correction count. Promotion does not accept self-reported capture time.

## Bind the conventional pre-trigger record

Create a record description from the issue/spec/diff/tests/review material without importing Decision Recall's dependency roles, then content-address it:

```bash
PYTHONPATH=src python scripts/decision_recall_benchmark.py record \
  --input path/to/pre-trigger-record.json \
  --output path/to/records/decision-001.json
```

Build `eligible-bases.json` independently from the conventional records. It may and should contain real recorded bases that the tiny manifest omitted. The catalog file also carries a custody declaration: who built it, when, the construction method, the source scope, and `manifest_visible: false`. The catalog builder must be role-separated from the manifest drafting/confirmation actors and should receive only the conventional records. This catalog is benchmark instrumentation: it prevents the product from defining its own challenge universe.

The deterministic gate can verify the declared custody, timestamps, role IDs, source scope, and resulting bytes. It cannot prove that a human secretly avoided seeing a manifest; preserve an auditable handoff/role receipt for the empirical run.

## Seal the stream

After at least 30 real accepted decisions:

```bash
PYTHONPATH=src python scripts/decision_recall_benchmark.py seal \
  --manifest-dir path/to/manifests \
  --record-dir path/to/records \
  --eligible-bases path/to/eligible-bases.json \
  --benchmark-id decision-recall-prospective-001-live \
  --output path/to/stream-seal.json
```

The checked `promotion-policy.json` is already frozen. Promotion additionally verifies that its declaration timestamp predates the first accepted decision in the empirical stream; do not regenerate it after capture begins.

## Select controlled revocations after the seal

A separate runner creates random seed bytes only after the stream is sealed, then runs:

```bash
PYTHONPATH=src python scripts/select_controlled_revocations.py \
  --stream-seal path/to/stream-seal.json \
  --seed-file path/to/independent-seed.bin \
  --count 10 \
  --selection-at <post-seal timestamp> \
  --event-at <later timestamp> \
  --output path/to/controlled-revocations.private.json
```

Selection is deterministic from seed bytes created after the seal and the sealed eligible-basis universe. Each controlled event carries the seed and rank proof after selection so the choice can be replayed; the seed need not remain secret once the selection is committed. The selector never limits candidates to dependencies the manifest declared.

## Predict and adjudicate

For each selected event, run `predict`. It emits system predictions, a separate manifest-blind adjudication packet, and three system-specific review packets whose content IDs bind the exact human workload being timed:

```bash
PYTHONPATH=src python scripts/decision_recall_benchmark.py predict \
  --stream-seal path/to/stream-seal.json \
  --event path/to/event.json \
  --output-dir path/to/event-run
```

Give only `adjudication-packet.json` to the independent adjudication process. The adjudicator must not see the prospective manifest, system predictions, or the eventual system-specific review timings. Bind the returned labels (see `gold-labels.template.json`) with:

```bash
PYTHONPATH=src python scripts/decision_recall_benchmark.py gold \
  --adjudication-packet path/to/event-run/adjudication-packet.json \
  --labels path/to/gold-labels.json \
  --adjudicator-id independent-reviewer-id \
  --output path/to/event-run/gold.private.json
```

The adjudicator ID must be outside the manifest drafting/confirmation roles for promotion.

Measure reconstruction time for the three systems using the monotonic `time-review` surface. Do not let one condition teach the same reviewer the answer to a later condition: use separate blinded reviewers where possible, or randomize/counterbalance order and record the procedure. A typical condition is:

```bash
PYTHONPATH=src python scripts/decision_recall_benchmark.py time-review \
  --review-packet path/to/event-run/review-packet.full-history.json \
  --reviewer-id blinded-reviewer-a \
  --output path/to/event-run/timing-full-history.json
```

Repeat for `review-packet.flat-search.json` and `review-packet.decision-recall.json`. During the Full History and Flat Search timed conditions, the blinded baseline reviewer must also produce `REOPEN` / `SURVIVE` / `ESCALATE` labels for every surfaced row. Bind those labels **separately from gold** to the exact review packets:

```bash
PYTHONPATH=src python scripts/decision_recall_benchmark.py review-outcome \
  --review-packet path/to/event-run/review-packet.full-history.json \
  --labels path/to/full-history-reviewer-labels.json \
  --reviewer-id blinded-reviewer-a \
  --output path/to/event-run/review-outcome.full-history.json

PYTHONPATH=src python scripts/decision_recall_benchmark.py review-outcome \
  --review-packet path/to/event-run/review-packet.flat-search.json \
  --labels path/to/flat-search-reviewer-labels.json \
  --reviewer-id blinded-reviewer-b \
  --output path/to/event-run/review-outcome.flat-search.json
```

Those baseline reviewers are not the gold oracle and may be wrong. The gold adjudicator must be a different role. Then bind the three content-addressed workload/timing records:

```bash
PYTHONPATH=src python scripts/decision_recall_benchmark.py review-times \
  --stream-seal path/to/stream-seal.json \
  --event path/to/event.json \
  --records path/to/event-run/timing-full-history.json \
  --records path/to/event-run/timing-flat-search.json \
  --records path/to/event-run/timing-decision-recall.json \
  --output path/to/event-run/review-times.json

PYTHONPATH=src python scripts/decision_recall_benchmark.py score \
  --stream-seal path/to/stream-seal.json \
  --event path/to/event.json \
  --predictions path/to/event-run/predictions.json \
  --gold path/to/event-run/gold.private.json \
  --review-times path/to/event-run/review-times.json \
  --review-outcome path/to/event-run/review-outcome.full-history.json \
  --review-outcome path/to/event-run/review-outcome.flat-search.json \
  --output path/to/event-run/score.json
```

At least three controlled revocations need instrumented reviewer-time measurements for promotion. Scoring verifies that each timed record is bound to the exact system-specific review packet generated from the sealed state and predictions, and that the Full History / Flat Search timing reviewer IDs match the corresponding bound baseline-review outcomes. It can verify the packet binding, timing-source declaration, and arithmetic; it cannot prove that a human actually read carefully or followed the blinding/counterbalancing procedure. Preserve that procedural receipt separately.

Real failures can be added without editing the sealed basis catalog:

```bash
PYTHONPATH=src python scripts/decision_recall_benchmark.py natural-event \
  --stream-seal path/to/stream-seal.json \
  --basis-id dependency-that-actually-lost-standing \
  --reason "real post-seal basis failure" \
  --output path/to/natural-event.json
```

Natural events may identify a basis that the controlled catalog missed; they are reported separately and cannot fill the minimum controlled-revocation count.

Finally aggregate all scored revocations against the already-frozen policy:

```bash
PYTHONPATH=src python scripts/decision_recall_benchmark.py aggregate \
  --stream-seal path/to/stream-seal.json \
  --policy experiments/decision-recall-prospective-001/promotion-policy.json \
  --run-dir path/to/event-01 \
  --run-dir path/to/event-02 \
  --output path/to/promotion-result.json
```

The aggregator replays each event/prediction/gold/timing/score bundle before applying the gate; a self-consistent score JSON is not trusted on its own. It also revalidates the stream seal before grading. Duplicate/tampered scores, repeated event IDs, a policy declared after capture began, non-blind or capture-role basis catalogs, missing baseline-review outcomes, baseline/gold role collisions, unproved controlled selections, unverified score bundles, and all-positive controlled corpora cannot satisfy the frozen promotion gate.

A `NO_PROMOTION` is a valid result. Do not repair prospective manifests after seeing which dependency was missed.

The checked-in mechanics fixture has a separate module-free verifier. Run it in Python isolated mode so it cannot import the product package:

```bash
python -I scripts/verify_decision_recall_prospective_fixture.py \
  --artifact artifacts/decision-recall-prospective/conformance \
  --output /tmp/decision-recall-independent-verification.json
```
