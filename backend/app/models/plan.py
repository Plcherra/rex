from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


PlanType = Literal[
    "finance",
    "immigration",
    "career",
    "health",
    "dating",
    "housing",
    "creative",
    "personal",
    "other",
]

PlanStatus = Literal["active", "paused", "completed", "abandoned", "archived"]

MilestoneStatus = Literal["open", "in_progress", "completed", "missed", "canceled"]

MilestoneType = Literal["goal", "deadline", "checkpoint", "task", "other"]


class PlanCreateRequest(BaseModel):
    plan_type: PlanType
    title: str = Field(min_length=1)
    description: Optional[str] = None
    desired_outcome: Optional[str] = None
    primary_entity_id: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    priority: int = Field(default=3, ge=1, le=5)
    status: PlanStatus = "active"
    active: bool = True
    start_date: Optional[str] = None
    target_date: Optional[str] = None
    completed_at: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanUpdateRequest(BaseModel):
    plan_type: Optional[PlanType] = None
    title: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    desired_outcome: Optional[str] = None
    primary_entity_id: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    status: Optional[PlanStatus] = None
    active: Optional[bool] = None
    start_date: Optional[str] = None
    target_date: Optional[str] = None
    completed_at: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class PlanResponse(BaseModel):
    id: str
    plan_type: PlanType
    title: str
    description: Optional[str] = None
    desired_outcome: Optional[str] = None
    primary_entity_id: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    priority: int
    status: PlanStatus
    active: bool
    start_date: Optional[str] = None
    target_date: Optional[str] = None
    completed_at: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlanMilestoneCreateRequest(BaseModel):
    plan_id: str
    title: str = Field(min_length=1)
    description: Optional[str] = None
    milestone_type: MilestoneType = "checkpoint"
    target_date: Optional[str] = None
    completed_at: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    priority: int = Field(default=3, ge=1, le=5)
    status: MilestoneStatus = "open"
    active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanMilestoneUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    milestone_type: Optional[MilestoneType] = None
    target_date: Optional[str] = None
    completed_at: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    status: Optional[MilestoneStatus] = None
    active: Optional[bool] = None
    metadata: Optional[dict[str, Any]] = None


class PlanMilestoneResponse(BaseModel):
    id: str
    plan_id: str
    title: str
    description: Optional[str] = None
    milestone_type: MilestoneType = "checkpoint"
    target_date: Optional[str] = None
    completed_at: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    priority: int
    status: MilestoneStatus
    active: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
