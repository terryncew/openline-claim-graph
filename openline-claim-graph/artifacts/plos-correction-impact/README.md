# PLOS correction Evidence Recall specimen

Open `review.html` for the human surface or `REPORT.md` for the concise result.

This artifact applies a real PLOS correction to a signed, explicitly authored accepted-state dependency graph. It demonstrates deterministic source-impact propagation, not a truth oracle or a user-value result.

## Reproduce

```bash
PYTHONPATH=src python examples/build_plos_correction_case.py \
  --output artifacts/plos-correction-case

PYTHONPATH=src python examples/build_plos_correction_impact.py \
  --base artifacts/plos-correction-case \
  --output artifacts/plos-correction-impact

PYTHONPATH=src python -m openline_claim_graph verify-impact \
  --report artifacts/plos-correction-impact/impact-report.json \
  --snapshot artifacts/plos-correction-impact/accepted.snapshot.json \
  --sources artifacts/plos-correction-impact/sources.json \
  --event artifacts/plos-correction-impact/source-status-event.json \
  --policy artifacts/plos-correction-impact/impact-policy.json \
  --receipt artifacts/plos-correction-impact/accepted.receipt.json \
  --public-key d759793bbc13a2819a827c76adb6fba8a49aee007f49f2d0992d99b825ad2c48

PYTHONPATH=src python scripts/verify_plos_correction_impact.py \
  --artifact artifacts/plos-correction-impact
```

The independent verifier intentionally does not import the candidate impact implementation.

## What is real and what is authored

- Real: original PLOS article excerpts, correction DOI, and exact correction sentence.
- Authored: downstream review/decision claims and their admitted dependency edges.
- Mechanically established: content identity, receipt binding, exact affected spans, propagation under policy, survival on an admitted alternative path, witness paths, and report reproduction.
- Not established: automated extraction, semantic completeness, historical reliance, scientific truth, user demand, or commercial value.
