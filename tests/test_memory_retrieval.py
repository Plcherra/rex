import pytest

from app.config import Settings
from app.services.memory_service import SupabaseMemoryService


class InMemoryRetrievalService(SupabaseMemoryService):
    def __init__(
        self,
        memories,
        entities=None,
        entity_events=None,
        personal_rules=None,
        plans=None,
        plan_milestones=None,
        commitments=None,
    ):
        self.memories = memories
        self.entities = entities or []
        self.entity_events = entity_events or []
        self.personal_rules = personal_rules or []
        self.plans = plans or []
        self.plan_milestones = plan_milestones or []
        self.commitments = commitments or []

    async def list_long_term_memory(self, limit=50, memory_type=None, active=None):
        memories = self.memories
        if active is not None:
            memories = [memory for memory in memories if memory["active"] is active]
        if memory_type is not None:
            memories = [
                memory
                for memory in memories
                if memory["memory_type"] == memory_type
            ]
        return memories[:limit]

    async def list_entities(
        self,
        limit=50,
        entity_type=None,
        status=None,
        active=None,
        normalized_name=None,
    ):
        records = self.entities
        if active is not None:
            records = [record for record in records if record["active"] is active]
        if entity_type is not None:
            records = [
                record for record in records if record["entity_type"] == entity_type
            ]
        if status is not None:
            records = [record for record in records if record["status"] == status]
        if normalized_name is not None:
            records = [
                record
                for record in records
                if record["normalized_name"] == normalized_name
            ]
        return records[:limit]

    async def list_entity_events(
        self,
        limit=50,
        entity_id=None,
        event_type=None,
        active=None,
    ):
        records = self.entity_events
        if active is not None:
            records = [record for record in records if record["active"] is active]
        if entity_id is not None:
            records = [record for record in records if record["entity_id"] == entity_id]
        if event_type is not None:
            records = [
                record for record in records if record["event_type"] == event_type
            ]
        return records[:limit]

    async def list_personal_rules(
        self,
        limit=50,
        rule_type=None,
        status=None,
        active=None,
    ):
        records = self.personal_rules
        if active is not None:
            records = [record for record in records if record["active"] is active]
        if rule_type is not None:
            records = [record for record in records if record["rule_type"] == rule_type]
        if status is not None:
            records = [record for record in records if record["status"] == status]
        return records[:limit]

    async def list_plans(self, limit=50, plan_type=None, status=None, active=None):
        records = self.plans
        if active is not None:
            records = [record for record in records if record["active"] is active]
        if plan_type is not None:
            records = [record for record in records if record["plan_type"] == plan_type]
        if status is not None:
            records = [record for record in records if record["status"] == status]
        return records[:limit]

    async def list_plan_milestones(
        self,
        limit=50,
        plan_id=None,
        status=None,
        active=None,
    ):
        records = self.plan_milestones
        if active is not None:
            records = [record for record in records if record["active"] is active]
        if plan_id is not None:
            records = [record for record in records if record["plan_id"] == plan_id]
        if status is not None:
            records = [record for record in records if record["status"] == status]
        return records[:limit]

    async def list_commitments(
        self,
        limit=50,
        commitment_type=None,
        plan_id=None,
        entity_id=None,
        status=None,
        active=None,
    ):
        records = self.commitments
        if active is not None:
            records = [record for record in records if record["active"] is active]
        if commitment_type is not None:
            records = [
                record
                for record in records
                if record["commitment_type"] == commitment_type
            ]
        if plan_id is not None:
            records = [record for record in records if record["plan_id"] == plan_id]
        if entity_id is not None:
            records = [record for record in records if record["entity_id"] == entity_id]
        if status is not None:
            records = [record for record in records if record["status"] == status]
        return records[:limit]


class FakeVoiceTurnMemoryService(SupabaseMemoryService):
    def __init__(self):
        self.settings = Settings(_env_file=None)
        self.requests = []

    async def _request(self, method, table, body=None, query=None, prefer=None):
        self.requests.append(
            {
                "method": method,
                "table": table,
                "body": body,
                "query": query,
                "prefer": prefer,
            }
        )
        return [{"id": "voice-turn-1", **body}]


