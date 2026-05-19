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

    async def list_entities(
        self,
        limit=50,
        entity_type=None,
        status=None,
        active=None,
        normalized_name=None,
    ):
        rows = self.created_entities
        if entity_type is not None:
            rows = [row for row in rows if row.get("entity_type") == entity_type]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        if normalized_name is not None:
            rows = [
                row for row in rows if row.get("normalized_name") == normalized_name
            ]
        return rows[:limit]

    async def update_entity(self, entity_id, **updates):
        return _update(self.created_entities, entity_id, updates)

    async def create_entity_event(self, payload):
        event = {"id": f"event-{len(self.created_entity_events) + 1}", **payload}
        self.created_entity_events.append(event)
        return event

    async def create_personal_rule(self, payload):
        rule = {"id": f"rule-{len(self.created_rules) + 1}", **payload}
        self.created_rules.append(rule)
        return rule

    async def list_personal_rules(
        self,
        limit=50,
        rule_type=None,
        status=None,
        active=None,
    ):
        rows = self.created_rules
        if rule_type is not None:
            rows = [row for row in rows if row.get("rule_type") == rule_type]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_personal_rule(self, rule_id, **updates):
        return _update(self.created_rules, rule_id, updates)

    async def create_plan(self, payload):
        plan = {"id": f"plan-{len(self.created_plans) + 1}", **payload}
        self.created_plans.append(plan)
        return plan

    async def list_plans(self, limit=50, plan_type=None, status=None, active=None):
        rows = self.created_plans
        if plan_type is not None:
            rows = [row for row in rows if row.get("plan_type") == plan_type]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_plan(self, plan_id, **updates):
        return _update(self.created_plans, plan_id, updates)

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

    async def list_commitments(
        self,
        limit=50,
        commitment_type=None,
        plan_id=None,
        entity_id=None,
        status=None,
        active=None,
    ):
        rows = self.created_commitments
        if commitment_type is not None:
            rows = [
                row for row in rows if row.get("commitment_type") == commitment_type
            ]
        if plan_id is not None:
            rows = [row for row in rows if row.get("plan_id") == plan_id]
        if entity_id is not None:
            rows = [row for row in rows if row.get("entity_id") == entity_id]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if active is not None:
            rows = [row for row in rows if row.get("active") is active]
        return rows[:limit]

    async def update_commitment(self, commitment_id, **updates):
        return _update(self.created_commitments, commitment_id, updates)


