# Changelog

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
