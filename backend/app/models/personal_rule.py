from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


RuleType = Literal[
    "finance",
    "transport",
    "food_delivery",
    "coffee",
    "rent",
    "health",
    "dating",
    "work",
    "immigration",
    "personal",
    "other",
]

RuleStatus = Literal["active", "paused", "broken", "archived"]

RuleEnforcementStyle = Literal["gentle_direct", "strict", "reminder_only"]


class PersonalRuleCreateRequest(BaseModel):
    rule_type: RuleType
    title: str = Field(min_length=1)
    rule_text: str = Field(min_length=1)
    trigger_keywords: list[str] = Field(default_factory=list)
    enforcement_style: RuleEnforcementStyle = "gentle_direct"
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    priority: int = Field(default=3, ge=1, le=5)
    status: RuleStatus = "active"
    active: bool = True
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PersonalRuleUpdateRequest(BaseModel):
    rule_type: Optional[RuleType] = None
    title: Optional[str] = Field(default=None, min_length=1)
    rule_text: Optional[str] = Field(default=None, min_length=1)
    trigger_keywords: Optional[list[str]] = None
    enforcement_style: Optional[RuleEnforcementStyle] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    status: Optional[RuleStatus] = None
    active: Optional[bool] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class PersonalRuleResponse(BaseModel):
    id: str
    rule_type: RuleType
    title: str
    rule_text: str
    trigger_keywords: list[str] = Field(default_factory=list)
    enforcement_style: RuleEnforcementStyle
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    priority: int
    status: RuleStatus
    active: bool
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
