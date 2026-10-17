# OPENLINE-CI-INTEGRITY-001

**Verdict: BLOCKED for an integrity-preserving green-CI repair.** Diagnosis is
complete. This is a current maintenance audit, not a cohort observation, an
exclusion, a retrospective dependency manifest, or a new product experiment.
No historical classification or empirical count is changed.

## Root cause and verified GitHub outcomes

The jobs named `test (3.11)`, `test (3.12)` and `test (3.13)` pass their unit/hostile
test step, then fail the push-only cohort completeness guard in “Build and verify
prospective Decision Recall mechanics.” This is independent of Python version.
`python -m unittest discover -s tests -v` does not run this history guard.

| GitHub run | Event / exact head | Outcome across all three versions |
|---|---|---|
| [34782542781](https://github.com/terryncew/openline-claim-graph/actions/runs/34782542781) | main push `30a3ee1316d0b388fd4f20fa49e25556fef1985b` | FAIL at cohort mechanics, exit 2 |
| [39067395980](https://github.com/terryncew/openline-claim-graph/actions/runs/39067395980) | branch push `e1fe5678bbb11c90dbedd257996ddfe81ce0a9ca` | FAIL at cohort mechanics, exit 2 |
| [39067704349](https://github.com/terryncew/openline-claim-graph/actions/runs/39067704349) | PR #12 event, same `e1fe5678…` head | PASS |

**The issue predates PR #12:** main failed on September 13; the Assessment Recall
branch push failed October 17. PR #12 is still Draft and open. Its successful PR
check is not evidence of a repaired cohort history: `.github/workflows/ci.yml`
returns immediately from the inline history guard unless the event is `push`.
The broader mechanics fixture still runs on PR events.

The Actions jobs and annotations were read through GitHub's API. Full log bodies
could not be downloaded: supported log redirects were denied at
`results-receiver.actions.githubusercontent.com` and Azure log-storage hosts.
Public job pages also require sign-in for logs. No claim is made to have read
those hosted log bodies. The user's reported log diagnosis is independently
corroborated by job/step metadata, exit-2 annotations, and exact local execution
of the unchanged workflow guard. Evidence summaries retain source job URLs.

## Every currently unclassified subject

The declared activation rule is the latest designation modification, so generation
2 starts at `9c1405f62f01ae13052f4e186caa80437ed98b81`. Its installation commit
is not an eligible observation. The workflow already uses that boundary.

| Commit | Canonical change-set SHA-256 | Disposition from this audit |
|---|---|---|
| `30a3ee1316d0b388fd4f20fa49e25556fef1985b` | `c716c7d78e777f8402b8bcf9edd03e7d1dbd07f90ad7cd3f6c4548bdf2d284b3` | Unresolved historical capture gap: substantive qualifying repository change, accepted on main, not an admissible empirical observation |
| `e1fe5678bbb11c90dbedd257996ddfe81ce0a9ca` | `ec60f31b3f99b21d9c5fdd8e32a99248e5afae4e4221646ab8c9da995875fbd0` | Unresolved/pending substantive branch change; Draft PR #12 remains unmerged; not an admitted cohort observation or justified exclusion |

`30a3ee1` adds `identity_binding_gate.py`, executable receiver admission behavior,
its tests, an example, and `IDENTITY_BINDING_GATE_001.md`. That contract says it
closes an admission gap and changes whether a proposed identity may commit. It
is not mechanical bookkeeping or merely generated metadata. Main contains the
accepted change. No prospective manifest, conventional pre-trigger record or
cohort observation was found in repository history for this change.

`e1fe567` adds the bounded Assessment Recall example, comparator, verification
and tests. Synthetic approvals inside its fixture are not empirical enterprise
or cohort decisions. The repository change itself is substantive; its experimental
status and unchanged core engine do not establish a legitimate exclusion. Draft
status does not supply prospective capture. This audit does not presume future
acceptance, invent a rejection, or claim a missing observation is present. A real,
documented nonacceptance could be considered under the existing rules, but would
not fix main's earlier gap. Assessment Recall remains PARITY and is not modified.

### Two additional frozen-status diagnostic entries

`scripts/cohort001.py status` still selects the original designation file addition
`443538f88091a6e4aacc56f06ed82586521e875b`, unlike the declared generation-2 rule.
It consequently also reports:

- `a2d5eb059ea8f3c09472b60c4917caba7c936b48`, digest
  `b3ae43c791e3caa52a2a13e761a665bf0b382e35f476dbd1a964386d9be6b9ea`:
  gain-trigger experiment predating generation-2 activation; outside this generation.
- `9c1405f62f01ae13052f4e186caa80437ed98b81`, digest
  `acef51fd5c0f79fd15b9de10002e458e0aed852a27bb808ec19f1aac92e810f9`:
  generation-2 restart/install itself; excluded from eligibility by construction.

These are not the current push guard's blockers. The existing wrapper already
compensates for this frozen-tool discrepancy. The frozen script, designation,
activation history and previous exclusions remain untouched.

## Why no safe green correction is available

`COHORT.md` explicitly includes real bug fixes, CI repairs, benchmark corrections,
behavior-affecting documentation and accepted mechanism decisions. Its Capture
section and `OPERATOR_CONTRACT.md` require drafting and monotonic capture **before**
the ordinary ship/reject confirmation, and inclusion with the accepted change.
The repository has zero recorded cohort observations; its three empirical record
directories contain only installation placeholders throughout Git history.

The permitted exclusion reasons are `NON_CONSEQUENTIAL_MECHANICAL`,
`GENERATED_METADATA_ONLY`, `COHORT_BOOKKEEPING_ONLY`, `MERGE_ONLY`, and
`NO_ACCEPTED_STATE_CHANGE`. None describes “substantive accepted change whose
prospective capture was missed.” Existing broad exclusions for other historical
experiments are not authority to misclassify these changes. No historical
exclusion is edited or endorsed by this bounded audit.

Do not manufacture a monotonic capture, backdate a record, claim zero accepted
state change just because capture is absent, lower thresholds, suppress the guard,
or move activation past the gap. A present-day reconstructed manifest would be
retrospective and cannot repair the required chronology. A verified contemporaneous
capture packet, if one actually exists outside this repository, could be audited
against the frozen rules; its existence or admissibility cannot be assumed.
Otherwise a separately authorized future protocol/cohort decision must acknowledge
the gap. No restart, instrument repair, or new experiment is performed here.

## Minimal maintenance change

Only this report and current audit evidence are appended beneath the existing
cohort bookkeeping directory. Its paths are already excluded by the designation's
`artifacts/decision-recall-prospective/cohort-001/**` glob. They do not classify any
subject or count as an empirical decision, and their canonical substantive
change-set is empty. No observation, exclusion, historical record, scoring
instrument, threshold, workflow, engine or Assessment Recall file is changed.
The maintenance Draft PR records a blocker; it is not a CI-fix claim and must not
be merged as a way to make the failing checks disappear.

## Reproduction and tested evidence

Read `evidence.json` for exact source heads, API step results, classification,
recording time, frozen-hash check and local command outcomes. Raw evidence:
`unit-tests.txt`, `conformance-verification.json`, `main-push-guard.json`, and
`assessment-push-guard.json`. Local runtime: Python 3.12.14. The 162 existing tests
pass; the independently verified prospective mechanics fixture passes. The
unchanged guard fails on both source heads as expected, and is skipped for the PR
event. The maintenance commit leaves main's guard failure visible.

From the repository root, use the existing `.venv` and run:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/build_decision_recall_prospective_fixture.py --output /tmp/ci-integrity-conformance
.venv/bin/python -I scripts/verify_decision_recall_prospective_fixture.py --artifact /tmp/ci-integrity-conformance --output /tmp/ci-integrity-verification.json
.venv/bin/python scripts/cohort001.py --root . status
```

To reproduce the actual workflow history guard, extract its unchanged inline Python:

```bash
.venv/bin/python - <<'PY'
import textwrap
from pathlib import Path
workflow = Path('.github/workflows/ci.yml').read_text()
start = workflow.index('          import importlib.util\n')
end = workflow.index('          PY\n', start)
Path('/tmp/ci-integrity-guard.py').write_text(textwrap.dedent(workflow[start:end]))
PY
GITHUB_EVENT_NAME=push .venv/bin/python /tmp/ci-integrity-guard.py
```

Expected exit is **2**, identifying `30a3ee1` on this main-based maintenance branch.
The test/reproduction commands do not create observations or exclusions. Consult
the delivery message and Git history for the exact tested maintenance commit and
its GitHub outcomes; a passing PR-event check must not be described as RESOLVED.
