# Changelog

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
