from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


CommitmentType = Literal[
    "task",
    "habit",
    "promise",
    "money",
    "health",
    "relationship",
    "work",
    "immigration",
    "deadline",
    "other",
]

CommitmentStatus = Literal[
    "open",
    "in_progress",
    "completed",
    "missed",
    "canceled",
    "archived",
]


class CommitmentCreateRequest(BaseModel):
    commitment_type: CommitmentType
    title: str = Field(min_length=1)
    commitment_text: str = Field(min_length=1)
    plan_id: Optional[str] = None
    milestone_id: Optional[str] = None
    entity_id: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    priority: int = Field(default=3, ge=1, le=5)
    status: CommitmentStatus = "open"
    active: bool = True
    due_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommitmentUpdateRequest(BaseModel):
    commitment_type: Optional[CommitmentType] = None
    title: Optional[str] = Field(default=None, min_length=1)
    commitment_text: Optional[str] = Field(default=None, min_length=1)
    plan_id: Optional[str] = None
    milestone_id: Optional[str] = None
    entity_id: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    status: Optional[CommitmentStatus] = None
    active: Optional[bool] = None
    due_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class CommitmentResponse(BaseModel):
    id: str
    commitment_type: CommitmentType
    title: str
    commitment_text: str
    plan_id: Optional[str] = None
    milestone_id: Optional[str] = None
    entity_id: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    priority: int
    status: CommitmentStatus
    active: bool
    due_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
