# Protocol v0.3 — Claim Graph Receiver Discovery Pilot

Status: `PROTOCOL_READY_CASE_PACK_EMPTY`

This protocol replaces the earlier two-arm and mixed-condition sketches. It is designed to fail visibly. It does not claim that the claim graph improves decisions, and Stage 1 cannot establish that claim.

## 1. Research question and target

For a declared population of **human receivers** working in one declared domain, does either of the following improve discovery of a consequential fault line in a fixed, pre-resolution source packet?

1. claim-level extraction compared with an ordinary summary; or
2. explicit graph structure compared with an information-matched prose rendering of the same extraction.

This study does not test agent receivers. A later machine-receiver study would require separate tasks, surfaces, outcome measures, and claims.

## 2. Three arms

Every receiver receives the identical numbered source packet plus one aid:

- **Arm A — ordinary summary:** a prose summary produced directly from the source packet under the frozen baseline prompt and budget. It does not use the claim extraction.
- **Arm B — extraction rendered as prose:** every admitted claim, source reference, and relation from one frozen extraction is expressed in prose.
- **Arm C — extraction rendered as a graph:** the exact claim, source-reference, and relation inventory used by Arm B is rendered as nodes and labeled edges.

The comparisons have different meanings:

- B vs. A estimates the contribution of claim-level extraction.
- C vs. B estimates the contribution of graph structure.
- C vs. A estimates the whole workflow as presented to a human receiver.

Arm B and Arm C must pass the information-parity check in `SURFACE_SPEC.md`. Arm A is intentionally the realistic baseline and is not forced to contain the graph extraction's inventory.

## 3. Assignment and repeated cases

Condition is assigned **between receivers**. A receiver sees only Arm A, only Arm B, or only Arm C for the entire session. This prevents exposure to the graph from teaching a receiver a method that could leak into later control cases.

Cases are repeated within receiver. Stage 1 uses a balanced incomplete block:

- 8–12 admitted cases in one domain;
- target 25% no-conflict cases, with a permitted range of 20–30%;
- four cases per receiver unless the usability dry run establishes a lower fatigue-safe number;
- target of eight completed receiver observations per case per arm;
- absolute minimum of six completed observations per case per arm for a reportable pilot;
- case order randomized within receiver;
- each receiver identifier assigned to exactly one arm.

Changing the cases-per-receiver value after the dry run requires a protocol amendment before any analyzed trial.

## 4. Blinding

- Receivers are told that document presentations are being compared. They are not told which arm is expected to perform better or that graph structure is the sponsor's hypothesis.
- Surface builders never receive the private answer key or resolving document.
- Scorers receive de-identified responses, the fixed rubric, and the answer key. They do not receive arm, receiver identity, timing, or surface files until scoring and adjudication are locked.
- The analyst receives arm labels only after exclusions, scoring, and protocol deviations are frozen.

Receivers cannot be blind to the presentation they see. The study blinds the favored hypothesis and the scoring process, not the visible format.

## 5. Case boundary

All analyzed cases must pass `CASE_ADMISSION.md` before selection.

Positive cases use sources that predate an independent resolving event. The event must explicitly identify that a consequential fault line existed and locate it closely enough to construct a key without deciding which worldview was ultimately true. The resolving document is private during the trial.

Author-invented fault lines and cases chosen because a graph already looks impressive are excluded from the analyzed pack. They may appear in a separately labeled development pack only.

No-conflict cases cannot prove the absence of every possible disagreement. They require agreement by two independent adjudicators that no **consequential target-level fault line** exists under the same rubric and source boundary. Their lower evidentiary status is reported.

## 6. Receiver population

The case pack must declare before recruitment:

- the domain;
- the knowledge needed to read its source packets;
- inclusion and exclusion criteria;
- how prior familiarity with a case is screened;
- the intended population to which results may generalize.

One pilot does not pool lawyers, scientists, engineers, and general readers. Domain diversity without enough cases per domain creates a decorative average rather than a useful result.

## 7. Response task

For each case, a receiver has the fixed time stated in the case-pack manifest and may submit:

- one top-ranked answer; and
- one optional second-ranked answer.

Allowed answer types are:

- `DISAGREEMENT`;
- `MISSING_PREMISE`;
- `NO_CONSEQUENTIAL_FAULT_LINE`.

The top-ranked answer is the primary outcome. The optional second answer is reported only as secondary top-two recall and counts toward false-discovery measures when wrong. This prevents a receiver from winning by naming every plausible tension.

