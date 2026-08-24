# Prior-art and source boundary

Frozen: 2026-08-24

## Dependency-Guided Rollback Repair

**Caili Yu et al.**  
*From Faulty Memories to Corrected Actions: Dependency-Guided Rollback Repair for Memory-Augmented Agents*  
arXiv:2608.10502, submitted 2026-08-11.

Source-supported points used by SRE-001:

- input begins with a failed execution and diagnosed faulty memories;
- diagnosis is outside the paper's scope;
- the method builds a typed memory-to-action dependency graph;
- it traces downstream dependencies, preserves independently supported candidates,
  deactivates unsupported state, and selectively replays affected computation;
- the controlled benchmark contains 150 cases across three tool-use domains and four
  memory failure types;
- the paper's stale injection simulates an old memory that should have been deleted or
  superseded remaining active.

SRE-001 does **not** call its delayed external-standing event equivalent to that stale
injection.

## MemoRepair

**Yang Zhao et al.**  
*MEMOREPAIR: Barrier-First Cascade Repair in Agentic Memory*  
arXiv:2605.07242, submitted 2026-05-08.

Source-supported points used by SRE-001:

- invalidated roots induce an affected cascade through influence provenance;
- affected artifacts are withdrawn before repair;
- successors are constructed from retained support and repaired predecessors;
- republication requires validation and predecessor closure;
- the paper evaluates deletion, correction, and migration events;
- its guarantees rely strongly on complete influence provenance.

SRE-001 therefore does **not** claim that later invalidation propagation itself is new.

## Code/data availability boundary at freeze

The arXiv records did not expose an author repository in the linked code/data section at
protocol freeze; CatalyzeX listed the August paper as “Request Code.” SRE-001's checked
fixture is consequently a local conformance adaptation, not an execution of either
authors' benchmark.

Any later author release must be pinned by commit/content hash in a new external-run
addendum before results are inspected.
