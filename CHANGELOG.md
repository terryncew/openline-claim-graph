# Changelog

## 0.6.1.dev0 — gain-of-standing Decision Recall extension

- Add receiver-bound standing/blocker state and `GAIN_OF_STANDING` events inside Decision Recall.
- Gain analysis recomputes existing sufficient-support sets before/after the exact restoration event; naive downstream reachability is not used for eligibility.
- `RECONSIDERABLE` is explicitly a review projection only. It does not restore accepted state, clear independent blockers, certify truth, or confer execution authority.
- Preserve replay safety, exact basis/state binding, unresolved-blocker containment, and alternative-support attribution boundaries.
- Retire the empty first Cohort 001 instrument generation and restart Cohort 001 at generation 2 because the frozen Decision Recall instrument changed before any eligible prospective observations were admitted. The prior gain-trigger evidence commit remains historical research evidence and is not retroactively counted.
- No new module or branded subsystem is introduced.


## 0.6.0.dev0 — prospective Decision Recall benchmark

- Designated **Prospective Decision Recall Cohort 001** as the self-hosted natural development stream. The install commit is excluded; only independently warranted repository decisions can count.
- Added a cohort operator that binds observations to canonical subject change sets, surfaces every unclassified post-activation commit, records explicit exclusions, and forces cohort restart if frozen instrument files change during accumulation.
- Added an independent stdlib-only zero-state verifier and cohort-specific tests. This is measuring-instrument setup, not prospective product evidence.


- Froze the next empirical question instead of extending the 0.5.2 inference engine: can a small dependency record be captured at decision time cheaply enough to support safe selective recall later?
- Added content-addressed decision manifests with measured human confirmation time, required dependencies, sufficient alternative support, assumptions, invalidation conditions, and resulting-artifact bindings.
- Separated the dependency manifest from the conventional complete pre-trigger record used by baselines and blind gold.
- Added an independently sealed eligible-basis universe that may contain bases omitted from the manifest. Controlled revocations are selected from that universe only after the stream seal exists, so the benchmark can expose missing prospective dependencies instead of testing only what the product remembered to declare.
- Added explicit eligible-basis catalog custody: the empirical catalog must be enumerated from conventional pre-trigger records by a manifest-blind role separated from manifest drafting/confirmation; builder, timestamp, method, source scope, and manifest visibility are bound into the stream seal and promotion gate.
- Added Full-History Review and Flat Log/Search baselines. Gold is bound from a prediction- and manifest-blind adjudication packet rather than treating full-history review as an oracle.
- Full History and Flat Search now carry separately bound blinded human reviewer outcomes. Their reviewers can be wrong relative to independent gold; the conformance fixture intentionally contains one Full History miss that Decision Recall catches so the evaluator cannot silently treat review-all as truth.
- The promotion policy is itself time-bound and must predate the first accepted decision, blocking post-hoc tuning of thresholds after capture data exists.
- Hardened promotion custody against duplicate/tampered score artifacts, capture-role adjudicators, and all-positive controlled corpora; only the controlled stratum counts toward the frozen promotion bar. Promotion aggregation revalidates the sealed stream and replays each bound event/prediction/gold/baseline-review/timing/score bundle instead of trusting a standalone score merely because its content ID is self-consistent.
- Added conditional attention-payback and break-even-revocation accounting while explicitly refusing to infer annual ROI from controlled revocations.
- Froze the empirical promotion bar at >=30 real accepted decisions, >=10 post-seal controlled revocations, zero additional missed warranted reopenings, >=40% review-load reduction versus full-history review, >=10% reduction versus flat search, <60s median human capture, and zero silent survival of gold-ambiguous cases.
- Added a mechanics-only conformance corpus with an intentionally omitted dependency. Decision Recall misses that injected case; the verifier requires the miss to remain visible. The fixture is explicitly not product evidence.
- Replaced the first circular prospective verifier with a stdlib-only module-free verifier that independently reproduces restricted canonicalization, content IDs, reference dispositions, blind adjudication packets, system-specific review packets, and score arithmetic under `python -I`.
- Bound the accepted decision statement into the conventional pre-trigger record so blinded gold no longer needs to source any field from the prospective dependency manifest.
- Added content-addressed review workloads and a monotonic `time-review` surface. Timing only counts as instrumented when it is bound to the exact Full History / Flat Search / Decision Recall packet generated from the sealed state and predictions.
- Preserved the 0.5.2 Evidence Recall engine hashes unchanged.

