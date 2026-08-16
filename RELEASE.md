# Push status

Version: `0.1.0.dev0`

Disposition: `READY_TO_PUSH_AS_EXPERIMENTAL_PROTOTYPE`

This is suitable for a public source repository only if the repository description preserves the same boundary:

> Experimental signed receipts for versioned, source-anchored claim graphs. Mechanical integrity and lineage prototype; no truth or extraction-accuracy claim.

It is **not** ready to be described as a production OpenLine component, knowledge standard, truth system, legal-proof system, or validated decision aid.

Verified locally before packaging:

- Python source compilation
- 23 unit/adversarial tests
- 10,000 deterministic tamper mutations with zero misses
- controlled branch/merge demo
- composed bundle verification
- 1/10/100/1,000-claim scaling probe
- wheel build
- clean target-directory install and import

The GitHub Actions matrix explicitly installs the declared build backend before exercising no-build-isolation wheel construction. It does not rely on Python runner images to bundle `setuptools`.

No model calls, API charges, pushes, releases, or external publication occurred during construction.
