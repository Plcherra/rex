from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


MemoryCandidateType = Literal[
    "long_term_memory",
    "entity",
    "entity_event",
    "personal_rule",
    "plan",
    "plan_milestone",
    "commitment",
    "correction",
    "archive",
    "merge",
]

MemoryCandidateStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "applied",
    "failed",
]

MemoryCandidateRiskLevel = Literal["low", "medium", "high"]


class MemoryCandidateCreateRequest(BaseModel):
    candidate_type: MemoryCandidateType
    payload: dict[str, Any] = Field(default_factory=dict)
    risk_level: MemoryCandidateRiskLevel = "medium"
    reason: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None


class MemoryCandidateUpdateRequest(BaseModel):
    payload: Optional[dict[str, Any]] = None
    risk_level: Optional[MemoryCandidateRiskLevel] = None
    reason: Optional[str] = None
    decision: Optional[dict[str, Any]] = None
    verification: Optional[dict[str, Any]] = None


class MemoryCandidateApproveRequest(BaseModel):
    approved_by: Optional[str] = "user"
    reason: Optional[str] = None
    decision: dict[str, Any] = Field(default_factory=dict)


class MemoryCandidateRejectRequest(BaseModel):
    reason: Optional[str] = None
    decision: dict[str, Any] = Field(default_factory=dict)


class MemoryCandidateBulkDecisionRequest(BaseModel):
    source_conversation_id: Optional[str] = None
    candidate_ids: list[str] = Field(default_factory=list)
    include_high_risk: bool = False
    reason: Optional[str] = None
    decided_by: Optional[str] = "user"


class MemoryCandidateResponse(BaseModel):
    id: str
    candidate_type: MemoryCandidateType
    payload: dict[str, Any] = Field(default_factory=dict)
    status: MemoryCandidateStatus
    risk_level: MemoryCandidateRiskLevel
    decision: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    applied_at: Optional[str] = None
    rejected_at: Optional[str] = None
    applied_record_table: Optional[str] = None
    applied_record_id: Optional[str] = None
    verification: Optional[dict[str, Any]] = None
    preview: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryCandidateBulkDecisionResponse(BaseModel):
    approved: list[MemoryCandidateResponse] = Field(default_factory=list)
    rejected: list[MemoryCandidateResponse] = Field(default_factory=list)
    skipped: list[MemoryCandidateResponse] = Field(default_factory=list)
