import pytest

from app.services.memory_service import SupabaseMemoryService


class InMemoryRetrievalService(SupabaseMemoryService):
    def __init__(self, memories):
        self.memories = memories

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
