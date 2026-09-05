"""Receiver-owned prospective verification contracts.

This module stays separate from Decision Recall. It records a verification
obligation prospectively, validates later external observations, requires a
separate receiver admission artifact, and emits LOSS_OF_STANDING only when
fresh admitted evidence falsifies the frozen predicate.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Mapping
from .canonical import content_id

VERIFICATION_CONTRACT_SCHEMA="openline.verification-contract.v1"
VERIFICATION_RESULT_SCHEMA="openline.verification-result.v1"
VERIFICATION_ADMISSION_SCHEMA="openline.verification-admission.v1"
VERIFICATION_EVALUATION_SCHEMA="openline.verification-evaluation.v1"
SUPPORTED_PREDICATES=("STATE_EQUALS",)
SUPPORTED_MATERIALITIES=("REQUIRED_FOR_CONTINUED_STANDING",)

class VerificationContractError(ValueError):
    """Raised when a verification-contract artifact fails closed."""

def _token(value: Any)->str:
    return " ".join(str(value or "").strip().split())

def _parse_time(value: Any)->datetime:
    text=str(value or "").strip()
    if not text: raise VerificationContractError("timestamp missing")
    if text.endswith("Z"): text=text[:-1]+"+00:00"
    try: parsed=datetime.fromisoformat(text)
    except ValueError as exc: raise VerificationContractError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None: raise VerificationContractError(f"timestamp must include timezone: {value}")
    return parsed.astimezone(timezone.utc)

def _time(value: Any)->str:
    return _parse_time(value).isoformat(timespec="seconds").replace("+00:00","Z")

def _sha256(value: Any)->str:
    text=str(value or "").lower().strip()
    if len(text)!=64 or any(c not in "0123456789abcdef" for c in text):
        raise VerificationContractError("evidence_sha256 must be 64 lowercase hex characters")
    return text

def create_verification_contract(*,dependency_id:str,subject_id:str,required_value:str,recognized_verifier_id:str,freshness_seconds:int,predicate:str="STATE_EQUALS",materiality:str="REQUIRED_FOR_CONTINUED_STANDING",metadata:Mapping[str,Any]|None=None)->dict[str,Any]:
    dependency=_token(dependency_id); subject=_token(subject_id); required=_token(required_value); verifier=_token(recognized_verifier_id)
    predicate=_token(predicate).upper(); materiality=_token(materiality).upper(); freshness=int(freshness_seconds)
    if not dependency: raise VerificationContractError("dependency_id missing")
    if not subject: raise VerificationContractError("subject_id missing")
    if not required: raise VerificationContractError("required_value missing")
    if not verifier: raise VerificationContractError("recognized_verifier_id missing")
    if predicate not in SUPPORTED_PREDICATES: raise VerificationContractError(f"unsupported predicate: {predicate}")
    if materiality not in SUPPORTED_MATERIALITIES: raise VerificationContractError(f"unsupported materiality: {materiality}")
    if freshness<=0: raise VerificationContractError("freshness_seconds must be positive")
    body={"schema":VERIFICATION_CONTRACT_SCHEMA,"dependency_id":dependency,"subject_id":subject,"predicate":predicate,"required_value":required,"recognized_verifier_id":verifier,"freshness_seconds":freshness,"receiver_admission_required":True,"materiality":materiality,"metadata":dict(sorted((metadata or {}).items()))}
    return {"contract_id":content_id("verification-contract",body),**body}

def validate_verification_contract(contract:Mapping[str,Any])->dict[str,Any]:
    errors=[]
    try:
        rebuilt=create_verification_contract(dependency_id=contract["dependency_id"],subject_id=contract["subject_id"],required_value=contract["required_value"],recognized_verifier_id=contract["recognized_verifier_id"],freshness_seconds=contract["freshness_seconds"],predicate=contract.get("predicate",""),materiality=contract.get("materiality",""),metadata=contract.get("metadata",{}))
        if dict(contract)!=rebuilt: errors.append("contract payload or contract_id mismatch")
    except (KeyError,TypeError,ValueError,VerificationContractError) as exc: errors.append(str(exc))
    return {"valid":not errors,"errors":errors}

def decision_recall_binding(contract:Mapping[str,Any])->dict[str,Any]:
    check=validate_verification_contract(contract)
    if not check["valid"]: raise VerificationContractError(f"invalid verification contract: {check['errors']}")
    dep=str(contract["dependency_id"]); short=str(contract["contract_id"]).rsplit(":",1)[-1][:16]
    return {"basis":{"basis_id":dep,"kind":"VERIFICATION_CONTRACT","statement":f"{contract['subject_id']} must satisfy {contract['predicate']} {contract['required_value']} under fresh receiver-admitted verification","locator":str(contract["subject_id"]),"evidence_sha256":"","role":"REQUIRED","alternative_group":""},"required_dependency":dep,"invalidation_condition":{"condition_id":f"verification-contract-failed:{short}","dependency_id":dep,"event_types":["LOSS_OF_STANDING"],"note":"fresh receiver-admitted verification falsified the prospective predicate"}}

def create_verification_result(*,contract:Mapping[str,Any],verifier_id:str,observed_value:str,observed_at:str,evidence_sha256:str,locator:str="")->dict[str,Any]:
    if not validate_verification_contract(contract)["valid"]: raise VerificationContractError("invalid verification contract")
    verifier=_token(verifier_id); observed=_token(observed_value)
    if not verifier: raise VerificationContractError("verifier_id missing")
    if not observed: raise VerificationContractError("observed_value missing")
    body={"schema":VERIFICATION_RESULT_SCHEMA,"contract_id":contract["contract_id"],"dependency_id":contract["dependency_id"],"subject_id":contract["subject_id"],"verifier_id":verifier,"observed_value":observed,"observed_at":_time(observed_at),"locator":_token(locator),"evidence_sha256":_sha256(evidence_sha256)}
    return {"verification_result_id":content_id("verification-result",body),**body}

def validate_verification_result(result:Mapping[str,Any],contract:Mapping[str,Any])->dict[str,Any]:
    errors=[]
    if not validate_verification_contract(contract)["valid"]: return {"valid":False,"errors":["invalid verification contract"]}
    try:
        rebuilt=create_verification_result(contract=contract,verifier_id=result["verifier_id"],observed_value=result["observed_value"],observed_at=result["observed_at"],evidence_sha256=result["evidence_sha256"],locator=result.get("locator",""))
        if dict(result)!=rebuilt: errors.append("verification result payload, binding, or result_id mismatch")
    except (KeyError,TypeError,ValueError,VerificationContractError) as exc: errors.append(str(exc))
    return {"valid":not errors,"errors":errors}

def create_receiver_admission(*,contract:Mapping[str,Any],result:Mapping[str,Any],receiver_id:str,admitted_at:str)->dict[str,Any]:
    check=validate_verification_result(result,contract)
    if not check["valid"]: raise VerificationContractError(f"invalid verification result: {check['errors']}")
    if result["verifier_id"]!=contract["recognized_verifier_id"]: raise VerificationContractError("receiver cannot admit a result from an unrecognized verifier")
    receiver=_token(receiver_id)
    if not receiver: raise VerificationContractError("receiver_id missing")
    admitted=_time(admitted_at)
    if _parse_time(admitted)<_parse_time(result["observed_at"]): raise VerificationContractError("receiver admission cannot predate observation")
    body={"schema":VERIFICATION_ADMISSION_SCHEMA,"contract_id":contract["contract_id"],"verification_result_id":result["verification_result_id"],"receiver_id":receiver,"admitted_at":admitted}
    return {"admission_id":content_id("verification-admission",body),**body}

def validate_receiver_admission(admission:Mapping[str,Any],*,contract:Mapping[str,Any],result:Mapping[str,Any])->dict[str,Any]:
    errors=[]
    try:
        if not validate_verification_result(result,contract)["valid"]: raise VerificationContractError("invalid verification result")
        body={"schema":VERIFICATION_ADMISSION_SCHEMA,"contract_id":contract["contract_id"],"verification_result_id":result["verification_result_id"],"receiver_id":_token(admission["receiver_id"]),"admitted_at":_time(admission["admitted_at"])}
        if not body["receiver_id"]: raise VerificationContractError("receiver_id missing")
        rebuilt={"admission_id":content_id("verification-admission",body),**body}
        if dict(admission)!=rebuilt: errors.append("admission payload, binding, or admission_id mismatch")
        if _parse_time(body["admitted_at"])<_parse_time(result["observed_at"]): errors.append("receiver admission predates observation")
    except (KeyError,TypeError,ValueError,VerificationContractError) as exc: errors.append(str(exc))
    return {"valid":not errors,"errors":errors}

def _evaluation(*,contract,evaluation_at,disposition,reason,result,admission,event):
    body={"schema":VERIFICATION_EVALUATION_SCHEMA,"contract_id":contract.get("contract_id",""),"evaluation_at":_time(evaluation_at),"disposition":disposition,"reason":reason,"verification_result_id":result.get("verification_result_id","") if isinstance(result,Mapping) else "","admission_id":admission.get("admission_id","") if isinstance(admission,Mapping) else "","event":dict(event) if event else None}
    return {"evaluation_id":content_id("verification-evaluation",body),**body}

def evaluate_verification_contract(*,contract:Mapping[str,Any],accepted_at:str,evaluation_at:str,result:Mapping[str,Any]|None=None,admission:Mapping[str,Any]|None=None)->dict[str,Any]:
    check=validate_verification_contract(contract)
    if not check["valid"]: raise VerificationContractError(f"invalid verification contract: {check['errors']}")
    accepted=_parse_time(accepted_at); evaluation=_parse_time(evaluation_at)
    if evaluation<accepted: return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="ESCALATE",reason="evaluation boundary predates decision acceptance",result=result,admission=admission,event=None)
    freshness=int(contract["freshness_seconds"])
    if result is None:
        if admission is not None: return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="ESCALATE",reason="receiver admission supplied without a verification result",result=None,admission=admission,event=None)
        age=int((evaluation-accepted).total_seconds())
        return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="SURVIVE" if age<=freshness else "ESCALATE",reason="verification budget remains open; no polling result is required yet" if age<=freshness else "verification freshness budget expired without admissible evidence",result=None,admission=None,event=None)
    rcheck=validate_verification_result(result,contract)
    if not rcheck["valid"]: return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="ESCALATE",reason=f"verification result failed validation: {rcheck['errors']}",result=result,admission=admission,event=None)
    if result["verifier_id"]!=contract["recognized_verifier_id"]: return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="ESCALATE",reason="verification result came from an unrecognized verifier",result=result,admission=admission,event=None)
    if admission is None: return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="ESCALATE",reason="verification result has not been separately admitted by the receiver",result=result,admission=None,event=None)
    acheck=validate_receiver_admission(admission,contract=contract,result=result)
    if not acheck["valid"]: return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="ESCALATE",reason=f"receiver admission failed validation: {acheck['errors']}",result=result,admission=admission,event=None)
    observed=_parse_time(result["observed_at"]); admitted=_parse_time(admission["admitted_at"])
    if observed<accepted: return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="ESCALATE",reason="verification observation predates the prospective contract acceptance boundary",result=result,admission=admission,event=None)
    if observed>evaluation: return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="ESCALATE",reason="verification observation postdates the evaluation boundary",result=result,admission=admission,event=None)
    if admitted>evaluation: return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="ESCALATE",reason="receiver admission postdates the evaluation boundary",result=result,admission=admission,event=None)
    if int((evaluation-observed).total_seconds())>freshness: return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="ESCALATE",reason="verification result is stale at the evaluation boundary",result=result,admission=admission,event=None)
    if result["observed_value"]==contract["required_value"]: return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="SURVIVE",reason="fresh receiver-admitted verification satisfies the prospective predicate",result=result,admission=admission,event=None)
    event={"basis_id":contract["dependency_id"],"event_type":"LOSS_OF_STANDING"}
    return _evaluation(contract=contract,evaluation_at=evaluation_at,disposition="EVENT",reason="fresh receiver-admitted verification falsifies the prospective predicate",result=result,admission=admission,event=event)
