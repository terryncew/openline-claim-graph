# SRE-001 External Adaptation — LongMemEval-V2

Status at installation: **EXTERNAL_ADAPTATION_READY_UNRUN**  
Policy authority: **NONE**

## Frozen question

Does the SRE-001 standing mechanism retain its selectivity when the underlying decision facts are bound to records from an independently developed agent-memory trajectory substrate, while strong rollback/repair contract baselines receive the same delayed lifecycle event?

This lane does **not** modify the frozen SRE-001 mechanism or its promotion policy. It supplies an external source adapter and stronger paper-contract baselines.

## External substrate

The source records are pinned public **LongMemEval-V2** sample trajectory excerpts. The repository pin supplies the public trajectory schema and tooling. The Hugging Face revision supplies the source bytes used by CI.

This is deliberately **not** described as the DGRR paper's 50-case LongMemEval-V2 adaptation. That private adaptation is not public here. It is also not the complete LongMemEval-V2 benchmark. The pinned public sample contains trajectory excerpts intended for direct inspection.

## Source selection — frozen before the external run

The adapter reads the pinned trajectory-excerpt JSONL and selects exactly ten records using a structural rule that does not inspect benchmark success or any later SRE outcome:

1. require non-empty `id`, `domain`, and `environment`;
2. require at least two states;
3. require at least two states with non-empty URLs;
4. sort eligible records lexicographically by trajectory ID;
5. take the first five;
6. select two structural anchors from each trajectory: the first and last usable state by source-list order.

Each of the resulting **10 state anchors** is expanded into one `EXPIRE`, one `REVOKE`, one `SUPERSEDE`, and one `CORRECT` event, producing exactly **40** external-source lifecycle episodes and **10** episodes per event type. The 40 episodes are not treated as 40 independent trajectories: they are repeated controlled interventions over 10 anchors drawn from 5 external trajectories.

The trajectory record is external. The lifecycle event is synthetic. The source bytes are not rewritten to manufacture a fault. At `t0`, all evidence is admissible and all scored decisions stand. At `t2`, the receiver changes only the standing of `E1`.

## Decision mapping

For each external trajectory state anchor:

- `E1` binds the selected state's `environment`, `domain`, and exact `state_url`.
- `E2` independently binds the trajectory's `environment`, `domain`, `outcome`, and `start_url`.
- `D1` requires the environment and may satisfy it from `E1` **or** `E2`.
- `D1.core_environment` is supported by either `E1` or `E2`.
- `D1.state_url` is supported only by `E1`.
- `D2` relies specifically on `D1.state_url`.
- `D3` relies on `D1.core_environment`.
- `D4` is an independent branch supported by `E2.domain`.

After `E1` loses standing, the frozen gold relation is therefore:

- `D1`: SURVIVE
- `D2`: REOPEN
- `D3`: SURVIVE
- `D4`: SURVIVE

For `SUPERSEDE` and `CORRECT`, a replacement state is exposed as new evidence but is **not** silently substituted for the old property/value dependency. A new source can earn a new decision; it does not retroactively rewrite what the finalized decision relied on.

## Baselines

### DGRR contract adaptation

`DGRR_CONTRACT_NODE_SUPPORT_EXTERNAL_V1` implements the published diagnosed-root / affected-subgraph shape at node granularity. Independent support for an affected decision must come from outside the root and outside the initially affected set. Affected nodes do not recursively certify one another as independent support.

This is **not DGRR author code** and no DGRR-reported benchmark number is reproduced by this lane.

### Strong MemoRepair contract adaptation

`MEMOREPAIR_CONTRACT_PROPERTY_VALIDATION_EXTERNAL_V1` is intentionally strong. It performs barrier-first withdrawal over the entire affected descendant set, then gives reconstruction an **exact property-aware validation oracle**. That means it is allowed to determine that `D1` remains valid, that `D1.core_environment` remains supported, and that `D1.state_url` does not.

This choice prevents OpenLine from winning merely because a MemoRepair-style baseline was made artificially node-blind. The discriminating question becomes whether receiver-owned standing can reach the same correct consequence while reconsidering less already-valid state than barrier-first repair.

This remains a paper-contract adaptation, **not MemoRepair author code**, its min-cut selector, or its reported benchmark.

## Frozen metrics and promotion rule

The parent SRE-001 promotion policy remains authoritative for this experiment. In particular:

- at least 40 external-source episodes;
- at least 10 per lifecycle event;
- at least 10 independent-support cases;
- at least 10 surviving-upstream / narrower-downstream-property cases;
- OpenLine affected-decision recall >= 0.95;
- OpenLine unaffected-state preservation >= 0.95;
- zero additional misses or false reopenings versus the strongest baseline;
- if a baseline matches OpenLine accuracy, OpenLine replay surface must be at least 10% smaller;
- independent verification mismatches must be zero before any result is accepted.

## Falsifier

A successful run does **not** establish that MemoRepair cannot express property-aware validation. In this lane it is explicitly allowed to do so.

The mechanism claim should be narrowed or retired if a MemoRepair-compatible barrier-first repair reaches the same recall, preservation **and** repair surface without adding receiver-owned standing semantics. If it matches accuracy but touches materially more state, the only earned separation is the narrower one: selective standing recomputation can preserve already-valid history with a smaller repair surface.

## No-rescue rule

The source pins, source-selection rule, decision mapping, lifecycle expansion, baseline contracts, metrics, and thresholds are frozen before the first repository-visible external run. An empirical failure may expose an implementation error or invalidate the proposed separation. It must not be repaired by changing the scientific rule after observing the result.

Pure infrastructure repairs are allowed only when they do not change source selection, event construction, baseline semantics, scoring, thresholds, or the OpenLine mechanism.
