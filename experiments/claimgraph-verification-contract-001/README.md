# CLAIMGRAPH-VERIFICATION-CONTRACT-001

Bounded experiment for the primitive earned by `CLAIMGRAPH-UNOBSERVED-STATE-001`.

Frozen base: `b238f6f1c0a9025cfdccc7367b3c256ab4d50792`

The experiment records a verification obligation at acceptance time while leaving
the live external state outside the Claim Graph. A small receiver-side admission
gate decides whether later verification is fresh and admissible. Only an admitted
predicate failure is converted into the existing `LOSS_OF_STANDING` event that
Decision Recall already propagates.

No production file is modified by this experiment.
