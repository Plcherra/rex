import pytest

from app.config import Settings
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