@pytest.mark.asyncio
async def test_get_relevant_memories_ranks_keyword_and_concept_matches():
    service = InMemoryRetrievalService(
        [
            {
                "id": "memory-work",
                "memory_type": "fact",
                "content": "I am dealing with pressure from my manager at work.",
                "importance": 4,
                "active": True,
                "created_at": "2026-05-11T10:00:00Z",
                "last_accessed_at": "2026-05-11T10:00:00Z",
            },
            {
                "id": "memory-money",
                "memory_type": "fact",
                "content": "I am trying to reduce rent and debt stress.",
                "importance": 5,
                "active": True,
                "created_at": "2026-05-11T09:00:00Z",
                "last_accessed_at": "2026-05-11T09:00:00Z",
            },
            {
                "id": "memory-food",
                "memory_type": "preference",
                "content": "I like sushi.",
                "importance": 2,
                "active": True,
                "created_at": "2026-05-11T08:00:00Z",
                "last_accessed_at": "2026-05-11T08:00:00Z",
            },
        ]
    )

    memories = await service.get_relevant_memories(
        "I need advice about work pressure and money.",
        limit=2,
    )

    assert [memory["id"] for memory in memories] == [
        "memory-work",
        "memory-money",
    ]
    assert all("relevance_score" in memory for memory in memories)
    assert all(memory["relevance_score"] > 0 for memory in memories)
    assert "Matched current message terms" in memories[0]["relevance_reason"]


@pytest.mark.asyncio
async def test_get_relevant_memories_filters_irrelevant_low_priority_memories():
    service = InMemoryRetrievalService(
        [
            {
                "id": "memory-food",
                "memory_type": "preference",
                "content": "I like sushi.",
                "importance": 2,
                "active": True,
                "created_at": "2026-05-11T08:00:00Z",
                "last_accessed_at": "2026-05-11T08:00:00Z",
            }
        ]
    )

    memories = await service.get_relevant_memories(
        "What should I do about my visa?",
        limit=8,
    )

    assert memories == []


@pytest.mark.asyncio
async def test_get_relevant_memories_keeps_high_priority_preferences_available():
    service = InMemoryRetrievalService(
        [
            {
                "id": "memory-style",
                "memory_type": "preference",
                "content": "I prefer direct concise answers.",
                "importance": 5,
                "active": True,
                "created_at": "2026-05-10T08:00:00Z",
                "last_accessed_at": "2026-05-10T08:00:00Z",
            }
        ]
    )

    memories = await service.get_relevant_memories(
        "What should I do next?",
        limit=8,
    )

    assert len(memories) == 1
    assert memories[0]["id"] == "memory-style"
    assert memories[0]["relevance_reason"] == "Included high-priority user preference."


@pytest.mark.asyncio
async def test_get_relevant_memories_retrieves_location_when_user_asks_where_they_live():
    service = InMemoryRetrievalService(
        [
            {
                "id": "memory-location",
                "memory_type": "fact",
                "content": "I am in Massachusetts.",
                "importance": 3,
                "active": True,
                "created_at": "2026-05-18T20:00:00Z",
                "last_accessed_at": "2026-05-18T20:00:00Z",
            },
            {
                "id": "memory-app",
                "memory_type": "fact",
                "content": "I am building Rex as my first personal app.",
                "importance": 4,
                "active": True,
                "created_at": "2026-05-18T19:00:00Z",
                "last_accessed_at": "2026-05-18T19:00:00Z",
            },
        ]
    )

    memories = await service.get_relevant_memories(
        "Do you remember where I live?",
        limit=2,
    )

    assert memories
    assert memories[0]["id"] == "memory-location"
    assert "location" in memories[0]["relevance_reason"]


@pytest.mark.asyncio
async def test_get_relevant_memories_retrieves_timezone_context_from_state_question():
    service = InMemoryRetrievalService(
        [
            {
                "id": "memory-timezone",
                "memory_type": "fact",
                "content": "I live in Massachusetts and use Eastern time.",
                "importance": 4,
                "active": True,
                "created_at": "2026-05-18T20:00:00Z",
                "last_accessed_at": "2026-05-18T20:00:00Z",
            }
        ]
    )

    memories = await service.get_relevant_memories(
        "What state or timezone am I in?",
        limit=1,
    )

    assert [memory["id"] for memory in memories] == ["memory-timezone"]
    assert "location" in memories[0]["relevance_reason"]


@pytest.mark.asyncio
async def test_get_relevant_memories_ignores_inactive_stale_correction_rows():
    service = InMemoryRetrievalService(
        [
            {
                "id": "memory-stale-name",
                "memory_type": "event",
                "content": "I am planning to ask Al out for dinner Monday.",
                "importance": 4,
                "active": False,
                "created_at": "2026-05-18T19:00:00Z",
                "last_accessed_at": "2026-05-18T19:00:00Z",
            },
            {
                "id": "memory-corrected-name",
                "memory_type": "fact",
                "content": "The person for the next-week dinner plan is Melissa.",
                "importance": 4,
                "active": True,
                "created_at": "2026-05-19T01:00:00Z",
                "last_accessed_at": "2026-05-19T01:00:00Z",
            },
        ]
    )

    memories = await service.get_relevant_memories(
        "Do you remember the person for my next week dinner plan?",
        limit=5,
    )

    assert [memory["id"] for memory in memories] == ["memory-corrected-name"]