def _update(rows, row_id, updates):
    for row in rows:
        if row["id"] == row_id:
            row.update(updates)
            return row
    return None


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
async def test_memory_extraction_deduplicates_and_links_structured_candidates():
    ai_service = FakeExtractionAIService(
        """
        {
          "memories": [],
          "structured_memories": {
            "entities": [
              {
                "entity_type": "person",
                "display_name": "Clara from work",
                "relationship": "Dating interest",
                "summary": "Clara is someone the user knows from work.",
                "importance": 4,
                "rationale": "Named person."
              }
            ],
            "entity_events": [
              {
                "entity_name": "Clara",
                "event_type": "interaction",
                "title": "Lunch conversation",
                "content": "The user talked with Clara at lunch.",
                "importance": 4,
                "rationale": "Relevant relationship context."
              }
            ],
            "personal_rules": [
              {
                "rule_type": "food_delivery",
                "title": "No delivery",
                "rule_text": "No DoorDash this month.",
                "trigger_keywords": ["DoorDash", "Uber Eats"],
                "priority": 5,
                "rationale": "Budget rule."
              }
            ],
            "plans": [
              {
                "plan_type": "immigration",
                "title": "Move abroad",
                "desired_outcome": "Leave with enough runway.",
                "priority": 5,
                "rationale": "Major plan."
              }
            ],
            "plan_milestones": [
              {
                "plan_title": "Move abroad",
                "title": "Save relocation runway",
                "milestone_type": "goal",
                "priority": 4,
                "rationale": "Progress marker."
              }
            ],
            "commitments": [
              {
                "commitment_type": "relationship",
                "title": "Text Clara",
                "commitment_text": "Text Clara tomorrow.",
                "entity_name": "Clara",
                "priority": 4,
                "rationale": "Direct commitment."
              }
            ]
          }
        }
        """
    )
    memory_store = FakeMemoryStore()
    memory_store.created_entities.append(
        {
            "id": "entity-existing",
            "entity_type": "person",
            "display_name": "Clara",
            "normalized_name": "clara",
            "aliases": ["Clara"],
            "importance": 3,
            "active": True,
            "metadata": {},
        }
    )
    memory_store.created_rules.append(
        {
            "id": "rule-existing",
            "rule_type": "food_delivery",
            "title": "No DoorDash",
            "rule_text": "No DoorDash this month.",
            "trigger_keywords": ["DoorDash"],
            "priority": 3,
            "active": True,
            "metadata": {},
        }
    )
    memory_store.created_plans.append(
        {
            "id": "plan-existing",
            "plan_type": "immigration",
            "title": "Move abroad",
            "priority": 3,
            "active": True,
            "metadata": {},
        }
    )
    service = MemoryExtractionService(ai_service, memory_store)

    saved = await service.extract_and_save(
        "conversation-1",
        {"id": "message-1", "content": "I need to text Clara tomorrow."},
        {"id": "message-2", "content": "I will track that."},
    )

    assert [item["structured_type"] for item in saved] == [
        "entity",
        "entity_event",
        "personal_rule",
        "plan",
        "plan_milestone",
        "commitment",
    ]
    assert memory_store.created_entities == [
        {
            "id": "entity-existing",
            "entity_type": "person",
            "display_name": "Clara",
            "normalized_name": "clara",
            "aliases": ["Clara"],
            "importance": 4,
            "active": True,
            "metadata": {"extraction_rationale": "Named person."},
            "relationship": "Dating interest",
            "summary": "Clara is someone the user knows from work.",
            "source_conversation_id": "conversation-1",
            "source_message_id": "message-1",
        }
    ]
    assert memory_store.created_entity_events[0]["entity_id"] == "entity-existing"
    assert memory_store.created_rules[0]["id"] == "rule-existing"
    assert memory_store.created_rules[0]["trigger_keywords"] == [
        "DoorDash",
        "Uber Eats",
    ]
    assert memory_store.created_plans[0]["id"] == "plan-existing"
    assert memory_store.created_milestones[0]["plan_id"] == "plan-existing"
    assert memory_store.created_commitments[0]["entity_id"] == "entity-existing"


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


@pytest.mark.asyncio
async def test_memory_extraction_ignores_invalid_structured_payloads_but_keeps_valid():
    ai_service = FakeExtractionAIService(
        """
        {
          "memories": [],
          "structured_memories": {
            "entities": "not a list",
            "personal_rules": [
              {
                "rule_type": "finance",
                "title": "Current request",
                "rule_text": "The user asked Rex to answer the current question.",
                "priority": 5,
                "rationale": "Noisy current-turn instruction."
              },
              {
                "rule_type": "food_delivery",
                "title": "No DoorDash",
                "rule_text": "Do not order DoorDash this week.",
                "trigger_keywords": ["DoorDash", "delivery"],
                "priority": 4,
                "rationale": "Useful recurring budget rule."
              },
              {
                "rule_type": "random",
                "title": "Invalid",
                "rule_text": "This should not save.",
                "priority": 5,
                "rationale": "Invalid enum."
              }
            ],
            "plans": [
              "not an object",
              {
                "plan_type": "immigration",
                "title": "",
                "priority": 5,
                "rationale": "Missing title."
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
        {"id": "message-1", "content": "No DoorDash this week."},
        {"id": "message-2", "content": "I will hold you to that."},
    )

    assert [item["structured_type"] for item in saved] == ["personal_rule"]
    assert memory_store.created_rules == [
        {
            "id": "rule-1",
            "rule_type": "food_delivery",
            "title": "No DoorDash",
            "rule_text": "Do not order DoorDash this week.",
            "trigger_keywords": ["DoorDash", "delivery"],
            "enforcement_style": "gentle_direct",
            "source_conversation_id": "conversation-1",
            "source_message_id": "message-1",
            "priority": 4,
            "status": "active",
            "active": True,
            "metadata": {"extraction_rationale": "Useful recurring budget rule."},
        }
    ]
    assert memory_store.created_entities == []
    assert memory_store.created_plans == []
