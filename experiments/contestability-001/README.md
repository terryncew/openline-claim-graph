# CONTESTABILITY-001 — foreign contestation → selective reopen

Status: **MECHANICS PASS — external draft profile, local receiver authority**

This experiment asks one narrow question:

> Can an OpenLine receiver ingest a foreign contestation event, decide locally whether that event changes standing, and reopen exactly the dependent consequences without treating the foreign artifact as self-authorizing?

The external substrate is `draft-pinto-agent-authz-contestability-00`, published 29 August 2026. The draft separates the issuer's declared effect policy, executor acceptance, authenticated filing trigger, and claimed application. CONTESTABILITY-001 preserves those as separate foreign facts and adds two receiver-owned stages: local standing acceptance and local consequence application.

The experiment deliberately does **not** implement the draft's CBOR/COSE verifier. It consumes a deterministic structured verifier result through a data-defined adapter profile. Foreign cryptographic verification remains foreign. OpenLine owns only its local interpretation and consequences.

## Smallest path

1. `auth-A` is valid.
2. `action-A` executes.
3. An affected party files an authenticated contestation.
4. A foreign verifier result arrives.
5. OpenLine normalizes it without applying anything.
6. Receiver policy separately accepts or rejects a standing transition.
7. Only after local acceptance may OpenLine apply selective reopen.
8. The action history remains `EXECUTED`; only reopenable dependent consequences change.
9. An independent authorization/action/consequence branch remains untouched.

Run:

```bash
python experiments/contestability-001/scripts/run_contestability.py \
  --output /tmp/contestability-result.json

python experiments/contestability-001/scripts/verify_result.py \
  --result /tmp/contestability-result.json
```

## Pass conditions

- authenticated filing alone changes no OpenLine state;
- a declared foreign effect changes no OpenLine state;
- executor acceptance is represented separately from the filing trigger;
- a foreign claim that an effect was applied cannot apply it locally;
- receiver acceptance is an explicit local decision under `receiver-policy.json`;
- local application is a later, separately recorded stage;
- the accepted case reopens exactly the dependent consequences;
- unrelated consequences remain closed;
- an alternate foreign object shape produces the same neutral event by changing only the adapter profile.

## Falsifier

The integration fails if OpenLine must hard-code this draft's field layout or semantics into its receiver logic; if `filed`, `accepted`, and `applied` collapse into one state; if a foreign declared effect or application claim mutates local state; or if the receiver reopens unrelated consequences.

No production OpenLine core file is changed by this experiment.
