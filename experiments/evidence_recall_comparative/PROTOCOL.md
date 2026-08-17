# Evidence Recall Three-Way Comparative Benchmark

## Question

Given an independently grounded upstream invalidation and a pre-gold dependency representation, does the shipped Evidence Recall engine improve on two simpler mechanisms without hiding the cost in unresolved review?

The three systems are frozen:

1. **Direct Lookup** — flags only immediate dependents of the invalidated source/node.
2. **Naive Transitive Taint** — quarantines every node reachable over every directed edge. It ignores relation type, receiver authority, and surviving support.
3. **Evidence Recall** — calls the existing `analyze_source_impact()` implementation. It uses receiver-frozen HARD / ADVISORY / UNADMITTED relation authority, preserves surviving hard support paths, and sends advisory exposure to `AFFECTED_UNRESOLVED`.

No benchmark-specific relation algebra, quantitative weighting, cut-set solver, or post-gold rescue rule is added to Evidence Recall.

## Evaluation assets

### Main stratum: Schneider et al. / Matsuyama second-generation citations

- Article DOI: `10.1007/s11192-020-03631-1`
- Data DOI: `10.13012/B2IDB-3331845_V2`
- Canonical CSV: `2010-2019 SG to specific not mentioned FG-v2.csv`
- Published result: 161 second-generation citations in the selected network; 152 accessible for context analysis; 23 marked as possible misinformation diffusion. Four of the 161 second-generation nodes are also direct citations.

The importer reads the raw CSV once and produces four separately bound artifacts:

- `pack.json`: public topology/text/identifiers only;
- `authority.json`: label-independent relation authority;
- `gold.private.json`: external outcome annotations;
- `import-report.json`: source hash and count checks.

The public pack rejects answer-bearing metadata keys. The authority rule is fixed without consulting the `Review possible impact overall?` field:

- Matsuyama -> selected first-generation paper: `HARD`, because the corpus selection already requires that those direct papers discuss Matsuyama methods/results.
- Ordinary first-generation -> second-generation citation: `ADVISORY`.
- A public second-generation node that is also a direct citation: direct edge `HARD`.

This is intentionally conservative. The benchmark may show that Evidence Recall merely converts hard over-taint into unresolved-review burden. Selective semantic authority must be independently constructed before gold is unsealed if it is ever tested.

Canonical import fails closed unless it recovers 152 accessible rows and 23 positive external annotations.

## Negative control: van der Vet & Nijveen

- Article DOI: `10.1186/s41073-016-0008-5`
- Published result: ten indirect candidates in the 2015 overlap were manually inspected; no indirect propagation was found in that case study.

The DOT importer accepts the published supplementary citation graph plus the predeclared inspected target IDs. The paper's DOT arrows point citing -> cited; the benchmark inverts them to prerequisite -> dependent before propagation. Direct root edges are hard; later citation edges are advisory. Gold is `NO_EXPOSURE` for the manually inspected indirect targets.

## Quantitative abstraction stress test: JAMA Internal Medicine 2025

- Article DOI: `10.1001/jamainternmed.2025.0256`
- 166 meta-analyses were rerun after retracted studies were removed.
- Statistical significance changed in 18.
- 21 had no change in the pooled effect estimate.
- Of 163 with effect evolution calculable, 57 changed >=10%, 31 changed >=30%, and 23 changed >=50%.
- 7 of 50 reviews had changes potentially meaningful to abstract interpretation.

This stratum is **not** scored as `SURVIVE` vs `QUARANTINE` gold. Evidence Recall quarantine means an accepted state lost a basis and should be reconsidered; it does not predict that recomputation must change the numerical result. JAMA is therefore an abstraction/selectivity stress test for categorical dependency semantics, not a false-positive oracle.

## Primary scored metrics

For case-level external labels:

- `missed_exposure`: gold `EXPOSED` and system returns `UNAFFECTED`;
- `hard_false_quarantine`: gold `NO_EXPOSURE` and system returns `QUARANTINE`;
- `unnecessary_unresolved_review`: gold `NO_EXPOSURE` and system returns `AFFECTED_UNRESOLVED`;
- `total_review_load`: every `QUARANTINE` or `AFFECTED_UNRESOLVED`;
- `unnecessary_review_load`: review load on gold `NO_EXPOSURE` cases.

`AFFECTED_UNRESOLVED` counts as exposure detection but is never free. `SURVIVES` counts as structurally touched without a hard action. The benchmark publishes counts, not a composite score.

## Anti-leakage order

1. Acquire and hash raw source bytes.
2. Build the public pack with outcome fields excluded.
3. Freeze the authority artifact from public/pre-outcome information only.
4. Run all three systems and persist `predictions.json`.
5. Only then bind/open `gold.private.json` for scoring.
6. Score without changing Evidence Recall.

The software cannot prove that a human operator did not inspect the gold before step 3. It makes the artifacts separable, content-addressed, reproducible, and auditable so the custody order can be independently enforced in a sealed execution environment.

## Promotion rule

There is deliberately no automatic product-promotion threshold in code. The benchmark can return any of the following without a rescue patch:

- Direct lookup misses real indirect exposure.
- Naive taint over-quarantines.
- Evidence Recall reduces hard over-taint but creates equivalent unresolved-review load.
- Evidence Recall's categorical relation algebra is inadequate for quantitative aggregation.
- All three systems are roughly equivalent or inadequate.

Only a completed case-level run on independently sourced bytes can support an empirical mechanism-advantage claim.
