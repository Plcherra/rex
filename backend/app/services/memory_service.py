import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote, urlencode

import httpx

from app.config import Settings, get_settings
from app.services.http_client import request_with_retries

VALID_MEMORY_TYPES = {"fact", "preference", "event"}
VALID_MEMORY_CORRECTION_TYPES = {
    "entity_name",
    "entity_relationship",
    "plan_detail",
    "rule_detail",
    "commitment_detail",
    "location",
    "preference",
    "other",
}
LONG_TERM_MEMORY_SELECT = (
    "id,memory_type,content,source_conversation_id,source_message_id,"
    "importance,active,created_at,updated_at,last_accessed_at"
)
MEMORY_CORRECTION_SELECT = (
    "id,correction_type,old_value,new_value,target_table,target_id,"
    "source_conversation_id,source_message_id,applied,confidence,metadata,created_at"
)
ENTITIES_TABLE = "entities"
ENTITY_EVENTS_TABLE = "entity_events"
PERSONAL_RULES_TABLE = "personal_rules"
PLANS_TABLE = "plans"
PLAN_MILESTONES_TABLE = "plan_milestones"
COMMITMENTS_TABLE = "commitments"
ENTITY_SELECT = (
    "id,entity_type,display_name,normalized_name,aliases,relationship,summary,"
    "source_conversation_id,source_message_id,source_memory_id,importance,status,"
    "active,metadata,first_seen_at,last_seen_at,created_at,updated_at"
)
ENTITY_EVENT_SELECT = (
    "id,entity_id,event_type,title,content,occurred_at,source_conversation_id,"
    "source_message_id,source_memory_id,importance,active,metadata,created_at,"
    "updated_at"
)
PERSONAL_RULE_SELECT = (
    "id,rule_type,title,rule_text,trigger_keywords,enforcement_style,"
    "source_conversation_id,source_message_id,source_memory_id,priority,status,"
    "active,starts_at,ends_at,last_checked_at,metadata,created_at,updated_at"
)
PLAN_SELECT = (
    "id,plan_type,title,description,desired_outcome,primary_entity_id,source_conversation_id,"
    "source_message_id,source_memory_id,priority,status,active,start_date,"
    "target_date,completed_at,last_reviewed_at,metadata,created_at,updated_at"
)
PLAN_MILESTONE_SELECT = (
    "id,plan_id,title,description,milestone_type,target_date,completed_at,"
    "source_conversation_id,source_message_id,source_memory_id,priority,status,"
    "active,metadata,created_at,updated_at"
)
COMMITMENT_SELECT = (
    "id,commitment_type,title,commitment_text,plan_id,entity_id,"
    "source_conversation_id,source_message_id,source_memory_id,priority,status,"
    "active,due_at,completed_at,last_checked_at,metadata,created_at,updated_at"
)
RELEVANT_MEMORY_SCAN_LIMIT = 100
RELEVANT_MEMORY_MINIMUM_SCORE = 0.12
STRUCTURED_MEMORY_SCAN_LIMIT = 50
STRUCTURED_MEMORY_DIRECT_LIMIT = 5
STRUCTURED_MEMORY_RELATED_LIMIT = 8
STRUCTURED_MEMORY_MINIMUM_SCORE = 0.14
HIGH_PRIORITY_STRUCTURED_THRESHOLD = 4
STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "because",
    "but",
    "can",
    "could",
    "for",
    "from",
    "have",
    "how",
    "into",
    "just",
    "like",
    "more",
    "need",
    "not",
    "now",
    "should",
    "that",
    "the",
    "this",
    "what",
    "when",
    "where",
    "with",
    "would",
    "you",
    "your",
}
CONCEPT_GROUPS = {
    "work": {"career", "job", "manager", "office", "salary", "work", "workplace"},
    "money": {"bill", "budget", "debt", "finance", "money", "rent", "savings"},
    "location": {
        "address",
        "area",
        "city",
        "eastern",
        "edt",
        "est",
        "home",
        "house",
        "live",
        "lives",
        "living",
        "location",
        "massachusetts",
        "place",
        "state",
        "timezone",
    },
    "relationship": {
        "date",
        "dating",
        "girl",
        "girlfriend",
        "monday",
        "name",
        "offday",
        "person",
        "restaurant",
        "relationship",
        "wife",
    },
    "time": {
        "clock",
        "date",
        "day",
        "eastern",
        "edt",
        "est",
        "morning",
        "night",
        "schedule",
        "time",
        "timezone",
        "today",
        "tomorrow",
        "tonight",
        "week",
    },
    "immigration": {"ead", "green", "immigration", "status", "uscis", "visa"},
    "stress": {
        "anxiety",
        "burnout",
        "frustrated",
        "pressure",
        "stress",
        "stressed",
    },
}


class MemoryServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 503) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class SupabaseMemoryService:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def create_conversation(self) -> str:
        row = await self.create_conversation_record()
        conversation_id = row.get("id")
        if not conversation_id:
            raise MemoryServiceError("Supabase did not return a conversation id.")

        return str(conversation_id)

    async def create_conversation_record(self) -> dict:
        rows = await self._request(
            "POST",
            self.settings.supabase_conversations_table,
            body={},
            query={"select": "id,title,timestamp"},
            prefer="return=representation",
        )
        return self._conversation_with_preview(self._first_row(rows), None)

    async def list_conversations(self, limit: int = 50) -> list[dict]:
        rows = await self._request(
            "GET",
            self.settings.supabase_conversations_table,
            query={
                "select": "id,title,timestamp",
                "order": "timestamp.desc",
                "limit": str(limit),
            },
        )

        conversations = []
        for row in rows:
            conversation_id = str(row.get("id", ""))
            recent_messages = await self.get_recent_messages(
                conversation_id,
                limit=1,
            )
            last_message = recent_messages[-1] if recent_messages else None
            conversations.append(self._conversation_with_preview(row, last_message))

        return conversations

    async def conversation_exists(self, conversation_id: str) -> bool:
        rows = await self._request(
            "GET",
            self.settings.supabase_conversations_table,
            query={
                "id": f"eq.{conversation_id}",
                "select": "id",
                "limit": "1",
            },
        )
        return bool(rows)

    async def save_message(self, conversation_id: str, role: str, content: str) -> dict:
        rows = await self._request(
            "POST",
            self.settings.supabase_messages_table,
            body={
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
            },
            query={"select": "id,conversation_id,role,content,timestamp"},
            prefer="return=representation",
        )
        return self._first_row(rows)

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> list[dict]:
        rows = await self._request(
            "GET",
            self.settings.supabase_messages_table,
            query={
                "conversation_id": f"eq.{conversation_id}",
                "select": "id,conversation_id,role,content,timestamp",
                "order": "timestamp.desc",
                "limit": str(limit),
            },
        )
        return list(reversed(rows))

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 100,
    ) -> Optional[list[dict]]:
        if not await self.conversation_exists(conversation_id):
            return None

        return await self.get_recent_messages(conversation_id, limit=limit)

    async def delete_conversation(self, conversation_id: str) -> bool:
        if not await self.conversation_exists(conversation_id):
            return False

        await self._request(
            "DELETE",
            self.settings.supabase_conversations_table,
            query={"id": f"eq.{conversation_id}"},
        )
        return True

    async def save_voice_turn(
        self,
        conversation_id: str,
        user_message_id: Optional[str] = None,
        assistant_message_id: Optional[str] = None,
        transcript_confidence: Optional[float] = None,
        audio_duration_seconds: Optional[float] = None,
        input_mime_type: Optional[str] = None,
        output_audio_encoding: Optional[str] = None,
        stt_vendor: str = "deepgram",
        tts_vendor: str = "google_tts",
        metadata: Optional[dict] = None,
    ) -> dict:
        rows = await self._request(
            "POST",
            self.settings.supabase_voice_turns_table,
            body={
                "conversation_id": conversation_id,
                "user_message_id": user_message_id,
                "assistant_message_id": assistant_message_id,
                "transcript_confidence": transcript_confidence,
                "audio_duration_seconds": audio_duration_seconds,
                "input_mime_type": input_mime_type,
                "output_audio_encoding": output_audio_encoding,
                "stt_vendor": stt_vendor,
                "tts_vendor": tts_vendor,
                "metadata": metadata or {},
            },
            query={
                "select": (
                    "id,conversation_id,user_message_id,assistant_message_id,"
                    "transcript_confidence,audio_duration_seconds,input_mime_type,"
                    "output_audio_encoding,stt_vendor,tts_vendor,metadata,created_at"
                )
            },
            prefer="return=representation",
        )
        return self._first_row(rows)

    async def save_long_term_memory(
        self,
        memory_type: str,
        content: str,
        source_conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        importance: int = 3,
    ) -> dict:
        rows = await self._request(
            "POST",
            self.settings.supabase_long_term_memory_table,
            body={
                "memory_type": memory_type,
                "content": content,
                "source_conversation_id": source_conversation_id,
                "source_message_id": source_message_id,
                "importance": importance,
            },
            query={
                "select": (
                    "id,memory_type,content,source_conversation_id,"
                    "source_message_id,importance,active,created_at,"
                    "updated_at,last_accessed_at"
                )
            },
            prefer="return=representation",
        )
        return self._first_row(rows)

    async def save_long_term_memory_from_message(
        self,
        conversation_id: str,
        message: dict,
    ) -> Optional[dict]:
        memory = self._memory_candidate(str(message.get("content", "")))
        if not memory:
            return None

        return await self.save_long_term_memory(
            memory_type=memory["memory_type"],
            content=memory["content"],
            source_conversation_id=conversation_id,
            source_message_id=str(message.get("id")) if message.get("id") else None,
            importance=memory["importance"],
        )

    async def get_long_term_memory(
        self,
        query: Optional[str] = None,
        limit: int = 8,
    ) -> list[dict]:
        if query is None:
            return await self.list_long_term_memory(limit=limit, active=True)

        return await self.get_relevant_memories(query=query, limit=limit)

    async def get_relevant_memories(self, query: str, limit: int = 8) -> list[dict]:
        memories = await self.list_long_term_memory(
            limit=max(RELEVANT_MEMORY_SCAN_LIMIT, limit),
            active=True,
        )
        query_terms = self._expanded_terms(query)
        scored_memories = []

        for memory in memories:
            scored_memory = self._score_memory(memory, query_terms)
            if scored_memory is not None:
                scored_memories.append(scored_memory)

        scored_memories.sort(
            key=lambda memory: (
                memory.get("relevance_score", 0),
                memory.get("importance", 0),
                str(
                    memory.get("last_accessed_at")
                    or memory.get("created_at")
                    or ""
                ),
            ),
            reverse=True,
        )
        scored_memories = self._filter_stale_corrected_memories(scored_memories)
        return scored_memories[:limit]

    async def get_structured_memory_context(self, query: str) -> dict:
        (
            entities,
            entity_events,
            personal_rules,
            plans,
            plan_milestones,
            commitments,
        ) = await asyncio.gather(
            self.list_entities(limit=STRUCTURED_MEMORY_SCAN_LIMIT, active=True),
            self.list_entity_events(limit=STRUCTURED_MEMORY_SCAN_LIMIT, active=True),
            self.list_personal_rules(limit=STRUCTURED_MEMORY_SCAN_LIMIT, active=True),
            self.list_plans(limit=STRUCTURED_MEMORY_SCAN_LIMIT, active=True),
            self.list_plan_milestones(limit=STRUCTURED_MEMORY_SCAN_LIMIT, active=True),
            self.list_commitments(limit=STRUCTURED_MEMORY_SCAN_LIMIT, active=True),
        )

        query_terms = self._expanded_terms(query)
        selected_entities = self._rank_structured_records(
            entities,
            query_terms=query_terms,
            text_fields=("display_name", "normalized_name", "relationship", "summary"),
            list_fields=("aliases",),
            weight_field="importance",
            status_values={"active"},
            limit=STRUCTURED_MEMORY_DIRECT_LIMIT,
        )
        selected_rules = self._rank_structured_records(
            personal_rules,
            query_terms=query_terms,
            text_fields=("title", "rule_text", "rule_type"),
            list_fields=("trigger_keywords",),
            weight_field="priority",
            status_values={"active"},
            include_high_priority=True,
            limit=STRUCTURED_MEMORY_DIRECT_LIMIT,
        )
        selected_plans = self._rank_structured_records(
            plans,
            query_terms=query_terms,
            text_fields=("title", "description", "desired_outcome", "plan_type"),
            weight_field="priority",
            status_values={"active", "paused"},
            include_high_priority=True,
            limit=STRUCTURED_MEMORY_DIRECT_LIMIT,
        )
        selected_commitments = self._rank_structured_records(
            commitments,
            query_terms=query_terms,
            text_fields=("title", "commitment_text", "commitment_type"),
            weight_field="priority",
            status_values={"open", "in_progress"},
            include_high_priority=True,
            limit=STRUCTURED_MEMORY_DIRECT_LIMIT,
        )

        selected_entity_ids = {str(entity.get("id")) for entity in selected_entities}
        selected_plan_ids = {str(plan.get("id")) for plan in selected_plans}
        selected_entity_ids.update(
            str(commitment.get("entity_id"))
            for commitment in selected_commitments
            if commitment.get("entity_id")
        )
        selected_entity_ids.update(
            str(plan.get("primary_entity_id"))
            for plan in selected_plans
            if plan.get("primary_entity_id")
        )
        related_entities = self._related_records(
            entities,
            link_field="id",
            selected_ids=selected_entity_ids,
            weight_field="importance",
            status_values={"active"},
            limit=STRUCTURED_MEMORY_RELATED_LIMIT,
        )
        selected_entities = self._merge_related_records(
            selected_entities,
            related_entities,
        )
        selected_entity_ids = {str(entity.get("id")) for entity in selected_entities}
        related_plans = self._related_records(
            plans,
            link_field="primary_entity_id",
            selected_ids=selected_entity_ids,
            weight_field="priority",
            status_values={"active", "paused"},
            limit=STRUCTURED_MEMORY_RELATED_LIMIT,
        )
        selected_plans = self._merge_related_records(selected_plans, related_plans)
        selected_plan_ids.update(
            str(commitment.get("plan_id"))
            for commitment in selected_commitments
            if commitment.get("plan_id")
        )
        selected_plan_ids.update(
            str(plan.get("id"))
            for plan in selected_plans
            if plan.get("id")
        )

        related_entity_events = self._related_records(
            entity_events,
            link_field="entity_id",
            selected_ids=selected_entity_ids,
            weight_field="importance",
            limit=STRUCTURED_MEMORY_RELATED_LIMIT,
        )
        related_milestones = self._related_records(
            plan_milestones,
            link_field="plan_id",
            selected_ids=selected_plan_ids,
            weight_field="priority",
            status_values={"open", "in_progress"},
            limit=STRUCTURED_MEMORY_RELATED_LIMIT,
        )

        return {
            "entities": selected_entities,
            "entity_events": related_entity_events,
            "personal_rules": selected_rules,
            "plans": selected_plans,
            "plan_milestones": related_milestones,
            "commitments": selected_commitments,
        }

    async def list_long_term_memory(
        self,
        limit: int = 50,
        memory_type: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        self._validate_memory_type(memory_type)
        query = {
            "select": LONG_TERM_MEMORY_SELECT,
            "order": "importance.desc,last_accessed_at.desc,created_at.desc",
            "limit": str(limit),
        }
        if memory_type is not None:
            query["memory_type"] = f"eq.{memory_type}"
        if active is not None:
            query["active"] = f"eq.{str(active).lower()}"

        return await self._request(
            "GET",
            self.settings.supabase_long_term_memory_table,
            query=query,
        )

    async def update_long_term_memory(
        self,
        memory_id: str,
        memory_type: Optional[str] = None,
        content: Optional[str] = None,
        importance: Optional[int] = None,
        active: Optional[bool] = None,
    ) -> Optional[dict]:
        self._validate_memory_type(memory_type)
        updates: dict = {}
        if memory_type is not None:
            updates["memory_type"] = memory_type
        if content is not None:
            updates["content"] = content
        if importance is not None:
            if importance < 1 or importance > 5:
                raise MemoryServiceError(
                    "Memory importance must be between 1 and 5.",
                    400,
                )
            updates["importance"] = importance
        if active is not None:
            updates["active"] = active

        if not updates:
            raise MemoryServiceError(
                "At least one memory field must be provided.",
                400,
            )

        rows = await self._request(
            "PATCH",
            self.settings.supabase_long_term_memory_table,
            body=updates,
            query={
                "id": f"eq.{memory_id}",
                "select": LONG_TERM_MEMORY_SELECT,
            },
            prefer="return=representation",
        )
        return rows[0] if rows else None

    async def deactivate_long_term_memory(self, memory_id: str) -> bool:
        memory = await self.update_long_term_memory(memory_id, active=False)
        return memory is not None

    async def create_memory_correction(self, correction: dict) -> dict:
        correction_type = correction.get("correction_type")
        if correction_type not in VALID_MEMORY_CORRECTION_TYPES:
            raise MemoryServiceError("Invalid memory correction type.", 400)
        new_value = str(correction.get("new_value") or "").strip()
        if not new_value:
            raise MemoryServiceError("Memory correction new value is required.", 400)

        payload = {
            "correction_type": correction_type,
            "old_value": correction.get("old_value"),
            "new_value": new_value,
            "target_table": correction.get("target_table"),
            "target_id": correction.get("target_id"),
            "source_conversation_id": correction.get("source_conversation_id"),
            "source_message_id": correction.get("source_message_id"),
            "applied": bool(correction.get("applied", False)),
            "confidence": correction.get("confidence", 0.9),
            "metadata": correction.get("metadata") or {},
        }
        return await self._create_record(
            self.settings.supabase_memory_corrections_table,
            payload,
            MEMORY_CORRECTION_SELECT,
        )

    async def list_memory_corrections(
        self,
        limit: int = 50,
        correction_type: Optional[str] = None,
        applied: Optional[bool] = None,
        target_table: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> list[dict]:
        if correction_type is not None and (
            correction_type not in VALID_MEMORY_CORRECTION_TYPES
        ):
            raise MemoryServiceError("Invalid memory correction type.", 400)
        return await self._list_records(
            self.settings.supabase_memory_corrections_table,
            select=MEMORY_CORRECTION_SELECT,
            filters={
                "correction_type": correction_type,
                "applied": applied,
                "target_table": target_table,
                "target_id": target_id,
            },
            order="created_at.desc",
            limit=limit,
        )

    async def create_entity(self, entity: dict) -> dict:
        return await self._create_record(ENTITIES_TABLE, entity, ENTITY_SELECT)

    async def list_entities(
        self,
        limit: int = 50,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        normalized_name: Optional[str] = None,
    ) -> list[dict]:
        filters = {
            "entity_type": entity_type,
            "status": status,
            "active": active,
            "normalized_name": normalized_name,
        }
        return await self._list_records(
            ENTITIES_TABLE,
            select=ENTITY_SELECT,
            filters=filters,
            order="importance.desc,last_seen_at.desc,updated_at.desc",
            limit=limit,
        )

    async def update_entity(self, entity_id: str, **updates: object) -> Optional[dict]:
        return await self._update_record(
            ENTITIES_TABLE,
            entity_id,
            updates=updates,
            select=ENTITY_SELECT,
            empty_detail="At least one entity field must be provided.",
        )

    async def deactivate_entity(self, entity_id: str) -> bool:
        entity = await self.update_entity(entity_id, active=False, status="inactive")
        return entity is not None

    async def create_entity_event(self, event: dict) -> dict:
        return await self._create_record(
            ENTITY_EVENTS_TABLE,
            event,
            ENTITY_EVENT_SELECT,
        )

    async def list_entity_events(
        self,
        limit: int = 50,
        entity_id: Optional[str] = None,
        event_type: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        filters = {
            "entity_id": entity_id,
            "event_type": event_type,
            "active": active,
        }
        return await self._list_records(
            ENTITY_EVENTS_TABLE,
            select=ENTITY_EVENT_SELECT,
            filters=filters,
            order="importance.desc,created_at.desc",
            limit=limit,
        )

    async def update_entity_event(
        self,
        event_id: str,
        **updates: object,
    ) -> Optional[dict]:
        return await self._update_record(
            ENTITY_EVENTS_TABLE,
            event_id,
            updates=updates,
            select=ENTITY_EVENT_SELECT,
            empty_detail="At least one entity event field must be provided.",
        )

    async def deactivate_entity_event(self, event_id: str) -> bool:
        event = await self.update_entity_event(event_id, active=False)
        return event is not None

    async def create_personal_rule(self, rule: dict) -> dict:
        return await self._create_record(
            PERSONAL_RULES_TABLE,
            rule,
            PERSONAL_RULE_SELECT,
        )

    async def list_personal_rules(
        self,
        limit: int = 50,
        rule_type: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        filters = {
            "rule_type": rule_type,
            "status": status,
            "active": active,
        }
        return await self._list_records(
            PERSONAL_RULES_TABLE,
            select=PERSONAL_RULE_SELECT,
            filters=filters,
            order="priority.desc,updated_at.desc",
            limit=limit,
        )

    async def update_personal_rule(
        self,
        rule_id: str,
        **updates: object,
    ) -> Optional[dict]:
        return await self._update_record(
            PERSONAL_RULES_TABLE,
            rule_id,
            updates=updates,
            select=PERSONAL_RULE_SELECT,
            empty_detail="At least one personal rule field must be provided.",
        )

    async def deactivate_personal_rule(self, rule_id: str) -> bool:
        rule = await self.update_personal_rule(
            rule_id,
            active=False,
            status="archived",
        )
        return rule is not None

    async def create_plan(self, plan: dict) -> dict:
        return await self._create_record(PLANS_TABLE, plan, PLAN_SELECT)

    async def list_plans(
        self,
        limit: int = 50,
        plan_type: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        filters = {
            "plan_type": plan_type,
            "status": status,
            "active": active,
        }
        return await self._list_records(
            PLANS_TABLE,
            select=PLAN_SELECT,
            filters=filters,
            order="priority.desc,target_date.asc,updated_at.desc",
            limit=limit,
        )

    async def update_plan(self, plan_id: str, **updates: object) -> Optional[dict]:
        return await self._update_record(
            PLANS_TABLE,
            plan_id,
            updates=updates,
            select=PLAN_SELECT,
            empty_detail="At least one plan field must be provided.",
        )

    async def deactivate_plan(self, plan_id: str) -> bool:
        plan = await self.update_plan(plan_id, active=False, status="archived")
        return plan is not None

    async def create_plan_milestone(self, milestone: dict) -> dict:
        return await self._create_record(
            PLAN_MILESTONES_TABLE,
            milestone,
            PLAN_MILESTONE_SELECT,
        )

    async def list_plan_milestones(
        self,
        limit: int = 50,
        plan_id: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        filters = {
            "plan_id": plan_id,
            "status": status,
            "active": active,
        }
        return await self._list_records(
            PLAN_MILESTONES_TABLE,
            select=PLAN_MILESTONE_SELECT,
            filters=filters,
            order="priority.desc,target_date.asc,updated_at.desc",
            limit=limit,
        )

    async def update_plan_milestone(
        self,
        milestone_id: str,
        **updates: object,
    ) -> Optional[dict]:
        return await self._update_record(
            PLAN_MILESTONES_TABLE,
            milestone_id,
            updates=updates,
            select=PLAN_MILESTONE_SELECT,
            empty_detail="At least one plan milestone field must be provided.",
        )

    async def deactivate_plan_milestone(self, milestone_id: str) -> bool:
        milestone = await self.update_plan_milestone(
            milestone_id,
            active=False,
            status="canceled",
        )
        return milestone is not None

    async def create_commitment(self, commitment: dict) -> dict:
        return await self._create_record(
            COMMITMENTS_TABLE,
            commitment,
            COMMITMENT_SELECT,
        )

    async def list_commitments(
        self,
        limit: int = 50,
        commitment_type: Optional[str] = None,
        plan_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        filters = {
            "commitment_type": commitment_type,
            "plan_id": plan_id,
            "entity_id": entity_id,
            "status": status,
            "active": active,
        }
        return await self._list_records(
            COMMITMENTS_TABLE,
            select=COMMITMENT_SELECT,
            filters=filters,
            order="priority.desc,due_at.asc,updated_at.desc",
            limit=limit,
        )

    async def update_commitment(
        self,
        commitment_id: str,
        **updates: object,
    ) -> Optional[dict]:
        return await self._update_record(
            COMMITMENTS_TABLE,
            commitment_id,
            updates=updates,
            select=COMMITMENT_SELECT,
            empty_detail="At least one commitment field must be provided.",
        )

    async def deactivate_commitment(self, commitment_id: str) -> bool:
        commitment = await self.update_commitment(
            commitment_id,
            active=False,
            status="archived",
        )
        return commitment is not None

    async def _create_record(self, table: str, body: dict, select: str) -> dict:
        rows = await self._request(
            "POST",
            table,
            body=body,
            query={"select": select},
            prefer="return=representation",
        )
        return self._first_row(rows)

    async def _list_records(
        self,
        table: str,
        select: str,
        filters: Optional[dict[str, object]] = None,
        order: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        query = {
            "select": select,
            "limit": str(limit),
        }
        if order is not None:
            query["order"] = order

        for field, value in (filters or {}).items():
            if value is None:
                continue
            query[field] = self._eq_filter(value)

        return await self._request("GET", table, query=query)

    async def _update_record(
        self,
        table: str,
        record_id: str,
        updates: dict[str, object],
        select: str,
        empty_detail: str,
    ) -> Optional[dict]:
        updates = {key: value for key, value in updates.items() if value is not None}
        if not updates:
            raise MemoryServiceError(empty_detail, 400)

        rows = await self._request(
            "PATCH",
            table,
            body=updates,
            query={
                "id": f"eq.{record_id}",
                "select": select,
            },
            prefer="return=representation",
        )
        return rows[0] if rows else None

    def _eq_filter(self, value: object) -> str:
        if isinstance(value, bool):
            return f"eq.{str(value).lower()}"

        return f"eq.{value}"

    async def _request(
        self,
        method: str,
        table: str,
        body: Optional[dict] = None,
        query: Optional[dict[str, str]] = None,
        prefer: Optional[str] = None,
    ) -> list[dict]:
        rest_url = self.settings.supabase_rest_url
        service_key = self.settings.supabase_service_role_key
        if not rest_url or not service_key:
            raise MemoryServiceError("Supabase memory is not configured.")

        url = f"{rest_url}/{quote(table)}"
        if query:
            url = f"{url}?{urlencode(query)}"

        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
        }
        json_body = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            json_body = body
        if prefer:
            headers["Prefer"] = prefer

        try:
            response = await request_with_retries(
                method,
                url,
                headers=headers,
                json=json_body,
            )
            response.raise_for_status()
            raw_response = response.text
        except httpx.HTTPStatusError as error:
            raise MemoryServiceError("Supabase memory returned an error.") from error
        except (httpx.RequestError, TimeoutError) as error:
            raise MemoryServiceError("Cannot reach Supabase memory.") from error

        if not raw_response:
            return []

        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise MemoryServiceError(
                "Supabase memory returned an unreadable response.",
                status_code=500,
            ) from error

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]

        raise MemoryServiceError("Supabase memory returned an unreadable response.")

    def _first_row(self, rows: list[dict]) -> dict:
        if not rows:
            raise MemoryServiceError("Supabase memory returned no rows.")

        return rows[0]

    def _conversation_with_preview(
        self,
        row: dict,
        last_message: Optional[dict],
    ) -> dict:
        return {
            "id": str(row.get("id", "")),
            "title": row.get("title"),
            "timestamp": row.get("timestamp"),
            "last_message": last_message,
        }

    def _memory_candidate(self, message: str) -> Optional[dict]:
        text = " ".join(message.strip().split())
        if not text:
            return None

        lowered = text.lower()
        if lowered.startswith(("remember that ", "remember: ")):
            content = re.sub(r"^remember(?: that|:)\s+", "", text, flags=re.I)
            return {
                "memory_type": self._classify_memory(content),
                "content": content,
                "importance": 5,
            }

        if re.match(r"^i (prefer|like|love|hate|dislike|want|need)\b", lowered):
            return {
                "memory_type": "preference",
                "content": text,
                "importance": 4,
            }

        if re.match(r"^i (am|work|live|have|own|use)\b", lowered):
            return {
                "memory_type": "fact",
                "content": text,
                "importance": 3,
            }

        event_markers = (
            "my birthday is",
            "my anniversary is",
            "i started",
            "i moved",
            "i graduated",
            "i got married",
        )
        if any(marker in lowered for marker in event_markers):
            return {
                "memory_type": "event",
                "content": text,
                "importance": 4,
            }

        return None

    def _classify_memory(self, content: str) -> str:
        lowered = content.lower()
        if any(
            word in lowered
            for word in ("prefer", "like", "love", "hate", "want")
        ):
            return "preference"
        if any(word in lowered for word in ("birthday", "anniversary", "started")):
            return "event"

        return "fact"

    def _validate_memory_type(self, memory_type: Optional[str]) -> None:
        if memory_type is not None and memory_type not in VALID_MEMORY_TYPES:
            raise MemoryServiceError("Invalid memory type.", 400)

    def _score_memory(
        self,
        memory: dict,
        query_terms: set[str],
    ) -> Optional[dict]:
        content = str(memory.get("content", ""))
        memory_terms = self._expanded_terms(content)
        matched_terms = sorted(query_terms & memory_terms)
        has_direct_match = bool(matched_terms)
        is_high_priority_preference = (
            memory.get("memory_type") == "preference"
            and int(memory.get("importance") or 0) >= 4
        )

        if not query_terms:
            has_direct_match = True
        if not has_direct_match and not is_high_priority_preference:
            return None

        overlap_score = (
            len(matched_terms) / max(len(query_terms), 1) if query_terms else 0.2
        )
        importance_score = max(1, min(int(memory.get("importance") or 3), 5)) / 5
        recency_score = self._recency_score(memory)
        correction_pairs = self._memory_correction_pairs(memory)
        correction_boost = 0.16 if correction_pairs else 0
        relevance_score = (
            (0.65 * overlap_score)
            + (0.25 * importance_score)
            + (0.10 * recency_score)
            + correction_boost
        )

        if relevance_score < RELEVANT_MEMORY_MINIMUM_SCORE:
            return None

        if matched_terms:
            reason = f"Matched current message terms: {', '.join(matched_terms[:6])}"
        elif is_high_priority_preference:
            reason = "Included high-priority user preference."
        else:
            reason = "Included as recent important context."
        if correction_pairs:
            reason = f"{reason}. Includes corrected current truth."

        return {
            **memory,
            "relevance_score": round(relevance_score, 4),
            "relevance_reason": reason,
        }

    def _rank_structured_records(
        self,
        records: list[dict],
        *,
        query_terms: set[str],
        text_fields: tuple[str, ...],
        weight_field: str,
        list_fields: tuple[str, ...] = (),
        status_values: Optional[set[str]] = None,
        include_high_priority: bool = False,
        limit: int = STRUCTURED_MEMORY_DIRECT_LIMIT,
    ) -> list[dict]:
        scored_records = []
        for record in records:
            if status_values is not None and record.get("status") not in status_values:
                continue

            scored = self._score_structured_record(
                record,
                query_terms=query_terms,
                text_fields=text_fields,
                list_fields=list_fields,
                weight_field=weight_field,
                include_high_priority=include_high_priority,
            )
            if scored is not None:
                scored_records.append(scored)

        scored_records.sort(
            key=lambda record: (
                record.get("relevance_score", 0),
                int(record.get(weight_field) or 0),
                str(record.get("updated_at") or record.get("created_at") or ""),
            ),
            reverse=True,
        )
        return scored_records[:limit]

    def _score_structured_record(
        self,
        record: dict,
        *,
        query_terms: set[str],
        text_fields: tuple[str, ...],
        list_fields: tuple[str, ...],
        weight_field: str,
        include_high_priority: bool,
    ) -> Optional[dict]:
        record_text = self._structured_record_text(record, text_fields, list_fields)
        record_terms = self._expanded_terms(record_text)
        matched_terms = sorted(query_terms & record_terms)
        weight = max(1, min(int(record.get(weight_field) or 3), 5))
        is_high_priority = (
            include_high_priority and weight >= HIGH_PRIORITY_STRUCTURED_THRESHOLD
        )

        if not query_terms:
            matched_terms = []
            has_direct_match = is_high_priority
        else:
            has_direct_match = bool(matched_terms)
        if not has_direct_match and not is_high_priority:
            return None

        overlap_score = (
            len(matched_terms) / max(len(query_terms), 1)
            if matched_terms
            else 0.18
        )
        weight_score = weight / 5
        recency_score = self._recency_score(record)
        exact_match_boost = self._exact_match_boost(record_text, query_terms)
        relevance_score = (
            (0.62 * overlap_score)
            + (0.30 * weight_score)
            + (0.08 * recency_score)
            + exact_match_boost
        )
        if relevance_score < STRUCTURED_MEMORY_MINIMUM_SCORE:
            return None

        if matched_terms:
            reason = f"Matched current message terms: {', '.join(matched_terms[:6])}"
            if exact_match_boost:
                reason = f"{reason}. Strong exact-name match."
        elif is_high_priority:
            reason = "Included high-priority active structured memory."
        else:
            reason = "Included as relevant structured context."

        return {
            **record,
            "relevance_score": round(relevance_score, 4),
            "relevance_reason": reason,
        }

    def _structured_record_text(
        self,
        record: dict,
        text_fields: tuple[str, ...],
        list_fields: tuple[str, ...],
    ) -> str:
        values = [str(record.get(field) or "") for field in text_fields]
        for field in list_fields:
            raw_value = record.get(field) or []
            if isinstance(raw_value, list):
                values.extend(str(item) for item in raw_value)
        return " ".join(values)

    def _related_records(
        self,
        records: list[dict],
        *,
        link_field: str,
        selected_ids: set[str],
        weight_field: str,
        status_values: Optional[set[str]] = None,
        limit: int = STRUCTURED_MEMORY_RELATED_LIMIT,
    ) -> list[dict]:
        if not selected_ids:
            return []

        related = []
        for record in records:
            if str(record.get(link_field) or "") not in selected_ids:
                continue
            if status_values is not None and record.get("status") not in status_values:
                continue
            related.append(record)

        related.sort(
            key=lambda record: (
                int(record.get(weight_field) or 0),
                str(record.get("occurred_at") or record.get("target_date") or ""),
                str(record.get("updated_at") or record.get("created_at") or ""),
            ),
            reverse=True,
        )
        return related[:limit]

    def _merge_related_records(
        self,
        selected: list[dict],
        related: list[dict],
    ) -> list[dict]:
        seen_ids = {str(record.get("id")) for record in selected if record.get("id")}
        merged = [*selected]
        for record in related:
            record_id = str(record.get("id") or "")
            if not record_id or record_id in seen_ids:
                continue
            merged.append(
                {
                    **record,
                    "relevance_reason": "Included through linked structured memory.",
                }
            )
            seen_ids.add(record_id)
        return merged

    def _filter_stale_corrected_memories(
        self,
        scored_memories: list[dict],
    ) -> list[dict]:
        correction_pairs = []
        for memory in scored_memories:
            for old_value, new_value in self._memory_correction_pairs(memory):
                correction_pairs.append(
                    {
                        "source_id": str(memory.get("id") or ""),
                        "old": old_value,
                        "new": new_value,
                    }
                )
        if not correction_pairs:
            return scored_memories

        filtered = []
        for memory in scored_memories:
            memory_id = str(memory.get("id") or "")
            content = str(memory.get("content") or "")
            stale = False
            for pair in correction_pairs:
                if memory_id == pair["source_id"]:
                    continue
                if self._contains_word(content, pair["old"]) and not self._contains_word(
                    content,
                    pair["new"],
                ):
                    stale = True
                    break
            if not stale:
                filtered.append(memory)
        return filtered

    def _memory_correction_pairs(self, memory: dict) -> list[tuple[str, str]]:
        content = str(memory.get("content") or "")
        if not content:
            return []

        pairs: list[tuple[str, str]] = []
        correction_patterns = [
            r"\b(?P<new>[A-Z][A-Za-z]{2,})\b[^.\n]{0,120}?\b(?:not|corrected from|instead of|rather than)\s+(?P<old>[A-Z][A-Za-z]{1,})\b",
            r"\b(?:not|wrong|incorrect)\s+(?P<old>[A-Z][A-Za-z]{1,})\b[^.\n]{0,120}?\b(?:correct|real|actual|now|is)\s+(?P<new>[A-Z][A-Za-z]{2,})\b",
            r"\b(?P<old>[A-Z][A-Za-z]{1,})\b[^.\n]{0,80}?\b(?:was wrong|is wrong)\b[^.\n]{0,120}?\b(?P<new>[A-Z][A-Za-z]{2,})\b",
        ]
        for pattern in correction_patterns:
            for match in re.finditer(pattern, content):
                old_value = match.group("old").strip()
                new_value = match.group("new").strip()
                if self._valid_correction_pair(old_value, new_value):
                    pairs.append((old_value, new_value))
        for match in re.finditer(
            r"\b(?:corrected from|not|instead of|rather than)\s+(?P<old>[A-Z][A-Za-z]{1,})\b",
            content,
        ):
            old_value = match.group("old").strip()
            prefix = content[: match.start()]
            new_value = self._last_name_candidate(prefix)
            if new_value and self._valid_correction_pair(old_value, new_value):
                pairs.append((old_value, new_value))

        return list(dict.fromkeys(pairs))

    def _valid_correction_pair(self, old_value: str, new_value: str) -> bool:
        if old_value.lower() == new_value.lower():
            return False
        blocked_values = {"the", "this", "that", "user", "person", "name"}
        return new_value.lower() not in blocked_values

    def _last_name_candidate(self, text: str) -> Optional[str]:
        blocked_values = {"The", "This", "That", "User", "Person", "Name"}
        candidates = [
            candidate
            for candidate in re.findall(r"\b[A-Z][A-Za-z]{2,}\b", text)
            if candidate not in blocked_values
        ]
        return candidates[-1] if candidates else None

    def _contains_word(self, text: str, word: str) -> bool:
        return re.search(rf"\b{re.escape(word)}\b", text, flags=re.I) is not None

    def _exact_match_boost(self, record_text: str, query_terms: set[str]) -> float:
        if not query_terms:
            return 0
        record_terms = self._expanded_terms(record_text)
        matched_terms = query_terms & record_terms
        if not matched_terms:
            return 0
        if len(matched_terms) >= 2:
            return 0.08
        return 0.04

    def _expanded_terms(self, text: str) -> set[str]:
        terms = {
            self._normalize_token(token)
            for token in re.findall(r"[a-z0-9']+", text.lower())
        }
        terms = {
            term
            for term in terms
            if len(term) >= 3 and term not in STOP_WORDS
        }

        expanded_terms = set(terms)
        for concept, words in CONCEPT_GROUPS.items():
            normalized_words = {self._normalize_token(word) for word in words}
            if terms & normalized_words:
                expanded_terms.add(concept)

        return expanded_terms

    def _normalize_token(self, token: str) -> str:
        token = token.strip("'")
        for suffix in ("ing", "ed", "es", "s"):
            if len(token) > len(suffix) + 3 and token.endswith(suffix):
                return token[: -len(suffix)]

        return token

    def _recency_score(self, memory: dict) -> float:
        timestamp = memory.get("last_accessed_at") or memory.get("created_at")
        if not timestamp:
            return 0.3

        try:
            parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except ValueError:
            return 0.3

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        age_days = max((datetime.now(timezone.utc) - parsed).days, 0)
        return 1 / (1 + (age_days / 30))


def is_active_memory(memory: dict) -> bool:
    return memory.get("active") is not False


def memory_accountability_text(memory: dict) -> str:
    return " ".join(
        str(memory.get(field) or "")
        for field in ("content", "memory_type", "relevance_reason")
    )