## 0.5.2 — 2026-08-17

- Added **Temporal Selectivity Replication** as corpus/evaluator work only; the three frozen Evidence Recall engine files remain byte-identical to `0.5.0.dev0` / `0.5.1`.
- Expanded the real historical corpus from 2 to 5 trigger episodes and from 4 to 14 scored targets: retained Shah/Darwish, expanded the manually inspected Narayan episode, and added three separate Sato trial-retraction episodes using explicit inclusion/non-reliance findings from the later Avenell audit.
- Added episode-level reporting so one large graph cannot hide failure elsewhere: pooled totals, per-trigger recall/load/savings/additional misses, and mean/median reviewer savings are all recorded.
- Preserved the predeclared pooled promotion bar: >=95% reconsideration recall, >=40% review-load reduction versus Review-All Reachability, and zero additional missed reopenings. Added only the requested sufficiency condition: positive savings with zero additional misses must recur across at least three trigger episodes.
- Pooled result: Review-All reviews 14 targets and catches 8/8 warranted reopenings; frozen Evidence Recall reviews 8, catches 8/8, and avoids all 6 affirmative unnecessary reviews. Reviewer reduction is 42.85% (4285 basis points), with positive savings and zero additional misses in 4/5 episodes.
- Verdict under the frozen rule: `PROMOTION`. This promotes the observed temporal-selectivity behavior to a serious product candidate; it does not establish commercial moat, cross-domain generality, or hidden-edge discovery.
- Recorded Kataoka's aggregate 335/239 corpus pathway but admitted zero scored Kataoka rows because reproducible case-level inclusion/affirmative-exclusion rows were not available to this build. No aggregate count or silence was converted into gold.
- Made `POINT / BECAUSE / BUT / SO` the canonical human-facing contract: the 0.5.2 card is now reconstructed from scored artifacts, carries a byte-traceable audit sidecar, requires a material `BUT`, and constrains `SO` to the narrow benchmark-supported consequence.
- Added a stdlib-only independent verifier, deterministic rebuild tests, a target ledger, custody record, and contract/audit checks.
- No weighted support, generalized revocation, dependency contracts, hidden-edge discovery, UI, Frame Ledger expansion, Receipt Gate work, or Successor Gate work was added.

## 0.5.1 — 2026-08-17

- Added the first mixed real temporal selectivity corpus without changing any frozen Evidence Recall semantics.
- Reused the Shah/Darwish `0.5.0.dev1` episode unchanged and added a second pre-retraction Narayan SIRT2 episode with one later affirmative `REOPEN` and one affirmative `NO_REOPEN` from the independent van der Vet/Nijveen citation-context audit.
- Added a predeclared promotion policy before gold construction: Evidence Recall must retain at least 95% reconsideration recall, reduce review load at least 40% versus Review-All Reachability, and add no missed reopenings versus Review-All. No composite score is used.
- Mixed-corpus result: Direct Lookup catches 2/3 warranted reopenings with review load 3; Review-All catches 3/3 with review load 4 and one unnecessary review; frozen Evidence Recall catches 3/3 with review load 3 and zero unnecessary reviews.
- Evidence Recall therefore demonstrates one unit of real case-level attention selectivity, a 25% review-load reduction versus Review-All, but fails the predeclared 40% materiality bar. Verdict: `NO_PROMOTION`.
- Added a stdlib-only independent verifier, deterministic corpus-rebuild tests, and release-gate / installed-wheel coverage for the mixed corpus.
- Preserved the three frozen engine files byte-for-byte. No weighted support, generalized revocation, hidden-edge discovery, UI, Receipt Gate work, Successor Gate work, or post-hoc semantic repair was added.

## 0.5.0.dev1 — 2026-08-17

