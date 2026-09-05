# CLAIMGRAPH-UNOBSERVED-STATE-001

A frozen discriminating experiment for the DNative-Twin unobserved-tool-state failure mode.

It uses the current Decision Recall disposition logic as-is. The target accepted decision is anchored to the existing PLOS accepted graph state, while the consequential external registry state is deliberately absent from the frozen dependency record.

Run from repository root:

```bash
python experiments/claimgraph-unobserved-state-001/scripts/run_experiment.py
python experiments/claimgraph-unobserved-state-001/scripts/verify_result.py
pytest -q experiments/claimgraph-unobserved-state-001/tests
```

The expected frozen result on base `e5b272bb048bd6b224eb430ebd9931713698cc13` is a **falsifier trigger**, not a pass: current Decision Recall silently preserves the target even after fresh verified material state is supplied because that basis was absent from the accepted manifest.

No production semantics are changed by this experiment.