@pytest.mark.asyncio
async def test_get_relevant_memories_prefers_active_correction_over_stale_row():
    service = InMemoryRetrievalService(
        [
            {
                "id": "memory-stale-name",
                "memory_type": "event",
                "content": "I am planning to ask Al out for dinner Monday.",
                "importance": 4,
                "active": True,
                "created_at": "2026-05-18T19:00:00Z",
                "last_accessed_at": "2026-05-18T19:00:00Z",
            },
            {
                "id": "memory-corrected-name",
                "memory_type": "fact",
                "content": (
                    "The person for the next-week dinner plan is Melissa, "
                    "corrected from Al."
                ),
                "importance": 4,
                "active": True,
                "created_at": "2026-05-19T01:00:00Z",
                "last_accessed_at": "2026-05-19T01:00:00Z",
            },
        ]
    )

    memories = await service.get_relevant_memories(
        "Do you remember the person for my next week dinner plan?",
        limit=5,
    )

    assert [memory["id"] for memory in memories] == ["memory-corrected-name"]
    assert "corrected current truth" in memories[0]["relevance_reason"]


@pytest.mark.asyncio
async def test_get_structured_memory_context_ranks_records_and_links_children():
    service = InMemoryRetrievalService(
        [],
        entities=[
            {
                "id": "entity-clara",
                "entity_type": "person",
                "display_name": "Clara",
                "normalized_name": "clara",
                "aliases": ["girl from work"],
                "relationship": "dating interest from work",
                "summary": "Clara touched my arm and is part of the dating story.",
                "importance": 5,
                "status": "active",
                "active": True,
                "updated_at": "2026-05-18T10:00:00Z",
            },
            {
                "id": "entity-gym",
                "entity_type": "place",
                "display_name": "Gym",
                "normalized_name": "gym",
                "aliases": [],
                "relationship": "workout location",
                "summary": "Local gym.",
                "importance": 2,
                "status": "active",
                "active": True,
                "updated_at": "2026-05-10T10:00:00Z",
            },
        ],
        entity_events=[
            {
                "id": "event-clara-touch",
                "entity_id": "entity-clara",
                "event_type": "interaction",
                "title": "Clara touched my arm",
                "content": "This felt like flirting at work.",
                "importance": 4,
                "active": True,
                "occurred_at": "2026-05-18T12:00:00Z",
            }
        ],
        personal_rules=[
            {
                "id": "rule-doordash",
                "rule_type": "finance",
                "title": "Avoid DoorDash",
                "rule_text": "Do not order DoorDash while the budget is slipping.",
                "trigger_keywords": ["doordash", "delivery", "budget"],
                "priority": 5,
                "status": "active",
                "active": True,
                "updated_at": "2026-05-18T09:00:00Z",
            }
        ],
        plans=[
            {
                "id": "plan-visa",
                "plan_type": "immigration",
                "title": "Visa runway",
                "description": "Protect legal and financial runway.",
                "desired_outcome": "Leave with enough money and clean paperwork.",
                "priority": 5,
                "status": "active",
                "active": True,
                "target_date": "2026-07-01",
                "updated_at": "2026-05-18T08:00:00Z",
            }
        ],
        plan_milestones=[
            {
                "id": "milestone-visa-docs",
                "plan_id": "plan-visa",
                "milestone_type": "deadline",
                "title": "Prepare immigration documents",
                "description": "Collect visa paperwork.",
                "priority": 3,
                "status": "open",
                "active": True,
                "target_date": "2026-06-01",
            }
        ],
        commitments=[
            {
                "id": "commitment-visa-docs",
                "commitment_type": "deadline",
                "title": "Review visa paperwork",
                "commitment_text": "Review the visa documents before June.",
                "plan_id": "plan-visa",
                "entity_id": None,
                "priority": 4,
                "status": "open",
                "active": True,
                "due_at": "2026-05-31T18:00:00Z",
                "updated_at": "2026-05-18T08:30:00Z",
            }
        ],
    )

    context = await service.get_structured_memory_context(
        "I saw Clara at work and I need to stop DoorDash while handling my visa.",
    )

    assert [entity["id"] for entity in context["entities"]] == ["entity-clara"]
    assert [event["id"] for event in context["entity_events"]] == [
        "event-clara-touch"
    ]
    assert [rule["id"] for rule in context["personal_rules"]] == ["rule-doordash"]
    assert [plan["id"] for plan in context["plans"]] == ["plan-visa"]
    assert [milestone["id"] for milestone in context["plan_milestones"]] == [
        "milestone-visa-docs"
    ]
    assert [commitment["id"] for commitment in context["commitments"]] == [
        "commitment-visa-docs"
    ]
    assert "clara" in context["entities"][0]["relevance_reason"]


