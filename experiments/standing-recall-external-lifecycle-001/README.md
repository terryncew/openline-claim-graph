# Standing Recall Test — External Lifecycle (SRE-001)

This experiment asks what happens **after** a validly finalized decision when evidence it
relied on later loses receiver-admissible standing.

Current status:

`FROZEN_PROTOCOL_CONFORMANCE_PASS_EXTERNAL_ADAPTATION_UNRUN`

The checked 64-episode fixture is mechanics-only. It is not an execution of DGRR,
MemoRepair, LongMemEval-V2, ToolBench, or MemoryArena.

## Checked conformance result

| System | Recall | Preservation | Replay surface |
|---|---:|---:|---:|
| DGRR-style node-support abstraction | 0.6667 | 1.0000 | 40 |
| MemoRepair-style cascade abstraction | 0.6667 | 1.0000 | 160 |
| OpenLine standing propagation | 1.0000 | 1.0000 | 60 |

These numbers are deliberately **not** a promotion claim. The fixture contains
property-specific cases designed to test whether whole-node support is enough.

## Run

```bash
python -m unittest discover \
  -s experiments/standing-recall-external-lifecycle-001/tests -v

python experiments/standing-recall-external-lifecycle-001/scripts/build_fixture.py \
  --output /tmp/sre001-fixture.json

python experiments/standing-recall-external-lifecycle-001/scripts/run_benchmark.py \
  --fixture /tmp/sre001-fixture.json \
  --output /tmp/sre001-score.json

python -I experiments/standing-recall-external-lifecycle-001/scripts/verify_benchmark.py \
  --fixture /tmp/sre001-fixture.json \
  --score /tmp/sre001-score.json \
  --output /tmp/sre001-independent.json
```

See `PROTOCOL.md` for the frozen novelty boundary and falsifier.
