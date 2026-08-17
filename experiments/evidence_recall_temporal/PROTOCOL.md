# Evidence Recall Temporal Holdout Benchmark

Version: `0.5.0.dev0`

Status: `TEMPORAL_HOLDOUT_PIPELINE_READY_REAL_CASE_LEVEL_PROMOTION_UNTESTED`

## Question

Given only an accepted dependency state frozen at time `t0`, and one correction, retraction, or equivalent status event that becomes available at `t1`, can a frozen Evidence Recall engine identify the smallest set of accepted items that later independent records show really warranted reconsideration?

The benchmark does not ask whether a claim later became false. A target is positive when an independently dated later record shows that it was formally reconsidered, revised, corrected, reanalyzed, withdrawn, or otherwise reopened because of the event. A target may ultimately survive and still be a correct positive.

## Blindfold

For each historical episode:

1. Choose `t0` before the triggering event.
2. Construct nodes and relations only from material available on or before `t0`.
3. Freeze receiver relation authority without using later outcome labels.
4. Build a private content-addressed manifest of later records and bind only its commitment into the public pack.
5. Reveal the triggering event at `t1`.
6. Run all prediction systems. They receive the frozen pack and authority, not the later records or gold.
7. Unseal later records dated after `t1` and bind external `REOPEN`, `NO_REOPEN`, or `UNASSESSED` labels.
8. Score the already frozen predictions.

The code enforces timestamps, artifact bindings, and answer-bearing-field separation. It cannot prove that a human reconstructing a historical graph did not consult future knowledge. The corpus construction procedure therefore remains part of the empirical protocol and must be auditable.

## Systems

### Direct Lookup

Review only targets that are immediate dependents of the invalidated node.

### Review-All Reachability

Review every target reachable from the invalidated node over any directed edge. This is the principal embarrassing baseline: if Evidence Recall cannot wake fewer targets without missing later documented reopenings, typed authority and alternative-support semantics have not bought reviewer attention.

### Frozen Evidence Recall

Run the existing Evidence Recall impact semantics unchanged. `QUARANTINE` and `AFFECTED_UNRESOLVED` require review. `SURVIVES` and `UNAFFECTED` do not.

### Naive Transitive Taint (diagnostic only)

Optionally hard-quarantine every reachable target. This remains useful for severity comparison but is not the main temporal baseline.

## Gold

Gold is later independently recorded reconsideration, not later falsity.

Positive evidence may include a later systematic-review revision or reanalysis, guideline reconsideration, downstream correction/withdrawal/retraction, predeclared quantitative threshold crossing, regulatory change, formally reopened decision, or independent dependency audit that establishes reliance.

Negative evidence must be affirmative. The benchmark permits explicit independent no-reliance/context or formal scope-exclusion records. Mere absence of a later correction is never `NO_REOPEN`.

An explicit later reanalysis that concludes "no change" still supports `REOPEN`, because the accepted item was in fact reconsidered.

## Primary metrics

For each system the score reports:

- true reopen reviews;
- missed reopenings;
- unnecessary reviews;
- total review load;
- reconsideration precision;
- reconsideration recall;
- review burden;
- unnecessary-review rate; and
- relevant reopenings caught per unnecessary review.

The score also reports reviewer savings versus Review-All Reachability and any additional missed reopenings paid for those savings.

There is no composite score and no automatic product-promotion threshold.

## First corpus family

The first real version is restricted to scientific and clinical material because publication, retraction, revision, and reanalysis dates are unusually legible. The source-backed candidate registry includes:

- Kataoka et al. (2022), DOI `10.1016/j.jclinepi.2022.06.015`, as a candidate pre-retraction systematic-review/guideline cohort;
- Graña Possamai et al. (2025), DOI `10.1001/jamainternmed.2025.0256`, as a quantitative reanalysis stress asset;
- VITALITY Study I (2025), DOI `10.1136/bmj-2024-082068`, as a large retracted-trial/meta-analysis/guideline substrate; and
- the Cochrane letrozole review, DOI `10.1002/14651858.CD010287.pub3`, as a positive example where review was warranted even though conclusions did not change.

These sources are candidates, not a temporal benchmark result. No case-level temporal promotion claim is checked into `0.5.0.dev0`.

## Frozen boundaries

This version does not add weighted support, hidden-edge discovery, new basis types, generalized revocation, multi-edge cut-set analysis, UI, or changes to other OpenLine gates.
