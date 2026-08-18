# Prospective Decision Recall 001

Status: **PROTOCOL FROZEN FOR THE NEXT EMPIRICAL RUN — NO PRODUCT PROMOTION YET**

## Question

Can a small dependency record, captured when an agent-generated software decision is accepted and before any future revocation is known, later reduce human reopening work without adding missed warranted reopenings?

This experiment tests the missing upstream assumption behind Evidence Recall. It does **not** change the 0.5.2 Evidence Recall engine and does not treat declared dependencies as causal truth.

## Decision-time record

For each accepted decision, an agent may draft the record, but the receiver must confirm or correct the consequential fields. The frozen manifest contains:

- decision
- basis/evidence
- required dependencies
- independently sufficient alternative support
- assumptions
- invalidation conditions
- resulting artifact
- capture timing and correction count

A manifest is accepted operational dependency state. Omitting a dependency that later proves material is a benchmark failure, not permission to repair history after the trigger. `required_dependencies` is the primary sufficient support path, not a claim that every listed item is globally irreplaceable: a separately declared `alternative_support` group is another independently sufficient path. If that distinction cannot be stated honestly at acceptance time, the dependency should be marked ambiguous and later loss of standing must escalate.

## Custody

1. Capture manifests while decisions are accepted.
2. Separately bind the conventional complete pre-trigger record. A role-separated catalog builder receives **only those conventional records, not the prospective manifests**, and enumerates the eligible-basis catalog. The catalog is not limited to dependencies the manifest declared.
3. Bind catalog custody (`builder_id`, build time, construction method, source scope, and whether the manifest was visible), then content-address and seal manifests, full records, the eligible-basis universe, and that custody declaration together.
4. Only after the seal exists, an independent runner supplies random seed bytes and selects controlled revocations from the eligible-basis catalog.
5. Predictions may see the sealed pre-trigger state and the revocation event. They may not see adjudication gold.
6. Gold is produced independently from a prediction- and manifest-blind packet containing the conventional complete pre-trigger record and the new event. The adjudicator does not see Decision Recall's dependency declaration.
7. Gold adjudicators are role-separated from manifest drafters/confirmers. System-specific reconstruction timing is measured separately so the gold judgment cannot be contaminated by seeing which condition was faster.
8. No manifest or prediction may be semantically repaired after gold is known.

Natural revocations may be appended as a second, stronger stratum when they occur. Controlled revocations estimate conditional performance when a basis breaks; they do not estimate how often bases break in production.

## Systems

**Full-history review** — every accepted decision is sent to a blinded baseline reviewer, who must return `REOPEN`, `SURVIVE`, or `ESCALATE`. This reviewer can be wrong; independent gold is scored separately.

**Flat log/search** — any decision whose conventional pre-trigger record mentions the revoked basis is sent to a blinded baseline reviewer for the same disposition. Unsurfaced decisions remain closed. It uses the independent basis index, not Decision Recall's declared materiality.

**Decision Recall** — the frozen dependency record emits `REOPEN`, `SURVIVE`, or `ESCALATE` plus the recorded witness path. It may not invent post-trigger alternative support.

## Gold

An independent blinded adjudicator sees the complete pre-trigger record and revocation event, but none of the three systems' predictions. Each decision receives one label:

- `REOPEN` — the accepted decision warrants reconsideration;
- `SURVIVE` — the accepted record is sufficient to leave it closed;
- `ESCALATE` — the available record is genuinely insufficient for an automatic disposition.

Full-history review can therefore be wrong about a final disposition. The benchmark records that human baseline outcome rather than silently treating presentation-for-review as correctness, so Decision Recall can legitimately catch a case the Full History reviewer missed.

## Primary metrics

- warranted reopenings missed;
- review load and unnecessary review;
- silent survival of gold-ambiguous cases;
- median human capture time per accepted decision;
- percentage accepted without correction;
- blinded reconstruction time by system when measured;
- conditional attention savings per revocation;
- break-even meaningful revocations = total capture time / mean attention saved per measured revocation.

The promotion run uses `INDEPENDENT_BLINDED_REVIEW` gold, instrumented capture timing, and a manifest-blind eligible-basis catalog built by a role separated from manifest drafting/confirmation. The deterministic artifacts can verify custody declarations, role IDs, timestamps, source-scope declarations, and byte bindings. They cannot prove that a human catalog builder secretly avoided seeing a manifest, that a reviewer read carefully, or that a seed was truly first generated when claimed; those remain procedural audit obligations.

