# Analysis Plan v0.3

Stage 1 is an estimation and operations pilot. It has no confirmatory p-value and cannot promote or archive the decision-value claim.

## 1. Lock order

Before arm labels are released to the analyst, lock:

- source, key, surface, and assignment hashes;
- receiver eligibility and exclusions;
- technical failures and protocol deviations;
- both scorer files and adjudicated scores;
- timing-quality flags;
- the analysis script or exact analysis commands.

## 2. Analysis population

Use intention-to-treat by assigned arm. A receiver remains in the assigned arm even if they dislike or underuse the aid.

Pre-arm exclusions are limited to:

- failed eligibility screening;
- declared prior familiarity with an assigned case;
- inability to access the surface before any case content was displayed;
- duplicate receiver identity;
- dry-run participation.

After content is displayed, unanswered and timed-out eligible cases are misses. Technical interruptions are reported separately under the rule fixed in the pack manifest; they may not be reclassified after unblinding.

## 3. Stage 1 reports

For every arm and every case report:

- receiver count and completed case count;
- top-ranked hit, partial, and miss counts;
- top-two hit count;
- top-ranked and any-candidate false-discovery counts;
- median and distribution of completion time;
- scorer agreement before adjudication;
- protocol deviations and missing data;
- artifact-production cost and receiver time.

Never publish only the pooled arm average. Case-level results expose whether an apparent effect comes from one unusually suitable case.

## 4. Effect estimates

Report raw risk differences:

- B minus A for extraction;
- C minus B for graph structure;
- C minus A for the full workflow.

Fit a mixed-effects logistic model for top-ranked hit when the model converges, with arm as a fixed effect and random intercepts for case and receiver. Report estimates and uncertainty as pilot quantities, not confirmatory results. If the model does not converge, report that failure and the raw case-stratified estimates; do not swap in a more favorable model after inspecting results.

Stage 1 confidence intervals describe uncertainty but do not activate a disposition beyond the continuation rules in `PROTOCOL.md`.

## 5. Timing

Report time to final top-ranked submission for all responses. For exploratory time-to-correct analysis, hits use submission time and misses are censored at the fixed limit. Do not compare time among hits alone without also reporting the differing miss rates.

Timing cannot rescue a failure of the Stage 1 accuracy continuation threshold.

## 6. Cost

Report total creation cost for each arm and incremental cost for C relative to A and B. When receiver-time savings are positive, calculate:

`break_even_receiver_uses = incremental_creation_minutes / receiver_minutes_saved_per_use`

If the denominator is zero or negative, report no time-cost break-even rather than an infinite or fabricated value.

## 7. Stage 2 power

If Stage 1 clears the operational continuation gate, simulate the planned Stage 2 crossed data using the observed case and receiver variance. The Stage 2 preregistration must specify:

- the number of independent cases;
- receivers per arm and cases per receiver;
- expected attrition;
- the hierarchical C-vs.-A then C-vs.-B testing order;
- the 15-point and 5-point practical effect thresholds;
- the 5-point false-conflict noninferiority margin;
- power for the complete gate, not only one comparison.

The simulation code, seed, assumptions, and output are frozen with the Stage 2 protocol. The Stage 1 observed effect may inform plausible scenarios but may not lower the practical thresholds.

## 8. Scope of inference

Results apply only to the declared receiver population, case sampling frame, domain, source-packet range, and frozen surfaces. Repeating a few cases many times does not create case generality. Cross-domain claims require separately powered samples from each claimed domain.
