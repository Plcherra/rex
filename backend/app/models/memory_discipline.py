from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MemoryCandidateKind(str, Enum):
    LONG_TERM_MEMORY = "long_term_memory"
    ENTITY = "entity"
    ENTITY_EVENT = "entity_event"
    PERSONAL_RULE = "personal_rule"
    PLAN = "plan"
    PLAN_MILESTONE = "plan_milestone"
    COMMITMENT = "commitment"


class MemoryDisciplineAction(str, Enum):
    CREATE_ENTITY = "create_entity"
    UPDATE_ENTITY = "update_entity"
    ARCHIVE_ENTITY = "archive_entity"
    CREATE_ENTITY_EVENT = "create_entity_event"
    CREATE_PLAN = "create_plan"
    UPDATE_PLAN = "update_plan"
    ARCHIVE_PLAN = "archive_plan"
    CREATE_MILESTONE = "create_milestone"
    UPDATE_MILESTONE = "update_milestone"
    CREATE_COMMITMENT = "create_commitment"
    UPDATE_COMMITMENT = "update_commitment"
    CREATE_RULE = "create_rule"
    UPDATE_RULE = "update_rule"
    ARCHIVE_RULE = "archive_rule"
    ASK_CONFIRMATION = "ask_confirmation"
    IGNORE_NOISY_CANDIDATE = "ignore_noisy_candidate"


class MemoryDisciplineCandidate(BaseModel):
    kind: MemoryCandidateKind
    payload: dict[str, Any] = Field(default_factory=dict)
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    source_memory_id: Optional[str] = None


class MemoryRelatedRecord(BaseModel):
    table: str
    id: str
    score: float = Field(ge=0, le=1)
    title: Optional[str] = None
    reason: str
    record: dict[str, Any] = Field(default_factory=dict)


class MemoryDisciplineContext(BaseModel):
    candidate: MemoryDisciplineCandidate
    active_entities: list[dict[str, Any]] = Field(default_factory=list)
    active_plans: list[dict[str, Any]] = Field(default_factory=list)
    active_milestones: list[dict[str, Any]] = Field(default_factory=list)
    active_commitments: list[dict[str, Any]] = Field(default_factory=list)
    active_rules: list[dict[str, Any]] = Field(default_factory=list)
    active_long_term_memories: list[dict[str, Any]] = Field(default_factory=list)
    related_entities: list[MemoryRelatedRecord] = Field(default_factory=list)
    related_plans: list[MemoryRelatedRecord] = Field(default_factory=list)
    related_milestones: list[MemoryRelatedRecord] = Field(default_factory=list)
    related_commitments: list[MemoryRelatedRecord] = Field(default_factory=list)
    related_rules: list[MemoryRelatedRecord] = Field(default_factory=list)
    related_long_term_memories: list[MemoryRelatedRecord] = Field(default_factory=list)


class MemoryDisciplineDecision(BaseModel):
    action: MemoryDisciplineAction
    candidate_kind: MemoryCandidateKind
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str
    confidence: float = Field(default=0.75, ge=0, le=1)
    target_table: Optional[str] = None
    target_id: Optional[str] = None
    requires_confirmation: bool = False
    related_records: list[MemoryRelatedRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
