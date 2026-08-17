# Push status

Version: `0.5.0.dev1`

Disposition: `READY_TO_PUSH_AS_EXPERIMENTAL_FIRST_REAL_TEMPORAL_CASE_NO_PROMOTION`

This build adds one empirical asset only: the first real historical case pack for the Evidence Recall Temporal Holdout Benchmark. The frozen `0.5.0.dev0` Evidence Recall engine is byte-for-byte unchanged.

The case freezes the 2021 Shah et al. intravenous-iron meta-analysis before the January 19, 2023 retraction of an included Darwish randomized trial. The pre-cutoff review explicitly places that trial (reference 76) inside the 111-RCT hemoglobin analysis. A private future seal commits to the January 27, 2025 JAMA correction before prediction; the correction later records an explicit reanalysis without the retracted study and says the reported results were unaffected.

Under the frozen gold rule, both scored targets are `REOPEN`: the pooled hemoglobin result and the downstream improved-hemoglobin finding were actually reconsidered.

Result:

- Direct Lookup: 1/2 reopenings caught; review load 1.
- Review-All Reachability: 2/2 caught; review load 2.
- Frozen Evidence Recall: 2/2 caught; review load 2.
- Evidence Recall reviewer savings vs Review-All: **0**.

Verdict: `NO_PROMOTION`. The case establishes real historical temporal mechanism contact but no attention-selectivity advantage. Because both gold labels are positive, it does not estimate false-review precision and cannot by itself grade the larger product thesis.

A stdlib-only verifier independently checks 36 custody, timestamp, content-ID, frozen-engine, reachability, gold, and score properties. The release gate also rebuilds the case, validates it through the installed wheel, and requires the no-selectivity result to remain exact.

Status: `FIRST_REAL_TEMPORAL_CASE_RUN_NO_SELECTIVITY_ADVANTAGE_MORE_CASES_REQUIRED`

No weighted support, new basis type, generalized revocation, hidden-edge discovery, UI, Receipt Gate work, Successor Gate work, or semantic rescue is included.
