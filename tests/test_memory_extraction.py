import pytest

from app.services.memory_extraction_service import (
    MEMORY_EXTRACTION_PROMPT,
    MemoryExtractionService,
)


class FakeExtractionAIService:
    def __init__(self, response):
        self.response = response
        self.messages = []

    async def generate_response(self, messages):
        self.messages = messages
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeMemoryStore:
    def __init__(self, existing_memories=None):
        self.existing_memories = existing_memories or []
        self.saved_memories = []
        self.created_entities = []
        self.created_entity_events = []
        self.created_rules = []
        self.created_plans = []
        self.created_milestones = []
        self.created_commitments = []
        self.relevant_queries = []

    async def get_relevant_memories(self, query, limit=8):
        self.relevant_queries.append({"query": query, "limit": limit})
        return self.existing_memories[:limit]

    async def save_long_term_memory(
        self,
        memory_type,
        content,
        source_conversation_id=None,
        source_message_id=None,
        importance=3,
    ):
        memory = {
            "id": f"memory-{len(self.saved_memories) + 1}",
            "memory_type": memory_type,
            "content": content,
            "source_conversation_id": source_conversation_id,
            "source_message_id": source_message_id,
            "importance": importance,
            "active": True,
        }
        self.saved_memories.append(memory)
        return memory

    async def create_entity(self, payload):
        entity = {"id": f"entity-{len(self.created_entities) + 1}", **payload}
        self.created_entities.append(entity)
        return entity

    async def create_entity_event(self, payload):
        event = {"id": f"event-{len(self.created_entity_events) + 1}", **payload}
        self.created_entity_events.append(event)
        return event

    async def create_personal_rule(self, payload):
        rule = {"id": f"rule-{len(self.created_rules) + 1}", **payload}
        self.created_rules.append(rule)
        return rule

    async def create_plan(self, payload):
        plan = {"id": f"plan-{len(self.created_plans) + 1}", **payload}
        self.created_plans.append(plan)
        return plan

    async def create_plan_milestone(self, payload):
        milestone = {"id": f"milestone-{len(self.created_milestones) + 1}", **payload}
        self.created_milestones.append(milestone)
        return milestone

    async def create_commitment(self, payload):
        commitment = {
            "id": f"commitment-{len(self.created_commitments) + 1}",
            **payload,
        }
        self.created_commitments.append(commitment)
        return commitment


@pytest.mark.asyncio
async def test_memory_extraction_saves_valid_candidates():
    ai_service = FakeExtractionAIService(
        """
        {
          "memories": [
            {
              "memory_type": "preference",
              "content": "I prefer direct advice about career decisions.",
              "importance": 4,
              "rationale": "The user stated a recurring advice preference."
            }
          ]
        }
        """
    )
    memory_store = FakeMemoryStore()
    service = MemoryExtractionService(ai_service, memory_store)

    saved = await service.extract_and_save(
        "conversation-1",
        {
            "id": "message-1",
            "content": "Remember that I prefer direct advice about career decisions.",
        },
        {"id": "message-2", "content": "Got it."},
    )

    assert MEMORY_EXTRACTION_PROMPT in ai_service.messages[0]["content"]
    assert "structured_memories" in ai_service.messages[0]["content"]
    assert len(saved) == 1
    assert saved[0]["memory_type"] == "preference"
    assert saved[0]["extraction_kind"] == "long_term_memory"
    assert saved[0]["source_conversation_id"] == "conversation-1"
    assert saved[0]["source_message_id"] == "message-1"
    assert saved[0]["extraction_rationale"] == (
        "The user stated a recurring advice preference."
    )


@pytest.mark.asyncio
async def test_memory_extraction_parses_fenced_json_and_filters_noise():
    ai_service = FakeExtractionAIService(
        """
        ```json
        {
          "memories": [
            {
              "memory_type": "fact",
              "content": "I am waiting on my work visa renewal.",
              "importance": 5,
              "rationale": "Important immigration context."
            },
            {
              "memory_type": "fact",
              "content": "The user asked for advice.",
              "importance": 5,
              "rationale": "Noisy current-turn summary."
            },
            {
              "memory_type": "preference",
              "content": "I like tea.",
              "importance": 2,
              "rationale": "Low importance."
            }
          ]
        }
        ```
        """
    )
    memory_store = FakeMemoryStore()
    service = MemoryExtractionService(ai_service, memory_store)

    saved = await service.extract_and_save(
        "conversation-1",
        {"id": "message-1", "content": "My work visa renewal is stressing me out."},
        {"id": "message-2", "content": "That is important context."},
    )

    assert len(saved) == 1
    assert saved[0]["content"] == "I am waiting on my work visa renewal."


@pytest.mark.asyncio
async def test_memory_extraction_deduplicates_similar_existing_memories():
    ai_service = FakeExtractionAIService(
        """
        {
          "memories": [
            {
              "memory_type": "fact",
              "content": "I work best in the morning.",
              "importance": 4,
              "rationale": "Recurring productivity context."
            }
          ]
        }
        """
    )
    memory_store = FakeMemoryStore(
        existing_memories=[
            {
                "id": "memory-existing",
                "memory_type": "fact",
                "content": "I work best during the morning.",
                "importance": 4,
                "active": True,
            }
        ]
    )
    service = MemoryExtractionService(ai_service, memory_store)

    saved = await service.extract_and_save(
        "conversation-1",
        {"id": "message-1", "content": "I work best in the morning."},
        {"id": "message-2", "content": "Makes sense."},
    )

    assert saved == []
    assert memory_store.saved_memories == []
    assert memory_store.relevant_queries[0]["query"] == "I work best in the morning."


