# SRE-002 public-record sources

Retrieved/reviewed: 2026-08-24.

The source registry is embedded in `NATURAL_CASES.json`. These links anchor the historical lifecycle events and the disclosed target dispositions. SRE-002 does not claim that a URL, citation, or publisher name automatically proves the authored dependency mapping. The mapping from public record → evidence facet → finalized decision is a separate, retrospective representation claim.

## CORRECT

### BMJ — Hemkens et al. correction/reanalysis

- The BMJ, correction notice: https://www.bmj.com/content/362/bmj.k3210
- Frozen use: original inversion strategy was judged biased; the requested reanalysis did not change the reported results or interpretation, so the method-specific target reopens while result/interpretation targets survive.

### NEJM — GM-1 spinal-cord injury trial correction

- New England Journal of Medicine, correction: https://www.nejm.org/doi/full/10.1056/NEJM199112053252321
- Frozen use: corrected Table 5/Abstract values replace the exact original numeric statement; the correction says the published conclusions remain unchanged and identifies other reported support for the cervical lower-extremity finding.

## REVOKE

### DigiNotar

- Mozilla Foundation Security Advisory 2011-34: https://www.mozilla.org/en-US/security/advisories/mfsa2011-34/
- Mozilla follow-up: https://blog.mozilla.org/security/2011/09/02/diginotar-removal-follow-up/
- Google security update: https://security.googleblog.com/2011/08/update-on-attempted-man-in-middle.html
- Frozen use: DigiNotar root trust was removed; the temporary Dutch-government exception was later removed; Chrome had an independent protection path for the fraudulent Google certificate.

### Legacy Symantec PKI

- Google Online Security Blog: https://security.googleblog.com/2018/03/distrust-of-symantec-pki-immediate.html
- Mozilla Security Blog: https://blog.mozilla.org/security/2018/03/12/distrust-symantec-tls-certificates/
- Frozen use: legacy Symantec trust was phased out; narrow Apple/Google-controlled subordinate exceptions existed in Mozilla's plan; transition material distinguished legacy infrastructure from new managed infrastructure.

## SUPERSEDE

### TLS 1.0 / TLS 1.1

- RFC 8996: https://www.rfc-editor.org/info/rfc8996/
- Mozilla Security Blog: https://blog.mozilla.org/security/2018/10/15/removing-old-versions-of-tls/
- Frozen use: RFC 8996 formally deprecated TLS 1.0/1.1, moved them to Historic, prohibited fallback/negotiation in the updated guidance, and replaced old minimum-version references with TLS 1.2.

### NIST SHA-1 policy

- NIST hash-function policy: https://csrc.nist.gov/projects/hash-functions/nist-policy-on-hash-functions
- NIST SHA-1 collision update: https://csrc.nist.gov/news/2017/research-results-on-sha-1-collisions
- Frozen use: SHA-1 digital-signature generation crossed from deprecated to disallowed after the transition period, while legacy signature verification and specified HMAC/KDF uses remained permitted under the cited policy. This is intentionally a use-specific standing case.

## EXPIRE

### DST Root CA X3

- Let's Encrypt: https://letsencrypt.org/ca/docs/dst-root-ca-x3-expiration-september-2021/
- Let's Encrypt Android compatibility note: https://letsencrypt.org/2020/12/21/extending-android-compatibility.html
- Frozen use: DST Root CA X3 expired on 2021-09-30; older non-Android clients without ISRG Root X1 could fail, while modern X1-trusting clients and the documented older-Android compatibility path could continue.

### Ericsson/O2 security certificate

- Ofcom investigation conclusion: https://www.ofcom.org.uk/siteassets/resources/documents/about-ofcom/bulletins/enforcement-bulletin/all-cases/cw_01235/decision-to-conclude-investigation---o2-network-outage?v=321087
- Frozen use: Ofcom records that a hardcoded certificate expired at 04:30 on 2018-12-06, triggered Ericsson SGSN-MME software failure, and disrupted O2 2G, 3G, and 4G data services.

## Source boundary

CI freezes the registry bytes and verifies the mechanics built from them. It does not continuously refetch these pages, prove their semantic truth, or convert source authority into OpenLine policy authority.

`policy_authority: NONE`