Source packets use immutable document and paragraph identifiers. Free-form citations such as an entire document do not satisfy the location requirement.

## 8. Timing

The trial system records, for each case:

- case-open timestamp;
- first answer-submission timestamp;
- final submission timestamp;
- timeout or technical interruption.

The primary timing measure is time to final top-ranked submission. A miss is right-censored at the case time limit for any later time-to-correct analysis. If trustworthy timestamps are unavailable, timing is omitted rather than reconstructed from memory.

## 9. Stage 1 purpose

Stage 1 is a pilot. It may establish only:

- whether instructions and surfaces are usable;
- whether key-blind builders can produce the arms reproducibly;
- whether scorers can apply the rubric reliably;
- raw and model-based effect-size estimates with wide uncertainty;
- receiver, case, and timing variance estimates for later power simulation;
- the direction and magnitude of false-discovery differences;
- actual production and receiver-time costs.

Stage 1 performs no promote/archive test and does not validate decision value.

## 10. Stage 1 continuation gate

A Stage 2 protocol may be designed only when all operational conditions hold:

- at least six completed observations per case per arm;
- at least 90% of started, eligible case trials produce a scoreable response;
- blind scorers agree on at least 80% of top-ranked hit/partial/miss classifications before adjudication;
- no unresolved surface defect or information-parity failure affected analyzed trials;
- all exclusions and deviations were fixed before arm labels were released;
- Arm C's raw top-ranked hit-rate estimate exceeds Arm A by at least 10 percentage points **and** Arm B by at least 5 points;
- Arm C's raw false-conflict rate does not exceed either comparator by more than 5 points.

These are continuation rules, not evidence of efficacy. Failure stops the graph-surface study. A strong B-vs.-A result may justify studying extraction as prose, but it cannot rescue the graph claim.

## 11. Stage 2 boundary

Stage 2 requires a new preregistration written after Stage 1 operations close. It must:

- define a target case population and sampling frame;
- use substantially more independent cases, with 30 as a floor rather than a sufficient guarantee;
- determine receiver and case counts by simulation using Stage 1 variance and clustering estimates;
- keep condition between receivers unless Stage 1 supplies evidence supporting another design;
- make top-ranked hit rate the sole primary endpoint;
- use hierarchical testing: C vs. A first, then C vs. B only if C vs. A passes;
- require a practical C-vs.-A effect of at least 15 points and a practical C-vs.-B effect of at least 5 points, with confidence intervals excluding zero;
- require the upper confidence bound on Arm C's false-conflict increase to stay below a predeclared 5-point noninferiority margin;
- treat speed, cost, and top-two recall as secondary; they cannot rescue a failed accuracy result.

The familiar calculation of roughly 169 independent observations per arm for a 50% vs. 65% difference is only a lower-bound intuition. It is not the Stage 2 sample size because it ignores repeated receivers, repeated cases, three arms, case sampling, and the safety gate.

## 12. Cost accounting

For every arm record:

- model and tool versions;
- prompts and settings;
- model tokens or equivalent compute;
- API cost;
- human preparation and review minutes;
- output size;
- receiver minutes.

Report the graph's incremental preparation cost and its receiver-time difference. If the graph saves time, report the number of receiver uses required to recover its extra preparation time. Cost is part of value, not an appendix added after a favorable result.

## 13. Dispositions

Stage 1 dispositions:

- `PILOT_SUPPORTS_STAGE2_DESIGN` — every continuation condition passes.
- `PILOT_SUPPORTS_EXTRACTION_ONLY` — B appears useful, but C does not clear the C-vs.-B continuation threshold.
- `PILOT_DOES_NOT_SUPPORT_CONTINUATION` — operational conditions or effect thresholds fail.
- `PILOT_INVALID` — custody, blinding, surface parity, assignment, or scoring was materially compromised.

None is a product promotion.

Possible Stage 2 dispositions, to be finalized in its own preregistration:

- graph decision value demonstrated for the declared case and receiver populations;
- extraction-only value demonstrated; retire graph-as-human-surface claim;
- decision-value claim not demonstrated; mechanical substrate remains experimental;
- study invalid.

## 14. Explicitly not claimed

This protocol does not validate truth, neutrality, completeness, the graph ontology, automated extraction, signatures, merge logic, agent usefulness, or general usefulness across domains. The repository's existing tests establish controlled mechanical behavior only. This pilot asks whether one human-facing representation helps under one declared boundary.
