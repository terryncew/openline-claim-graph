# Evidence Recall Temporal Holdout — Real Case 001

Status: `REAL_TEMPORAL_CASE_001_RUN_NO_SELECTIVITY_ADVANTAGE`

## Case

- Accepted review: Shah et al., JAMA Network Open, 2021, DOI `10.1001/jamanetworkopen.2021.33935`.
- Invalidated study: Darwish et al., DOI `10.1080/14767058.2017.1379988`.
- `t0`: 2023-01-18T23:59:59Z (day before the publisher retraction).
- `t1`: 2023-01-19T00:00:00Z (publisher retraction date, DOI `10.1080/14767058.2023.2169999`).
- Later record: 2025-01-27T00:00:00Z, JAMA Network Open correction DOI `10.1001/jamanetworkopen.2025.0887`.

The pre-cutoff review explicitly places reference 76 (Darwish) inside the 111-RCT hemoglobin analysis. The pack therefore models a HARD `DERIVED_FROM` relation from the Darwish trial to the pooled hemoglobin result, and a second HARD derivation from that pooled result to the review's improved-hemoglobin finding. No later correction is needed to construct either edge.

The later JAMA correction explicitly reports that the review was reanalyzed without the retracted study and that the reported results did not change. Under the frozen temporal-gold rule, both targets are `REOPEN`: reconsideration really occurred even though the findings survived.

## Frozen predictions and score

| System | Reopenings caught | Missed | Review load | Reviewer savings vs Review-All |
|---|---:|---:|---:|---:|
| Direct Lookup | 1/2 | 1 | 1 | 1 |
| Review-All Reachability | 2/2 | 0 | 2 | 0 |
| Frozen Evidence Recall | 2/2 | 0 | 2 | 0 |

Direct Lookup catches the immediate pooled result but misses the downstream improved-hemoglobin finding. Review-All and frozen Evidence Recall catch both. Evidence Recall saves **zero** reviews versus Review-All in this first real historical episode.

## Verdict

`NO_PROMOTION`.

This episode establishes real temporal mechanism contact: a graph frozen before a 2023 retraction is graded by a 2025 trigger-attributed reanalysis. It does **not** establish an attention-selectivity advantage. On this two-target HARD dependency chain, Evidence Recall and Review-All are equivalent.

The result is intentionally not rescued. No relation semantics, weighting, basis type, or evaluator rule changed after the later record was examined. More real historical episodes are required before any product-level temporal claim can be considered.

## Boundaries

- This is one small real case, not a corpus-level estimate.
- Both scored gold labels are positive; this case does not estimate false-review precision.
- The local evidence JSON files are source-backed factual snapshots, not byte-for-byte publisher archives.
- The historical reconstruction was authored after the events occurred; mechanical timestamp controls prevent explicit data leakage into the pack but cannot prove human ignorance.
- Infection and RBC-transfusion branches are excluded from scoring because the pre-cutoff review's enumerated study lists do not include reference 76 and the later trigger-specific correction does not provide an independent target-level negative-gold record for them.
