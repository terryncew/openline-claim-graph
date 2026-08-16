# Frame Ledger — Washington Post headline specimen

Open `review.html` for the readable surface.

Status: `MECHANICAL_DEVICES_REPRODUCED_ON_ONE_HEADLINE_NO_BIAS_VERDICT`

The exact headline supplied by the maintainer is scanned under the checked-in mechanical ruleset. Seven findings reproduce: one conflict lexeme, one co-occurrence cue, two issue-frame lexemes, one narrow local-attribution-pattern absence, and two receiver-declared term-set absences.

The green status means those operations reproduce from exact UTF-8 bytes. It does not mean the article is biased, fair, false, propaganda, or rationalizing anyone. The article body is not in this specimen.

No frontier or open-weight model was called while building this artifact. `proposal-task.json` is the exact bounded task that may be sent through `scripts/frame_agent_adapter.py`; any returned inference still needs the receiver's signed heterogeneous-review quorum.

## Reproduce

```bash
PYTHONPATH=src python examples/build_wapo_frame_ledger.py \
  --output artifacts/wapo-headline-frame-ledger

PYTHONPATH=src python -m openline_claim_graph verify-frame \
  --report artifacts/wapo-headline-frame-ledger/report.json \
  --source artifacts/wapo-headline-frame-ledger/source.json \
  --findings artifacts/wapo-headline-frame-ledger/findings.json \
  --policy artifacts/wapo-headline-frame-ledger/policy.json
```

Report: `frame-ledger-report:sha256:04f9668dee5daaa4d57ecda9fe64bc78d650b730afa1438963b7375945fc2dfb`
