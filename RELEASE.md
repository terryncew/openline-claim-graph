# Push status

Version: `0.5.0.dev0`

Disposition: `READY_TO_PUSH_AS_EXPERIMENTAL_TEMPORAL_HOLDOUT_PIPELINE`

This build adds one capability only: the Evidence Recall Temporal Holdout Benchmark. Evidence Recall itself is frozen and receives no semantic rescue.

The temporal evaluator freezes accepted state at `t0`, binds a private later-record corpus by content commitment, reveals one triggering event at `t1`, runs Direct Lookup / Review-All Reachability / frozen Evidence Recall without the later records, and then scores the frozen predictions against independently dated post-event reconsideration evidence. Naive Transitive Taint is retained only as an optional diagnostic.

The main comparison is now against **Review-All Reachability**. If Evidence Recall wakes essentially the same reachable set, typed relation authority has not demonstrated an attention-saving advantage.

Gold is later recorded reconsideration, not eventual falsity. A later reanalysis whose conclusion survives is still a positive reopen. Silence is never negative gold; `NO_REOPEN` requires affirmative later no-reliance or explicit scope evidence.

The checked-in five-target fixture is conformance-only. It demonstrates that the evaluator can preserve full fixture recall while distinguishing review burden: Review-All wakes 5 targets and frozen Evidence Recall wakes 3. That result is authored by the fixture and is **not** empirical evidence for the product thesis.

The source-backed diagnostic records candidate scientific/clinical corpora and independently verified published counts. No real case-level temporal holdout score is present, so Evidence Recall remains unpromoted.

Status: `TEMPORAL_HOLDOUT_PIPELINE_READY_REAL_CASE_LEVEL_PROMOTION_UNTESTED`

No UI, AI edge discovery, weighted support, generalized basis revocation, new basis types, multi-edge cut sets, Receipt Gate work, or Successor Gate work is included.
