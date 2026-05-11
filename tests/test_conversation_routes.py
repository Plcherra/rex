from fastapi.testclient import TestClient

from app.main import app
from app.routes import conversations as conversations_route


class FakeConversationMemoryService:
    def __init__(self):
        self.deleted_conversation_ids = []
        self.conversations = [
            {
                "id": "conversation-1",
                "title": "Work stress",
                "timestamp": "2026-05-11T10:00:00Z",
                "last_message": {
                    "id": "message-2",
                    "conversation_id": "conversation-1",
                    "role": "assistant",
                    "content": "Let's be practical.",
                    "timestamp": "2026-05-11T10:02:00Z",
                },
            },
            {
                "id": "conversation-2",
                "title": None,
                "timestamp": "2026-05-11T11:00:00Z",
                "last_message": None,
            },
        ]
        self.messages = {
            "conversation-1": [
                {
                    "id": "message-1",
                    "conversation_id": "conversation-1",
                    "role": "user",
                    "content": "I am stressed about work.",
                    "timestamp": "2026-05-11T10:01:00Z",
                },
                {
                    "id": "message-2",
                    "conversation_id": "conversation-1",
                    "role": "assistant",
                    "content": "Let's be practical.",
                    "timestamp": "2026-05-11T10:02:00Z",
                },
            ]
        }

    async def list_conversations(self):
        return self.conversations

    async def create_conversation_record(self):
        return {
            "id": "conversation-new",
            "title": None,
            "timestamp": "2026-05-11T12:00:00Z",
            "last_message": None,
        }

    async def get_conversation_messages(self, conversation_id):
        return self.messages.get(conversation_id)

    async def delete_conversation(self, conversation_id):
        if conversation_id not in {"conversation-1", "conversation-2"}:
            return False

        self.deleted_conversation_ids.append(conversation_id)
        return True


def test_list_conversations_returns_last_message_preview(monkeypatch):
    fake_memory_service = FakeConversationMemoryService()
    monkeypatch.setattr(
        conversations_route,
        "memory_service",
        fake_memory_service,
    )
    client = TestClient(app)

    response = client.get("/conversations")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "conversation-1"
    assert data[0]["last_message"]["content"] == "Let's be practical."
    assert data[1]["last_message"] is None


def test_create_conversation(monkeypatch):
    monkeypatch.setattr(
        conversations_route,
        "memory_service",
        FakeConversationMemoryService(),
    )
    client = TestClient(app)

    response = client.post("/conversations")

    assert response.status_code == 201
    assert response.json()["id"] == "conversation-new"
    assert response.json()["last_message"] is None


def test_get_conversation_messages(monkeypatch):
    monkeypatch.setattr(
        conversations_route,
        "memory_service",
        FakeConversationMemoryService(),
    )
    client = TestClient(app)

    response = client.get("/conversations/conversation-1/messages")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["role"] == "user"
    assert data[1]["role"] == "assistant"


def test_get_conversation_messages_returns_404_for_missing_conversation(monkeypatch):
    monkeypatch.setattr(
        conversations_route,
        "memory_service",
        FakeConversationMemoryService(),
    )
    client = TestClient(app)

    response = client.get("/conversations/missing/messages")

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."


def test_delete_conversation(monkeypatch):
    fake_memory_service = FakeConversationMemoryService()
    monkeypatch.setattr(
        conversations_route,
        "memory_service",
        fake_memory_service,
    )
    client = TestClient(app)

    response = client.delete("/conversations/conversation-1")

    assert response.status_code == 204
    assert fake_memory_service.deleted_conversation_ids == ["conversation-1"]


def test_delete_conversation_returns_404_for_missing_conversation(monkeypatch):
    monkeypatch.setattr(
        conversations_route,
        "memory_service",
        FakeConversationMemoryService(),
    )
    client = TestClient(app)

    response = client.delete("/conversations/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."