- Added the first real historical Evidence Recall temporal-holdout episode without changing the frozen `0.5.0.dev0` inference semantics.
- Case: Shah et al. 2021 intravenous-iron meta-analysis (`10.1001/jamanetworkopen.2021.33935`), the Darwish trial later retracted on 2023-01-19 (`10.1080/14767058.2023.2169999`), and the 2025 JAMA correction reporting explicit reanalysis without that study (`10.1001/jamanetworkopen.2025.0887`).
- Froze the accepted state on 2023-01-18 from explicit pre-cutoff evidence: the Darwish trial is reference 76 inside the 111-RCT hemoglobin analysis, and the review's improved-hemoglobin finding derives from that pooled result.
- Bound the later 2025 correction into a private future seal before prediction; `pack.json` carries only its commitment. Direct Lookup / Review-All Reachability / frozen Evidence Recall predictions are reproducible without the later record or gold.
- Gold labels both scored targets `REOPEN` because the later correction records an actual reanalysis, even though the reported results survived unchanged.
- Result: Direct Lookup catches 1/2 warranted reopenings with review load 1; Review-All catches 2/2 with load 2; frozen Evidence Recall catches 2/2 with load 2. Evidence Recall saves **zero** reviews versus Review-All.
- Verdict: `NO_PROMOTION`. This first real case establishes temporal mechanism contact but no attention-selectivity advantage. Both labels are positive, so it does not estimate false-review precision.
- Added a stdlib-only 36-check independent verifier, deterministic case-rebuild tests, release-gate coverage, and installed-wheel validation.
- Preserved the frozen engine byte-for-byte; no weighted support, new basis types, generalized revocation, hidden-edge discovery, UI, Receipt Gate work, or Successor Gate work was added.

## 0.5.0.dev0 — 2026-08-17

- Added the Evidence Recall Temporal Holdout Benchmark: freeze accepted state at `t0`, reveal one later event at `t1`, predict without later records, then score against separately sealed post-event reconsideration evidence.
- Added **Review-All Reachability** as the principal temporal baseline; every reachable target consumes human review rather than being hard-quarantined.
- Reused the shipped Evidence Recall impact semantics unchanged; no weighted support, new basis types, hidden-edge discovery, generalized revocation, or cut-set logic.
- Added content-addressed future-record seals whose commitment is bound into the public pack before predictions. Future records and gold are not required to run the prediction systems.
- Added strict temporal validation: pre-cutoff nodes/edges must not postdate `t0`; the trigger must occur after `t0`; gold evidence must postdate the trigger and reproduce the committed future seal.
- Defined gold as later independently recorded reconsideration rather than falsity. Explicit reanalysis with no conclusion change is still `REOPEN`; silence cannot become `NO_REOPEN`.
- Added exact reconsideration precision/recall, review-burden, unnecessary-review, and reviewer-savings metrics without a composite score.
- Added a five-target synthetic conformance fixture where Review-All reviews 5 targets and frozen Evidence Recall reviews 3 while preserving full fixture recall. This is evaluator conformance, not empirical product evidence.
- Added a source-backed clinical/scientific temporal-corpus candidate diagnostic and independent stdlib-only verification. No real case-level temporal holdout result is claimed.

## 0.4.0.dev0 — 2026-08-17

- Added the Evidence Recall three-way comparative benchmark: Direct Lookup vs naive transitive taint vs the unchanged shipped Evidence Recall engine.
- Separated public case pack, receiver authority, predictions, and external gold into independently content-addressed artifacts; predictions never require gold.
- Added explicit error metrics for missed exposure, hard false quarantine, unnecessary unresolved review, total review load, and unnecessary review load; no composite score or automatic promotion rule exists.
- Added a Schneider V2 CSV importer that strips answer-bearing annotation fields from the public pack, freezes a label-independent conservative authority rule, binds private gold separately, hashes raw source bytes, and fails closed unless the canonical corpus yields 152 accessible rows and 23 positives.
- Added a van der Vet/Nijveen DOT importer that reverses the paper's citing→cited arrows into dependency-flow direction and freezes inspected indirect targets as a negative-control gold set.
- Added a source-backed published aggregate diagnostic for Schneider, van der Vet/Nijveen, and the 2025 JAMA meta-analysis reanalysis, plus a stdlib-only independent verifier.
- The aggregate result is intentionally non-promotional: Direct Lookup misses the 23 published non-direct Schneider positives; naive taint has at least 125 hard over-taint candidates; conservative Evidence Recall has at least 125 unnecessary unresolved reviews and the same 152-item total review load. This does not establish a precision or reviewer-load advantage.
- Kept JAMA as an abstraction/selectivity stress test rather than mislabeling unchanged recomputations as false quarantine.
- Added ten comparative benchmark tests; the full suite is now 86 tests.
- Added CI and installed-wheel coverage for the new comparative benchmark commands.
- Did not add new UI, generalized basis revocation, weighted support, cut-set solving, or changes to Receipt Gate / Successor Gate. Evidence Recall semantics remain frozen for the empirical test.

