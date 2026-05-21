from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


AccountabilitySignalType = Literal[
    "rule_violation",
    "missed_commitment",
    "plan_drift",
    "repeated_pattern",
    "upcoming_deadline",
    "budget_risk",
    "positive_follow_through",
]

AccountabilitySeverity = Literal["info", "low", "medium", "high", "critical"]

AccountabilityStatus = Literal["active", "dismissed", "resolved", "archived"]

AccountabilitySourceType = Literal[
    "personal_rule",
    "commitment",
    "plan",
    "plan_milestone",
    "entity",
    "entity_event",
    "long_term_memory",
    "message",
    "conversation",
    "system",
]


class AccountabilitySourceRef(BaseModel):
    source_type: AccountabilitySourceType
    source_id: Optional[str] = None
    title: Optional[str] = None
    excerpt: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AccountabilitySignal(BaseModel):
    signal_type: AccountabilitySignalType
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    severity: AccountabilitySeverity = "medium"
    confidence: float = Field(default=0.7, ge=0, le=1)
    status: AccountabilityStatus = "active"
    source_refs: list[AccountabilitySourceRef] = Field(default_factory=list)
    suggested_prompt: Optional[str] = None
    recommended_action: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class AccountabilitySignalResponse(AccountabilitySignal):
    id: Optional[str] = None


class AccountabilityContext(BaseModel):
    signals: list[AccountabilitySignal] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AccountabilityOverviewResponse(BaseModel):
    signals: list[AccountabilitySignalResponse] = Field(default_factory=list)
    rule_risks: list[AccountabilitySignalResponse] = Field(default_factory=list)
    plan_risks: list[AccountabilitySignalResponse] = Field(default_factory=list)
    recent_patterns: list[AccountabilitySignalResponse] = Field(default_factory=list)
    active_rules: list[dict[str, Any]] = Field(default_factory=list)
    open_commitments: list[dict[str, Any]] = Field(default_factory=list)
    active_plans: list[dict[str, Any]] = Field(default_factory=list)
    open_milestones: list[dict[str, Any]] = Field(default_factory=list)
    completed_milestones: list[dict[str, Any]] = Field(default_factory=list)
    plan_hierarchy: list[dict[str, Any]] = Field(default_factory=list)
    pending_memory_candidates: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_warnings: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
