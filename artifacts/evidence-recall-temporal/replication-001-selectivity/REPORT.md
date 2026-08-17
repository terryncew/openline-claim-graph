# Evidence Recall 0.5.2 — Temporal Selectivity Replication

Status: `TEMPORAL_SELECTIVITY_REPLICATION_PROMOTED`

## Frozen question

Can the unchanged Evidence Recall engine repeatedly avoid waking reachable targets that later case-level records establish did not require reconsideration, while retaining near-Review-All recall?

## Corpus rule

Only explicit case-level reliance/reconsideration or affirmative non-reliance/scope exclusion is scored. Silence is UNASSESSED. Kataoka's aggregate 335/239 pathway is recorded but contributes zero scored rows because this build cannot reproduce its case-level inclusion/exclusion rows without inventing them. JAMA and VITALITY remain quantitative stress assets rather than negative-gold factories.

The scored corpus contains 5 trigger episodes and 14 targets: Shah/Darwish, expanded Narayan, and three separately triggered Sato retractions evaluated against the later Avenell manual audit.

## Pooled result

| System | Reopenings caught | Missed | Review load | Unnecessary reviews |
|---|---:|---:|---:|---:|
| Direct Lookup | 7/8 | 1 | 13 | 6 |
| Review-All Reachability | 8/8 | 0 | 14 | 6 |
| Frozen Evidence Recall | 8/8 | 0 | 8 | 0 |

Evidence Recall reduces review load by 6 of 14 items (42.85%) while retaining 100.00% reconsideration recall and adding 0 misses versus Review-All.

## Episode-level replication

| Episode | ER recall | Review-All load | ER load | Saved | Savings | Extra misses |
|---|---:|---:|---:|---:|---:|---:|
| Darwish retraction -> Shah intravenous-iron meta-analysis | 2/2 | 2 | 2 | 0 | 0.00% | 0 |
| Narayan SIRT2 retraction — expanded manually inspected direct contexts | 3/3 | 4 | 3 | 1 | 25.00% | 0 |
| Sato trial 11 retraction — explicit inclusion versus affirmative non-reliance | 1/1 | 3 | 1 | 2 | 66.66% | 0 |
| Sato trial 12 retraction — explicit inclusion versus affirmative non-reliance | 1/1 | 2 | 1 | 1 | 50.00% | 0 |
| Sato trial 8 retraction — explicit inclusion versus affirmative non-reliance | 1/1 | 3 | 1 | 2 | 66.66% | 0 |

Mean episode savings: 41.66%  
Median episode savings: 50.00%  
Episodes with positive savings and zero additional misses: 4/5

## Promotion rule and verdict

Predeclared pooled bar: >=95% recall, >=40% review-load reduction, zero additional misses. Replication sufficiency: positive savings with zero additional misses in at least 3 trigger episodes.

**PROMOTION**

This verdict promotes only the observed temporal-selectivity behavior under this frozen benchmark contract. It is not proof of commercial moat, broad-domain generality, or automated dependency discovery.

## Boundaries

- The engine files are byte-identical to 0.5.0.dev0 / 0.5.1.
- Historical construction occurred after outcomes were known; artifact separation cannot prove constructor psychology.
- Three of five trigger episodes belong to the same Sato research-misconduct family and are graded by the same later Avenell audit. That clustering limits claims of independence.
- Kataoka contributes no scored rows because aggregate counts are not case-level gold.
- No engine repair, weighted support, generalized revocation, hidden-edge discovery, UI, Frame Ledger expansion, Receipt Gate work, or Successor Gate work is included.