## Unreleased

- Added deterministic single-edge adjudication counterfactuals on top of Evidence Recall.
- `analyze_adjudication_impact()` promotes one advisory relation at a time into hard receiver authority, reruns the existing impact engine, and reports only the accepted claim/decision classifications that change.
- Added a content-addressed adjudication-impact report, exact reproduction verifier, accepted-state receipt bundle verification, and CLI commands `adjudication-impact` / `verify-adjudication-impact`.
- Added the PLOS correction review-surface artifact: its one advisory edge changes exactly one claim from `AFFECTED_UNRESOLVED` to `QUARANTINE`.
- Kept the boundary explicit: mechanical consequence selects the review surface; it does not establish that the edge is true, important, or worthy of admission.

## 0.3.0.dev0 — 2026-08-16

- Added `Frame Ledger`, a content-addressed ruleset and report for exact epistemic lexemes, context cues, declared issue-frame lexemes, narrow local-attribution patterns, and receiver-declared term-set absences.
- Added strict UTF-8 span reproduction for positive matches and full-scope binding for declared absences.
- Prohibited truth, bias-score, fairness, deception-intent, rationalization, and propaganda verdicts from the typed finding layer.
- Added signed model proposals and reviews with receiver-pinned Ed25519 execution identities.
- Enforced non-self-review, unique reviewers, distinct declared-family quorum, optional challenge blocking, and `OPTIONAL` / `REQUIRED` / `DISABLED` human confirmation.
- Added a fully unattended proposer → multi-reviewer → receiver-policy pipeline; model endpoints cannot mutate accepted state or promote their own output.
- Added strict exact-quote import and an eight-finding cap for model proposals. Schema-valid invented quotes fail closed.
- Added standard-library adapters for OpenAI-compatible chat-completions servers (including vLLM, SGLang, and llama.cpp deployments) and the official Responses API with Structured Outputs and `store: false`.
- Added a current, machine-readable open-weight candidate registry split into practical local/workstation and datacenter tiers. Every model remains explicitly unrun.
- Added one natural Washington Post headline specimen with seven reproduced mechanical findings, a fail-closed HTML surface, and a 20-check independent verifier that does not import the Frame Ledger implementation.
- Added 16 unit/adversarial/adapter/autonomy tests; full suite now contains 73 tests.
- Kept the boundary explicit: the specimen contains only the headline; the ruleset lacks corpus validation; no model was run; no claim is made about article fairness, truth, intent, rationalization, propaganda, reader effect, usefulness, or demand.

## 0.2.0.dev1 CI correction — 2026-08-16

- Seed the clean GitHub Actions specimen directory with the checked-in, independently produced PLOS upstream-verification record before building Evidence Recall. The prior local release run reused that record in-place, while a clean runner correctly exposed the missing copy step.

## 0.2.0.dev1 — 2026-08-16

- Added content-addressed `CORRECTED`, `RETRACTED`, `WITHDRAWN`, `SUPERSEDED`, and `REVOKED` source-status events with exact byte scopes and exact notice anchors.
- Added receiver-owned hard, advisory, and unadmitted relation authority. Only `SUPPORTS`, `DEPENDS_ON`, and `DERIVED_FROM` have impact semantics in v1.
- Added deterministic, cycle-safe blast-radius analysis using grounded surviving support rather than citation counts.
- Preserved claims with an admitted alternative basis; ungrounded support cycles cannot self-rescue.
- Added exact downstream witness paths and a fail-closed Evidence Recall HTML renderer.
- Added `impact`, `verify-impact`, and `render-impact` CLI commands.
- Added a real PLOS correction specimen over an explicitly authored accepted dependency state: 5 direct exposures, 7 quarantines, 2 downstream claims beyond direct lookup, 1 alternative-basis survivor, 1 advisory review, and 1 accepted decision touched.
- Added an independent verifier that does not import the impact engine and reproduces the state, receipt, event, policy, classifications, paths, and review hash.
- Added a 2,000-case randomized differential probe with zero oracle mismatches.
- Added 14 focused authority, receipt-binding, tamper, exact-span, alternative-support, cycle, witness-path, and fail-closed rendering tests; full suite now contains 57 tests.
- Kept the boundary explicit: the real correction is external; the downstream dependency state is authored; extraction, completeness, adoption, and economic value remain untested.

