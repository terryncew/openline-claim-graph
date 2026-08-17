# Evidence Recall Temporal Holdout — Mixed Selectivity Corpus 001

Status: `MIXED_TEMPORAL_SELECTIVITY_CORPUS_RUN_BELOW_PROMOTION_BAR`

## Frozen question

Given only the accepted dependency state available before each trigger, can frozen Evidence Recall retain near-Review-All reconsideration recall while materially reducing how many targets humans must reopen?

The promotion bar was written before gold construction: at least **95% reconsideration recall**, at least **40% review-load reduction versus Review-All Reachability**, and **no additional missed reopenings** versus Review-All. There is no composite score.

## Real historical episodes

1. **Shah / Darwish intravenous iron** — reused byte-for-byte at the episode level from `0.5.0.dev1`. Two targets later received explicit reanalysis after the included Darwish trial was retracted. Both remain `REOPEN` even though the reanalysis reported no change.
2. **Narayan SIRT2 / necroptosis** — frozen on 2014-02-25T23:59:59Z, before Nature's 2014-02-26T00:00:00Z retraction. The pre-cutoff Nature News & Views summary is a HARD derivation. A pre-cutoff Vitner paper is reachable because it cites Narayan in experimental-method context, but the candidate conclusion-level relation is UNADMITTED. A 2016 independent citation audit later identifies the News & Views item as a summary of Narayan while singling out Vitner as method-only rather than propagation of the retracted scientific result into the Gaucher-disease conclusion.

This produces the first real mixed gold in the temporal line: **3 REOPEN + 1 affirmative NO_REOPEN**. The negative is not institutional silence; it is a later independent citation-context audit of the exact target relationship.

## Result

| System | Reopenings caught | Missed | Review load | Unnecessary reviews | Savings vs Review-All |
|---|---:|---:|---:|---:|---:|
| Direct Lookup | 2/3 | 1 | 3 | 1 | 1 |
| Review-All Reachability | 3/3 | 0 | 4 | 1 | 0 |
| Frozen Evidence Recall | 3/3 | 0 | 3 | 0 | 1 |

Frozen Evidence Recall retains **100.00% recall** and reduces review load from 4 to 3, a **25.00% reduction**. It eliminates the one affirmative unnecessary review in this small corpus. Direct Lookup uses the same review load as Evidence Recall but misses one warranted downstream reopening.

## Promotion verdict

`NO_PROMOTION`

Evidence Recall clears the recall requirement and adds no misses versus Review-All, but its 25.00% attention saving is below the predeclared 40% materiality threshold. This is the first case-level evidence that typed authority can buy back *some* attention rather than merely relabeling Review-All, but the effect is too small and the corpus is too small to promote the product thesis.

No engine semantics were changed. The failure is recorded as-is.

## Boundaries

- Four scored targets across two historical episodes are not a stable population estimate.
- The Narayan negative gold is narrow: the later audit establishes that Vitner's citation was method-only rather than reliance of the scored Gaucher-disease conclusion on the retracted SIRT2-necroptosis result. It does not certify every method from the retracted paper.
- The historical packs were reconstructed in 2026. Mechanical timestamps and sealed artifacts prevent explicit future records from entering prediction, but cannot prove constructor ignorance.
- No weighted support, generalized revocation, hidden-edge discovery, UI, Receipt Gate work, or Successor Gate work was added.
