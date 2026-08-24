# Standing Recall evidence ledger

This directory permanently preserves the repository-visible evidence from the two frozen Standing Recall experiments.

The surviving result is narrow:

> A strong property-aware MemoRepair-style baseline matched OpenLine on scored correctness. On these frozen evaluations, OpenLine's distinction was that it reached the same standing disposition while reopening or replaying less state.

## SRE-001 — External LongMemEval-V2 adaptation

- external substrate: 5 pinned LongMemEval-V2 trajectory excerpts;
- 10 unique state anchors expanded into 40 controlled lifecycle episodes;
- events: `EXPIRE`, `REVOKE`, `SUPERSEDE`, `CORRECT`;
- OpenLine recall: 100%;
- OpenLine unaffected-state preservation: 100%;
- OpenLine replay surface: 40;
- strongest accuracy-matching MemoRepair-style baseline replay surface: 120;
- reduction: 66.67%;
- verdict: `EXTERNAL_STANDING_SEPARATION_ADAPTED_LONGMEMEVAL_V2`.

The lifecycle events in SRE-001 are controlled adaptations. The 40 episodes are not 40 independent trajectories.

## SRE-002 — Natural Standing Events

- 8 natural public-record lifecycle events;
- 24 scored target dispositions: 12 `REOPEN`, 12 `SURVIVE`;
- 2 events each of `CORRECT`, `REVOKE`, `SUPERSEDE`, and `EXPIRE`;
- OpenLine recall: 100%;
- OpenLine unaffected-state preservation: 100%;
- OpenLine replay surface: 12;
- strongest accuracy-matching MemoRepair-style baseline replay surface: 24;
- reduction: 50%;
- verdict: `NATURAL_STANDING_SELECTIVITY`.

SRE-002's event occurrence and target dispositions are public-record anchored. The dependency and facet mappings are retrospective human-authored representations. The corpus is small, unblinded, and non-random.

## Why these files are checked in

The original GitHub Actions artifacts are temporary. `RUN_RECEIPT.json` records the source workflow run, PR/head/merge SHAs, Actions artifact ID, artifact ZIP digest, and the hashes of the exact result files copied here.

No experiment is rerun by this closure. No threshold, corpus, mechanism, or score is changed.

`INDEX.json` is the bounded cross-experiment summary. `scripts/verify_standing_recall_evidence.py` verifies the checked evidence ledger without importing the product package.

`policy_authority: NONE`
