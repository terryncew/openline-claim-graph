# Temporal Holdout Claim Boundary

`0.5.0.dev0` implements a prospective-style historical evaluation protocol. It does not establish that Evidence Recall wins that evaluation.

The public temporal pack binds only pre-cutoff graph state, the later trigger event, receiver authority, and a commitment to a separately sealed future-record corpus. Predictions can be reproduced without the future seal or gold. Later labels must cite records from the sealed corpus that postdate the trigger.

`REOPEN` means later independent evidence records that the target warranted reconsideration. It does not mean the target was false. A later reanalysis with unchanged conclusions is still a positive reconsideration event.

`NO_REOPEN` cannot be inferred from silence. It requires affirmative later evidence of non-reliance or explicit scope exclusion. `UNASSESSED` remains outside scored denominators.

The temporal validator can detect timestamp violations, content-ID tampering, future-seal substitution, answer-bearing public keys, missing affirmative gold evidence, and prediction/score reproduction mismatches. It cannot prove that a human historical-corpus constructor ignored information learned after `t0`; that remains a procedural and audit requirement.

The conformance fixture is synthetic and exists only to prove that the evaluator can distinguish a system that catches reopenings from one that saves reviewer attention. It is not empirical evidence for Evidence Recall.

Status: `TEMPORAL_HOLDOUT_PIPELINE_READY_REAL_CASE_LEVEL_PROMOTION_UNTESTED`.