## 0.1.0.dev4 — 2026-08-15

- Added a provider-neutral automated receiver benchmark harness.
- Separated public A/B/C surfaces from a gold file bound to the exact pack hash.
- Added deterministic full-factorial plans across receivers, cases, arms, and repetitions.
- Added fresh-process receiver execution over stdin/stdout, strict answer schemas, timeout handling, resumable output, output hashes, and declared micro-dollar stop ceilings.
- Added deterministic label, evidence, premise, false-conflict, cost, and paired-effect scoring. Missing and invalid trials count as misses.
- Added a machine-readable continuation gate that blocks development packs, incomplete runs, insufficient datasets or receiver families, absent negative controls, weak effects, non-positive confidence bounds, and false-conflict regressions.
- Added a development-only 24-case ARCT A/B/C pack and plan. It contains no receiver result and is structurally ineligible for promotion.
- Added seven benchmark custody, parity, tamper, planning, runner, resume, duplicate, and scoring tests.
- Kept provider SDKs, API keys, model grading, and human-comprehension claims outside the trusted core.

## 0.1.0.dev3 — 2026-08-15

- Added `render-review`, a fail-closed static HTML surface over a fully verified receiver bundle.
- Made represented fault lines, exact source spans, receiver-policy limits, and state lineage readable without exposing raw graph JSON.
- Added deterministic rendering, wrong-pin, source-tamper, and HTML-injection tests.
- Added one natural-material PLOS ONE case with five abstract/main-text numerical conflicts and a later explicit external correction recorded outside the receiver bundle.
- Kept the claim boundary: the natural case establishes mechanism contact with reality, not automated extraction, completeness, or receiver-value superiority.

## 0.1.0.dev2 — 2026-08-15

- Added a deterministic 24-case development subset of the independently annotated ARCT missing-premise benchmark, with upstream commit, blob, license, selection rule, and attribution fixed in the repository.
- Recorded one label-blind interactive mapping pass before revealing the upstream gold labels: 21/24 correct. All three misses remain visible.
- Added executable gold-oracle and inverted-warrant controls: 24/24 and 0/24, respectively.
- Built and validated 72 graph states across blind, oracle, and inverted mappings; the selected warrant changes the committed state in every case.
- Added four real-data development tests and a source-tamper check.
- Kept the result outside the receiver pilot. It does not test graph-versus-summary value, open-ended extraction, or Stage 1 continuation.

## 0.1.0.dev1 — 2026-08-15

- Added the unrun, human receiver decision-value pilot protocol.
- Separated ordinary summarization, claim extraction, and graph structure into three arms.
- Assigned condition between receivers to prevent cross-arm learning.
- Added externally anchored case-admission, deterministic sampling, hidden-key custody, negative-control, surface-parity, scoring, analysis, and cost rules.
- Added machine-readable templates and a deterministic balanced assignment tool.
- Added six assignment/contract invariance tests. External decision value remains untested.

## 0.1.0.dev0 CI correction — 2026-08-15

- Install the declared `setuptools` and `wheel` build requirements explicitly before using `--no-build-isolation` in GitHub Actions. Python 3.12 and 3.13 runner environments do not guarantee that `setuptools` is preinstalled.

## 0.1.0.dev0 — 2026-08-15

Initial mechanical prototype.

- Added typed, content-addressed claims and relations.
- Added exact source-span verification and explicit disclosure for semantic mappings that cannot be mechanically verified.
- Added deterministic graph roots, source-manifest roots, bounded Merkle projections, and source disclosures.
- Added receiver-pinned Ed25519 graph-state receipts.
- Added parent/delta lineage, explicit multi-parent conflict handling, and append-only wallet custody.
- Added deterministic branch comparison and disagreement reports without truth ranking.
- Added composed receiver verification with `ADMIT`, `QUARANTINE`, and `DENY` dispositions.
- Added controlled demo, scaling evidence, 23 offline tests, and a 10,000-mutation hostile sweep.

External extraction fidelity and decision value remain untested and unclaimed.
