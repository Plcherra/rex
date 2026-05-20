from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


EntityType = Literal[
    "person",
    "place",
    "organization",
    "job",
    "project",
    "object",
    "topic",
    "other",
]

EntityStatus = Literal["active", "inactive", "archived"]

EntityEventType = Literal[
    "note",
    "interaction",
    "relationship_update",
    "preference",
    "commitment",
    "conflict",
    "milestone",
    "other",
]

ENTITY_NORMALIZATION_METADATA_KEYS = {
    "canonical_entity_id",
    "alias_source",
    "obsolete_aliases",
    "obsolete_names",
    "removed_wrong_aliases",
    "correction_confidence",
}


class EntityCreateRequest(BaseModel):
    entity_type: EntityType
    display_name: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    relationship: Optional[str] = None
    summary: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    importance: int = Field(default=3, ge=1, le=5)
    status: EntityStatus = "active"
    active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityUpdateRequest(BaseModel):
    entity_type: Optional[EntityType] = None
    display_name: Optional[str] = Field(default=None, min_length=1)
    normalized_name: Optional[str] = Field(default=None, min_length=1)
    aliases: Optional[list[str]] = None
    relationship: Optional[str] = None
    summary: Optional[str] = None
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    status: Optional[EntityStatus] = None
    active: Optional[bool] = None
    metadata: Optional[dict[str, Any]] = None


class EntityResponse(BaseModel):
    id: str
    entity_type: EntityType
    display_name: str
    normalized_name: str
    aliases: list[str] = Field(default_factory=list)
    relationship: Optional[str] = None
    summary: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    importance: int
    status: EntityStatus
    active: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EntityEventCreateRequest(BaseModel):
    entity_id: str
    event_type: EntityEventType = "note"
    title: Optional[str] = None
    content: str = Field(min_length=1)
    occurred_at: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    importance: int = Field(default=3, ge=1, le=5)
    active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityEventUpdateRequest(BaseModel):
    event_type: Optional[EntityEventType] = None
    title: Optional[str] = None
    content: Optional[str] = Field(default=None, min_length=1)
    occurred_at: Optional[str] = None
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    active: Optional[bool] = None
    metadata: Optional[dict[str, Any]] = None


class EntityEventResponse(BaseModel):
    id: str
    entity_id: str
    event_type: EntityEventType
    title: Optional[str] = None
    content: str
    occurred_at: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None
    importance: int
    active: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
