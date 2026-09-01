# Sources

Primary external substrate:

- Tiago Pinto, **Contestability Bindings for Authorized Agent Actions**, `draft-pinto-agent-authz-contestability-00`, Internet-Draft, published 2026-08-29.
- IETF HTML: https://www.ietf.org/ietf-ftp/internet-drafts/draft-pinto-agent-authz-contestability-00.html
- Datatracker: https://datatracker.ietf.org/doc/draft-pinto-agent-authz-contestability/

Pinned interpretation used by this experiment:

- the contestability binding is transport-independent;
- the bound contestation parameters identify forum/procedure/standing/time/effect-policy material;
- the verifier keeps the issuer's declared effect, executor acceptance, authenticated trigger, and claimed application distinct;
- the draft does not itself determine standing or compel an external executor/receiver to honor a declared effect.

The local `foreign-verifier-result.json` is a diagnostic projection fixture, not the draft's wire encoding. CONTESTABILITY-001 intentionally delegates foreign syntax/COSE verification and tests only the receiver-side semantic boundary.
