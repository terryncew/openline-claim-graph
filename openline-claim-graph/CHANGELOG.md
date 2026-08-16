# Changelog

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
