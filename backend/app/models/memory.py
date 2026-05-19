from typing import Literal, Optional

from pydantic import BaseModel, Field


MemoryType = Literal["fact", "preference", "event"]
MemoryCorrectionType = Literal[
    "entity_name",
    "entity_relationship",
    "plan_detail",
    "rule_detail",
    "commitment_detail",
    "location",
    "preference",
    "other",
]


class MemoryResponse(BaseModel):
    id: str
    memory_type: MemoryType
    content: str
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    importance: int
    active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_accessed_at: Optional[str] = None
    relevance_score: Optional[float] = None
    relevance_reason: Optional[str] = None


class MemoryUpdateRequest(BaseModel):
    memory_type: Optional[MemoryType] = None
    content: Optional[str] = Field(default=None, min_length=1)
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    active: Optional[bool] = None


class MemoryCorrectionResponse(BaseModel):
    id: str
    correction_type: MemoryCorrectionType
    old_value: Optional[str] = None
    new_value: str
    target_table: Optional[str] = None
    target_id: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    applied: bool
    confidence: float
    metadata: dict = Field(default_factory=dict)
    created_at: Optional[str] = None
