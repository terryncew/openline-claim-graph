"""Receiver-owned admission gate for real-world entity bindings."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, json
from typing import Any, Iterable
SCHEMA = "openline.identity-binding-gate.v1"
def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()
@dataclass(frozen=True)
class BindingEvidence:
    attribute: str
    target_value: str
    candidate_value: str
    source_id: str
    provenance_status: str = "VERIFIED"
    authoritative: bool = False
    @property
    def matches(self) -> bool:
        return self.target_value.strip().casefold() == self.candidate_value.strip().casefold()
@dataclass(frozen=True)
class BindingPolicy:
    policy_id: str
    min_independent_matches: int = 2
    required_attributes: tuple[str, ...] = ()
    hard_conflict_attributes: tuple[str, ...] = ()
    authoritative_attributes: tuple[str, ...] = ()
    require_verified_provenance: bool = True
    same_name_only_never_sufficient: bool = True
    def __post_init__(self) -> None:
        if self.min_independent_matches < 1:
            raise ValueError("min_independent_matches must be >= 1")
@dataclass(frozen=True)
class BindingProposal:
    proposal_id: str
    target_entity: str
    candidate_entity: str
    evidence: tuple[BindingEvidence, ...]
class IdentityBindingGate:
    """Deterministic receiver gate. It never calls a model or external resolver."""
    def __init__(self, policy: BindingPolicy): self.policy = policy
    def evaluate(self, proposal: BindingProposal) -> dict[str, Any]:
        if not proposal.evidence:
            return self._decision(proposal, "QUARANTINE", "UNRESOLVED_IDENTITY", [], [])
        bad = [e for e in proposal.evidence if e.provenance_status != "VERIFIED"]
        if self.policy.require_verified_provenance and bad:
            return self._decision(proposal, "QUARANTINE", "PROVENANCE_NOT_VERIFIED", [], [f"{e.attribute}:{e.source_id}" for e in bad])
        hard = [e for e in proposal.evidence if e.attribute in self.policy.hard_conflict_attributes and not e.matches]
        if hard:
            return self._decision(proposal, "DENY", "IDENTITY_CONFLICT", [], [f"{e.attribute}:{e.source_id}" for e in hard])
        matches = [e for e in proposal.evidence if e.matches]
        attrs = {e.attribute for e in matches}
        sources = {e.source_id for e in matches}
        if any(e.authoritative and e.attribute in self.policy.authoritative_attributes for e in matches):
            return self._decision(proposal, "COMMIT", "AUTHORITATIVE_BINDING_EARNED", matches, [])
        if self.policy.same_name_only_never_sufficient and attrs and attrs <= {"name", "full_name"}:
            return self._decision(proposal, "QUARANTINE", "UNRESOLVED_IDENTITY", matches, [])
        if set(self.policy.required_attributes).issubset(attrs) and len(sources) >= self.policy.min_independent_matches:
            return self._decision(proposal, "COMMIT", "CORROBORATED_BINDING_EARNED", matches, [])
        return self._decision(proposal, "QUARANTINE", "UNRESOLVED_IDENTITY", matches, [])
    def _decision(self, proposal: BindingProposal, disposition: str, reason: str, matches: Iterable[BindingEvidence], conflicts: list[str]) -> dict[str, Any]:
        proposal_doc = {"proposal_id": proposal.proposal_id, "target_entity": proposal.target_entity, "candidate_entity": proposal.candidate_entity, "evidence": [asdict(e) for e in proposal.evidence]}
        body = {"schema": SCHEMA, "policy_id": self.policy.policy_id, "policy_sha256": _hash(asdict(self.policy)), "proposal_sha256": _hash(proposal_doc), "proposal_id": proposal.proposal_id, "target_entity": proposal.target_entity, "candidate_entity": proposal.candidate_entity, "disposition": disposition, "reason": reason, "matched_attributes": sorted({e.attribute for e in matches}), "matched_source_ids": sorted({e.source_id for e in matches}), "conflicts": sorted(conflicts), "semantic_truth_attested": False}
        body["receipt_sha256"] = _hash(body)
        return body
def evidence_from_dict(item: dict[str, Any]) -> BindingEvidence:
    allowed = {"attribute", "target_value", "candidate_value", "source_id", "provenance_status", "authoritative"}
    extra = set(item) - allowed
    if extra: raise ValueError("unknown_evidence_fields:" + ",".join(sorted(extra)))
    return BindingEvidence(**item)
def proposal_from_dict(doc: dict[str, Any]) -> BindingProposal:
    allowed = {"proposal_id", "target_entity", "candidate_entity", "evidence"}
    extra = set(doc) - allowed
    if extra: raise ValueError("unknown_proposal_fields:" + ",".join(sorted(extra)))
    return BindingProposal(str(doc["proposal_id"]), str(doc["target_entity"]), str(doc["candidate_entity"]), tuple(evidence_from_dict(x) for x in doc.get("evidence", [])))
