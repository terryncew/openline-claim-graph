# Cohort 001 autonomous operator contract

This file is operational guidance for any coding agent maintaining this repository
while Cohort 001 is active. It does not alter Decision Recall semantics.

For every natural consequential repository change after the cohort installation
commit:

1. Build the change because it was independently warranted, never to fill the cohort.
2. Before the ordinary ship / reject confirmation, draft the small prospective
   dependency manifest from information available at that time only.
3. Start `scripts/decision_recall_benchmark.py capture` and present its compact
   decision / required / alternatives / assumptions / invalidation summary as part
   of the normal ship decision. The receiver's ordinary approval is the capture
   confirmation. Corrections are recorded rather than silently incorporated.
4. Independently construct the conventional pre-trigger record from the ordinary
   change record; do not use the prospective manifest to decide what enters it.
5. Compute the canonical subject change-set digest with `scripts/cohort001.py
   changeset`. The manifest's resulting artifact hash must bind that digest.
6. Append the observation with `scripts/cohort001.py append`. If the change is not
   an eligible accepted-state decision, record an explicit exclusion instead.
7. Do not change any frozen instrument file during accumulation. If an instrument
   health defect requires such a change, report `RESTART_REQUIRED` and restart the
   cohort rather than preserving the count.
8. Do not inspect future challenge selection or later gold while capturing state.
9. Do not manufacture decisions, dependencies, negative controls, or revocations
   to improve promotion odds.

The setup/install commit itself is excluded by construction and must never become
observation 1.
