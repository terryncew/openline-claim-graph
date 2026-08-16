# Evidence Recall: PLOS correction specimen

Status: `IMPACT_COMPUTED_CONDITIONALLY`

A real PLOS correction notice was admitted against an authored, signed accepted-state graph. The deterministic engine computed what must be reopened under the receiver's declared edge policy.

## Result

- Direct source claims exposed: **5**
- Claims proposed for quarantine: **7**
- Claims retaining an admitted alternative basis: **1**
- Claims requiring review because an advisory edge is involved: **1**
- Accepted decisions touched: **1**
- Direct-only baseline misses: **2** downstream claims

## Proposed quarantine

- **accepted.denominator_decision** — REQUIRED_DEPENDENCY_LOST; `abstract.sample.mdd → DERIVED_FROM → accepted.abstract_interpretation → DEPENDS_ON → accepted.denominator_decision`
- **claim:sha256:09d18d57737be4c580e31a79b83e1a73b9077d7fa0865cfa3b9db2bc38b714ed** — SOURCE_BASIS_LOST; `direct source anchor`
- **claim:sha256:390e35fdc0f5c97b77482baead810e923646b1203b95c79c79c39f8d42691105** — SOURCE_BASIS_LOST; `direct source anchor`
- **claim:sha256:4cea459edc9cee087549869e11c814b972b34016d24ec2b5a3ec9676221282d0** — SOURCE_BASIS_LOST; `direct source anchor`
- **accepted.abstract_interpretation** — REQUIRED_DEPENDENCY_LOST; `abstract.sample.mdd → DERIVED_FROM → accepted.abstract_interpretation`
- **claim:sha256:8d5bea6d66ca1437b31effa2ad31ce11bd1f9478250f0d3ac626564e9c62b43c** — SOURCE_BASIS_LOST; `direct source anchor`
- **abstract.sample.mdd** — SOURCE_BASIS_LOST; `direct source anchor`

## Preserved and unresolved

- **accepted.approximate_sample** survives; retained support: `main.sample.mdd`
- **accepted.summary_review** requires review; an advisory dependency is involved.

## Boundary

Given this exact accepted graph, source-status event, and receiver-owned edge policy, these are the mechanically implied exposures. The report does not certify the semantic truth or completeness of any claim, edge, event scope, or source. It proposes review; it does not mutate the accepted graph.

Event: `source-status-event:sha256:d49971d40209a6539622106430e9bdf47b5f2af59a8b868a0b0671fc1be3f8fc`
Report: `claim-impact-report:sha256:67fc15a96446717ee1c46233672b91538849f5612d441321cac9dd8d1e6d8319`

The article passages and correction notice are real natural material. The downstream review and decision dependencies are an authored specimen, not a claim about what any historical institution actually relied on.