@pytest.mark.asyncio
async def test_memory_extraction_accepts_top_level_list_response():
    ai_service = FakeExtractionAIService(
        """
        [
          {
            "memory_type": "event",
            "content": "I started a new job in May 2026.",
            "importance": 4,
            "rationale": "Important work timeline."
          }
        ]
        """
    )
    memory_store = FakeMemoryStore()
    service = MemoryExtractionService(ai_service, memory_store)

    saved = await service.extract_and_save(
        "conversation-1",
        {"id": "message-1", "content": "I started a new job in May 2026."},
        {"id": "message-2", "content": "That matters."},
    )

    assert len(saved) == 1
    assert saved[0]["memory_type"] == "event"


@pytest.mark.asyncio
async def test_memory_extraction_rejects_unreadable_json_safely():
    ai_service = FakeExtractionAIService("not json")
    memory_store = FakeMemoryStore()
    service = MemoryExtractionService(ai_service, memory_store)

    saved = await service.extract_and_save(
        "conversation-1",
        {"id": "message-1", "content": "Remember this."},
        {"id": "message-2", "content": "Okay."},
    )

    assert saved == []
    assert memory_store.saved_memories == []


@pytest.mark.asyncio
async def test_memory_extraction_saves_structured_candidates():
    ai_service = FakeExtractionAIService(
        """
        {
          "memories": [],
          "structured_memories": {
            "entities": [
              {
                "id": "entity-1",
                "entity_type": "person",
                "display_name": "Clara",
                "aliases": ["Clara from work", "Clara from work"],
                "relationship": "Dating interest",
                "summary": "Clara is someone from work the user is interested in.",
                "importance": 4,
                "rationale": "Named person in recurring dating context."
              }
            ],
            "entity_events": [
              {
                "entity_id": "entity-1",
                "event_type": "interaction",
                "title": "Touched arm",
                "content": "Clara touched the user's arm at work.",
                "importance": 4,
                "rationale": "Relevant dating interaction."
              }
            ],
            "personal_rules": [
              {
                "rule_type": "food_delivery",
                "title": "No DoorDash",
                "rule_text": "Avoid DoorDash while the budget is slipping.",
                "trigger_keywords": ["DoorDash"],
                "priority": 5,
                "rationale": "Recurring money rule."
              }
            ],
            "plans": [
              {
                "id": "plan-1",
                "plan_type": "immigration",
                "title": "Move abroad",
                "desired_outcome": "Leave with enough financial runway.",
                "priority": 5,
                "rationale": "Major long-term life plan."
              }
            ],
            "plan_milestones": [
              {
                "plan_id": "plan-1",
                "title": "Save relocation runway",
                "milestone_type": "goal",
                "priority": 4,
                "rationale": "Concrete progress marker."
              }
            ],
            "commitments": [
              {
                "commitment_type": "health",
                "title": "Morning workout",
                "commitment_text": "Work out tomorrow morning.",
                "due_at": "2026-05-18T12:00:00Z",
                "priority": 4,
                "rationale": "The user made a direct commitment."
              }
            ]
          }
        }
        """
    )
    memory_store = FakeMemoryStore()
    service = MemoryExtractionService(ai_service, memory_store)

    saved = await service.extract_and_save(
        "conversation-1",
        {
            "id": "message-1",
            "content": "Clara from work touched my arm. Also no DoorDash. I will work out tomorrow.",
        },
        {"id": "message-2", "content": "That is worth tracking."},
    )

    assert [item["structured_type"] for item in saved] == [
        "entity",
        "entity_event",
        "personal_rule",
        "plan",
        "plan_milestone",
        "commitment",
    ]
    assert memory_store.created_entities[0]["display_name"] == "Clara"
    assert memory_store.created_entities[0]["normalized_name"] == "clara"
    assert memory_store.created_entities[0]["aliases"] == ["Clara from work"]
    assert memory_store.created_entities[0]["source_conversation_id"] == (
        "conversation-1"
    )
    assert memory_store.created_rules[0]["rule_type"] == "food_delivery"
    assert memory_store.created_plans[0]["plan_type"] == "immigration"
    assert memory_store.created_entity_events[0]["entity_id"] == "entity-1"
    assert memory_store.created_milestones[0]["plan_id"] == "plan-1"
    assert memory_store.created_commitments[0]["due_at"] == "2026-05-18T12:00:00Z"


@pytest.mark.asyncio
async def test_memory_extraction_filters_low_value_structured_candidates():
    ai_service = FakeExtractionAIService(
        """
        {
          "memories": [],
          "structured_memories": {
            "entities": [
              {
                "entity_type": "person",
                "display_name": "someone",
                "importance": 5,
                "rationale": "Too vague."
              },
              {
                "entity_type": "person",
                "display_name": "Clara",
                "importance": 2,
                "rationale": "Too low."
              }
            ],
            "personal_rules": [
              {
                "rule_type": "finance",
                "title": "Current request",
                "rule_text": "The user asked Rex to answer the current question.",
                "priority": 5,
                "rationale": "Noisy."
              }
            ]
          }
        }
        """
    )
    memory_store = FakeMemoryStore()
    service = MemoryExtractionService(ai_service, memory_store)

    saved = await service.extract_and_save(
        "conversation-1",
        {"id": "message-1", "content": "Can you answer this?"},
        {"id": "message-2", "content": "Yes."},
    )

    assert saved == []
    assert memory_store.created_entities == []
    assert memory_store.created_rules == []