No annual ROI is inferred from controlled revocations because the experiment does not estimate natural revocation frequency. Natural revocations may name a basis absent from the controlled catalog; those cases can expose catalog omissions but do not substitute for the randomized controlled sample.

## Frozen promotion bar

The promotion policy is frozen before the first empirical accepted decision. The first empirical run then requires at least **30 prospectively captured accepted decisions** and **10 post-seal controlled revocations**.

Promotion requires all of the following:

- zero additional missed warranted reopenings versus the **actual blinded Full History reviewer outcomes**;
- at least **40%** lower review load than full-history review;
- median human capture time **under 60 seconds** per accepted decision, measured by an instrumented monotonic capture surface rather than self-report;
- zero silent `SURVIVE` dispositions and zero forced `REOPEN` dispositions on gold `ESCALATE` cases;
- at least **10%** lower review load than flat log/search, not merely an improvement over Review-All;
- measured positive conditional attention savings on at least **3** revocations, with reviewer times from an instrumented monotonic timing surface;
- at least **3** controlled revocations containing both `REOPEN` and `SURVIVE` gold labels;
- the promotion policy must predate the first accepted decision in the empirical stream;
- the eligible-basis catalog must be declared as manifest-blind, derived only from conventional pre-trigger records, and built by a role separated from manifest drafters/confirmers;
- Full History and Flat Search must have human baseline outcomes bound to their exact review packets;
- baseline reviewers must be separated from manifest capture roles and from the independent gold adjudicator;
- blinded gold adjudicators must be role-separated from manifest drafters/confirmers and baseline reviewers;
- controlled events used for promotion must carry a reproducible post-seal random-selection proof;
- every aggregated score must be reproduced from its bound event, predictions, blind gold, and timing artifacts rather than trusted as a standalone content-addressed claim.

The exact policy is content-addressed in `promotion-policy.json` before an empirical stream is scored. The deterministic selector proves that a chosen basis follows from the supplied post-seal seed; it cannot cryptographically prove when an operator first generated that seed. For the empirical run, seed custody must therefore be independent and externally timestamped or otherwise auditable.

## Failure is binding

- Cheap capture + bad recall: the record is too weak.
- Good recall + expensive capture: the tollbooth is operationally dead.
- Flat search nearly matches Decision Recall: dependency structure is unnecessary.
- Revocations save attention but occur too rarely to repay capture cost: potentially useful infrastructure, weak business.
- Missing prospective dependencies that later matter: central product assumption failed. Do not relabel this as an extraction bug after the fact.

## Claim boundary

The checked-in conformance fixture proves only that the custody, prediction, baseline-review, blindness, scoring, and economic arithmetic are executable. It uses authored fixture decisions, fixture gold, and synthetic fixture review times. Its verifier is stdlib-only and can run under `python -I`, independently reproducing content IDs, dispositions, blind packets, baseline-review outcomes, review workloads, and score arithmetic without importing `openline_claim_graph`. The fixture deliberately includes one authored case where the Full History reviewer baseline misses a warranted reopening that Decision Recall catches, proving Full History is not wired in as the gold oracle. It is not empirical evidence for product promotion.

## Omission test

Controlled revocations are sampled from the independently sealed eligible-basis universe, not only from manifest dependencies. A basis present in the full pre-trigger record but omitted from the prospective manifest can therefore be revoked and produce a real Decision Recall miss. The conformance fixture contains exactly such an injected case to prove the evaluator can expose the central failure mode.
## Cohort 001 self-hosted natural stream

The first empirical stream is `decision-recall-cohort-001`, the natural development history of this repository after the cohort apparatus is installed. The installation commit itself never counts. Only decisions that would have happened without the benchmark are eligible; no work may be manufactured to fill the cohort. Every substantive post-activation commit must be represented by an observation or an explicit exclusion so silent favorable selection is visible.

The cohort freezes the capture/challenge/scoring instrument by file hash. Any change to a frozen instrument file during accumulation requires a cohort restart. Missing dependencies, capture friction, Flat Search wins, and adverse dispositions are data and may not be repaired in place. The ordinary ship / reject / accept decision is the receiver confirmation event; the agent uses the existing monotonic capture surface around that ordinary decision rather than adding a separate questionnaire.

The cohort remains mechanics-only until real observations accumulate. Its zero-state designation and operator contract live under `experiments/decision-recall-prospective-001/cohort-001/`; empirical records live under `artifacts/decision-recall-prospective/cohort-001/`.

