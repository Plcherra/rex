import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_chat_service
from app.main import app
from app.services.ai_service import AIServiceError
from app.services.chat_service import ConversationNotFoundError
from app.services.memory_service import MemoryServiceError


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class FakeChatService:
    def __init__(self, error=None, stream_error=None):
        self.calls = []
        self.error = error
        self.stream_error = stream_error

    async def send_message(self, message, conversation_id=None, file=None):
        self.calls.append(
            {
                "message": message,
                "conversation_id": conversation_id,
                "file": file,
                "stream": False,
            }
        )
        if self.error is not None:
            raise self.error

        return {
            "conversation_id": conversation_id or "conversation-1",
            "response": "Rex response",
            "messages": [
                {
                    "id": "message-1",
                    "conversation_id": conversation_id or "conversation-1",
                    "role": "assistant",
                    "content": "Rex response",
                    "timestamp": "2026-05-11T00:00:00Z",
                }
            ],
        }

    async def stream_message(self, message, conversation_id=None, file=None):
        self.calls.append(
            {
                "message": message,
                "conversation_id": conversation_id,
                "file": file,
                "stream": True,
            }
        )
        if self.stream_error is not None:
            raise self.stream_error

        resolved_conversation_id = conversation_id or "conversation-stream"
        yield {"event": "conversation", "conversation_id": resolved_conversation_id}
        yield {"event": "token", "token": "Rex "}
        yield {"event": "token", "token": "stream"}
        yield {
            "event": "done",
            "conversation_id": resolved_conversation_id,
            "response": "Rex stream",
            "messages": [],
        }


def override_chat_service(fake_chat_service):
    app.dependency_overrides[get_chat_service] = lambda: fake_chat_service


def test_chat_accepts_json(client):
    fake_chat_service = FakeChatService()
    override_chat_service(fake_chat_service)

    response = client.post(
        "/chat",
        json={
            "message": "Hello Rex",
            "conversation_id": "conversation-existing",
        },
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "conversation-existing"
    assert fake_chat_service.calls == [
        {
            "message": "Hello Rex",
            "conversation_id": "conversation-existing",
            "file": None,
            "stream": False,
        }
    ]


def test_chat_accepts_multipart_file_upload(client):
    fake_chat_service = FakeChatService()
    override_chat_service(fake_chat_service)

    response = client.post(
        "/chat",
        data={"message": "Read this", "conversation_id": "conversation-existing"},
        files={"file": ("notes.md", b"Project notes", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json()["response"] == "Rex response"
    assert fake_chat_service.calls[0]["message"] == "Read this"
    assert fake_chat_service.calls[0]["conversation_id"] == "conversation-existing"
    assert fake_chat_service.calls[0]["file"].filename == "notes.md"


def test_chat_streams_json_when_requested(client):
    fake_chat_service = FakeChatService()
    override_chat_service(fake_chat_service)

    with client.stream(
        "POST",
        "/chat",
        json={"message": "Hello Rex", "stream": True},
    ) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: conversation" in body
    assert '"conversation_id": "conversation-stream"' in body
    assert "event: token" in body
    assert '"token": "Rex "' in body
    assert "event: done" in body
    assert '"response": "Rex stream"' in body
    assert fake_chat_service.calls[0]["stream"] is True


def test_chat_streams_multipart_when_requested(client):
    fake_chat_service = FakeChatService()
    override_chat_service(fake_chat_service)

    with client.stream(
        "POST",
        "/chat",
        data={"message": "Read this", "stream": "true"},
        files={"file": ("notes.txt", b"notes", "text/plain")},
    ) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert "event: token" in body
    assert fake_chat_service.calls[0]["file"].filename == "notes.txt"


def test_chat_rejects_empty_json_message(client):
    override_chat_service(FakeChatService())

    response = client.post("/chat", json={"message": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "Message cannot be empty."


def test_chat_rejects_unsupported_content_type(client):
    override_chat_service(FakeChatService())

    response = client.post(
        "/chat",
        data="message=Hello",
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "Use application/json or multipart/form-data."


def test_chat_returns_404_for_missing_conversation(client):
    override_chat_service(FakeChatService(error=ConversationNotFoundError()))

    response = client.post(
        "/chat",
        json={"message": "Hello", "conversation_id": "missing"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."


def test_chat_maps_ai_service_errors(client):
    override_chat_service(
        FakeChatService(error=AIServiceError("Grok unavailable.", status_code=503))
    )

    response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Grok unavailable."


def test_chat_maps_memory_service_errors(client):
    override_chat_service(
        FakeChatService(
            error=MemoryServiceError("Supabase unavailable.", status_code=503)
        )
    )

    response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Supabase unavailable."


def test_chat_stream_returns_error_event(client):
    override_chat_service(
        FakeChatService(
            stream_error=AIServiceError("Grok stream failed.", status_code=503)
        )
    )

    with client.stream(
        "POST",
        "/chat",
        json={"message": "Hello Rex", "stream": True},
    ) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert "event: error" in body
    assert '"detail": "Grok stream failed."' in body
