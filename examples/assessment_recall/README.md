# Assessment Recall 001

A synthetic, local example of enterprise-owned assessment continuity. **Comparison:
PARITY. Overall delivery: PARTIAL pending the full competitor review and remote
Draft PR access.** Nothing here changes stable engine semantics or production approval.

Three public test identities represent an evaluator, developer and enterprise.
The evaluator's sandbox assessment binds an exact model/tool/safeguard configuration.
The receiver separately signs its acceptance, dependency table and original two
approvals. A signed developer change is not automatically granted policy authority:
the enterprise signs its own scope/admissibility judgment. Existing Evidence Recall
then identifies payments for review and preserves offline export via a separately
accepted, independently sufficient no-tool assessment. Historical assessments stay
intact. A review status is never an assertion of unsafe operation or a new approval.

## Clean install and reproduce

From an existing clone with Python 3.11+ (tested on Python 3.12.14):

```bash
cd /workspace/openline-claim-graph
python -m venv /tmp/assessment-recall-venv
/tmp/assessment-recall-venv/bin/python -m pip install -e '.[test]'
/tmp/assessment-recall-venv/bin/python -m pip check
/tmp/assessment-recall-venv/bin/python examples/assessment_recall/demo.py --output /tmp/assessment-recall-run
/tmp/assessment-recall-venv/bin/python examples/assessment_recall/verify.py --output /tmp/assessment-recall-run --checkpoint /tmp/assessment-recall-run/checkpoint.json
/tmp/assessment-recall-venv/bin/python examples/assessment_recall/baseline.py --packets /tmp/assessment-recall-run/bundle.json --output /tmp/assessment-recall-run/conventional-signed.json
/tmp/assessment-recall-venv/bin/python -m unittest discover -s examples/assessment_recall -p 'test_*.py' -v
/tmp/assessment-recall-venv/bin/python -m unittest discover -s tests -v
```

Open the generated `review.html` as a local file. No web service, commercial model,
API key or database is required. Outputs are outside tracked historical artifacts.
The repository has no lockfile; these commands honor its dependency ranges, not
bit-for-bit future dependency resolution. Tested versions are in `evidence/`.

The example repeats deterministically except for machine timing. It overwrites
only its chosen output directory's named example files. Use a dedicated directory.
Existing cloud tasks are isolated; use the existing checkout, not a new worktree.

## Verification and trust

`verify.py` is a separate-process replay verifier using existing pinned receipt
verification, graph impact verification and independent flat-table computation.
It verifies signed records and compares recorded decisions, graph outputs and HTML.
It is not an independent implementation of the graph algorithm. The flat baseline
is independently implemented for this deliberately small alternative-basis workflow.
It is not a second general graph engine. Timing measurements are diagnostic and
unprotected; decision/evidence outputs are replay-checked.

For genuine independent transfer, obtain `checkpoint.json` from the enterprise via
a separate trusted channel and pass that path to `--checkpoint`. Co-delivery of
bundle and checkpoint only checks consistency: it cannot prevent whole-history
rollback. The test keys are intentionally public in `demo.py`; every signer is
forgeable by anyone reading this example. Role rejection demonstrates the checking
logic, not adversarial key custody. Real trust roots, storage permissions and
external current-head distribution are outside this prototype.

The `authorize` guard rejects historical approval after the current review event
and refuses developer/evaluator approval. It does not execute deployment actions.
An affected approval needs fresh evidence and a new enterprise decision, a manual
process outside the implemented demo; no automatic reapproval is provided.

Missing/ambiguous declarations escalate conservatively. A false completeness claim
or incorrectly declared sufficient alternative can still silently preserve approval:
`test_declared_capture_gap_is_real` deliberately demonstrates that bypass in both
systems. Signatures cannot detect missing business knowledge. A receiver's trusted
but mistaken event mapping likewise cannot be resolved by cryptography. The adapter
assumes the admitted affected-basis list is an accurate enterprise judgment.

See [SOURCE_AUDIT.md](SOURCE_AUDIT.md), [RESULTS.md](RESULTS.md),
[COMPETITORS.md](COMPETITORS.md) and raw [evidence/](evidence/).
