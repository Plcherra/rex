import pytest
from fastapi import HTTPException

from app.config import Settings
from app.services.chat_service import ChatService, FILE_CONTEXT_PREFIX
from app.services.file_service import FileService
from app.services.memory_service import SupabaseMemoryService, MemoryServiceError


class FakeAIService:
    def __init__(self):
        self.messages = []

    async def generate_response(self, messages):
        self.messages = messages
        return "Rex response"

    async def stream_response(self, messages):
        self.messages = messages
        for token in ["Rex ", "stream"]:
            yield token


class FailingAIService:
    async def generate_response(self, messages):
        raise RuntimeError("AI failed")

    async def stream_response(self, messages):
        raise RuntimeError("AI failed")
        yield


class FakeMemoryService:
    def __init__(self):
        self.conversations = set()
        self.messages = []
        self.long_term_memory = []
        self.next_conversation_id = 1
        self.next_message_id = 1
        self.next_memory_id = 1
        self.relevant_memory_queries = []

    async def create_conversation(self):
        conversation_id = f"conversation-{self.next_conversation_id}"
        self.next_conversation_id += 1
        self.conversations.add(conversation_id)
        return conversation_id

    async def conversation_exists(self, conversation_id):
        return conversation_id in self.conversations

    async def save_message(self, conversation_id, role, content):
        message = {
            "id": f"message-{self.next_message_id}",
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "timestamp": "2026-05-11T00:00:00Z",
        }
        self.next_message_id += 1
        self.messages.append(message)
        return message

    async def get_recent_messages(self, conversation_id, limit=20):
        messages = [
            message
            for message in self.messages
            if message["conversation_id"] == conversation_id
        ]
        return messages[-limit:]

    async def save_long_term_memory_from_message(self, conversation_id, message):
        content = message["content"]
        if not content.lower().startswith("remember that "):
            return None

        memory = {
            "id": f"memory-{self.next_memory_id}",
            "memory_type": "fact",
            "content": content.removeprefix("Remember that "),
            "source_conversation_id": conversation_id,
            "source_message_id": message["id"],
            "importance": 5,
            "active": True,
        }
        self.next_memory_id += 1
        self.long_term_memory.append(memory)
        return memory

    async def save_long_term_memory(
        self,
        memory_type,
        content,
        source_conversation_id=None,
        source_message_id=None,
        importance=3,
    ):
        memory = {
            "id": f"memory-{self.next_memory_id}",
            "memory_type": memory_type,
            "content": content,
            "source_conversation_id": source_conversation_id,
            "source_message_id": source_message_id,
            "importance": importance,
            "active": True,
        }
        self.next_memory_id += 1
        self.long_term_memory.append(memory)
        return memory

    async def get_relevant_memories(self, query, limit=8):
        self.relevant_memory_queries.append({"query": query, "limit": limit})
        return self.long_term_memory[-limit:]


class FakeMemoryExtractionService:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.calls = []

    async def extract_and_save(self, conversation_id, user_message, assistant_message):
        self.calls.append(
            {
                "conversation_id": conversation_id,
                "user_message": user_message,
                "assistant_message": assistant_message,
            }
        )
        if self.should_fail:
            raise RuntimeError("extraction failed")
        return []


class FakeUpload:
    def __init__(self, filename, content):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


@pytest.mark.asyncio
async def test_file_upload_rejects_files_over_2mb():
    file_service = FileService()
    upload = FakeUpload("notes.txt", b"a" * (2 * 1024 * 1024 + 1))

    with pytest.raises(HTTPException) as error:
        await file_service.read_text_file(upload)

    assert error.value.status_code == 413
    assert error.value.detail == "Uploaded file is too large. Maximum size is 2MB."


@pytest.mark.asyncio
async def test_chat_service_handles_normal_chat():
    ai_service = FakeAIService()
    memory_service = FakeMemoryService()
    chat_service = ChatService(ai_service, FileService(), memory_service)

    result = await chat_service.send_message("Hello Rex")

    assert result["conversation_id"] == "conversation-1"
    assert result["response"] == "Rex response"
    assert [message["role"] for message in result["messages"]] == [
        "user",
        "assistant",
    ]
    assert ai_service.messages[-1]["content"] == "Hello Rex"


