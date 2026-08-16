# Case Admission and Hidden-Key Custody

Case selection is the experiment's largest bias surface. These rules are fixed before a case pack is built.

## 1. Declare the population first

The public pack manifest must identify:

- one domain;
- one bounded candidate source universe;
- a start and end date;
- the target receiver population;
- the source-packet word-count range;
- the positive/negative-control ratio;
- the future public randomness event that will supply the sampling seed.

The candidate universe must be reproducible: for example, every qualifying item in one named registry, court, journal, incident archive, or repository during the declared dates. “Cases that looked interesting” is not a sampling frame.

## 2. Positive-case eligibility

A positive case is eligible only when all conditions hold:

1. At least two pre-resolution claims, or one argument with a proposed bridge, are available in stable source material.
2. Every receiver source predates the resolving event and carries an immutable document hash and numbered paragraph map.
3. The source packet is readable by the declared receiver population without undisclosed specialist context.
4. The packet fits the predeclared length range without omitting material needed to locate the fault line.
5. A later independent document explicitly identifies the consequential disagreement or missing bridge closely enough to anchor a key.
6. The resolving document is independent of the surface builder and is not included in, linked from, named by, or inferable from filenames in the receiver packet.
7. Redistribution is lawful, or the pack contains stable citations and permitted excerpts rather than copied material.
8. No graph, summary, or experimental surface has been produced for the case before eligibility and sampling are locked.

Examples of potentially admissible anchors include a retraction notice that names a specific unsupported inference, a formal postmortem that identifies a previously missing operational assumption, or a legal ruling that identifies the disputed legal element. A ruling anchors the legal fault line; it does not certify metaphysical or empirical truth.

## 3. Anchor strength

- **E1 — explicit external anchor:** the resolving document itself names the relevant fault line or missing bridge. Eligible for the analyzed positive pack.
- **E2 — interpreted external anchor:** the resolving document concerns the outcome, but an adjudicator must infer the precise fault line. Development or exploratory use only.
- **A — author-adjudicated:** no independent resolving event. Development use only.

Only E1 positive cases count in Stage 1 continuation calculations. E2 and A cases must live outside the analyzed pack and may not be pooled later.

## 4. No-conflict controls

No document can prove that no possible disagreement exists. A negative control therefore means something narrower:

> Under the fixed task and consequentiality definition, two independent adjudicators found no target-level fault line in the source packet.

Negative controls must:

- come from the same domain and candidate universe as positive cases;
- match the positive cases' source count and length distribution as closely as feasible;
- undergo independent review by two adjudicators;
- have disagreements resolved before surface construction;
- be labeled `N1_CONSENSUS_NEGATIVE`, never “externally proven no conflict.”

At least 20% and no more than 30% of the analyzed pack is negative control unless a protocol amendment is committed before sampling.

## 5. Screening and sampling

1. Enumerate the complete candidate universe.
2. Apply the eligibility rules without building any experimental surface.
3. Record every inclusion and exclusion with a short reason in the public screening log.
4. Commit and hash the eligible list.
5. Wait for the predeclared future public randomness event.
6. Derive the sampling seed exactly as declared in the pack manifest.
7. Sample the required E1 positives and matched N1 controls without substitution.

If a sampled case later fails packet construction for a reason that should have been visible during screening, report the failure and use the next case in the original deterministic sample order. Do not choose a replacement by preference.

## 6. Custody roles

The minimum roles are:

- **screener/custodian:** maintains the candidate log, resolving documents, private keys, and hashes;
- **two key adjudicators:** independently draft the target and acceptable scoring descriptions;
- **surface builder:** receives only the pre-resolution source packet;
- **receivers:** unfamiliar with the cases and repository;
- **two scorers:** independently score de-identified responses while blind to arm;
- **analyst:** receives labels only after scores, exclusions, and deviations are locked.

One person may perform more than one administrative role only when it does not cross the hidden-key boundary. The surface builder may not be a key adjudicator. The case selector may not be the sole key author. A receiver may not score or build their case.

If those separations cannot be staffed, the run is a development dry run and cannot enter Stage 1.

## 7. Hidden-key construction

For each sampled case, both adjudicators independently receive:

- the pre-resolution packet;
- the resolving document;
- the rubric;
- no experimental surface.

They produce private entries using `templates/case-key.private.template.json`. Before surface construction they must agree on:

- case type;
- target-level consequentiality;
- the source paragraphs forming the fault line, or both sides of the missing bridge;
- acceptable and explicitly unacceptable answer formulations;
- anchor class and exact anchor passage;
- confidence that the packet contains sufficient evidence for the declared receiver population.

Disagreements are adjudicated and logged before the key hash is published. After the key hash is locked, semantic target changes invalidate the case. Typographical corrections create a new key version with a parent hash.

## 8. Public/private split

Before recruitment, publish:

- public case records and source hashes;
- the screening log and eligible-list hash;
- the sampled case identifiers;
- hashes of each private key;
- surface hashes;
- prompt, model/tool, budget, and assignment configuration;
- the pack manifest hash.

Keep private until scoring is locked:

- resolving documents when their identity would reveal the answer;
- target type and target description;
- acceptable answer formulations;
- gold paragraph identifiers;
- adjudicator notes.

After analysis, disclose the private key files and verify them against the pre-run hashes unless legal or privacy constraints declared before recruitment prohibit disclosure.

## 9. Case-pack stop conditions

Do not run when:

- the eligible population was assembled after seeing graph outputs;
- the public sampling seed was known before the eligible list was locked;
- an E1 anchor does not itself identify the target fault line;
- the mapper or surface builder saw any private key;
- Arms B and C fail information parity;
- a source packet silently omits material that contradicts the keyed target;
- fewer than two independent adjudicators produced the key;
- a case cannot be scored under the frozen rubric without inventing a new rule.

Stopping is a valid result. Quiet repair is not.
