# Temporal Holdout Claim Boundary

`0.5.0.dev0` implements a prospective-style historical evaluation protocol. `0.5.0.dev1` adds the first real historical episode. Neither establishes that Evidence Recall has a product-level temporal advantage.

The public temporal pack binds only pre-cutoff graph state, the later trigger event, receiver authority, and a commitment to a separately sealed future-record corpus. Predictions can be reproduced without the future seal or gold. Later labels must cite records from the sealed corpus that postdate the trigger.

`REOPEN` means later independent evidence records that the target warranted reconsideration. It does not mean the target was false. A later reanalysis with unchanged conclusions is still a positive reconsideration event.

`NO_REOPEN` cannot be inferred from silence. It requires affirmative later evidence of non-reliance or explicit scope exclusion. `UNASSESSED` remains outside scored denominators.

The first real case freezes the Shah et al. 2021 intravenous-iron review on 2023-01-18, reveals the Darwish trial retraction on 2023-01-19, and scores against the 2025 JAMA correction that records a reanalysis without that trial. Direct Lookup catches 1/2 warranted reopenings. Review-All and frozen Evidence Recall catch 2/2, but both review two targets. Evidence Recall therefore shows **zero reviewer savings** in this episode.

This is `NO_PROMOTION`. Both gold targets are positive, so the case cannot estimate false-review precision or demonstrate selective survival of reachable non-reopen targets. More real episodes with affirmative positive and negative later records are required before the attention-saving thesis can be graded.

The temporal validator can detect timestamp violations, content-ID tampering, future-seal substitution, answer-bearing public keys, missing affirmative gold evidence, and prediction/score reproduction mismatches. The independent real-case verifier also checks frozen engine hashes and simple reachability without importing the candidate temporal module. Neither can prove that a human historical-corpus constructor ignored information learned after `t0`; that remains a procedural and audit limitation.

Status: `FIRST_REAL_TEMPORAL_CASE_RUN_NO_SELECTIVITY_ADVANTAGE_MORE_CASES_REQUIRED`.
