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
    assert len(saved) == 1
    assert saved[0]["memory_type"] == "preference"
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
async def test_memory_extraction_raises_on_unreadable_json():
    ai_service = FakeExtractionAIService("not json")
    memory_store = FakeMemoryStore()
    service = MemoryExtractionService(ai_service, memory_store)

    with pytest.raises(ValueError):
        await service.extract_and_save(
            "conversation-1",
            {"id": "message-1", "content": "Remember this."},
            {"id": "message-2", "content": "Okay."},
        )

    assert memory_store.saved_memories == []
