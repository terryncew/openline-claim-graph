# Scoring Rubric v0.3

Scoring is performed on de-identified responses before arm labels or timing data are released.

## Response commitment

The receiver may submit one top-ranked answer and one optional second-ranked answer. The top-ranked answer determines the primary outcome.

## Disagreement cases

Top-ranked classification:

- **Hit:** identifies the keyed consequential tension and cites both keyed source locations using the permitted document/paragraph identifiers. Alternative paragraph pairs count only when listed in the locked key.
- **Partial:** identifies the keyed tension but omits or miscites one or both locations, or locates the correct pair without expressing the consequential tension accurately.
- **Miss:** identifies another issue, gives only a topic, provides no answer, or exceeds the time limit.

A citation to an entire document is not a location hit.

## Missing-premise cases

The absent premise has no source span. The receiver instead must identify both sides of the gap.

- **Hit:** cites the keyed upstream and downstream paragraphs and states a linking premise semantically matching an acceptable formulation in the locked key.
- **Partial:** locates both sides of the gap but gives the wrong or materially incomplete bridge, or states the correct bridge without locating both sides.
- **Miss:** identifies another gap, merely restates the conclusion, gives no answer, or exceeds the time limit.

Semantic matching is determined independently by two scorers. New acceptable formulations cannot be added after arm labels are disclosed.

## No-conflict cases

- **Hit:** top-ranked answer is `NO_CONSEQUENTIAL_FAULT_LINE` and supplies no contradictory candidate.
- **Miss / false conflict:** top-ranked answer asserts a consequential disagreement or missing premise.

If the optional second answer asserts a conflict after a top-ranked no-conflict answer, the top-ranked outcome remains a hit but the response counts as a secondary false discovery.

## False discoveries

For positive cases, any submitted candidate that does not match the key is a false candidate. For negative controls, every asserted conflict is false under the adjudicated task boundary.

Report:

- top-ranked false-conflict rate;
- any-candidate false-discovery rate;
- number of candidates submitted per response.

## Two scorers and adjudication

Two scorers independently assign hit/partial/miss, target match, and false-discovery flags. They then resolve disagreements while still blind to condition. Preserve both original scores and the adjudicated score.

If pre-adjudication agreement on top-ranked hit/partial/miss is below 80%, Stage 1 cannot continue to a Stage 2 design under this rubric.

## Primary and secondary outcomes

- Primary: adjudicated top-ranked `Hit` vs. not-Hit.
- Secondary: partial rate, top-two recall, false discoveries, and timing.

Partial does not receive fractional primary credit. This avoids choosing weights after seeing which arm produced more partial answers.
