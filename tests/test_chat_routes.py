from fastapi.testclient import TestClient

from app.main import app
from app.routes import chat as chat_route


class FakeChatService:
    def __init__(self):
        self.calls = []

    async def send_message(self, message, conversation_id=None, file=None):
        self.calls.append(
            {
                "message": message,
                "conversation_id": conversation_id,
                "file": file,
            }
        )
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


def test_chat_accepts_json(monkeypatch):
    fake_chat_service = FakeChatService()
    monkeypatch.setattr(chat_route, "chat_service", fake_chat_service)
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={
            "message": "Hello Rex",
            "conversation_id": "conversation-existing",
        },
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "conversation-existing"
    assert fake_chat_service.calls[0]["message"] == "Hello Rex"
    assert fake_chat_service.calls[0]["conversation_id"] == "conversation-existing"
    assert fake_chat_service.calls[0]["file"] is None


def test_chat_accepts_multipart(monkeypatch):
    fake_chat_service = FakeChatService()
    monkeypatch.setattr(chat_route, "chat_service", fake_chat_service)
    client = TestClient(app)

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


def test_chat_rejects_empty_json_message(monkeypatch):
    monkeypatch.setattr(chat_route, "chat_service", FakeChatService())
    client = TestClient(app)

    response = client.post("/chat", json={"message": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "Message cannot be empty."