@pytest.mark.asyncio
async def test_chat_service_streams_tokens_and_persists_final_response():
    ai_service = FakeAIService()
    memory_service = FakeMemoryService()
    chat_service = ChatService(ai_service, FileService(), memory_service)

    events = [
        event async for event in chat_service.stream_message("Hello Rex", file=None)
    ]

    assert events[:3] == [
        {"event": "conversation", "conversation_id": "conversation-1"},
        {"event": "token", "token": "Rex "},
        {"event": "token", "token": "stream"},
    ]
    assert events[-1]["event"] == "done"
    assert events[-1]["response"] == "Rex stream"
    assert [message["role"] for message in memory_service.messages] == [
        "user",
        "assistant",
    ]
    assert memory_service.messages[-1]["content"] == "Rex stream"


@pytest.mark.asyncio
async def test_chat_service_handles_file_upload():
    ai_service = FakeAIService()
    memory_service = FakeMemoryService()
    chat_service = ChatService(ai_service, FileService(), memory_service)
    upload = FakeUpload("notes.md", b"Project notes")

    result = await chat_service.send_message("Read this file", file=upload)

    assert result["response"] == "Rex response"
    assert ai_service.messages[-2]["content"] == (
        f"{FILE_CONTEXT_PREFIX}Project notes"
    )
    assert ai_service.messages[-1]["content"] == "Read this file"


@pytest.mark.asyncio
async def test_chat_service_includes_long_term_memory():
    ai_service = FakeAIService()
    memory_service = FakeMemoryService()
    memory_service.long_term_memory.append(
        {
            "id": "memory-1",
            "memory_type": "preference",
            "content": "I prefer concise answers",
            "importance": 4,
        }
    )
    chat_service = ChatService(ai_service, FileService(), memory_service)

    await chat_service.send_message("What should I do next?")

    assert memory_service.relevant_memory_queries == [
        {"query": "What should I do next?", "limit": 8}
    ]
    assert ai_service.messages[0]["role"] == "system"
    assert "Relevant long-term memory" in ai_service.messages[0]["content"]
    assert "- preference: I prefer concise answers" in ai_service.messages[0]["content"]


@pytest.mark.asyncio
async def test_chat_service_limits_injected_memory_context():
    ai_service = FakeAIService()
    memory_service = FakeMemoryService()
    memory_service.long_term_memory.append(
        {
            "id": "memory-1",
            "memory_type": "fact",
            "content": "work " * 1000,
            "importance": 5,
        }
    )
    chat_service = ChatService(ai_service, FileService(), memory_service)

    await chat_service.send_message("I need advice about work.")

    assert len(ai_service.messages[0]["content"]) < 2200
    assert "[truncated]" in ai_service.messages[0]["content"]


@pytest.mark.asyncio
async def test_chat_service_runs_memory_extraction_after_successful_response():
    ai_service = FakeAIService()
    memory_service = FakeMemoryService()
    extraction_service = FakeMemoryExtractionService()
    chat_service = ChatService(
        ai_service,
        FileService(),
        memory_service,
        extraction_service,
    )

    await chat_service.send_message("Remember that I work best in the morning")

    assert len(extraction_service.calls) == 1
    assert extraction_service.calls[0]["conversation_id"] == "conversation-1"
    assert extraction_service.calls[0]["user_message"]["content"] == (
        "Remember that I work best in the morning"
    )
    assert extraction_service.calls[0]["assistant_message"]["content"] == (
        "Rex response"
    )


@pytest.mark.asyncio
async def test_chat_service_ignores_memory_extraction_failures():
    ai_service = FakeAIService()
    memory_service = FakeMemoryService()
    extraction_service = FakeMemoryExtractionService(should_fail=True)
    chat_service = ChatService(
        ai_service,
        FileService(),
        memory_service,
        extraction_service,
    )

    result = await chat_service.send_message("Remember that I work best in the morning")

    assert result["response"] == "Rex response"
    assert len(extraction_service.calls) == 1


@pytest.mark.asyncio
async def test_chat_service_does_not_extract_memory_when_ai_fails():
    memory_service = FakeMemoryService()
    extraction_service = FakeMemoryExtractionService()
    chat_service = ChatService(
        FailingAIService(),
        FileService(),
        memory_service,
        extraction_service,
    )

    with pytest.raises(RuntimeError):
        await chat_service.send_message("Hello Rex")

    assert memory_service.conversations == {"conversation-1"}
    assert [message["role"] for message in memory_service.messages] == ["user"]
    assert memory_service.long_term_memory == []
    assert extraction_service.calls == []


@pytest.mark.asyncio
async def test_supabase_memory_requires_configuration():
    memory_service = SupabaseMemoryService(
        Settings(
            supabase_url=None,
            supabase_service_role_key=None,
        )
    )

    with pytest.raises(MemoryServiceError) as error:
        await memory_service.create_conversation()

    assert error.value.detail == "Supabase memory is not configured."