@pytest.mark.asyncio
async def test_structured_memory_context_includes_plans_linked_to_selected_person():
    service = InMemoryRetrievalService(
        memories=[],
        entities=[
            {
                "id": "entity-melissa",
                "entity_type": "person",
                "display_name": "Melissa",
                "normalized_name": "melissa",
                "aliases": ["girl from work"],
                "relationship": "Dating interest",
                "summary": "Person connected to the next-week date plan.",
                "importance": 4,
                "status": "active",
                "active": True,
            }
        ],
        plans=[
            {
                "id": "plan-date",
                "plan_type": "dating",
                "title": "Dinner invitation",
                "description": "Ask her out next Monday.",
                "desired_outcome": "Successful date.",
                "primary_entity_id": "entity-melissa",
                "priority": 3,
                "status": "active",
                "active": True,
            }
        ],
        plan_milestones=[
            {
                "id": "milestone-date-line",
                "plan_id": "plan-date",
                "milestone_type": "task",
                "title": "Prepare the invitation",
                "priority": 4,
                "status": "open",
                "active": True,
            }
        ],
    )

    context = await service.get_structured_memory_context(
        "What do you remember about Melissa?",
    )

    assert [entity["id"] for entity in context["entities"]] == ["entity-melissa"]
    assert [plan["id"] for plan in context["plans"]] == ["plan-date"]
    assert context["plans"][0]["relevance_reason"] == (
        "Included through linked structured memory."
    )
    assert [milestone["id"] for milestone in context["plan_milestones"]] == [
        "milestone-date-line"
    ]


@pytest.mark.asyncio
async def test_structured_memory_context_includes_person_linked_to_selected_plan():
    service = InMemoryRetrievalService(
        memories=[],
        entities=[
            {
                "id": "entity-melissa",
                "entity_type": "person",
                "display_name": "Melissa",
                "normalized_name": "melissa",
                "aliases": ["girl from work"],
                "relationship": "Dating interest",
                "summary": "Person connected to the next-week date plan.",
                "importance": 4,
                "status": "active",
                "active": True,
            }
        ],
        plans=[
            {
                "id": "plan-date",
                "plan_type": "dating",
                "title": "Dinner invitation",
                "description": "Ask Melissa out next Monday.",
                "desired_outcome": "Successful date with Melissa.",
                "primary_entity_id": "entity-melissa",
                "priority": 4,
                "status": "active",
                "active": True,
            }
        ],
    )

    context = await service.get_structured_memory_context(
        "Do you remember the next week date plan?",
    )

    assert [plan["id"] for plan in context["plans"]] == ["plan-date"]
    assert [entity["id"] for entity in context["entities"]] == ["entity-melissa"]
    assert context["entities"][0]["relevance_reason"]


@pytest.mark.asyncio
async def test_save_voice_turn_persists_safe_metadata_shape():
    service = FakeVoiceTurnMemoryService()

    result = await service.save_voice_turn(
        conversation_id="conversation-1",
        user_message_id="user-message-1",
        assistant_message_id="assistant-message-1",
        transcript_confidence=0.95,
        audio_duration_seconds=1.2,
        input_mime_type="audio/mp4",
        output_audio_encoding="MP3",
        metadata={"stt": {"request_id": "request-1"}},
    )

    assert result["id"] == "voice-turn-1"
    request = service.requests[0]
    assert request["method"] == "POST"
    assert request["table"] == "voice_turns"
    assert request["prefer"] == "return=representation"
    assert request["body"] == {
        "conversation_id": "conversation-1",
        "user_message_id": "user-message-1",
        "assistant_message_id": "assistant-message-1",
        "transcript_confidence": 0.95,
        "audio_duration_seconds": 1.2,
        "input_mime_type": "audio/mp4",
        "output_audio_encoding": "MP3",
        "stt_vendor": "deepgram",
        "tts_vendor": "google_tts",
        "metadata": {"stt": {"request_id": "request-1"}},
    }
